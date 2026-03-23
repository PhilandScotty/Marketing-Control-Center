import json
import os
import logging
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db, SessionLocal
from app.models import (
    Project, Channel, Task, Automation, EmailSequence, ContentPiece,
    OutreachContact, AIInsight, Metric, SubscriberSnapshot, MonthlyRevenue,
    AutonomousTool, AutonomousToolHealth, MorningBrief, ApprovalQueueItem,
    TaskStatus, TaskPriority, AutomationHealth, HealthStatus,
    ContentStatus, InsightSeverity, ContactStatus, ChannelStatus,
    SubscriberStage, QueueItemStatus, InsightType, InsightSourceType,
)
from app.ai.engine import simple_completion, is_configured as ai_configured

from app.routes.budget import _get_budget_summary

logger = logging.getLogger("mcc.dashboard")

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

LAUNCH_DATE = date(2026, 4, 1)


# ---------------------------------------------------------------------------
# Execution Score (used by other modules)
# ---------------------------------------------------------------------------

def calc_execution_score(db: Session, project_id: int) -> dict:
    today = date.today()

    # 1. Tasks on track (25%)
    overdue_tasks = db.query(Task).filter(
        Task.project_id == project_id,
        Task.due_date < today,
        Task.status.notin_([TaskStatus.done, TaskStatus.archived, TaskStatus.recurring]),
    ).all()
    overdue_count = 0
    critical_overdue = 0
    for t in overdue_tasks:
        overdue_count += 1
        if t.priority == TaskPriority.launch_critical:
            critical_overdue += 1
    tasks_score = max(0, 100 - (overdue_count * 5) - (critical_overdue * 10))

    # 2. Automations healthy (20%)
    all_autos = db.query(Automation).filter_by(project_id=project_id).all()
    stale_count = sum(1 for a in all_autos if a.health == AutomationHealth.stale)
    failed_count = sum(1 for a in all_autos if a.health == AutomationHealth.failed)
    auto_score = max(0, 100 - (stale_count * 15) - (failed_count * 25))

    # 3. Channels healthy (20%)
    all_channels = db.query(Channel).filter_by(project_id=project_id).all()
    warning_count = sum(1 for c in all_channels if c.health == HealthStatus.warning)
    critical_count = sum(1 for c in all_channels if c.health == HealthStatus.critical)
    channel_score = max(0, 100 - (warning_count * 10) - (critical_count * 20))

    # 4. Content pipeline (15%)
    week_start = today - timedelta(days=today.weekday())
    published_this_week = db.query(ContentPiece).filter(
        ContentPiece.project_id == project_id,
        ContentPiece.status == ContentStatus.published,
        ContentPiece.published_at >= datetime.combine(week_start, datetime.min.time()),
    ).count()
    weekly_target = 3
    content_score = min(100, int((published_this_week / weekly_target) * 100)) if weekly_target > 0 else 100

    # 5. Recurring tasks done (10%)
    recurring_tasks = db.query(Task).filter(
        Task.project_id == project_id,
        Task.status == TaskStatus.recurring,
    ).all()
    recurring_due = [t for t in recurring_tasks if t.recurring_next_due and t.recurring_next_due <= today]
    recurring_done = 0
    recurring_total = max(len(recurring_due), 1)
    recurring_score = int((recurring_done / recurring_total) * 100) if recurring_due else 100

    # 6. Outreach follow-ups (10%)
    overdue_followups = db.query(OutreachContact).filter(
        OutreachContact.project_id == project_id,
        OutreachContact.next_follow_up < today,
        OutreachContact.next_follow_up.isnot(None),
    ).count()
    outreach_score = max(0, 100 - (overdue_followups * 5))

    total = int(
        tasks_score * 0.25 +
        auto_score * 0.20 +
        channel_score * 0.20 +
        content_score * 0.15 +
        recurring_score * 0.10 +
        outreach_score * 0.10
    )

    if total >= 85:
        color = "success"
    elif total >= 70:
        color = "warning"
    else:
        color = "critical"

    return {
        "total": total,
        "color": color,
        "components": {
            "tasks": {"score": tasks_score, "weight": 25, "overdue": overdue_count, "critical_overdue": critical_overdue},
            "automations": {"score": auto_score, "weight": 20, "stale": stale_count, "failed": failed_count},
            "channels": {"score": channel_score, "weight": 20, "warning": warning_count, "critical": critical_count},
            "content": {"score": content_score, "weight": 15, "published": published_this_week, "target": weekly_target},
            "recurring": {"score": recurring_score, "weight": 10},
            "outreach": {"score": outreach_score, "weight": 10, "overdue": overdue_followups},
        }
    }


# ---------------------------------------------------------------------------
# Zone 1: Status Bar data
# ---------------------------------------------------------------------------

def _get_status_bar(db: Session, pid: int) -> dict:
    """5 key numbers for the status bar."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    # 1. Email subscribers — from Kit/ConvertKit metric or SubscriberSnapshot
    email_subs = 0
    # Try metrics first (from ConvertKit integration)
    email_channels = db.query(Channel).filter(
        Channel.project_id == pid,
        Channel.name.like("%Kit%") | Channel.name.like("%Email%") | Channel.name.like("%email%"),
    ).all()
    for ch in email_channels:
        m = db.query(Metric).filter(
            Metric.channel_id == ch.id,
            Metric.metric_name.like("%subscriber%"),
        ).order_by(Metric.recorded_at.desc()).first()
        if m:
            email_subs = max(email_subs, int(m.metric_value))
    # Fallback to SubscriberSnapshot (waitlist leads = pre-launch email list)
    if email_subs == 0:
        snap = db.query(SubscriberSnapshot).filter(
            SubscriberSnapshot.project_id == pid,
            SubscriberSnapshot.stage == SubscriberStage.waitlist_lead,
        ).order_by(SubscriberSnapshot.snapshot_date.desc()).first()
        if snap:
            email_subs = snap.count

    # 2. Content published this week (all platforms)
    content_this_week = db.query(ContentPiece).filter(
        ContentPiece.project_id == pid,
        ContentPiece.status == ContentStatus.published,
        ContentPiece.published_at >= datetime.combine(week_start, datetime.min.time()),
    ).count()

    # 3. Outreach pipeline
    outreach_total = db.query(OutreachContact).filter_by(project_id=pid).count()
    outreach_contacted = db.query(OutreachContact).filter(
        OutreachContact.project_id == pid,
        OutreachContact.status.in_([
            ContactStatus.contacted, ContactStatus.responded,
            ContactStatus.in_conversation, ContactStatus.active,
        ]),
    ).count()

    # 4. Days to launch
    days_to_launch = (LAUNCH_DATE - today).days

    # 5. Budget burn
    budget = _get_budget_summary(db, pid)

    return {
        "email_subs": email_subs,
        "content_this_week": content_this_week,
        "outreach_total": outreach_total,
        "outreach_contacted": outreach_contacted,
        "days_to_launch": days_to_launch,
        "budget_spent": budget.get("total_actual", 0),
        "budget_total": budget.get("total_budgeted", 0),
        "budget_pct": budget.get("pct_used", 0),
    }


# ---------------------------------------------------------------------------
# Zone 2: Needs Attention items
# ---------------------------------------------------------------------------

def _get_needs_attention(db: Session, pid: int) -> list[dict]:
    """Items that require action. Empty list = everything is fine."""
    items = []
    today = date.today()
    now = datetime.utcnow()

    # 1. Integration failures — consolidate by integration_key
    failed_channels = db.query(Channel).filter(
        Channel.project_id == pid,
        Channel.health.in_([HealthStatus.critical, HealthStatus.warning]),
        Channel.integration_key.isnot(None),
    ).all()
    # Group by integration_key to consolidate (e.g. 3 Buffer channels → 1 alert)
    by_integration = {}
    for ch in failed_channels:
        key = ch.integration_key
        by_integration.setdefault(key, []).append(ch)
    for integration_key, chs in by_integration.items():
        names = [c.name for c in chs]
        worst = "red" if any(c.health == HealthStatus.critical for c in chs) else "yellow"
        reason = chs[0].health_reason or "integration issue"
        # Strip channel-specific reason prefix, show integration-level message
        if len(names) > 1:
            text = f"{integration_key.title()} API disconnected — affecting {', '.join(names)}"
        else:
            text = f"{names[0]}: {reason}"
        items.append({
            "type": "integration",
            "severity": worst,
            "text": text,
            "action_label": "Reconnect",
            "action_url": "/channels",
        })

    # 2. Outreach follow-ups due today or overdue
    followups_due = db.query(OutreachContact).filter(
        OutreachContact.project_id == pid,
        OutreachContact.next_follow_up <= today,
        OutreachContact.next_follow_up.isnot(None),
    ).count()
    if followups_due > 0:
        items.append({
            "type": "outreach",
            "severity": "yellow",
            "text": f"{followups_due} outreach follow-up{'s' if followups_due != 1 else ''} due",
            "action_label": "Review",
            "action_url": "/pipelines/outreach",
        })

    # 3. Approval queue
    queue_count = db.query(ApprovalQueueItem).filter_by(
        project_id=pid, status=QueueItemStatus.pending,
    ).count()
    if queue_count > 0:
        items.append({
            "type": "queue",
            "severity": "yellow",
            "text": f"{queue_count} draft{'s' if queue_count != 1 else ''} waiting for review",
            "action_label": "Review",
            "action_url": "/queue",
        })

    # 4. Content gaps — no content scheduled after a certain point
    latest_scheduled = db.query(ContentPiece).filter(
        ContentPiece.project_id == pid,
        ContentPiece.status == ContentStatus.scheduled,
    ).order_by(ContentPiece.published_at.desc()).first()
    if latest_scheduled and latest_scheduled.published_at:
        last_date = latest_scheduled.published_at.date() if isinstance(latest_scheduled.published_at, datetime) else latest_scheduled.published_at
        if last_date <= today + timedelta(days=3):
            day_name = last_date.strftime("%A")
            items.append({
                "type": "content",
                "severity": "yellow",
                "text": f"No posts scheduled after {day_name}",
                "action_label": "Schedule",
                "action_url": "/pipelines/content",
            })
    elif not latest_scheduled:
        # No scheduled content at all
        items.append({
            "type": "content",
            "severity": "yellow",
            "text": "No content currently scheduled",
            "action_label": "Schedule",
            "action_url": "/pipelines/content",
        })

    # 5. Overdue tasks (>1 day, excluding recurring)
    overdue_tasks = db.query(Task).filter(
        Task.project_id == pid,
        Task.due_date < today - timedelta(days=1),
        Task.status.notin_([TaskStatus.done, TaskStatus.archived, TaskStatus.recurring]),
    ).order_by(Task.due_date).limit(5).all()
    for task in overdue_tasks:
        days_late = (today - task.due_date).days
        items.append({
            "type": "task",
            "severity": "red" if task.priority == TaskPriority.launch_critical else "yellow",
            "text": f"Overdue {days_late}d: {task.title}",
            "action_label": "View",
            "action_url": "/tasks",
        })

    # 6. Stale/failed automations
    stale_autos = db.query(Automation).filter(
        Automation.project_id == pid,
        Automation.health.in_([AutomationHealth.stale, AutomationHealth.failed]),
    ).all()
    for auto in stale_autos:
        items.append({
            "type": "automation",
            "severity": "red" if auto.health == AutomationHealth.failed else "yellow",
            "text": f"Automation {auto.health.value}: {auto.name} ({auto.platform})",
            "action_label": "Check",
            "action_url": "/tasks",
        })

    return items


# ---------------------------------------------------------------------------
# Zone 3: Context widgets
# ---------------------------------------------------------------------------

def _get_growth_data(db: Session, pid: int) -> dict:
    """Column 1: Growth metrics."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    prev_week_start = week_start - timedelta(days=7)

    # Subscriber trend (last 30 days snapshots)
    thirty_days_ago = today - timedelta(days=30)
    snapshots = db.query(SubscriberSnapshot).filter(
        SubscriberSnapshot.project_id == pid,
        SubscriberSnapshot.stage == SubscriberStage.waitlist_lead,
        SubscriberSnapshot.snapshot_date >= thirty_days_ago,
    ).order_by(SubscriberSnapshot.snapshot_date).all()
    trend_data = [{"date": s.snapshot_date.isoformat(), "count": s.count} for s in snapshots]

    # Week comparisons
    # Email subscribers this week vs last week
    email_channels = db.query(Channel).filter(
        Channel.project_id == pid,
        Channel.name.like("%Kit%") | Channel.name.like("%Email%"),
    ).all()
    subs_this_week = 0
    subs_last_week = 0
    for ch in email_channels:
        m_this = db.query(Metric).filter(
            Metric.channel_id == ch.id,
            Metric.metric_name.like("%subscriber%"),
            Metric.recorded_at >= datetime.combine(week_start, datetime.min.time()),
        ).order_by(Metric.recorded_at.desc()).first()
        m_last = db.query(Metric).filter(
            Metric.channel_id == ch.id,
            Metric.metric_name.like("%subscriber%"),
            Metric.recorded_at >= datetime.combine(prev_week_start, datetime.min.time()),
            Metric.recorded_at < datetime.combine(week_start, datetime.min.time()),
        ).order_by(Metric.recorded_at.desc()).first()
        if m_this:
            subs_this_week = max(subs_this_week, int(m_this.metric_value))
        if m_last:
            subs_last_week = max(subs_last_week, int(m_last.metric_value))

    # Days to launch + growth rate projection
    days_to_launch = (LAUNCH_DATE - today).days
    growth_rate = 0
    if subs_last_week > 0 and subs_this_week > subs_last_week:
        weekly_growth = subs_this_week - subs_last_week
        growth_rate = weekly_growth
        weeks_to_launch = max(days_to_launch / 7, 1)
        projected_at_launch = subs_this_week + int(weekly_growth * weeks_to_launch)
    elif subs_this_week > 0 and subs_last_week == 0:
        # First week of data — can't project yet
        growth_rate = subs_this_week
        projected_at_launch = None
    else:
        projected_at_launch = None  # No growth data or flat — don't show a fake projection

    return {
        "trend_data": trend_data,
        "subs_this_week": subs_this_week,
        "subs_last_week": subs_last_week,
        "weekly_growth": growth_rate,
        "projected_at_launch": projected_at_launch,
    }


def _get_content_channels(db: Session, pid: int) -> dict:
    """Column 2: Content & Channels."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    now = datetime.utcnow()

    # Published this week by platform
    published = db.query(ContentPiece).filter(
        ContentPiece.project_id == pid,
        ContentPiece.status == ContentStatus.published,
        ContentPiece.published_at >= datetime.combine(week_start, datetime.min.time()),
    ).all()

    by_platform = {}
    for p in published:
        targets = p.platform_target or []
        if isinstance(targets, str):
            targets = [targets]
        for t in targets:
            label = t.replace("_", " ").title()
            by_platform[label] = by_platform.get(label, 0) + 1
    if not by_platform and published:
        by_platform["All"] = len(published)

    # Buffer queue depth
    buffer_queue = db.query(Metric).filter(
        Metric.metric_name == "buffer_total_queued",
    ).order_by(Metric.recorded_at.desc()).first()
    queue_posts = int(buffer_queue.metric_value) if buffer_queue else 0
    # Estimate days of content: assume 1-2 posts/day
    queue_days = round(queue_posts / 2, 1) if queue_posts > 0 else 0

    # Channel status (compact list with health dots)
    channels = db.query(Channel).filter_by(
        project_id=pid, status=ChannelStatus.live,
    ).order_by(Channel.name).all()

    channel_list = []
    for ch in channels:
        latest = db.query(Metric).filter_by(channel_id=ch.id).order_by(
            Metric.recorded_at.desc()
        ).first()

        if latest:
            days_since = (now - latest.recorded_at).days
        else:
            days_since = None  # No data ever

        # Fix the 990d bug: cap display and use meaningful labels
        if ch.health in (HealthStatus.critical, HealthStatus.warning) and ch.integration_key:
            status_label = "disconnected"
            dot = "critical"
        elif days_since is None:
            status_label = "no data"
            dot = "unknown"
        elif days_since > 90:
            status_label = "disconnected"
            dot = "critical"
        elif days_since > 14:
            status_label = f"{days_since}d stale"
            dot = "warning"
        else:
            status_label = f"{days_since}d ago" if days_since > 0 else "today"
            dot = "healthy"

        channel_list.append({
            "name": ch.name,
            "dot": dot,
            "status_label": status_label,
        })

    return {
        "by_platform": by_platform,
        "total_published": len(published),
        "queue_posts": queue_posts,
        "queue_days": queue_days,
        "channels": channel_list,
    }


def _get_outreach_budget(db: Session, pid: int) -> dict:
    """Column 3: Outreach & Budget."""
    today = date.today()

    # Pipeline funnel stages
    funnel_stages = [
        ("Identified", [ContactStatus.identified]),
        ("Contacted", [ContactStatus.contacted]),
        ("Responded", [ContactStatus.responded, ContactStatus.in_conversation]),
        ("Active", [ContactStatus.active]),
    ]
    funnel = []
    funnel_total = 0
    for label, statuses in funnel_stages:
        count = db.query(OutreachContact).filter(
            OutreachContact.project_id == pid,
            OutreachContact.status.in_(statuses),
        ).count()
        funnel.append({"label": label, "count": count})
        funnel_total += count

    # Calculate funnel bar widths
    max_count = max((f["count"] for f in funnel), default=1) or 1
    for f in funnel:
        f["pct"] = round(f["count"] / max_count * 100) if f["count"] > 0 else 0

    # Budget
    budget = _get_budget_summary(db, pid)

    # Next milestone
    days_to_launch = (LAUNCH_DATE - today).days
    if days_to_launch > 0:
        next_milestone = f"Launch: {LAUNCH_DATE.strftime('%b %d')} ({days_to_launch}d)"
    else:
        next_milestone = "Post-launch"

    return {
        "funnel": funnel,
        "funnel_total": funnel_total,
        "budget_spent": budget.get("total_actual", 0),
        "budget_total": budget.get("total_budgeted", 0),
        "budget_pct": budget.get("pct_used", 0),
        "daily_burn": budget.get("daily_burn", 0),
        "next_milestone": next_milestone,
    }


# ---------------------------------------------------------------------------
# Morning Brief (unchanged)
# ---------------------------------------------------------------------------

MORNING_BRIEF_SYSTEM = """You are the AI strategist for Grindlab's marketing operations.
Generate a concise morning briefing for Phil based on the data snapshot provided.
Return ONLY valid JSON with this structure:
{
  "priorities": [
    {"title": "Priority title", "body": "1-2 sentence explanation with specific numbers", "urgency": "high|medium|low"},
    {"title": "Priority title", "body": "1-2 sentence explanation with specific numbers", "urgency": "high|medium|low"},
    {"title": "Priority title", "body": "1-2 sentence explanation with specific numbers", "urgency": "high|medium|low"}
  ]
}
Rules:
- Exactly 3 priorities, ranked by importance
- Lead with the single most urgent or impactful item
- Reference specific numbers (overdue tasks, metric changes, budget status)
- Be actionable — say what to do, not just what's happening
- Keep each body under 40 words"""


def _build_brief_snapshot(db: Session, pid: int) -> dict:
    """Build data snapshot for morning brief AI prompt."""
    today = date.today()

    # Overdue tasks
    overdue = db.query(Task).filter(
        Task.project_id == pid,
        Task.due_date < today,
        Task.status.notin_([TaskStatus.done, TaskStatus.archived, TaskStatus.recurring]),
    ).all()
    overdue_titles = [f"{t.title} ({(today - t.due_date).days}d late)" for t in overdue[:5]]

    # Due today
    due_today = db.query(Task).filter(
        Task.project_id == pid,
        Task.due_date == today,
        Task.status.notin_([TaskStatus.done, TaskStatus.archived]),
    ).all()

    # Stale automations
    stale = db.query(Automation).filter(
        Automation.project_id == pid,
        Automation.health.in_([AutomationHealth.stale, AutomationHealth.failed]),
    ).all()

    # Critical channels
    crit_channels = db.query(Channel).filter(
        Channel.project_id == pid,
        Channel.health.in_([HealthStatus.critical, HealthStatus.warning]),
    ).all()

    # Follow-ups due
    followups = db.query(OutreachContact).filter(
        OutreachContact.project_id == pid,
        OutreachContact.next_follow_up <= today,
        OutreachContact.next_follow_up.isnot(None),
    ).count()

    # Content this week
    week_start = today - timedelta(days=today.weekday())
    published = db.query(ContentPiece).filter(
        ContentPiece.project_id == pid,
        ContentPiece.status == ContentStatus.published,
        ContentPiece.published_at >= datetime.combine(week_start, datetime.min.time()),
    ).count()

    # Budget
    budget = _get_budget_summary(db, pid)

    # Unresolved AI insights
    unresolved = db.query(AIInsight).filter(
        AIInsight.project_id == pid,
        AIInsight.acknowledged == False,
    ).count()

    return {
        "date": today.isoformat(),
        "day_of_week": today.strftime("%A"),
        "overdue_tasks": overdue_titles,
        "due_today": [t.title for t in due_today],
        "stale_automations": [a.name for a in stale],
        "critical_channels": [c.name for c in crit_channels],
        "followups_due": followups,
        "content_published_this_week": published,
        "content_target": 3,
        "budget_pct_used": budget.get("pct_used", 0),
        "budget_daily_burn": budget.get("daily_burn", 0),
        "over_budget_items": len(budget.get("over_budget_items", [])),
        "unresolved_insights": unresolved,
    }


async def generate_morning_brief(db: Session, pid: int) -> dict | None:
    """Generate morning brief using AI."""
    if not ai_configured():
        return None

    snapshot = _build_brief_snapshot(db, pid)
    prompt = f"Today is {snapshot['day_of_week']}, {snapshot['date']}.\n\nData snapshot:\n{json.dumps(snapshot, indent=2)}\n\nGenerate the morning brief."

    try:
        response = await simple_completion(prompt, system_override=MORNING_BRIEF_SYSTEM)
        if not response:
            return None

        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            text = text.rsplit("```", 1)[0]
        data = json.loads(text)

        brief = MorningBrief(
            project_id=pid,
            brief_date=date.today(),
            priorities=data.get("priorities", []),
            snapshot=snapshot,
            raw_response=response,
        )
        db.add(brief)
        db.commit()

        return {
            "date": brief.brief_date,
            "priorities": brief.priorities,
            "created_at": brief.created_at,
            "is_today": True,
        }
    except Exception as e:
        logger.error(f"Morning brief generation failed: {e}")
        return None


def _get_morning_brief(db: Session, pid: int) -> dict | None:
    """Get today's morning brief if it exists."""
    today = date.today()
    brief = db.query(MorningBrief).filter_by(
        project_id=pid, brief_date=today
    ).order_by(MorningBrief.created_at.desc()).first()

    if not brief:
        yesterday = today - timedelta(days=1)
        brief = db.query(MorningBrief).filter_by(
            project_id=pid, brief_date=yesterday
        ).order_by(MorningBrief.created_at.desc()).first()

    if brief:
        return {
            "date": brief.brief_date,
            "priorities": brief.priorities or [],
            "created_at": brief.created_at,
            "is_today": brief.brief_date == today,
        }
    return None


# ---------------------------------------------------------------------------
# Main Dashboard Route
# ---------------------------------------------------------------------------

@router.get("/")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("dashboard.html", {
            "request": request, "project": None,
            "current_page": "dashboard", "today": date.today(),
        })

    pid = project.id

    # Re-surface expired snoozes
    now = datetime.utcnow()
    expired_snoozes = db.query(AIInsight).filter(
        AIInsight.project_id == pid,
        AIInsight.acknowledged == True,
        AIInsight.snoozed_until.isnot(None),
        AIInsight.snoozed_until <= now,
        AIInsight.resolved_at.is_(None),
    ).all()
    for ins in expired_snoozes:
        ins.acknowledged = False
        ins.snoozed_until = None
    if expired_snoozes:
        db.commit()

    # Zone 1: Status bar
    status_bar = _get_status_bar(db, pid)

    # Zone 2: Needs attention
    attention_items = _get_needs_attention(db, pid)

    # Zone 3: Context
    growth = _get_growth_data(db, pid)
    content_channels = _get_content_channels(db, pid)
    outreach_budget = _get_outreach_budget(db, pid)

    # Channels list for metric form
    channels = db.query(Channel).filter_by(project_id=pid).order_by(Channel.name).all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "project": project,
        "status_bar": status_bar,
        "attention_items": attention_items,
        "growth": growth,
        "content_channels": content_channels,
        "outreach_budget": outreach_budget,
        "channels": channels,
        "current_page": "dashboard",
        "today": date.today(),
    })


# ---------------------------------------------------------------------------
# Morning Brief HTMX endpoints
# ---------------------------------------------------------------------------

@router.post("/morning-brief/generate", response_class=HTMLResponse)
async def generate_brief_endpoint(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse('<div class="text-mcc-critical text-xs">Project not found</div>')

    brief = await generate_morning_brief(db, project.id)
    if not brief:
        return HTMLResponse('<div class="text-mcc-critical text-xs">AI not configured or generation failed</div>')

    html = _render_brief_html(brief)
    return HTMLResponse(html)


def _render_brief_html(brief: dict) -> str:
    urgency_colors = {
        "high": ("mcc-critical", "mcc-critical/15"),
        "medium": ("mcc-warning", "mcc-warning/15"),
        "low": ("mcc-accent", "mcc-accent/15"),
    }
    items_html = ""
    for i, p in enumerate(brief.get("priorities", []), 1):
        urgency = p.get("urgency", "medium")
        text_color, bg_color = urgency_colors.get(urgency, ("mcc-accent", "mcc-accent/15"))
        items_html += f'''
        <div class="flex items-start gap-3 p-3 rounded-lg bg-{bg_color} border border-{text_color}/20">
            <span class="flex-shrink-0 w-6 h-6 rounded-full bg-{text_color}/20 text-{text_color} flex items-center justify-center text-xs font-bold">{i}</span>
            <div class="flex-1 min-w-0">
                <div class="text-sm font-semibold text-mcc-text">{p.get("title", "")}</div>
                <div class="text-xs text-mcc-muted mt-0.5">{p.get("body", "")}</div>
            </div>
            <span class="text-[9px] uppercase font-semibold text-{text_color} flex-shrink-0">{urgency}</span>
        </div>'''

    date_label = brief["date"].strftime("%B %d, %Y") if hasattr(brief["date"], "strftime") else str(brief["date"])
    stale_note = "" if brief.get("is_today") else ' <span class="text-[10px] text-mcc-warning">(yesterday)</span>'

    return f'''
    <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2">
            <svg class="w-5 h-5 text-mcc-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>
            <h3 class="text-sm font-semibold tracking-tight">Morning Brief</h3>
            {stale_note}
        </div>
        <span class="text-[10px] text-mcc-dim">{date_label}</span>
    </div>
    <div class="space-y-2">
        {items_html}
    </div>'''


# ---------------------------------------------------------------------------
# Manual Metric Recording endpoint
# ---------------------------------------------------------------------------

@router.post("/metrics/record", response_class=HTMLResponse)
async def record_metric(
    request: Request,
    db: Session = Depends(get_db),
):
    form = await request.form()
    channel_id = int(form.get("channel_id", 0))
    metric_name = form.get("metric_name", "")
    metric_value = float(form.get("metric_value", 0))
    unit = form.get("unit", "count")

    if not channel_id or not metric_name:
        return HTMLResponse('<span class="text-xs text-mcc-critical">Missing fields</span>')

    from app.models import Metric, MetricSource
    prev = db.query(Metric).filter_by(
        channel_id=channel_id, metric_name=metric_name,
    ).order_by(Metric.recorded_at.desc()).first()

    m = Metric(
        channel_id=channel_id,
        metric_name=metric_name,
        metric_value=metric_value,
        previous_value=prev.metric_value if prev else None,
        unit=unit,
        source=MetricSource.manual,
    )
    db.add(m)
    db.commit()
    return HTMLResponse('<span class="text-xs text-mcc-success">Saved</span>')


# ---------------------------------------------------------------------------
# Scheduler job for morning brief
# ---------------------------------------------------------------------------

def run_morning_brief():
    """Daily morning brief generation job."""
    import asyncio
    db = SessionLocal()
    try:
        project = db.query(Project).filter_by(slug="grindlab").first()
        if not project:
            return

        today = date.today()
        existing = db.query(MorningBrief).filter_by(
            project_id=project.id, brief_date=today
        ).first()
        if existing:
            logger.info("Morning brief already generated today")
            return

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(asyncio.run, generate_morning_brief(db, project.id)).result()
            else:
                loop.run_until_complete(generate_morning_brief(db, project.id))
        except RuntimeError:
            asyncio.run(generate_morning_brief(db, project.id))

        logger.info("Morning brief generated")
    except Exception as e:
        logger.error(f"Morning brief job failed: {e}")
    finally:
        db.close()


def _sync_wrap(fn):
    def wrapper():
        try:
            fn()
        except Exception as e:
            logger.error(f"Dashboard job {fn.__name__} failed: {e}")
    return wrapper


morning_brief_job = _sync_wrap(run_morning_brief)
