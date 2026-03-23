"""Website analytics page — GA4-powered traffic, pages, sources, UTMs, real-time, funnel, heatmap insights, AI intelligence."""
import json
import logging
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db, SessionLocal
from app.models import (
    Project, Channel, Task, TaskStatus, TaskPriority,
    HeatmapInsight, WebsiteAnalysis, WebsiteRecommendation,
    BudgetLineItem, BudgetMonthEntry,
    ChannelStatus, Metric,
)
from app.ai.engine import simple_completion, is_configured as ai_configured
from app.integrations.ga4_analytics import (
    is_ga4_configured,
    fetch_traffic_overview,
    fetch_page_performance,
    fetch_source_detail,
    fetch_utm_dashboard,
    fetch_realtime,
    fetch_conversion_funnel,
    fetch_dashboard_widget,
)

logger = logging.getLogger("mcc.website")

router = APIRouter(prefix="/website")
templates = Jinja2Templates(directory="app/templates")

SECTION_KEYS = [
    "traffic_diagnosis",
    "missing_sources",
    "conversion_blockers",
    "page_fixes",
    "quick_wins",
    "seo_opportunities",
    "unknown_unknowns",
]

SECTION_LABELS = {
    "traffic_diagnosis": "Traffic Diagnosis",
    "missing_sources": "Missing Traffic Sources",
    "conversion_blockers": "Conversion Blockers",
    "page_fixes": "Page-Specific Fixes",
    "quick_wins": "Quick Wins",
    "seo_opportunities": "SEO Opportunities",
    "unknown_unknowns": "What You Don't Know You Don't Know",
}

WEBSITE_ANALYSIS_SYSTEM = """You are a senior growth marketing analyst specializing in SaaS website optimization.
You provide extremely specific, data-driven, actionable recommendations — never vague advice.
Every recommendation must include: specific action, who does it, estimated time, and expected impact.
Respond in JSON format only."""


# ---------------------------------------------------------------------------
# Context builders for AI prompt
# ---------------------------------------------------------------------------

def _build_website_context(
    traffic: dict | None,
    pages: list | None,
    sources: list | None,
    funnel: dict | None,
    utms: list | None,
    db: Session,
    pid: int,
) -> str:
    """Build the full context string from website data + MCC data."""
    parts = []

    # Traffic overview
    if traffic:
        parts.append(f"""TRAFFIC:
- Visitors today: {traffic.get('visitors_today', 0)} (yesterday: {traffic.get('visitors_yesterday', 0)})
- This week: {traffic.get('visitors_week', 0)} ({traffic.get('new_users_week', 0)} new)
- This month: {traffic.get('visitors_month', 0)} ({traffic.get('new_users_month', 0)} new)
- Bounce rate today: {traffic.get('bounce_rate_today', 0)}%
- Unique vs returning today: {traffic.get('new_users_today', 0)} new / {traffic.get('returning_today', 0)} returning""")

        if traffic.get("traffic_sources"):
            src_lines = "\n".join(
                f"  - {s['name']}: {s['sessions']} sessions ({s['pct']}%)"
                for s in traffic["traffic_sources"]
            )
            parts.append(f"TOP TRAFFIC SOURCES (30d):\n{src_lines}")

        if traffic.get("landing_pages"):
            lp_lines = "\n".join(
                f"  - {lp['page']}: {lp['sessions']} sessions"
                for lp in traffic["landing_pages"][:10]
            )
            parts.append(f"TOP LANDING PAGES (30d):\n{lp_lines}")
    else:
        parts.append("TRAFFIC: GA4 not connected — no traffic data available.")

    # Funnel
    if funnel and funnel.get("stages"):
        funnel_lines = []
        for s in funnel["stages"]:
            if s.get("post_launch"):
                funnel_lines.append(f"  - {s['label']}: (post-launch)")
            else:
                conv = f", {s['conversion_rate']}% conv from prev" if s.get("conversion_rate") is not None else ""
                drop = f", {s['dropoff_pct']}% drop" if s.get("dropoff_pct") is not None else ""
                wow = f", WoW: {'+' if s.get('wow_diff', 0) > 0 else ''}{s.get('wow_diff', 0)}" if s.get("wow_diff") is not None else ""
                funnel_lines.append(f"  - {s['label']}: {s['count']}{conv}{drop}{wow}")
        parts.append(f"CONVERSION FUNNEL (this week):\n" + "\n".join(funnel_lines))
    else:
        parts.append("CONVERSION FUNNEL: No funnel data available.")

    # Page performance
    if pages:
        page_lines = "\n".join(
            f"  - {p['page']}: {p['views']} views, {p['unique_views']} sessions, {p['avg_time']}s avg, {p['bounce_rate']}% bounce, action: {p['conversion_action']}"
            for p in pages[:15]
        )
        parts.append(f"PAGE PERFORMANCE (30d):\n{page_lines}")

    # Source detail
    if sources:
        src_detail = "\n".join(
            f"  - {s['source']}/{s['medium']}: {s['total_sessions']} sessions, {s['total_users']} users, top pages: {', '.join(p['page'] for p in s['pages'][:3])}"
            for s in sources[:10]
        )
        parts.append(f"SOURCE DETAIL (30d):\n{src_detail}")

    # UTM data
    if utms:
        utm_lines = "\n".join(
            f"  - {u['campaign']} ({u['source']}/{u['medium']}): {u['sessions']} sessions, {u['bounce_rate']}% bounce"
            for u in utms[:10]
        )
        parts.append(f"UTM CAMPAIGNS (30d):\n{utm_lines}")
    else:
        parts.append("UTM CAMPAIGNS: No UTM-tagged traffic.")

    # Active channels from MCC
    channels = db.query(Channel).filter_by(project_id=pid).all()
    live = [c for c in channels if c.status == ChannelStatus.live]
    if live:
        ch_lines = []
        for ch in live:
            metrics = db.query(Metric).filter_by(channel_id=ch.id).order_by(Metric.recorded_at.desc()).limit(5).all()
            seen = {}
            for m in metrics:
                if m.metric_name not in seen:
                    seen[m.metric_name] = float(m.metric_value)
                if len(seen) >= 3:
                    break
            metric_str = ", ".join(f"{k}: {v:,.0f}" for k, v in seen.items()) if seen else "no metrics"
            ch_lines.append(f"  - {ch.name} ({ch.channel_type.value}): {metric_str}")
        parts.append(f"ACTIVE MARKETING CHANNELS:\n" + "\n".join(ch_lines))

    # Budget
    today = date.today()
    month_start = today.replace(day=1)
    items = db.query(BudgetLineItem).filter_by(project_id=pid).all()
    if items:
        total = 0
        budget_lines = []
        for item in items:
            entry = db.query(BudgetMonthEntry).filter_by(line_item_id=item.id, month=month_start).first()
            budgeted = float(entry.budgeted) if entry else float(item.default_amount)
            actual = float(entry.actual) if entry else 0
            total += budgeted
            if budgeted > 0:
                budget_lines.append(f"  - {item.name}: ${budgeted:,.0f}/mo (spent: ${actual:,.0f})")
        parts.append(f"BUDGET (${total:,.0f}/mo total):\n" + "\n".join(budget_lines))

    return "\n\n".join(parts)


def _build_analysis_prompt(context: str) -> str:
    return f"""You are analyzing website performance for grindlab.ai, a poker study SaaS tool at $18/month launching April 1, 2026. Here is the current data:

{context}

Analyze and provide these 7 sections as JSON. Each section contains an array of recommendations.

Return JSON in this exact format:
{{
  "traffic_diagnosis": [
    {{"headline": "action-ready headline", "body": "detailed analysis with specific numbers", "assignee": "phil|clint|automated", "estimated_time": "e.g. 2 hours", "expected_impact": "specific expected result", "impact_level": "high|medium|low", "difficulty": "easy|medium|hard"}}
  ],
  "missing_sources": [...same format...],
  "conversion_blockers": [...same format...],
  "page_fixes": [...same format...],
  "quick_wins": [...same format, limit to 3 items...],
  "seo_opportunities": [...same format...],
  "unknown_unknowns": [...same format...]
}}

SECTION GUIDELINES:

1. TRAFFIC DIAGNOSIS: What's the biggest bottleneck — not enough traffic, wrong traffic (high bounce = wrong audience), or enough traffic but poor conversion? Be specific with numbers. Don't say 'increase traffic' — say which source to double down on and which to fix or pause, with specific numbers.

2. MISSING TRAFFIC SOURCES: Based on where poker players spend time online, which sources should be getting visitors but show zero? For each: what it takes to activate, expected volume, timeline.

3. CONVERSION BLOCKERS: Looking at funnel drop-offs, identify the biggest leak. Diagnose the specific stage and suggest a fix.

4. PAGE-SPECIFIC FIXES: For each key page, what might be hurting performance based on data. Be specific about what to change.

5. QUICK WINS: 3 things that could be done THIS WEEK with no code changes and no budget that would likely improve website performance.

6. SEO OPPORTUNITIES: Which keywords should grindlab.ai target? Suggest 5 specific blog posts or pages that could drive organic traffic.

7. WHAT YOU DON'T KNOW YOU DON'T KNOW: Things probably not considered — missing retargeting, no FAQ page, slow mobile load, no schema markup, missing social proof, etc.

CRITICAL: Every recommendation must include specific action, who does it (Phil, Clint, or automated), estimated time, and expected impact. No vague advice."""


# ---------------------------------------------------------------------------
# Main page route
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def website_page(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()

    ga4_connected = is_ga4_configured()
    traffic = None
    pages = None
    sources = None
    utms = None
    realtime = None
    funnel = None

    if ga4_connected:
        traffic = await fetch_traffic_overview()
        pages = await fetch_page_performance()
        sources = await fetch_source_detail()
        utms = await fetch_utm_dashboard()
        realtime = await fetch_realtime()
        funnel = await fetch_conversion_funnel()

        if traffic is None and pages is None:
            ga4_connected = False

    # Heatmap insights
    heatmap_insights = []
    if project:
        heatmap_insights = db.query(HeatmapInsight).filter_by(
            project_id=project.id
        ).order_by(HeatmapInsight.insight_date.desc(), HeatmapInsight.created_at.desc()).all()

    # Latest website analysis
    latest_analysis = None
    analysis_recs = []
    analysis_history = []
    if project:
        latest_analysis = db.query(WebsiteAnalysis).filter_by(
            project_id=project.id
        ).order_by(WebsiteAnalysis.created_at.desc()).first()

        if latest_analysis:
            analysis_recs = db.query(WebsiteRecommendation).filter_by(
                analysis_id=latest_analysis.id
            ).order_by(WebsiteRecommendation.id).all()

        # History (last 10)
        analysis_history = db.query(WebsiteAnalysis).filter_by(
            project_id=project.id
        ).order_by(WebsiteAnalysis.created_at.desc()).limit(10).all()

    return templates.TemplateResponse("website.html", {
        "request": request,
        "project": project,
        "current_page": "website",
        "today": date.today(),
        "ga4_connected": ga4_connected,
        "traffic": traffic,
        "pages": pages,
        "sources": sources,
        "utms": utms,
        "realtime": realtime,
        "funnel": funnel,
        "heatmap_insights": heatmap_insights,
        "latest_analysis": latest_analysis,
        "analysis_recs": analysis_recs,
        "analysis_history": analysis_history,
        "ai_configured": ai_configured(),
        "section_keys": SECTION_KEYS,
        "section_labels": SECTION_LABELS,
    })


# ---------------------------------------------------------------------------
# AI Analysis endpoints
# ---------------------------------------------------------------------------

@router.post("/intelligence/generate", response_class=HTMLResponse)
async def generate_website_intelligence(request: Request, db: Session = Depends(get_db)):
    """Run AI analysis on current website data."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse('<div class="text-xs text-mcc-critical py-4 text-center">No project found</div>')
    if not ai_configured():
        return HTMLResponse('<div class="text-xs text-mcc-critical py-4 text-center">AI not configured — set ANTHROPIC_API_KEY in .env</div>')

    pid = project.id

    # Gather current website data
    ga4_connected = is_ga4_configured()
    traffic = None
    pages = None
    sources = None
    utms = None
    funnel = None

    if ga4_connected:
        traffic = await fetch_traffic_overview()
        pages = await fetch_page_performance()
        sources = await fetch_source_detail()
        utms = await fetch_utm_dashboard()
        funnel = await fetch_conversion_funnel()

    # Build context and prompt
    context = _build_website_context(traffic, pages, sources, funnel, utms, db, pid)
    prompt = _build_analysis_prompt(context)

    try:
        response = await simple_completion(prompt, system_override=WEBSITE_ANALYSIS_SYSTEM)
    except Exception as e:
        logger.error(f"Website intelligence generation failed: {e}")
        return HTMLResponse(f'<div class="text-xs text-mcc-critical py-4 text-center">AI analysis failed: {e}</div>')

    if not response:
        return HTMLResponse('<div class="text-xs text-mcc-critical py-4 text-center">AI returned empty response</div>')

    # Parse JSON response
    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error(f"Website intelligence JSON parse failed: {cleaned[:200]}")
        return HTMLResponse('<div class="text-xs text-mcc-critical py-4 text-center">AI response was not valid JSON. Try again.</div>')

    # Build snapshot of current data for historical comparison
    snapshot = {}
    if traffic:
        snapshot["traffic"] = {
            "visitors_today": traffic.get("visitors_today", 0),
            "visitors_week": traffic.get("visitors_week", 0),
            "visitors_month": traffic.get("visitors_month", 0),
            "bounce_rate": traffic.get("bounce_rate_today", 0),
        }
    if funnel and funnel.get("stages"):
        snapshot["funnel"] = {
            s["key"]: s["count"] for s in funnel["stages"] if s.get("count") is not None
        }

    # Create analysis record
    total_recs = 0
    high_impact = 0
    for section_key in SECTION_KEYS:
        recs = data.get(section_key, [])
        if isinstance(recs, list):
            total_recs += len(recs)
            high_impact += sum(1 for r in recs if isinstance(r, dict) and r.get("impact_level") == "high")

    analysis = WebsiteAnalysis(
        project_id=pid,
        snapshot_data=snapshot,
        sections=data,
        total_recommendations=total_recs,
        high_impact_count=high_impact,
    )
    db.add(analysis)
    db.flush()

    # Create recommendation records
    for section_key in SECTION_KEYS:
        recs = data.get(section_key, [])
        if not isinstance(recs, list):
            continue
        for rec in recs:
            if not isinstance(rec, dict):
                continue
            db.add(WebsiteRecommendation(
                analysis_id=analysis.id,
                section=section_key,
                headline=rec.get("headline", "Untitled")[:300],
                body=rec.get("body", ""),
                assignee=rec.get("assignee", "phil"),
                estimated_time=rec.get("estimated_time", ""),
                expected_impact=rec.get("expected_impact", ""),
                impact_level=rec.get("impact_level", "medium"),
                difficulty=rec.get("difficulty", "medium"),
            ))

    db.commit()

    # Return redirect to reload the page with new data
    return HTMLResponse(
        '<div class="text-xs text-mcc-success py-2 text-center">Analysis complete — reloading...</div>',
        headers={"HX-Redirect": "/website"},
    )


@router.post("/intelligence/recs/{rec_id}/task", response_class=HTMLResponse)
async def create_task_from_recommendation(rec_id: int, db: Session = Depends(get_db)):
    """Create a task from a website recommendation."""
    rec = db.get(WebsiteRecommendation, rec_id)
    if not rec:
        return HTMLResponse('<span class="text-mcc-critical text-xs">Not found</span>')

    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse('<span class="text-mcc-critical text-xs">No project</span>')

    priority = TaskPriority.high if rec.impact_level == "high" else TaskPriority.medium
    desc_parts = [rec.body]
    if rec.expected_impact:
        desc_parts.append(f"\nExpected impact: {rec.expected_impact}")
    if rec.estimated_time:
        desc_parts.append(f"Estimated time: {rec.estimated_time}")

    task = Task(
        project_id=project.id,
        title=f"[Web] {rec.headline[:150]}",
        description="\n".join(desc_parts),
        status=TaskStatus.backlog,
        priority=priority,
        assigned_to=rec.assignee if rec.assignee in ("phil", "clint") else "phil",
    )
    db.add(task)
    db.flush()
    rec.task_id = task.id
    db.commit()

    return HTMLResponse(
        f'<span class="text-[10px] px-1.5 py-0.5 rounded bg-mcc-success/15 text-mcc-success font-medium">Task #{task.id} created</span>'
    )


@router.get("/intelligence/history/{analysis_id}", response_class=HTMLResponse)
async def view_analysis_history(analysis_id: int, request: Request, db: Session = Depends(get_db)):
    """View a historical analysis."""
    analysis = db.get(WebsiteAnalysis, analysis_id)
    if not analysis:
        return HTMLResponse('<div class="text-xs text-mcc-critical">Analysis not found</div>')

    recs = db.query(WebsiteRecommendation).filter_by(
        analysis_id=analysis.id
    ).order_by(WebsiteRecommendation.id).all()

    # Check which recs were followed (task completed)
    for rec in recs:
        if rec.task_id:
            task = db.get(Task, rec.task_id)
            if task and task.status == TaskStatus.done:
                rec.followed = True

    html = _render_analysis_sections(analysis, recs)
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# Impact evaluation (called from scheduler)
# ---------------------------------------------------------------------------

def evaluate_past_recommendations():
    """Compare current metrics against metrics at time of recommendation (30+ days old)."""
    db = SessionLocal()
    try:
        project = db.query(Project).filter_by(slug="grindlab").first()
        if not project:
            return

        cutoff = datetime.utcnow() - timedelta(days=30)
        old_analyses = db.query(WebsiteAnalysis).filter(
            WebsiteAnalysis.project_id == project.id,
            WebsiteAnalysis.created_at <= cutoff,
        ).all()

        for analysis in old_analyses:
            recs = db.query(WebsiteRecommendation).filter(
                WebsiteRecommendation.analysis_id == analysis.id,
                WebsiteRecommendation.task_id.isnot(None),
                WebsiteRecommendation.impact_result.is_(None),
            ).all()

            for rec in recs:
                task = db.get(Task, rec.task_id)
                if task and task.status == TaskStatus.done:
                    rec.followed = True
                    rec.impact_result = f"Task #{task.id} completed on {task.completed_at.strftime('%b %d') if task.completed_at else 'unknown date'}. Review current metrics vs snapshot to assess impact."

            db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Real-time endpoint
# ---------------------------------------------------------------------------

@router.get("/realtime", response_class=HTMLResponse)
async def website_realtime_fragment(request: Request):
    """HTMX endpoint to refresh real-time data."""
    realtime = await fetch_realtime()
    if not realtime:
        return HTMLResponse('<div class="text-xs text-mcc-muted text-center py-4">Real-time data unavailable</div>')

    html = f"""
    <div class="flex items-center gap-3 mb-4">
        <div class="flex items-center gap-2">
            <span class="relative flex h-2.5 w-2.5">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
            </span>
            <span class="text-2xl font-bold text-mcc-text">{realtime['active_users']}</span>
        </div>
        <span class="text-sm text-mcc-muted">active users right now</span>
    </div>
    """
    if realtime["pages"]:
        html += '<div class="space-y-1.5">'
        for p in realtime["pages"][:8]:
            html += f"""
            <div class="flex items-center justify-between py-1 px-2 rounded bg-mcc-bg/50">
                <span class="text-xs text-mcc-muted font-mono">{p['page']}</span>
                <span class="text-xs font-medium text-mcc-accent">{p['users']}</span>
            </div>"""
        html += "</div>"

    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# Heatmap CRUD
# ---------------------------------------------------------------------------

@router.post("/heatmap", response_class=HTMLResponse)
async def add_heatmap_insight(
    request: Request,
    db: Session = Depends(get_db),
    insight_date: str = Form(...),
    page: str = Form(...),
    observation: str = Form(...),
    action_taken: str = Form(""),
):
    """Add a new heatmap/UX insight."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse('<div class="text-xs text-mcc-critical">No project found</div>')

    insight = HeatmapInsight(
        project_id=project.id,
        insight_date=date.fromisoformat(insight_date),
        page=page.strip(),
        observation=observation.strip(),
        action_taken=action_taken.strip(),
    )
    db.add(insight)
    db.commit()

    return _render_insight_card(insight)


@router.post("/heatmap/{insight_id}/task", response_class=HTMLResponse)
async def create_task_from_insight(insight_id: int, db: Session = Depends(get_db)):
    """Create a task from a heatmap insight."""
    insight = db.get(HeatmapInsight, insight_id)
    if not insight:
        return HTMLResponse('<span class="text-mcc-critical text-xs">Not found</span>')

    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse('<span class="text-mcc-critical text-xs">No project</span>')

    task = Task(
        project_id=project.id,
        title=f"[UX] {insight.page}: {insight.observation[:120]}",
        description=f"From heatmap insight ({insight.insight_date}):\n\n{insight.observation}\n\nAction: {insight.action_taken}" if insight.action_taken else f"From heatmap insight ({insight.insight_date}):\n\n{insight.observation}",
        status=TaskStatus.backlog,
        priority=TaskPriority.medium,
    )
    db.add(task)
    db.flush()
    insight.task_id = task.id
    db.commit()

    return _render_insight_card(insight, task_just_created=True)


@router.delete("/heatmap/{insight_id}", response_class=HTMLResponse)
async def delete_heatmap_insight(insight_id: int, db: Session = Depends(get_db)):
    """Delete a heatmap insight."""
    insight = db.get(HeatmapInsight, insight_id)
    if not insight:
        return HTMLResponse("")
    db.delete(insight)
    db.commit()
    return HTMLResponse("")


def _render_insight_card(insight: HeatmapInsight, task_just_created: bool = False) -> HTMLResponse:
    """Render a single heatmap insight card for HTMX swap."""
    task_badge = ""
    if insight.task_id:
        task_badge = f'<span class="text-[10px] px-1.5 py-0.5 rounded bg-mcc-success/15 text-mcc-success">Task #{insight.task_id}</span>'
    elif task_just_created:
        task_badge = '<span class="text-[10px] px-1.5 py-0.5 rounded bg-mcc-success/15 text-mcc-success">Task created</span>'

    task_btn = ""
    if not insight.task_id:
        task_btn = f'''<button class="text-[10px] px-1.5 py-0.5 rounded bg-mcc-accent/15 text-mcc-accent hover:bg-mcc-accent/25 font-medium transition-colors"
                hx-post="/website/heatmap/{insight.id}/task"
                hx-target="#heatmap-{insight.id}"
                hx-swap="outerHTML">+Task</button>'''

    action_html = ""
    if insight.action_taken:
        action_html = f'<div class="text-[11px] text-mcc-muted mt-1.5"><span class="text-mcc-accent font-medium">Action:</span> {insight.action_taken}</div>'

    html = f'''<div id="heatmap-{insight.id}" class="mcc-card p-4">
        <div class="flex items-start justify-between gap-3">
            <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                    <span class="text-[10px] text-mcc-dim">{insight.insight_date}</span>
                    <span class="text-[10px] font-mono text-mcc-accent">{insight.page}</span>
                    {task_badge}
                </div>
                <div class="text-xs text-mcc-text">{insight.observation}</div>
                {action_html}
            </div>
            <div class="flex items-center gap-1 flex-shrink-0">
                {task_btn}
                <button class="text-mcc-dim hover:text-mcc-critical p-0.5 transition-colors"
                        hx-delete="/website/heatmap/{insight.id}"
                        hx-target="#heatmap-{insight.id}"
                        hx-swap="outerHTML"
                        hx-confirm="Delete this insight?"
                        title="Delete">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                </button>
            </div>
        </div>
    </div>'''
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# Helper to render analysis sections (used by HTMX history view)
# ---------------------------------------------------------------------------

def _render_analysis_sections(analysis: WebsiteAnalysis, recs: list[WebsiteRecommendation]) -> str:
    """Render analysis sections as HTML string."""
    recs_by_section = {}
    for rec in recs:
        recs_by_section.setdefault(rec.section, []).append(rec)

    html = ""
    for section_key in SECTION_KEYS:
        section_recs = recs_by_section.get(section_key, [])
        if not section_recs:
            continue
        label = SECTION_LABELS.get(section_key, section_key)
        html += f'<div class="mb-4"><h4 class="text-xs font-semibold text-mcc-muted uppercase tracking-wider mb-2">{label}</h4><div class="space-y-2">'
        for rec in section_recs:
            color_class = _impact_color_class(rec)
            task_html = ""
            if rec.task_id:
                task_html = f'<span class="text-[10px] px-1.5 py-0.5 rounded bg-mcc-success/15 text-mcc-success">Task #{rec.task_id}</span>'
            impact_html = ""
            if rec.impact_result:
                impact_html = f'<div class="text-[11px] text-mcc-success mt-1 pt-1 border-t border-mcc-border/20">{rec.impact_result}</div>'
            html += f'''<div class="rounded-lg border {color_class} p-3">
                <div class="flex items-start justify-between gap-2">
                    <div class="flex-1"><div class="text-xs font-semibold text-mcc-text">{rec.headline}</div>
                    <div class="text-[11px] text-mcc-muted mt-1">{rec.body}</div></div>
                    {task_html}
                </div>
                {impact_html}
            </div>'''
        html += '</div></div>'

    return html


def _impact_color_class(rec: WebsiteRecommendation) -> str:
    if rec.impact_level == "high" and rec.difficulty == "easy":
        return "border-emerald-500/30 bg-emerald-500/5"
    elif rec.impact_level == "high":
        return "border-amber-500/30 bg-amber-500/5"
    else:
        return "border-cyan-500/30 bg-cyan-500/5"


# ---------------------------------------------------------------------------
# Dashboard widget helper
# ---------------------------------------------------------------------------

async def get_website_widget(db: Session, project_id: int) -> dict | None:
    """Dashboard widget data. Returns None if GA4 not configured."""
    if not is_ga4_configured():
        return None
    widget = await fetch_dashboard_widget()
    if widget is None:
        return None

    # Add recommendation counts
    latest = db.query(WebsiteAnalysis).filter_by(
        project_id=project_id
    ).order_by(WebsiteAnalysis.created_at.desc()).first()
    if latest:
        widget["total_recs"] = latest.total_recommendations
        widget["high_impact_recs"] = latest.high_impact_count
    else:
        widget["total_recs"] = 0
        widget["high_impact_recs"] = 0

    return widget


# ---------------------------------------------------------------------------
# Scheduled job for weekly auto-analysis
# ---------------------------------------------------------------------------

def run_website_intelligence():
    """Weekly job: auto-generate website intelligence analysis."""
    import asyncio

    db = SessionLocal()
    try:
        project = db.query(Project).filter_by(slug="grindlab").first()
        if not project:
            return
        if not ai_configured():
            return

        pid = project.id

        async def _run():
            ga4_connected = is_ga4_configured()
            traffic = None
            pages = None
            sources = None
            utms = None
            funnel = None

            if ga4_connected:
                traffic = await fetch_traffic_overview()
                pages = await fetch_page_performance()
                sources = await fetch_source_detail()
                utms = await fetch_utm_dashboard()
                funnel = await fetch_conversion_funnel()

            context = _build_website_context(traffic, pages, sources, funnel, utms, db, pid)
            prompt = _build_analysis_prompt(context)
            response = await simple_completion(prompt, system_override=WEBSITE_ANALYSIS_SYSTEM)

            if not response:
                logger.warning("Website intelligence: empty AI response")
                return

            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                logger.error("Website intelligence: JSON parse failed")
                return

            total_recs = 0
            high_impact = 0
            for sk in SECTION_KEYS:
                recs = data.get(sk, [])
                if isinstance(recs, list):
                    total_recs += len(recs)
                    high_impact += sum(1 for r in recs if isinstance(r, dict) and r.get("impact_level") == "high")

            snapshot = {}
            if traffic:
                snapshot["traffic"] = {
                    "visitors_today": traffic.get("visitors_today", 0),
                    "visitors_week": traffic.get("visitors_week", 0),
                    "visitors_month": traffic.get("visitors_month", 0),
                    "bounce_rate": traffic.get("bounce_rate_today", 0),
                }
            if funnel and funnel.get("stages"):
                snapshot["funnel"] = {s["key"]: s["count"] for s in funnel["stages"] if s.get("count") is not None}

            analysis = WebsiteAnalysis(
                project_id=pid,
                snapshot_data=snapshot,
                sections=data,
                total_recommendations=total_recs,
                high_impact_count=high_impact,
            )
            db.add(analysis)
            db.flush()

            for sk in SECTION_KEYS:
                recs = data.get(sk, [])
                if not isinstance(recs, list):
                    continue
                for rec in recs:
                    if not isinstance(rec, dict):
                        continue
                    db.add(WebsiteRecommendation(
                        analysis_id=analysis.id,
                        section=sk,
                        headline=rec.get("headline", "Untitled")[:300],
                        body=rec.get("body", ""),
                        assignee=rec.get("assignee", "phil"),
                        estimated_time=rec.get("estimated_time", ""),
                        expected_impact=rec.get("expected_impact", ""),
                        impact_level=rec.get("impact_level", "medium"),
                        difficulty=rec.get("difficulty", "medium"),
                    ))

            db.commit()
            logger.info(f"Website intelligence: generated {total_recs} recommendations ({high_impact} high impact)")

        # Run async code from sync context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(lambda: asyncio.run(_run())).result(timeout=120)
            else:
                loop.run_until_complete(_run())
        except RuntimeError:
            asyncio.run(_run())

        # Also evaluate old recommendations
        evaluate_past_recommendations()

    except Exception as e:
        logger.error(f"Website intelligence job failed: {e}")
    finally:
        db.close()


def _sync_wrap(fn):
    def wrapper():
        try:
            fn()
        except Exception as e:
            logger.error(f"Website job {fn.__name__} failed: {e}")
    return wrapper


website_intelligence_job = _sync_wrap(run_website_intelligence)
