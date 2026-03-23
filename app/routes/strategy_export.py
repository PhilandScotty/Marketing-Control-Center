"""Strategy Export — generates a comprehensive markdown report for Claude AI strategy sessions."""
import logging
import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db, SessionLocal
from app.models import (
    Project, Channel, Task, Automation, EmailSequence, ContentPiece,
    OutreachContact, AIInsight, Metric, MetricSnapshot, SubscriberSnapshot,
    AdCampaign, Tool, BudgetAllocation, BudgetExpense, LeadScore,
    TaskStatus, TaskPriority, AutomationHealth, HealthStatus,
    ContentStatus, ChannelStatus, AdStatus, SubscriberStage,
    BudgetCategory, LeadTier, ContactStatus,
)
from app.routes.dashboard import calc_execution_score

logger = logging.getLogger("mcc.routes.strategy_export")

router = APIRouter(prefix="/strategy-export")
templates = Jinja2Templates(directory="app/templates")

EXPORT_PATH = os.path.expanduser("~/clawd/projects/grindlab/MCC-STRATEGY-EXPORT.md")


def generate_strategy_markdown(db: Session) -> str | None:
    """Build the full strategy export markdown."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return None

    pid = project.id
    today = date.today()
    now = datetime.utcnow()
    days_to_launch = (project.launch_date - today).days if project.launch_date else "N/A"

    lines = []

    # --- Header ---
    lines.append(f"# {project.name} — Strategy Export")
    lines.append(f"**Date:** {today.strftime('%B %d, %Y')} | **Launch:** T-{days_to_launch} days")
    lines.append(f"*Paste this into your Claude strategy session for deep analysis.*")
    lines.append("")

    # === EXECUTION STATUS ===
    exec_score = calc_execution_score(db, pid)
    lines.append("## EXECUTION STATUS")
    lines.append("")
    lines.append(f"**Score: {exec_score['total']}/100** ({exec_score['color'].upper()})")
    lines.append("")
    lines.append("| Component | Score | Notes |")
    lines.append("|-----------|-------|-------|")
    for key, comp in exec_score["components"].items():
        notes = []
        if key == "tasks":
            if comp.get("overdue"):
                notes.append(f"{comp['overdue']} overdue")
            if comp.get("critical_overdue"):
                notes.append(f"{comp['critical_overdue']} launch-critical overdue")
        elif key == "automations":
            if comp.get("stale"):
                notes.append(f"{comp['stale']} stale")
            if comp.get("failed"):
                notes.append(f"{comp['failed']} failed")
        elif key == "channels":
            if comp.get("warning"):
                notes.append(f"{comp['warning']} warning")
            if comp.get("critical"):
                notes.append(f"{comp['critical']} critical")
        elif key == "content":
            notes.append(f"{comp.get('published', 0)}/{comp.get('target', 3)} this week")
        elif key == "outreach":
            if comp.get("overdue"):
                notes.append(f"{comp['overdue']} overdue follow-ups")
        lines.append(f"| {key.title()} ({comp['weight']}%) | {comp['score']} | {', '.join(notes) if notes else 'OK'} |")
    lines.append("")

    # Task breakdown
    tasks = db.query(Task).filter_by(project_id=pid).all()
    status_counts = {}
    for t in tasks:
        s = t.status.value
        status_counts[s] = status_counts.get(s, 0) + 1

    overdue = [t for t in tasks if t.due_date and t.due_date < today
               and t.status not in (TaskStatus.done, TaskStatus.archived, TaskStatus.recurring)]
    launch_critical = [t for t in tasks if t.priority == TaskPriority.launch_critical
                       and t.status not in (TaskStatus.done, TaskStatus.archived)]

    lines.append(f"**Tasks:** {len(tasks)} total | " + " | ".join(
        f"{s.replace('_', ' ').title()}: {c}" for s, c in sorted(status_counts.items())
    ))
    lines.append(f"**Overdue:** {len(overdue)} | **Launch-critical open:** {len(launch_critical)}")
    if overdue:
        lines.append("")
        for t in sorted(overdue, key=lambda x: x.due_date)[:8]:
            days_late = (today - t.due_date).days
            lines.append(f"- {t.title} — {days_late}d overdue ({t.priority.value})")
    lines.append("")

    # === CHANNEL PERFORMANCE ===
    lines.append("## CHANNEL PERFORMANCE")
    lines.append("")
    channels = db.query(Channel).filter_by(project_id=pid).all()

    for ch in channels:
        lines.append(f"### {ch.name}")
        lines.append(f"Status: {ch.status.value} | Health: {ch.health.value if ch.health else 'unknown'} | Automation: {ch.automation_level.value}")
        if ch.health_reason:
            lines.append(f"Health reason: {ch.health_reason}")

        # Get metrics with 7-day and 30-day comparisons
        cutoff_7d = now - timedelta(days=7)
        cutoff_30d = now - timedelta(days=30)

        recent_metrics = db.query(Metric).filter(
            Metric.channel_id == ch.id,
        ).order_by(Metric.recorded_at.desc()).all()

        # Group by metric name, get latest + previous
        seen = {}
        for m in recent_metrics:
            if m.metric_name not in seen:
                seen[m.metric_name] = {"latest": m, "prev_7d": None, "prev_30d": None}
            elif seen[m.metric_name]["prev_7d"] is None and m.recorded_at < cutoff_7d:
                seen[m.metric_name]["prev_7d"] = m
            elif seen[m.metric_name]["prev_30d"] is None and m.recorded_at < cutoff_30d:
                seen[m.metric_name]["prev_30d"] = m

        if seen:
            lines.append("")
            lines.append("| Metric | Current | 7d Change | 30d Change | Trend |")
            lines.append("|--------|---------|-----------|------------|-------|")
            for name, data in seen.items():
                current = float(data["latest"].metric_value)
                unit = data["latest"].unit or ""

                delta_7d = ""
                delta_30d = ""
                trend = "—"

                prev = data["latest"].previous_value
                if prev is not None:
                    d = current - float(prev)
                    delta_7d = f"+{d:.0f}" if d > 0 else f"{d:.0f}"
                    trend = "up" if d > 0 else ("down" if d < 0 else "flat")
                elif data["prev_7d"]:
                    d = current - float(data["prev_7d"].metric_value)
                    delta_7d = f"+{d:.0f}" if d > 0 else f"{d:.0f}"
                    trend = "up" if d > 0 else ("down" if d < 0 else "flat")

                if data["prev_30d"]:
                    d = current - float(data["prev_30d"].metric_value)
                    delta_30d = f"+{d:.0f}" if d > 0 else f"{d:.0f}"

                if unit == "percent":
                    fmt_val = f"{current:.1f}%"
                elif unit == "dollars":
                    fmt_val = f"${current:.2f}"
                elif unit == "rate":
                    fmt_val = f"{current:.2f}"
                else:
                    fmt_val = f"{current:.0f}"
                lines.append(f"| {name.replace('_', ' ').title()} | {fmt_val} | {delta_7d} | {delta_30d} | {trend} |")
        lines.append("")

    # === AD PERFORMANCE ===
    campaigns = db.query(AdCampaign).filter_by(project_id=pid).all()
    if campaigns:
        lines.append("## AD PERFORMANCE")
        lines.append("")
        total_spend = sum(float(c.spend_to_date or 0) for c in campaigns)
        total_conversions = sum(c.conversions or 0 for c in campaigns)
        lines.append(f"**Total spend:** ${total_spend:.2f} | **Total conversions:** {total_conversions}")
        lines.append("")
        lines.append("| Campaign | Platform | Status | Signal | Spend | Impr | Clicks | CTR | Conv | CPL |")
        lines.append("|----------|----------|--------|--------|-------|------|--------|-----|------|-----|")
        for c in campaigns:
            ctr = f"{float(c.ctr):.1f}%" if c.ctr else "—"
            cpl = f"${float(c.cpl):.2f}" if c.cpl else "—"
            lines.append(
                f"| {c.campaign_name} | {c.platform.value} | {c.status.value} | "
                f"{c.signal.value if c.signal else 'hold'} | ${float(c.spend_to_date or 0):.2f} | "
                f"{c.impressions or 0} | {c.clicks or 0} | {ctr} | {c.conversions or 0} | {cpl} |"
            )
        lines.append("")

    # === CONTENT PIPELINE ===
    lines.append("## CONTENT PIPELINE")
    lines.append("")
    content = db.query(ContentPiece).filter_by(project_id=pid).all()
    content_by_status = {}
    for p in content:
        s = p.status.value
        content_by_status[s] = content_by_status.get(s, 0) + 1

    lines.append("**By status:** " + " | ".join(
        f"{s.replace('_', ' ').title()}: {c}" for s, c in sorted(content_by_status.items())
    ))

    # Publishing velocity
    week_start = today - timedelta(days=today.weekday())
    month_ago = today - timedelta(days=30)
    published_this_week = sum(1 for p in content if p.status == ContentStatus.published
                              and p.published_at and p.published_at.date() >= week_start)
    published_this_month = sum(1 for p in content if p.status == ContentStatus.published
                               and p.published_at and p.published_at.date() >= month_ago)
    weeks_in_month = max(1, (today - month_ago).days / 7)
    velocity = published_this_month / weeks_in_month

    lines.append(f"**Publishing velocity:** {velocity:.1f} pieces/week ({published_this_week} this week, {published_this_month} last 30d)")
    lines.append("")

    # === OUTREACH PIPELINE ===
    contacts = db.query(OutreachContact).filter_by(project_id=pid).all()
    if contacts:
        lines.append("## OUTREACH PIPELINE")
        lines.append("")
        stage_counts = {}
        for c in contacts:
            s = c.status.value
            stage_counts[s] = stage_counts.get(s, 0) + 1

        lines.append("**By stage:** " + " | ".join(
            f"{s.replace('_', ' ').title()}: {c}" for s, c in sorted(stage_counts.items())
        ))

        overdue_followups = [c for c in contacts if c.next_follow_up and c.next_follow_up < today]
        if overdue_followups:
            lines.append(f"**Overdue follow-ups:** {len(overdue_followups)}")
            for c in overdue_followups[:5]:
                days = (today - c.next_follow_up).days
                lines.append(f"- {c.name} ({c.platform}) — {days}d overdue, stage: {c.status.value}")

        # Conversion rates
        total = len(contacts)
        contacted = sum(1 for c in contacts if c.status.value not in ('identified',))
        responded = sum(1 for c in contacts if c.status.value in ('responded', 'in_conversation', 'committed', 'active'))
        committed = sum(1 for c in contacts if c.status.value in ('committed', 'active'))
        if total > 0:
            lines.append(f"**Funnel:** {total} identified → {contacted} contacted ({contacted*100//total}%) → {responded} responded ({responded*100//max(contacted,1)}%) → {committed} committed ({committed*100//max(responded,1)}%)")
        lines.append("")

    # === SUBSCRIBER FUNNEL ===
    lines.append("## SUBSCRIBER FUNNEL")
    lines.append("")
    latest_date = db.query(func.max(SubscriberSnapshot.snapshot_date)).filter_by(project_id=pid).scalar()
    if latest_date:
        snapshots = db.query(SubscriberSnapshot).filter_by(
            project_id=pid, snapshot_date=latest_date
        ).all()

        total_subs = sum(s.count for s in snapshots)
        total_mrr = sum(float(s.mrr or 0) for s in snapshots)
        lines.append(f"**Total subscribers:** {total_subs} | **MRR:** ${total_mrr:.2f}")
        lines.append("")
        for s in snapshots:
            lines.append(f"- {s.stage.value.replace('_', ' ').title()}: {s.count}" +
                         (f" (${float(s.mrr):.2f} MRR)" if s.mrr and float(s.mrr) > 0 else ""))
    else:
        lines.append("No subscriber data yet.")
    lines.append("")

    # Lead score distribution
    leads = db.query(LeadScore).filter_by(project_id=pid).all()
    if leads:
        tier_counts = {}
        for l in leads:
            t = l.tier.value
            tier_counts[t] = tier_counts.get(t, 0) + 1
        lines.append("**Lead scores:** " + " | ".join(
            f"{t.title()}: {c}" for t, c in sorted(tier_counts.items())
        ))
        lines.append("")

    # === EMAIL PERFORMANCE ===
    sequences = db.query(EmailSequence).filter_by(project_id=pid).all()
    if sequences:
        lines.append("## EMAIL PERFORMANCE")
        lines.append("")
        lines.append("| Sequence | Status | Emails | Open Rate | Click Rate | Active Subs |")
        lines.append("|----------|--------|--------|-----------|------------|-------------|")
        for s in sequences:
            open_r = f"{float(s.open_rate):.1f}%" if s.open_rate else "—"
            click_r = f"{float(s.click_rate):.1f}%" if s.click_rate else "—"
            lines.append(f"| {s.name} | {s.status.value} | {s.email_count} | {open_r} | {click_r} | {s.subscribers_active or '—'} |")
        lines.append("")

    # === AUTOMATION HEALTH ===
    automations = db.query(Automation).filter_by(project_id=pid).all()
    lines.append("## AUTOMATION HEALTH")
    lines.append("")
    healthy = sum(1 for a in automations if a.health == AutomationHealth.running)
    stale = [a for a in automations if a.health == AutomationHealth.stale]
    failed = [a for a in automations if a.health == AutomationHealth.failed]
    lines.append(f"**{len(automations)} total** — {healthy} running, {len(stale)} stale, {len(failed)} failed")
    if stale or failed:
        lines.append("")
        for a in stale + failed:
            lines.append(f"- **{a.name}** ({a.platform}) — {a.health.value}" +
                         (f", last run: {a.last_confirmed_run.strftime('%b %d')}" if a.last_confirmed_run else ""))
    lines.append("")

    # === BUDGET ===
    allocations = db.query(BudgetAllocation).filter_by(project_id=pid).all()
    expenses = db.query(BudgetExpense).filter_by(project_id=pid).all()
    if allocations or expenses:
        lines.append("## BUDGET")
        lines.append("")

        # Group by category
        planned_by_cat = {}
        for a in allocations:
            cat = a.category.value
            planned_by_cat[cat] = planned_by_cat.get(cat, 0) + float(a.planned_monthly)

        # Current month expenses
        month_start = today.replace(day=1)
        month_expenses = [e for e in expenses if e.expense_date >= month_start]
        spent_by_cat = {}
        for e in month_expenses:
            cat = e.category.value
            spent_by_cat[cat] = spent_by_cat.get(cat, 0) + float(e.amount)

        all_cats = sorted(set(list(planned_by_cat.keys()) + list(spent_by_cat.keys())))
        if all_cats:
            total_planned = sum(planned_by_cat.values())
            total_spent = sum(spent_by_cat.values())
            lines.append(f"**Monthly budget:** ${total_planned:.2f} | **Spent this month:** ${total_spent:.2f} ({total_spent*100/max(total_planned,1):.0f}%)")
            lines.append("")
            lines.append("| Category | Planned | Spent | % Used |")
            lines.append("|----------|---------|-------|--------|")
            for cat in all_cats:
                planned = planned_by_cat.get(cat, 0)
                spent = spent_by_cat.get(cat, 0)
                pct = f"{spent*100/planned:.0f}%" if planned > 0 else "—"
                lines.append(f"| {cat.replace('_', ' ').title()} | ${planned:.2f} | ${spent:.2f} | {pct} |")
        lines.append("")

    # === AI INSIGHTS ===
    insights = db.query(AIInsight).filter(
        AIInsight.project_id == pid,
        AIInsight.acknowledged == False,
    ).order_by(AIInsight.created_at.desc()).limit(15).all()
    if insights:
        lines.append("## AI INSIGHTS (Unacknowledged)")
        lines.append("")
        for i in insights:
            lines.append(f"- **[{i.severity.value.upper()}]** {i.title}")
            if i.body:
                preview = i.body[:200].replace("\n", " ").strip()
                lines.append(f"  {preview}")
        lines.append("")

    # === OPEN QUESTIONS ===
    lines.append("## OPEN QUESTIONS / BLOCKERS")
    lines.append("")
    blocked_tasks = [t for t in tasks if t.status == TaskStatus.blocked]
    problem_channels = [c for c in channels if c.health in (HealthStatus.warning, HealthStatus.critical)]

    if blocked_tasks:
        lines.append("**Blocked tasks:**")
        for t in blocked_tasks:
            desc = f" — {t.description[:100]}" if t.description else ""
            lines.append(f"- {t.title}{desc}")
        lines.append("")

    if problem_channels:
        lines.append("**Channel issues:**")
        for c in problem_channels:
            reason = f" — {c.health_reason}" if c.health_reason else ""
            lines.append(f"- {c.name}: {c.health.value}{reason}")
        lines.append("")

    if not blocked_tasks and not problem_channels:
        lines.append("No blockers or open questions.")
        lines.append("")

    # --- Footer ---
    lines.append("---")
    lines.append(f"*Generated by MCC Strategy Export — {now.strftime('%Y-%m-%d %H:%M')} UTC*")

    return "\n".join(lines)


@router.get("/")
def strategy_export_page(request: Request, db: Session = Depends(get_db)):
    """Generate and display the strategy export."""
    md = generate_strategy_markdown(db)
    if not md:
        return HTMLResponse('<div class="text-center py-16 text-mcc-muted">No project loaded.</div>')

    project = db.query(Project).filter_by(slug="grindlab").first()

    # Check last export time
    last_exported = None
    if os.path.exists(EXPORT_PATH):
        mtime = os.path.getmtime(EXPORT_PATH)
        last_exported = datetime.fromtimestamp(mtime)

    return templates.TemplateResponse("strategy_export.html", {
        "request": request,
        "project": project,
        "markdown_content": md,
        "last_exported": last_exported,
        "current_page": "strategy_export",
        "today": date.today(),
    })


@router.get("/raw")
def strategy_export_raw(db: Session = Depends(get_db)):
    """Return raw markdown for clipboard copy."""
    md = generate_strategy_markdown(db)
    if not md:
        return HTMLResponse("No project loaded.")
    return HTMLResponse(md, media_type="text/plain; charset=utf-8")


@router.get("/download")
def strategy_export_download(db: Session = Depends(get_db)):
    """Download as .md file."""
    md = generate_strategy_markdown(db)
    if not md:
        return HTMLResponse("No project loaded.")

    buffer = BytesIO(md.encode("utf-8"))
    today = date.today().isoformat()
    return StreamingResponse(
        buffer,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="MCC-Strategy-Export-{today}.md"'},
    )


@router.post("/save")
def strategy_export_save(db: Session = Depends(get_db)):
    """Save to the auto-export path and return confirmation."""
    md = generate_strategy_markdown(db)
    if not md:
        return HTMLResponse('<span class="text-mcc-critical text-xs">No project loaded</span>')

    os.makedirs(os.path.dirname(EXPORT_PATH), exist_ok=True)
    with open(EXPORT_PATH, "w") as f:
        f.write(md)

    now = datetime.now()
    return HTMLResponse(
        f'<span class="text-mcc-success text-xs">Saved to {EXPORT_PATH} at {now.strftime("%I:%M %p")}</span>'
    )


# --- Scheduled job ---

def strategy_export_job():
    """APScheduler-compatible weekly export job (Sunday 6AM)."""
    db = SessionLocal()
    try:
        md = generate_strategy_markdown(db)
        if not md:
            logger.warning("No project — skipping strategy export")
            return

        os.makedirs(os.path.dirname(EXPORT_PATH), exist_ok=True)
        with open(EXPORT_PATH, "w") as f:
            f.write(md)
        logger.info(f"Weekly strategy export saved to {EXPORT_PATH}")
    except Exception as e:
        logger.error(f"Strategy export job failed: {e}")
    finally:
        db.close()
