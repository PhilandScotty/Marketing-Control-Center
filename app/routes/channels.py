import asyncio
import logging
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import (
    Project, Channel, Metric, MetricSnapshot, Task, Automation,
    TaskStatus, ChannelType, ChannelStatus, AutomationLevel, HealthStatus,
    AIInsight, InsightType, InsightSourceType, InsightSeverity,
    SubscriberEvent, MetricSource,
)
from app.ai.engine import simple_completion, is_configured as ai_configured
from app.alerts import send_telegram

logger = logging.getLogger("mcc.channels")

router = APIRouter(prefix="/channels")
templates = Jinja2Templates(directory="app/templates")

# Group labels and ordering for display
TYPE_GROUPS = [
    ("owned", "Owned Channels", [ChannelType.email, ChannelType.content, ChannelType.seo]),
    ("social", "Social Channels", [ChannelType.social, ChannelType.community]),
    ("paid", "Paid Channels", [ChannelType.paid_ads, ChannelType.cold_outreach]),
    ("referral", "Referral & Partner Channels", [ChannelType.referral, ChannelType.partnerships]),
]

# Reference channels for poker SaaS gap analysis
GAP_CHANNELS = [
    {
        "name": "Discord Community",
        "why": "GTO Wizard, Upswing, and Run It Once all have active Discord servers with 5K-50K members. Community drives retention and word-of-mouth.",
        "competitors": "GTO Wizard, Upswing Poker, Run It Once",
    },
    {
        "name": "Poker Podcasts",
        "why": "Guest appearances on podcasts like Thinking Poker, The Poker Guys, or Just Hands reach engaged poker learners. Sponsorships start at $200/episode.",
        "competitors": "Upswing, Pokercoaching.com",
    },
    {
        "name": "2+2 Forums",
        "why": "Largest poker strategy community (300K+ members). Active presence builds credibility with serious players — your core audience.",
        "competitors": "Most poker tools have presence here",
    },
    {
        "name": "Twitch",
        "why": "Live poker study sessions on Twitch build authentic audience. Poker category has 5K-15K concurrent viewers. Low competition for study-focused streams.",
        "competitors": "GTO Wizard streams, various poker coaches",
    },
    {
        "name": "Newsletter Cross-Promotions",
        "why": "SparkLoop partner network enables subscriber swaps with complementary newsletters. Cost-effective growth at $1-3/subscriber.",
        "competitors": "Common in SaaS, underused in poker niche",
    },
    {
        "name": "SEO/Blog Content",
        "why": "Competitor comparison pages ('GTO Wizard vs Grindlab'), poker study guides, and GTO strategy articles drive organic search traffic with high intent.",
        "competitors": "Upswing, GTO Wizard blog, Pokercoaching",
    },
    {
        "name": "Poker Room Partnerships",
        "why": "Co-marketing with online poker rooms (PokerStars, GGPoker) or live card rooms. Bundle study tools with poker room signup bonuses.",
        "competitors": "GTO Wizard has PokerStars partnership",
    },
]


def _get_channel_metrics(db: Session, channel_ids: list[int]) -> dict:
    """Get latest 3 unique metrics per channel."""
    result = {}
    if not channel_ids:
        return result
    metrics = db.query(Metric).filter(
        Metric.channel_id.in_(channel_ids)
    ).order_by(Metric.recorded_at.desc()).all()

    for m in metrics:
        if m.channel_id not in result:
            result[m.channel_id] = {}
        if len(result[m.channel_id]) < 3 and m.metric_name not in result[m.channel_id]:
            delta = None
            if m.previous_value is not None and float(m.previous_value) != 0:
                delta = ((float(m.metric_value) - float(m.previous_value)) / float(m.previous_value)) * 100
            result[m.channel_id][m.metric_name] = {
                "value": float(m.metric_value),
                "previous": float(m.previous_value) if m.previous_value else None,
                "unit": m.unit or "count",
                "delta": delta,
            }
    return result


def _get_task_counts(db: Session, channel_ids: list[int]) -> dict:
    """Get active task count per channel."""
    if not channel_ids:
        return {}
    rows = db.query(
        Task.channel_id, func.count(Task.id)
    ).filter(
        Task.channel_id.in_(channel_ids),
        Task.status.notin_([TaskStatus.done, TaskStatus.archived]),
    ).group_by(Task.channel_id).all()
    return {cid: cnt for cid, cnt in rows}


def _build_performance_ranking(db: Session, channels: list, channel_metrics: dict) -> list[dict]:
    """Rank live channels by effectiveness score."""
    rankings = []

    for ch in channels:
        if ch.status != ChannelStatus.live:
            continue

        metrics = channel_metrics.get(ch.id, {})

        # Reach: audience-related metrics
        reach = 0
        for name, m in metrics.items():
            if any(kw in name.lower() for kw in ["subscriber", "follower", "audience", "list_size", "members"]):
                reach = max(reach, m["value"])

        # Engagement: interaction metrics
        engagement = 0
        for name, m in metrics.items():
            if any(kw in name.lower() for kw in ["engagement", "open_rate", "click", "karma", "likes", "views"]):
                engagement = max(engagement, m["value"])

        # Conversion: subscriber events attributed to this channel
        conversion_count = db.query(SubscriberEvent).filter(
            SubscriberEvent.source_channel_id == ch.id,
        ).count()

        # Spend
        spend = float(ch.total_spend_to_date or 0)

        # Cost per subscriber
        cost_per_sub = 0.0
        if conversion_count > 0 and spend > 0:
            cost_per_sub = spend / conversion_count

        # Simple composite score (weighted)
        # Reach (0-40pts), Engagement (0-20pts), Conversions (0-30pts), Cost Efficiency (0-10pts)
        reach_score = min(40, (reach / 1000) * 10) if reach else 0
        engagement_score = min(20, engagement * 0.5) if engagement else 0
        conversion_score = min(30, conversion_count * 3)
        efficiency_score = 10 if spend == 0 else max(0, 10 - cost_per_sub)

        total_score = reach_score + engagement_score + conversion_score + efficiency_score

        # Primary metric for display
        primary_metric = ""
        primary_value = ""
        if metrics:
            first_name = next(iter(metrics))
            first_m = metrics[first_name]
            primary_metric = first_name.replace("_", " ")
            primary_value = f"{first_m['value']:,.0f} {first_m['unit']}" if first_m["unit"] != "count" else f"{first_m['value']:,.0f}"

        cost_label = f"${cost_per_sub:.2f}/sub" if conversion_count > 0 and spend > 0 else ("$0 (free)" if spend == 0 else f"${spend:,.0f} spent")

        rankings.append({
            "channel": ch,
            "score": round(total_score, 1),
            "reach": int(reach),
            "engagement": round(engagement, 1),
            "conversions": conversion_count,
            "spend": spend,
            "cost_per_sub": cost_per_sub,
            "cost_label": cost_label,
            "primary_metric": primary_metric,
            "primary_value": primary_value,
        })

    rankings.sort(key=lambda x: x["score"], reverse=True)
    return rankings


def _build_gap_analysis(db: Session, pid: int) -> list[dict]:
    """Compare active channels against poker SaaS reference set."""
    active_names = {ch.name.lower() for ch in db.query(Channel).filter_by(project_id=pid).all()}

    gaps = []
    for ref in GAP_CHANNELS:
        # Check if we already have something similar
        ref_lower = ref["name"].lower()
        has_it = False
        for name in active_names:
            if any(kw in name for kw in ref_lower.split()):
                has_it = True
                break
        if not has_it:
            gaps.append(ref)
    return gaps


def _check_stale_channels(db: Session, pid: int) -> list[dict]:
    """Find manual channels that haven't been updated in 7+ days."""
    stale = []
    now = datetime.utcnow()
    channels = db.query(Channel).filter_by(project_id=pid).all()

    for ch in channels:
        if ch.status != ChannelStatus.live:
            continue

        # Check latest metric
        latest = db.query(Metric).filter_by(channel_id=ch.id).order_by(
            Metric.recorded_at.desc()
        ).first()

        if latest:
            days_since = (now - latest.recorded_at).days
            if days_since >= 7:
                stale.append({
                    "channel": ch,
                    "days_since": days_since,
                    "last_metric": latest.metric_name,
                })
        elif ch.automation_level == AutomationLevel.manual:
            # Never updated
            stale.append({
                "channel": ch,
                "days_since": None,
                "last_metric": None,
            })
    return stale


def _check_metric_drops(db: Session, pid: int) -> list[dict]:
    """Find channels with >20% week-over-week metric drops."""
    drops = []
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    channels = db.query(Channel).filter_by(project_id=pid, status=ChannelStatus.live).all()

    for ch in channels:
        metric_names = db.query(Metric.metric_name).filter(
            Metric.channel_id == ch.id,
        ).distinct().all()

        for (mname,) in metric_names:
            # This week's latest
            this_week = db.query(Metric).filter(
                Metric.channel_id == ch.id,
                Metric.metric_name == mname,
                Metric.recorded_at >= week_ago,
            ).order_by(Metric.recorded_at.desc()).first()

            # Last week's latest
            last_week = db.query(Metric).filter(
                Metric.channel_id == ch.id,
                Metric.metric_name == mname,
                Metric.recorded_at >= two_weeks_ago,
                Metric.recorded_at < week_ago,
            ).order_by(Metric.recorded_at.desc()).first()

            if this_week and last_week and float(last_week.metric_value) > 0:
                pct = ((float(this_week.metric_value) - float(last_week.metric_value)) / float(last_week.metric_value)) * 100
                if pct <= -20:
                    drops.append({
                        "channel": ch,
                        "metric": mname,
                        "current": float(this_week.metric_value),
                        "previous": float(last_week.metric_value),
                        "pct_change": round(pct, 1),
                    })
    return drops


@router.get("/", response_class=HTMLResponse)
def channels_index(request: Request, db: Session = Depends(get_db),
                   sort: str = "name", filter_status: str = "all",
                   filter_type: str = "all"):
    project = db.query(Project).first()
    if not project:
        return templates.TemplateResponse("channels.html", {
            "request": request, "project": None, "groups": [],
            "current_page": "channels", "today": date.today(),
            "rankings": [], "gap_channels": [], "stale_alerts": [],
            "metric_drops": [], "ai_recommendations": None,
        })

    pid = project.id
    query = db.query(Channel).filter_by(project_id=pid)

    if filter_status != "all":
        query = query.filter(Channel.status == filter_status)
    if filter_type != "all":
        query = query.filter(Channel.channel_type == filter_type)

    if sort == "name":
        query = query.order_by(Channel.name)
    elif sort == "status":
        query = query.order_by(Channel.status, Channel.name)
    elif sort == "health":
        query = query.order_by(Channel.health, Channel.name)
    elif sort == "type":
        query = query.order_by(Channel.channel_type, Channel.name)
    else:
        query = query.order_by(Channel.name)

    all_channels = query.all()
    channel_ids = [c.id for c in all_channels]

    channel_metrics = _get_channel_metrics(db, channel_ids)
    task_counts = _get_task_counts(db, channel_ids)

    # Channel Intelligence
    rankings = _build_performance_ranking(db, all_channels, channel_metrics)
    gap_channels = _build_gap_analysis(db, pid)
    stale_alerts = _check_stale_channels(db, pid)
    metric_drops = _check_metric_drops(db, pid)

    # Cached AI recommendations (latest insight of type suggestion + source channel)
    ai_rec = db.query(AIInsight).filter(
        AIInsight.project_id == pid,
        AIInsight.insight_type == InsightType.suggestion,
        AIInsight.source_type == InsightSourceType.channel,
        AIInsight.dismissed_at.is_(None),
    ).order_by(AIInsight.created_at.desc()).first()

    # Group channels by type
    groups = []
    used_ids = set()
    for key, label, types in TYPE_GROUPS:
        channels = [c for c in all_channels if c.channel_type in types and c.id not in used_ids]
        for c in channels:
            used_ids.add(c.id)
        if channels:
            groups.append({"key": key, "label": label, "channels": channels})

    remaining = [c for c in all_channels if c.id not in used_ids]
    if remaining:
        groups.append({"key": "other", "label": "Other Channels", "channels": remaining})

    # Stats
    total = len(all_channels)
    live_count = sum(1 for c in all_channels if c.status == ChannelStatus.live)
    healthy_count = sum(1 for c in all_channels if c.health == HealthStatus.healthy)
    warning_count = sum(1 for c in all_channels if c.health in (HealthStatus.warning, HealthStatus.critical))

    return templates.TemplateResponse("channels.html", {
        "request": request,
        "project": project,
        "groups": groups,
        "channel_metrics": channel_metrics,
        "task_counts": task_counts,
        "total": total,
        "live_count": live_count,
        "healthy_count": healthy_count,
        "warning_count": warning_count,
        "current_page": "channels",
        "today": date.today(),
        "sort": sort,
        "filter_status": filter_status,
        "filter_type": filter_type,
        "channel_types": [(t.value, t.value.replace("_", " ").title()) for t in ChannelType],
        "channel_statuses": [(s.value, s.value.replace("_", " ").title()) for s in ChannelStatus],
        "automation_levels": [(a.value, a.value.replace("_", " ").title()) for a in AutomationLevel],
        # Intelligence
        "rankings": rankings,
        "gap_channels": gap_channels,
        "stale_alerts": stale_alerts,
        "metric_drops": metric_drops,
        "ai_recommendations": ai_rec,
        "ai_configured": ai_configured(),
    })


@router.post("/intelligence/refresh", response_class=HTMLResponse)
async def refresh_ai_recommendations(request: Request, db: Session = Depends(get_db)):
    """Generate fresh AI-powered channel recommendations using Claude."""
    project = db.query(Project).first()
    if not project:
        return HTMLResponse('<div class="text-red-400 text-sm">No project found</div>')

    if not ai_configured():
        return HTMLResponse('<div class="text-mcc-warning text-sm">AI not configured — set ANTHROPIC_API_KEY in .env</div>')

    pid = project.id
    channels = db.query(Channel).filter_by(project_id=pid).all()

    # Build context for Claude
    channel_data = []
    for ch in channels:
        metrics = db.query(Metric).filter_by(channel_id=ch.id).order_by(
            Metric.recorded_at.desc()
        ).all()
        seen = {}
        for m in metrics:
            if m.metric_name not in seen:
                seen[m.metric_name] = {
                    "name": m.metric_name,
                    "value": float(m.metric_value),
                    "previous": float(m.previous_value) if m.previous_value else None,
                    "unit": m.unit,
                }
            if len(seen) >= 5:
                break

        conversions = db.query(SubscriberEvent).filter(
            SubscriberEvent.source_channel_id == ch.id,
        ).count()

        channel_data.append({
            "name": ch.name,
            "type": ch.channel_type.value,
            "status": ch.status.value,
            "health": ch.health.value,
            "automation": ch.automation_level.value,
            "spend": float(ch.total_spend_to_date or 0),
            "metrics": list(seen.values()),
            "conversions": conversions,
        })

    prompt = f"""Analyze these marketing channels for Grindlab (a poker study SaaS) and provide specific, actionable recommendations.

CHANNELS:
{channel_data}

Provide exactly 4 recommendations in this format:
1. INVEST MORE: Which channel deserves more time/money and why? Be specific about what to do.
2. DEPRIORITIZE: Which channel has the lowest ROI and should be paused or reduced? Why?
3. ACTIVATE NEXT: Which new channel should be started next based on current resources? What's the first step?
4. SPECIFIC ACTION: One concrete tactical action for the channel with the most untapped potential. Be very specific — mention exact features, tools, or tactics.

Keep each recommendation to 2-3 sentences. Be direct and data-driven."""

    system = "You are a marketing strategist analyzing channel performance for a poker SaaS startup. Be specific, data-driven, and actionable. No fluff."

    try:
        response = await simple_completion(prompt, system_override=system)
    except Exception as e:
        logger.error(f"AI recommendation failed: {e}")
        return HTMLResponse(f'<div class="text-red-400 text-sm">AI request failed: {e}</div>')

    if not response:
        return HTMLResponse('<div class="text-mcc-warning text-sm">No response from AI — check API key</div>')

    # Save as insight
    insight = AIInsight(
        project_id=pid,
        insight_type=InsightType.suggestion,
        source_type=InsightSourceType.channel,
        title=f"Channel Recommendations — {date.today().strftime('%b %d')}",
        body=response,
        severity=InsightSeverity.info,
        action_items=[],
    )
    db.add(insight)
    db.commit()

    # Return the rendered recommendation block
    lines = response.split("\n")
    html_parts = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Bold the labels
        for label in ["INVEST MORE:", "DEPRIORITIZE:", "ACTIVATE NEXT:", "SPECIFIC ACTION:",
                       "1.", "2.", "3.", "4."]:
            if line.startswith(label):
                line = f'<span class="text-mcc-accent font-semibold">{label}</span>{line[len(label):]}'
                break
        html_parts.append(f'<p class="text-xs text-mcc-text leading-relaxed mb-2">{line}</p>')

    return HTMLResponse(f'''
        <div class="space-y-1 animate-fadeIn">
            <div class="flex items-center gap-2 mb-3">
                <span class="text-[10px] text-mcc-success font-medium">Updated {datetime.now().strftime("%b %d, %I:%M %p")}</span>
            </div>
            {"".join(html_parts)}
        </div>
    ''')


@router.post("/sync-integrations", response_class=HTMLResponse)
async def sync_integrations(request: Request, db: Session = Depends(get_db)):
    """Manually trigger all configured integration syncs (Buffer, ConvertKit, etc.)."""
    from app.integrations.engine import run_integration
    from app.scheduler import INTEGRATIONS

    synced = []
    failed = []
    for integration in INTEGRATIONS:
        if integration.is_configured():
            try:
                await run_integration(integration)
                synced.append(integration.name)
            except Exception as e:
                failed.append(f"{integration.name}: {e}")
                logger.error(f"Manual sync failed for {integration.name}: {e}")

    parts = []
    if synced:
        parts.append(f'<span class="text-mcc-success">Synced: {", ".join(synced)}</span>')
    if failed:
        parts.append(f'<span class="text-red-400">Failed: {", ".join(failed)}</span>')
    if not parts:
        parts.append('<span class="text-mcc-muted">No integrations configured</span>')

    return HTMLResponse(
        f'<div class="text-sm py-2">{" | ".join(parts)}</div>',
        headers={"HX-Trigger": "integrationSynced"},
    )


@router.post("/add", response_class=HTMLResponse)
def add_channel(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    channel_type: str = Form(...),
    status: str = Form("planned"),
    automation_level: str = Form("manual"),
    notes: str = Form(""),
):
    project = db.query(Project).first()
    if not project:
        return HTMLResponse("<div class='text-red-400 text-sm'>No project found</div>")

    channel = Channel(
        project_id=project.id,
        name=name,
        channel_type=ChannelType(channel_type),
        status=ChannelStatus(status),
        automation_level=AutomationLevel(automation_level),
        notes=notes,
    )
    db.add(channel)
    db.commit()
    return HTMLResponse(
        '<div class="text-mcc-success text-sm py-2">Channel added!</div>',
        headers={"HX-Redirect": "/channels"},
    )


@router.post("/{channel_id}/quick-metric", response_class=HTMLResponse)
def quick_metric(
    channel_id: int,
    request: Request,
    db: Session = Depends(get_db),
    metric_name: str = Form(...),
    metric_value: float = Form(...),
):
    channel = db.get(Channel, channel_id)
    if not channel:
        return HTMLResponse("<span class='text-red-400 text-xs'>Channel not found</span>")

    prev = db.query(Metric).filter_by(
        channel_id=channel_id, metric_name=metric_name
    ).order_by(Metric.recorded_at.desc()).first()

    metric = Metric(
        channel_id=channel_id,
        metric_name=metric_name,
        metric_value=metric_value,
        previous_value=prev.metric_value if prev else None,
        unit="count",
        source="manual",
    )
    db.add(metric)
    db.commit()
    return HTMLResponse('<span class="text-mcc-success text-xs">Saved</span>')


@router.get("/{channel_id}")
def channel_detail(channel_id: int, request: Request, db: Session = Depends(get_db)):
    channel = db.get(Channel, channel_id)
    if not channel:
        return templates.TemplateResponse("partials/error.html", {
            "request": request, "message": "Channel not found"
        })

    project = db.get(Project, channel.project_id)

    metrics = db.query(Metric).filter_by(channel_id=channel_id).order_by(
        Metric.recorded_at.desc()
    ).limit(50).all()

    latest_metrics = {}
    for m in metrics:
        if m.metric_name not in latest_metrics:
            latest_metrics[m.metric_name] = m

    metric_history = {}
    for m in reversed(metrics):
        if m.metric_name not in metric_history:
            metric_history[m.metric_name] = {"labels": [], "values": []}
        metric_history[m.metric_name]["labels"].append(
            m.recorded_at.strftime("%b %d %H:%M") if m.recorded_at else ""
        )
        metric_history[m.metric_name]["values"].append(float(m.metric_value))

    tasks = db.query(Task).filter(
        Task.channel_id == channel_id,
        Task.status.notin_([TaskStatus.done, TaskStatus.archived]),
    ).order_by(Task.due_date).all()

    automations = db.query(Automation).filter_by(channel_id=channel_id).all()
    all_channels = db.query(Channel).filter_by(project_id=channel.project_id).all()

    return templates.TemplateResponse("channel_detail.html", {
        "request": request,
        "project": project,
        "channel": channel,
        "latest_metrics": latest_metrics,
        "metric_history": metric_history,
        "tasks": tasks,
        "automations": automations,
        "all_channels": all_channels,
        "current_page": "channels",
        "today": date.today(),
    })


@router.get("/{channel_id}/partial")
def channel_detail_partial(channel_id: int, request: Request, db: Session = Depends(get_db)):
    """HTMX partial: loads channel detail into the dashboard area."""
    channel = db.get(Channel, channel_id)
    if not channel:
        return templates.TemplateResponse("partials/error.html", {
            "request": request, "message": "Channel not found"
        })

    metrics = db.query(Metric).filter_by(channel_id=channel_id).order_by(
        Metric.recorded_at.desc()
    ).limit(50).all()

    latest_metrics = {}
    for m in metrics:
        if m.metric_name not in latest_metrics:
            latest_metrics[m.metric_name] = m

    metric_history = {}
    for m in reversed(metrics):
        if m.metric_name not in metric_history:
            metric_history[m.metric_name] = {"labels": [], "values": []}
        metric_history[m.metric_name]["labels"].append(
            m.recorded_at.strftime("%b %d %H:%M") if m.recorded_at else ""
        )
        metric_history[m.metric_name]["values"].append(float(m.metric_value))

    tasks = db.query(Task).filter(
        Task.channel_id == channel_id,
        Task.status.notin_([TaskStatus.done, TaskStatus.archived]),
    ).order_by(Task.due_date).all()

    automations = db.query(Automation).filter_by(channel_id=channel_id).all()

    return templates.TemplateResponse("partials/channel_detail.html", {
        "request": request,
        "channel": channel,
        "latest_metrics": latest_metrics,
        "metric_history": metric_history,
        "tasks": tasks,
        "automations": automations,
        "today": date.today(),
    })
