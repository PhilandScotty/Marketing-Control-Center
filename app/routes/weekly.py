from datetime import date, datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import (
    Project, Channel, Task, Automation, Metric, Tool, AdCampaign,
    ContentPiece, OutreachContact, BudgetExpense, OnboardingMilestone,
    TaskStatus, ContentStatus, ContactStatus, ToolStatus,
)

router = APIRouter(prefix="/weekly")
templates = Jinja2Templates(directory="app/templates")


def _get_recurring_streaks(db: Session, project_id: int) -> list:
    """Calculate streak data for recurring tasks."""
    recurring = db.query(Task).filter(
        Task.project_id == project_id,
        Task.status == TaskStatus.recurring,
    ).all()

    streaks = []
    for rt in recurring:
        # Find all generated instances of this recurring task (same title, not recurring status)
        instances = db.query(Task).filter(
            Task.project_id == project_id,
            Task.title == rt.title,
            Task.status != TaskStatus.recurring,
        ).order_by(Task.due_date.desc()).limit(14).all()

        completed = sum(1 for t in instances if t.status in (TaskStatus.done, TaskStatus.archived))
        missed = sum(1 for t in instances if t.status not in (TaskStatus.done, TaskStatus.archived) and t.due_date and t.due_date < date.today())
        total = len(instances)

        # Current streak (consecutive completed from most recent)
        current_streak = 0
        for t in instances:
            if t.status in (TaskStatus.done, TaskStatus.archived):
                current_streak += 1
            else:
                break

        streaks.append({
            "title": rt.title,
            "schedule": rt.recurring_schedule,
            "next_due": rt.recurring_next_due,
            "current_streak": current_streak,
            "completed": completed,
            "missed": missed,
            "total": total,
        })

    return streaks


@router.get("/")
def weekly_review(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("weekly.html", {
            "request": request, "project": None, "current_page": "weekly",
            "today": date.today(),
        })

    pid = project.id
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    last_week_start = week_start - timedelta(days=7)
    last_week_end = week_start - timedelta(days=1)

    channels = db.query(Channel).filter_by(project_id=pid).all()

    # --- Metrics Table: every channel, every metric, this week vs last ---
    channel_metrics = []
    for ch in channels:
        # Get all unique metric names for this channel
        metric_names = db.query(Metric.metric_name).filter_by(
            channel_id=ch.id
        ).distinct().all()

        ch_data = {"channel": ch, "metrics": []}
        for (name,) in metric_names:
            # Latest this week
            this_week = db.query(Metric).filter(
                Metric.channel_id == ch.id,
                Metric.metric_name == name,
                Metric.recorded_at >= datetime.combine(week_start, datetime.min.time()),
            ).order_by(Metric.recorded_at.desc()).first()

            # Latest last week
            last_week = db.query(Metric).filter(
                Metric.channel_id == ch.id,
                Metric.metric_name == name,
                Metric.recorded_at >= datetime.combine(last_week_start, datetime.min.time()),
                Metric.recorded_at < datetime.combine(week_start, datetime.min.time()),
            ).order_by(Metric.recorded_at.desc()).first()

            # Sparkline data (last 7 values)
            spark_data = db.query(Metric.metric_value).filter(
                Metric.channel_id == ch.id,
                Metric.metric_name == name,
            ).order_by(Metric.recorded_at.desc()).limit(7).all()
            sparkline = [float(v[0]) for v in reversed(spark_data)]

            this_val = float(this_week.metric_value) if this_week else None
            last_val = float(last_week.metric_value) if last_week else None
            delta = None
            delta_pct = None
            if this_val is not None and last_val is not None:
                delta = this_val - last_val
                if last_val != 0:
                    delta_pct = round((delta / last_val) * 100, 1)

            ch_data["metrics"].append({
                "name": name,
                "unit": this_week.unit if this_week else "count",
                "this_week": this_val,
                "last_week": last_val,
                "delta": delta,
                "delta_pct": delta_pct,
                "sparkline": sparkline,
            })

        if ch_data["metrics"]:
            channel_metrics.append(ch_data)

    # --- Task Velocity ---
    tasks_completed = db.query(Task).filter(
        Task.project_id == pid,
        Task.completed_at >= datetime.combine(week_start, datetime.min.time()),
        Task.completed_at <= datetime.combine(week_end, datetime.max.time()),
    ).count()

    tasks_added = db.query(Task).filter(
        Task.project_id == pid,
        Task.created_at >= datetime.combine(week_start, datetime.min.time()),
        Task.created_at <= datetime.combine(week_end, datetime.max.time()),
    ).count()

    tasks_overdue = db.query(Task).filter(
        Task.project_id == pid,
        Task.due_date < today,
        Task.status.notin_([TaskStatus.done, TaskStatus.archived, TaskStatus.recurring]),
    ).count()

    total_tasks = db.query(Task).filter(
        Task.project_id == pid,
        Task.status.notin_([TaskStatus.recurring, TaskStatus.archived]),
    ).count()

    tasks_done_total = db.query(Task).filter(
        Task.project_id == pid,
        Task.status.in_([TaskStatus.done, TaskStatus.archived]),
    ).count()

    # --- Spend Report ---
    active_tools = db.query(Tool).filter(
        Tool.project_id == pid,
        Tool.status == ToolStatus.active,
    ).all()
    tool_spend = sum(float(t.monthly_cost) for t in active_tools)

    ad_spend = db.query(func.sum(AdCampaign.spend_to_date)).filter(
        AdCampaign.project_id == pid,
    ).scalar() or 0

    budget = float(project.monthly_budget) if project.monthly_budget else 0
    total_spend = tool_spend + float(ad_spend)
    budget_remaining = budget - total_spend

    # --- Content Pipeline ---
    content_by_status = {}
    for status in ContentStatus:
        count = db.query(ContentPiece).filter(
            ContentPiece.project_id == pid,
            ContentPiece.status == status,
        ).count()
        if count > 0:
            content_by_status[status.value] = count

    published_this_week = db.query(ContentPiece).filter(
        ContentPiece.project_id == pid,
        ContentPiece.status == ContentStatus.published,
        ContentPiece.published_at >= datetime.combine(week_start, datetime.min.time()),
    ).count()

    # --- Outreach Pipeline ---
    outreach_by_status = {}
    for status in ContactStatus:
        count = db.query(OutreachContact).filter(
            OutreachContact.project_id == pid,
            OutreachContact.status == status,
        ).count()
        if count > 0:
            outreach_by_status[status.value] = count

    outreach_total = db.query(OutreachContact).filter_by(project_id=pid).count()

    # --- Milestones ---
    milestones = db.query(OnboardingMilestone).filter_by(
        project_id=pid
    ).order_by(OnboardingMilestone.display_order).all()

    # --- Recurring Streaks ---
    streaks = _get_recurring_streaks(db, pid)

    return templates.TemplateResponse("weekly.html", {
        "request": request,
        "project": project,
        "channel_metrics": channel_metrics,
        "tasks_completed": tasks_completed,
        "tasks_added": tasks_added,
        "tasks_overdue": tasks_overdue,
        "total_tasks": total_tasks,
        "tasks_done_total": tasks_done_total,
        "tool_spend": tool_spend,
        "ad_spend": float(ad_spend),
        "total_spend": total_spend,
        "budget": budget,
        "budget_remaining": budget_remaining,
        "active_tools": active_tools,
        "content_by_status": content_by_status,
        "published_this_week": published_this_week,
        "outreach_by_status": outreach_by_status,
        "outreach_total": outreach_total,
        "milestones": milestones,
        "streaks": streaks,
        "week_label": f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}",
        "current_page": "weekly",
        "today": today,
    })
