"""Marketing Intelligence — Channel Discovery, Tool Discovery, Landscape Monitor."""
import json
import logging
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import (
    Project, Channel, Tool, Task, Metric, Competitor, CompetitorUpdate,
    BudgetLineItem, BudgetMonthEntry,
    IntelligenceItem, IntelItemType, IntelItemStatus,
    LandscapeCategory, LandscapeUrgency,
    ChannelStatus, ChannelType, AutomationLevel, ToolStatus, TaskStatus, TaskPriority,
)
from app.ai.engine import simple_completion, is_configured as ai_configured

logger = logging.getLogger("mcc.intelligence")

router = APIRouter(prefix="/intelligence")
templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# Helpers to build AI prompt context
# ---------------------------------------------------------------------------

def _channel_context(db: Session, pid: int) -> str:
    """Build channel context string for AI prompts."""
    channels = db.query(Channel).filter_by(project_id=pid).all()
    live = [c for c in channels if c.status == ChannelStatus.live]
    planned = [c for c in channels if c.status == ChannelStatus.planned]

    lines = ["Currently active channels:"]
    for ch in live:
        # Get latest metrics
        metrics = db.query(Metric).filter_by(channel_id=ch.id).order_by(
            Metric.recorded_at.desc()
        ).all()
        seen = {}
        for m in metrics:
            if m.metric_name not in seen:
                seen[m.metric_name] = float(m.metric_value)
            if len(seen) >= 3:
                break
        metric_str = ", ".join(f"{k}: {v:,.0f}" for k, v in seen.items()) if seen else "no metrics yet"
        lines.append(f"- {ch.name} ({ch.channel_type.value}) [{ch.automation_level.value}] — {metric_str}")

    lines.append("\nCurrently planned channels:")
    for ch in planned:
        lines.append(f"- {ch.name} ({ch.channel_type.value})")

    return "\n".join(lines)


def _tool_context(db: Session, pid: int) -> str:
    """Build tool stack context string for AI prompts."""
    tools = db.query(Tool).filter_by(project_id=pid).all()
    lines = ["Current tool stack:"]
    for t in tools:
        cost_str = f"${float(t.monthly_cost):.0f}/mo" if t.monthly_cost else "free"
        status_str = t.status.value
        lines.append(f"- {t.name} ({t.category.value}) — {t.purpose} [{cost_str}, {status_str}]")

    # Manual processes from recurring tasks
    recurring = db.query(Task).filter(
        Task.project_id == pid,
        Task.status == TaskStatus.recurring,
    ).all()
    if recurring:
        lines.append("\nRecurring manual processes:")
        for t in recurring:
            lines.append(f"- {t.title} ({t.recurring_frequency or 'unknown frequency'})")

    return "\n".join(lines)


def _budget_context(db: Session, pid: int) -> str:
    """Build budget context string for AI prompts."""
    today = date.today()
    month_start = today.replace(day=1)
    items = db.query(BudgetLineItem).filter(
        BudgetLineItem.project_id == pid,
    ).all()

    lines = ["Monthly budget allocation:"]
    total = 0
    for item in items:
        entry = db.query(BudgetMonthEntry).filter_by(
            line_item_id=item.id, month=month_start
        ).first()
        budgeted = float(entry.budgeted) if entry else float(item.default_amount)
        total += budgeted
        lines.append(f"- {item.name}: ${budgeted:,.0f}/mo")
    lines.append(f"Total monthly: ${total:,.0f}")
    return "\n".join(lines)


def _competitor_context(db: Session, pid: int) -> str:
    """Build competitor context string for AI prompts."""
    comps = db.query(Competitor).filter_by(project_id=pid).all()
    lines = ["Competitors:"]
    for c in comps:
        lines.append(f"- {c.name} ({c.website}): {c.positioning_summary}")
        if c.key_channels:
            lines.append(f"  Channels: {', '.join(c.key_channels)}")
    return "\n".join(lines)


def _dismissed_titles(db: Session, pid: int, item_type: IntelItemType) -> set:
    """Get titles of dismissed items to avoid re-recommending."""
    dismissed = db.query(IntelligenceItem.title).filter(
        IntelligenceItem.project_id == pid,
        IntelligenceItem.item_type == item_type,
        IntelligenceItem.status == IntelItemStatus.dismissed,
    ).all()
    return {t[0].lower() for t in dismissed}


# ---------------------------------------------------------------------------
# Summary counts for dashboard widget
# ---------------------------------------------------------------------------

def get_intelligence_counts(db: Session, pid: int) -> dict:
    """Get unreviewed counts for each intelligence tab."""
    base = db.query(func.count(IntelligenceItem.id)).filter(
        IntelligenceItem.project_id == pid,
        IntelligenceItem.status == IntelItemStatus.new,
        IntelligenceItem.is_not_recommended == False,
    )
    channels = base.filter(IntelligenceItem.item_type == IntelItemType.channel_discovery).scalar() or 0
    tools = base.filter(IntelligenceItem.item_type == IntelItemType.tool_discovery).scalar() or 0
    landscape = base.filter(IntelligenceItem.item_type == IntelItemType.landscape).scalar() or 0
    return {"channels": channels, "tools": tools, "landscape": landscape, "total": channels + tools + landscape}


# ---------------------------------------------------------------------------
# Main page route
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
def intelligence_page(request: Request, db: Session = Depends(get_db), tab: str = "channels"):
    project = db.query(Project).first()
    if not project:
        return templates.TemplateResponse("intelligence.html", {
            "request": request, "project": None, "tab": tab,
            "current_page": "intelligence", "today": date.today(),
        })

    pid = project.id

    # Channel Discovery items
    channel_items = db.query(IntelligenceItem).filter(
        IntelligenceItem.project_id == pid,
        IntelligenceItem.item_type == IntelItemType.channel_discovery,
        IntelligenceItem.is_not_recommended == False,
        IntelligenceItem.status != IntelItemStatus.dismissed,
    ).order_by(IntelligenceItem.fit_score.desc().nullslast(), IntelligenceItem.created_at.desc()).all()

    channel_not_recommended = db.query(IntelligenceItem).filter(
        IntelligenceItem.project_id == pid,
        IntelligenceItem.item_type == IntelItemType.channel_discovery,
        IntelligenceItem.is_not_recommended == True,
    ).order_by(IntelligenceItem.created_at.desc()).all()

    # Tool Discovery items
    tool_items = db.query(IntelligenceItem).filter(
        IntelligenceItem.project_id == pid,
        IntelligenceItem.item_type == IntelItemType.tool_discovery,
        IntelligenceItem.is_not_recommended == False,
        IntelligenceItem.status != IntelItemStatus.dismissed,
    ).order_by(IntelligenceItem.fit_score.desc().nullslast(), IntelligenceItem.created_at.desc()).all()

    tool_not_recommended = db.query(IntelligenceItem).filter(
        IntelligenceItem.project_id == pid,
        IntelligenceItem.item_type == IntelItemType.tool_discovery,
        IntelligenceItem.is_not_recommended == True,
    ).order_by(IntelligenceItem.created_at.desc()).all()

    # Stack health summary
    tools = db.query(Tool).filter_by(project_id=pid, status=ToolStatus.active).all()
    total_tool_spend = sum(float(t.monthly_cost or 0) for t in tools)

    # Landscape items
    landscape_items = db.query(IntelligenceItem).filter(
        IntelligenceItem.project_id == pid,
        IntelligenceItem.item_type == IntelItemType.landscape,
        IntelligenceItem.status != IntelItemStatus.dismissed,
    ).order_by(IntelligenceItem.created_at.desc()).limit(50).all()

    landscape_this_week = db.query(IntelligenceItem).filter(
        IntelligenceItem.project_id == pid,
        IntelligenceItem.item_type == IntelItemType.landscape,
        IntelligenceItem.created_at >= datetime.utcnow() - timedelta(days=7),
    ).count()

    counts = get_intelligence_counts(db, pid)

    # Group tool items by category
    tool_by_cat = {}
    for item in tool_items:
        cat = item.tool_category or "Other"
        tool_by_cat.setdefault(cat, []).append(item)

    return templates.TemplateResponse("intelligence.html", {
        "request": request,
        "project": project,
        "tab": tab,
        "channel_items": channel_items,
        "channel_not_recommended": channel_not_recommended,
        "tool_items": tool_items,
        "tool_not_recommended": tool_not_recommended,
        "tool_by_cat": tool_by_cat,
        "total_tool_spend": total_tool_spend,
        "tool_count": len(tools),
        "landscape_items": landscape_items,
        "landscape_this_week": landscape_this_week,
        "counts": counts,
        "ai_configured": ai_configured(),
        "current_page": "intelligence",
        "today": date.today(),
    })


# ---------------------------------------------------------------------------
# AI Generation endpoints
# ---------------------------------------------------------------------------

CHANNEL_SYSTEM = """You are a marketing strategist for Grindlab, a $18/month poker study SaaS tool launching April 1, 2026. Target audience: poker players aged 25-60, primarily live players, all skill levels. Current marketing budget: $10K total for 4 months. Team: one founder (Phil) handling all marketing with a video editor (Karen) and AI automation (Scotty). The product is NOT coaching, NOT a course, NOT a solver — it's a study system/platform with utility tools. Competitors: GTO Wizard, Upswing Poker, PokerCoaching.com, Run It Once.

CRITICAL FILTER: Do NOT recommend channels that require: large teams, budgets over $500/month to test, significant technical infrastructure we don't have, or audiences that don't overlap with poker players."""

TOOL_SYSTEM = """You are evaluating marketing tools for Grindlab, a poker study SaaS startup. CRITICAL FILTER: Only recommend tools that either: save Phil time on things he's currently doing manually, cost less than what we're currently paying for the same function, add a capability we've identified as needed, OR fix a known problem in our current stack. Do NOT recommend tools just because they exist."""

LANDSCAPE_SYSTEM = """You are monitoring the marketing landscape for Grindlab, a poker study SaaS tool. CRITICAL FILTER: Only surface things that have a direct, specific relevance to Grindlab. Generic industry news is not useful. Everything must connect to a specific action or awareness item for Phil."""


@router.post("/generate/channels", response_class=HTMLResponse)
async def generate_channel_discoveries(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).first()
    if not project or not ai_configured():
        return HTMLResponse('<div class="text-mcc-warning text-sm py-4">AI not configured — set ANTHROPIC_API_KEY</div>')

    pid = project.id
    ch_ctx = _channel_context(db, pid)
    budget_ctx = _budget_context(db, pid)
    dismissed = _dismissed_titles(db, pid, IntelItemType.channel_discovery)

    prompt = f"""{ch_ctx}

{budget_ctx}

Previously dismissed channels (do not re-recommend): {', '.join(dismissed) if dismissed else 'none'}

Identify 5-8 marketing channels we are NOT currently using. For each:

Return ONLY valid JSON (no markdown, no code blocks). Format:
{{
  "recommended": [
    {{
      "name": "Channel Name",
      "description": "What this channel is",
      "why_grindlab": "Why specifically for Grindlab",
      "time_per_week": "e.g. 3-5 hours",
      "cost_per_month": "e.g. $0-50",
      "timeline": "e.g. 2-4 weeks to first results",
      "fit_score": 8,
      "risk": "Any downsides"
    }}
  ],
  "not_recommended": [
    {{
      "name": "Channel Name",
      "reason": "Why this doesn't fit — be specific"
    }}
  ]
}}"""

    try:
        response = await simple_completion(prompt, system_override=CHANNEL_SYSTEM)
    except Exception as e:
        logger.error(f"Channel discovery AI failed: {e}")
        return HTMLResponse(f'<div class="text-red-400 text-sm py-4">AI error: {e}</div>')

    if not response:
        return HTMLResponse('<div class="text-mcc-warning text-sm py-4">No AI response</div>')

    # Parse JSON response
    try:
        # Strip markdown code fences if present
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse channel discovery JSON, saving raw")
        item = IntelligenceItem(
            project_id=pid, item_type=IntelItemType.channel_discovery,
            title="Channel Discovery (raw)", body=response, fit_score=5,
        )
        db.add(item)
        db.commit()
        return HTMLResponse(f'<div class="text-xs text-mcc-text py-4 whitespace-pre-wrap">{response}</div>', headers={"HX-Redirect": "/intelligence?tab=channels"})

    # Save recommended items
    for rec in data.get("recommended", []):
        existing = db.query(IntelligenceItem).filter(
            IntelligenceItem.project_id == pid,
            IntelligenceItem.item_type == IntelItemType.channel_discovery,
            IntelligenceItem.title == rec["name"],
        ).first()
        if existing:
            continue
        item = IntelligenceItem(
            project_id=pid,
            item_type=IntelItemType.channel_discovery,
            title=rec["name"],
            body=rec.get("why_grindlab", rec.get("description", "")),
            fit_score=rec.get("fit_score", 5),
            time_per_week=rec.get("time_per_week"),
            cost_per_month=rec.get("cost_per_month"),
            timeline_to_results=rec.get("timeline"),
            risk_downside=rec.get("risk"),
        )
        db.add(item)

    # Save not-recommended items
    for nr in data.get("not_recommended", []):
        existing = db.query(IntelligenceItem).filter(
            IntelligenceItem.project_id == pid,
            IntelligenceItem.item_type == IntelItemType.channel_discovery,
            IntelligenceItem.title == nr["name"],
        ).first()
        if existing:
            continue
        item = IntelligenceItem(
            project_id=pid,
            item_type=IntelItemType.channel_discovery,
            title=nr["name"],
            body="",
            is_not_recommended=True,
            rejection_reason=nr.get("reason", ""),
        )
        db.add(item)

    db.commit()
    return HTMLResponse('<div class="text-mcc-success text-sm py-2">Generated!</div>', headers={"HX-Redirect": "/intelligence?tab=channels"})


@router.post("/generate/tools", response_class=HTMLResponse)
async def generate_tool_discoveries(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).first()
    if not project or not ai_configured():
        return HTMLResponse('<div class="text-mcc-warning text-sm py-4">AI not configured</div>')

    pid = project.id
    tool_ctx = _tool_context(db, pid)
    budget_ctx = _budget_context(db, pid)
    dismissed = _dismissed_titles(db, pid, IntelItemType.tool_discovery)

    prompt = f"""{tool_ctx}

{budget_ctx}

Previously dismissed tools (do not re-recommend): {', '.join(dismissed) if dismissed else 'none'}

Recommend 5-8 marketing tools that would improve efficiency or reduce costs. For each:

Return ONLY valid JSON:
{{
  "recommended": [
    {{
      "name": "Tool Name",
      "description": "What it does",
      "replaces": "Which current tool it replaces or manual process it eliminates",
      "cost": "Free tier? Monthly cost?",
      "net_impact": "Saves $X or saves Y hours/week",
      "complexity": "Drop-in / Needs setup / Needs development",
      "confidence": "Proven / Established / New",
      "category": "Email / Social / Content / Analytics / Lead Gen / Automation / AI",
      "fit_score": 7
    }}
  ],
  "not_recommended": [
    {{
      "name": "Tool Name",
      "reason": "Why it doesn't fit"
    }}
  ]
}}"""

    try:
        response = await simple_completion(prompt, system_override=TOOL_SYSTEM)
    except Exception as e:
        return HTMLResponse(f'<div class="text-red-400 text-sm py-4">AI error: {e}</div>')

    if not response:
        return HTMLResponse('<div class="text-mcc-warning text-sm py-4">No AI response</div>')

    try:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        item = IntelligenceItem(
            project_id=pid, item_type=IntelItemType.tool_discovery,
            title="Tool Discovery (raw)", body=response, fit_score=5,
        )
        db.add(item)
        db.commit()
        return HTMLResponse('<div class="text-mcc-success text-sm py-2">Saved (raw format)</div>', headers={"HX-Redirect": "/intelligence?tab=tools"})

    for rec in data.get("recommended", []):
        existing = db.query(IntelligenceItem).filter(
            IntelligenceItem.project_id == pid,
            IntelligenceItem.item_type == IntelItemType.tool_discovery,
            IntelligenceItem.title == rec["name"],
        ).first()
        if existing:
            continue
        item = IntelligenceItem(
            project_id=pid,
            item_type=IntelItemType.tool_discovery,
            title=rec["name"],
            body=rec.get("description", ""),
            fit_score=rec.get("fit_score", 5),
            replaces_tool=rec.get("replaces"),
            tool_cost=rec.get("cost"),
            net_cost_impact=rec.get("net_impact"),
            integration_complexity=rec.get("complexity"),
            confidence_level=rec.get("confidence"),
            tool_category=rec.get("category"),
        )
        db.add(item)

    for nr in data.get("not_recommended", []):
        existing = db.query(IntelligenceItem).filter(
            IntelligenceItem.project_id == pid,
            IntelligenceItem.item_type == IntelItemType.tool_discovery,
            IntelligenceItem.title == nr["name"],
        ).first()
        if existing:
            continue
        item = IntelligenceItem(
            project_id=pid,
            item_type=IntelItemType.tool_discovery,
            title=nr["name"],
            body="",
            is_not_recommended=True,
            rejection_reason=nr.get("reason", ""),
        )
        db.add(item)

    db.commit()
    return HTMLResponse('<div class="text-mcc-success text-sm py-2">Generated!</div>', headers={"HX-Redirect": "/intelligence?tab=tools"})


@router.post("/generate/landscape", response_class=HTMLResponse)
async def generate_landscape_scan(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).first()
    if not project or not ai_configured():
        return HTMLResponse('<div class="text-mcc-warning text-sm py-4">AI not configured</div>')

    pid = project.id
    comp_ctx = _competitor_context(db, pid)
    ch_ctx = _channel_context(db, pid)

    prompt = f"""{comp_ctx}

{ch_ctx}

Search for and analyze recent developments. Return ONLY valid JSON:
{{
  "items": [
    {{
      "title": "What happened",
      "category": "competitor|platform|industry|trend",
      "why_matters": "Why it matters to Grindlab specifically",
      "action": "Recommended action or 'awareness only'",
      "urgency": "act_now|act_this_week|awareness",
      "source": "Source URL or description"
    }}
  ]
}}

Find 5-10 items across all categories. Focus on things from the last 2 weeks. Be specific — every item must connect to a concrete implication for Grindlab."""

    try:
        response = await simple_completion(prompt, system_override=LANDSCAPE_SYSTEM)
    except Exception as e:
        return HTMLResponse(f'<div class="text-red-400 text-sm py-4">AI error: {e}</div>')

    if not response:
        return HTMLResponse('<div class="text-mcc-warning text-sm py-4">No AI response</div>')

    try:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        item = IntelligenceItem(
            project_id=pid, item_type=IntelItemType.landscape,
            title="Landscape Scan (raw)", body=response,
            landscape_category=LandscapeCategory.trend,
            urgency=LandscapeUrgency.awareness,
        )
        db.add(item)
        db.commit()
        return HTMLResponse('<div class="text-mcc-success text-sm py-2">Saved</div>', headers={"HX-Redirect": "/intelligence?tab=landscape"})

    cat_map = {"competitor": LandscapeCategory.competitor, "platform": LandscapeCategory.platform,
               "industry": LandscapeCategory.industry, "trend": LandscapeCategory.trend}
    urg_map = {"act_now": LandscapeUrgency.act_now, "act_this_week": LandscapeUrgency.act_this_week,
               "awareness": LandscapeUrgency.awareness}

    for entry in data.get("items", []):
        existing = db.query(IntelligenceItem).filter(
            IntelligenceItem.project_id == pid,
            IntelligenceItem.item_type == IntelItemType.landscape,
            IntelligenceItem.title == entry["title"],
        ).first()
        if existing:
            continue
        item = IntelligenceItem(
            project_id=pid,
            item_type=IntelItemType.landscape,
            title=entry["title"],
            body=entry.get("why_matters", ""),
            landscape_category=cat_map.get(entry.get("category"), LandscapeCategory.trend),
            urgency=urg_map.get(entry.get("urgency"), LandscapeUrgency.awareness),
            source_url=entry.get("source"),
            action_recommended=entry.get("action"),
        )
        db.add(item)

    db.commit()
    return HTMLResponse('<div class="text-mcc-success text-sm py-2">Scan complete!</div>', headers={"HX-Redirect": "/intelligence?tab=landscape"})


# ---------------------------------------------------------------------------
# Action endpoints
# ---------------------------------------------------------------------------

@router.post("/items/{item_id}/dismiss", response_class=HTMLResponse)
def dismiss_item(item_id: int, db: Session = Depends(get_db), reason: str = Form("")):
    item = db.get(IntelligenceItem, item_id)
    if not item:
        return HTMLResponse('<span class="text-red-400 text-xs">Not found</span>')
    item.status = IntelItemStatus.dismissed
    item.dismiss_reason = reason or "Dismissed by Phil"
    item.reviewed_at = datetime.utcnow()
    db.commit()
    return HTMLResponse('<div class="text-[10px] text-mcc-muted py-2 text-center italic">Dismissed</div>')


@router.post("/items/{item_id}/mark-seen", response_class=HTMLResponse)
def mark_seen(item_id: int, db: Session = Depends(get_db)):
    item = db.get(IntelligenceItem, item_id)
    if not item:
        return HTMLResponse('<span class="text-red-400 text-xs">Not found</span>')
    item.status = IntelItemStatus.reviewed
    item.reviewed_at = datetime.utcnow()
    db.commit()
    return HTMLResponse('<span class="text-[10px] text-mcc-success">Seen</span>')


@router.post("/items/{item_id}/add-planned", response_class=HTMLResponse)
def add_as_planned_channel(item_id: int, db: Session = Depends(get_db)):
    """Add a channel discovery item as a Planned channel."""
    item = db.get(IntelligenceItem, item_id)
    if not item:
        return HTMLResponse('<span class="text-red-400 text-xs">Not found</span>')

    project = db.query(Project).first()
    if not project:
        return HTMLResponse('<span class="text-red-400 text-xs">No project</span>')

    # Create the channel
    channel = Channel(
        project_id=project.id,
        name=item.title,
        channel_type=ChannelType.social,  # default, can be changed later
        status=ChannelStatus.planned,
        automation_level=AutomationLevel.manual,
        notes=f"From Intelligence: {item.body}\nTime/week: {item.time_per_week or 'TBD'}\nCost: {item.cost_per_month or 'TBD'}",
    )
    db.add(channel)
    item.status = IntelItemStatus.accepted
    item.reviewed_at = datetime.utcnow()
    db.commit()
    return HTMLResponse(f'<span class="text-mcc-success text-xs">Added as planned channel</span>')


@router.post("/items/{item_id}/add-task", response_class=HTMLResponse)
def add_as_task(item_id: int, db: Session = Depends(get_db)):
    """Create a task from an intelligence item (tool evaluation or landscape action)."""
    item = db.get(IntelligenceItem, item_id)
    if not item:
        return HTMLResponse('<span class="text-red-400 text-xs">Not found</span>')

    project = db.query(Project).first()
    if not project:
        return HTMLResponse('<span class="text-red-400 text-xs">No project</span>')

    desc_parts = [item.body]
    if item.item_type == IntelItemType.tool_discovery:
        if item.replaces_tool:
            desc_parts.append(f"Replaces: {item.replaces_tool}")
        if item.tool_cost:
            desc_parts.append(f"Cost: {item.tool_cost}")
        if item.net_cost_impact:
            desc_parts.append(f"Impact: {item.net_cost_impact}")
    elif item.item_type == IntelItemType.landscape:
        if item.action_recommended:
            desc_parts.append(f"Action: {item.action_recommended}")
        if item.source_url:
            desc_parts.append(f"Source: {item.source_url}")

    priority = TaskPriority.medium
    if item.urgency == LandscapeUrgency.act_now:
        priority = TaskPriority.high

    task = Task(
        project_id=project.id,
        title=f"[Intel] {item.title[:150]}",
        description="\n".join(desc_parts),
        status=TaskStatus.backlog,
        priority=priority,
    )
    db.add(task)
    item.status = IntelItemStatus.accepted
    item.reviewed_at = datetime.utcnow()
    db.commit()
    return HTMLResponse(f'<span class="text-mcc-success text-xs">Task #{task.id} created</span>')
