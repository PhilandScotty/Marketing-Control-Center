from datetime import date, datetime, timedelta
from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Project, Channel, Task, Automation, Metric, MetricSnapshot,
    OutreachContact, ApprovalQueueItem,
    TaskStatus, TaskPriority, AutomationHealth,
    ContactStatus, QueueItemStatus,
)
from app.routes.tasks import _sort_recurring

router = APIRouter(prefix="/daily")
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def daily_ops(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("daily.html", {
            "request": request, "project": None, "current_page": "daily",
            "today": date.today(),
        })

    pid = project.id
    today = date.today()
    yesterday = today - timedelta(days=1)
    next_week = today + timedelta(days=7)
    next_48h = today + timedelta(days=2)

    # --- Auto-promote: backlog tasks due within 7 days -> this_week ---
    backlog_due_soon = db.query(Task).filter(
        Task.project_id == pid,
        Task.status == TaskStatus.backlog,
        Task.due_date != None,
        Task.due_date <= next_week,
    ).all()
    for t in backlog_due_soon:
        t.status = TaskStatus.this_week
    if backlog_due_soon:
        db.commit()

    # --- Section 1: Today's Tasks ---
    channels = db.query(Channel).filter_by(project_id=pid).all()
    channel_map = {c.id: c for c in channels}

    # Overdue (past due, not done/recurring)
    overdue_tasks = db.query(Task).filter(
        Task.project_id == pid,
        Task.due_date < today,
        Task.status.notin_([TaskStatus.done, TaskStatus.archived, TaskStatus.recurring]),
    ).order_by(Task.priority, Task.due_date).all()

    # Due today
    today_tasks = db.query(Task).filter(
        Task.project_id == pid,
        Task.due_date == today,
        Task.status.notin_([TaskStatus.done, TaskStatus.archived, TaskStatus.recurring]),
    ).order_by(Task.priority).all()

    # In progress
    in_progress = db.query(Task).filter(
        Task.project_id == pid,
        Task.status == TaskStatus.in_progress,
        Task.due_date != today,
    ).order_by(Task.priority).all()

    # This week (promoted from backlog, not overdue/today/in_progress)
    this_week_ids = {t.id for t in overdue_tasks + today_tasks + in_progress}
    this_week_tasks = db.query(Task).filter(
        Task.project_id == pid,
        Task.status == TaskStatus.this_week,
        Task.id.notin_(this_week_ids) if this_week_ids else True,
    ).order_by(Task.priority, Task.due_date).all()

    # Group today_tasks + in_progress by channel
    tasks_by_channel = {}
    for t in today_tasks + in_progress:
        ch_name = channel_map[t.channel_id].name if t.channel_id and t.channel_id in channel_map else "General"
        if ch_name not in tasks_by_channel:
            tasks_by_channel[ch_name] = []
        tasks_by_channel[ch_name].append(t)

    # --- Daily Routine (recurring tasks) ---
    daily_recurring = db.query(Task).filter(
        Task.project_id == pid,
        Task.status == TaskStatus.recurring,
        Task.recurring_schedule != None,
        Task.recurring_schedule.like("% * * *"),  # daily cron pattern
    ).all()
    daily_recurring = _sort_recurring(daily_recurring, today)

    weekly_recurring = db.query(Task).filter(
        Task.project_id == pid,
        Task.status == TaskStatus.recurring,
        Task.recurring_schedule != None,
        ~Task.recurring_schedule.like("% * * *"),  # non-daily
    ).all()
    weekly_recurring = _sort_recurring(weekly_recurring, today)

    # --- Upcoming: backlog tasks due within 48h ---
    upcoming_tasks = db.query(Task).filter(
        Task.project_id == pid,
        Task.status == TaskStatus.backlog,
        Task.due_date != None,
        Task.due_date > today,
        Task.due_date <= next_48h,
    ).order_by(Task.due_date, Task.priority).all()

    # --- Section 2: Autonomous Systems Status ---
    automations = db.query(Automation).filter_by(project_id=pid).order_by(
        Automation.health, Automation.name
    ).all()

    # --- Section 3: Overnight Changes ---
    overnight_changes = []
    yesterday_start = datetime.combine(yesterday, datetime.min.time())
    today_start = datetime.combine(today, datetime.min.time())

    for ch in channels:
        recent = db.query(Metric).filter(
            Metric.channel_id == ch.id,
            Metric.recorded_at >= yesterday_start,
        ).order_by(Metric.recorded_at.desc()).all()

        seen_names = set()
        for m in recent:
            if m.metric_name in seen_names:
                continue
            seen_names.add(m.metric_name)
            if m.previous_value and float(m.previous_value) > 0:
                pct_change = ((float(m.metric_value) - float(m.previous_value)) / float(m.previous_value)) * 100
                if abs(pct_change) > 10:
                    overnight_changes.append({
                        "channel": ch.name,
                        "metric": m.metric_name,
                        "current": float(m.metric_value),
                        "previous": float(m.previous_value),
                        "pct_change": round(pct_change, 1),
                        "unit": m.unit,
                    })

    # Daily actions from channels
    daily_actions = []
    for ch in channels:
        if ch.daily_actions and ch.status.value == "live":
            daily_actions.append({
                "channel": ch.name,
                "channel_id": ch.id,
                "actions": ch.daily_actions,
            })

    # Outreach alerts: new responses + follow-ups due today
    new_responses = db.query(OutreachContact).filter(
        OutreachContact.project_id == pid,
        OutreachContact.status == ContactStatus.responded,
        OutreachContact.stage_changed_at.isnot(None),
        OutreachContact.stage_changed_at >= datetime.combine(yesterday, datetime.min.time()),
    ).all()

    followups_due = db.query(OutreachContact).filter(
        OutreachContact.project_id == pid,
        OutreachContact.next_follow_up <= today,
        OutreachContact.next_follow_up.isnot(None),
        OutreachContact.status.notin_([ContactStatus.active, ContactStatus.declined, ContactStatus.ghosted]),
    ).all()

    # Queue count for badge
    queue_count = db.query(ApprovalQueueItem).filter_by(
        project_id=pid, status=QueueItemStatus.pending,
    ).count()

    return templates.TemplateResponse("daily.html", {
        "request": request,
        "project": project,
        "overdue_tasks": overdue_tasks,
        "tasks_by_channel": tasks_by_channel,
        "this_week_tasks": this_week_tasks,
        "daily_recurring": daily_recurring,
        "weekly_recurring": weekly_recurring,
        "upcoming_tasks": upcoming_tasks,
        "daily_actions": daily_actions,
        "automations": automations,
        "overnight_changes": overnight_changes,
        "channel_map": channel_map,
        "new_responses": new_responses,
        "followups_due": followups_due,
        "queue_count": queue_count,
        "current_page": "daily",
        "today": today,
    })


@router.post("/complete/{task_id}")
def complete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task:
        task.status = TaskStatus.done
        task.completed_at = datetime.utcnow()
        db.commit()
    return HTMLResponse('<span class="text-mcc-success text-xs">Done!</span>')
