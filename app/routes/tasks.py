from datetime import date, datetime, timedelta
from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import (
    Project, Channel, Task, Metric, ChecklistItem,
    TaskStatus, TaskPriority,
)
from app.routes.checklist import get_checklist_summary

router = APIRouter(prefix="/tasks")
templates = Jinja2Templates(directory="app/templates")

COLUMNS = [
    ("backlog", "Backlog"),
    ("this_week", "This Week"),
    ("in_progress", "In Progress"),
    ("blocked", "Blocked"),
    ("done", "Done"),
    ("monitoring", "Monitoring"),
    ("recurring", "Recurring"),
]

COLUMN_COLORS = {
    "backlog": "#6B6B8A",
    "this_week": "#164E63",
    "in_progress": "#06B6D4",
    "blocked": "#EF4444",
    "done": "#10B981",
    "monitoring": "#F59E0B",
    "recurring": "#3A3A5A",
}


FREQ_DAYS = {"daily": 1, "every_3_days": 3, "weekly": 7, "biweekly": 14, "monthly": 30}


def _freq_to_days(freq: str) -> int:
    """Convert a recurring_frequency value to number of days."""
    if freq in FREQ_DAYS:
        return FREQ_DAYS[freq]
    try:
        return int(freq)
    except (ValueError, TypeError):
        return 7


def _get_project(db: Session):
    return db.query(Project).filter_by(slug="grindlab").first()


def _log_completion_history(task: "Task", old_status: str, new_status: str):
    """Append completion/reopen entries to the task description as a history trail."""
    today_str = date.today().strftime("%b %d")
    entry = None
    if new_status == "done" and old_status != "done":
        entry = f"Completed: {today_str}"
    elif old_status == "done" and new_status != "done":
        entry = f"Reopened: {today_str}"

    if not entry:
        return

    desc = task.description or ""
    marker = "\n\n---\n**History:** "
    if marker.strip() in desc:
        desc += f" → {entry}"
    else:
        desc += f"{marker}{entry}"
    task.description = desc


def _sort_recurring(tasks: list, today: date | None = None) -> list:
    """Sort recurring tasks: overdue first, then due today, tomorrow, then chronologically."""
    if today is None:
        today = date.today()

    def _key(t):
        due = t.recurring_next_due
        if due is None:
            return (3, date.max)  # no due date — sort last
        if due < today:
            return (0, due)      # overdue
        if due == today:
            return (1, due)      # due today
        return (2, due)          # future
    return sorted(tasks, key=_key)


def _build_dep_map(tasks: list) -> dict:
    """Build maps of task_id -> blocked_by_ids and task_id -> blocks_ids."""
    blocked_by = {}
    blocks = {}
    for t in tasks:
        bb = t.blocked_by or []
        bl = t.blocks or []
        blocked_by[t.id] = [int(x) for x in bb if x]
        blocks[t.id] = [int(x) for x in bl if x]
    return blocked_by, blocks


ARCHIVE_AFTER_DAYS = 14


def _auto_archive_done(db: Session, project_id: int):
    """Move tasks that have been Done for 14+ days to archived status."""
    cutoff = datetime.utcnow() - timedelta(days=ARCHIVE_AFTER_DAYS)
    stale_done = db.query(Task).filter(
        Task.project_id == project_id,
        Task.status == TaskStatus.done,
        Task.completed_at.isnot(None),
        Task.completed_at <= cutoff,
    ).all()
    for task in stale_done:
        task.status = TaskStatus.archived
        task.updated_at = datetime.utcnow()
    if stale_done:
        db.commit()


def _process_recurring(db: Session, project_id: int):
    """Check recurring tasks and generate new instances if due."""
    today = date.today()
    recurring = db.query(Task).filter(
        Task.project_id == project_id,
        Task.status == TaskStatus.recurring,
        Task.recurring_next_due <= today,
        Task.recurring_next_due.isnot(None),
    ).all()

    for task in recurring:
        existing = db.query(Task).filter(
            Task.project_id == project_id,
            Task.title == task.title,
            Task.status != TaskStatus.recurring,
            Task.due_date == task.recurring_next_due,
        ).first()

        if not existing:
            prev_undone = db.query(Task).filter(
                Task.project_id == project_id,
                Task.title == task.title,
                Task.status.notin_([TaskStatus.done, TaskStatus.archived, TaskStatus.recurring]),
            ).first()

            new_task = Task(
                project_id=project_id,
                channel_id=task.channel_id,
                title=task.title,
                description=task.description + ("\n\n**WARNING: Previous instance not completed!**" if prev_undone else ""),
                status=TaskStatus.this_week,
                priority=TaskPriority.high if prev_undone else task.priority,
                assigned_to=task.assigned_to,
                due_date=task.recurring_next_due,
                start_date=today,
            )
            db.add(new_task)

            if task.recurring_frequency:
                delta = timedelta(days=_freq_to_days(task.recurring_frequency))
            else:
                # Fallback to cron parsing
                cron = task.recurring_schedule or ""
                if "* * *" in cron and "," not in cron:
                    delta = timedelta(days=1)
                elif "1,15" in cron:
                    delta = timedelta(days=14)
                elif "1 * *" in cron:
                    delta = timedelta(days=30)
                else:
                    delta = timedelta(days=7)
            task.recurring_next_due = task.recurring_next_due + delta

    if recurring:
        db.commit()


@router.get("/")
def tasks_kanban(request: Request, db: Session = Depends(get_db)):
    project = _get_project(db)
    if not project:
        return templates.TemplateResponse("tasks.html", {
            "request": request, "project": None, "current_page": "tasks",
            "today": date.today(),
        })

    _process_recurring(db, project.id)
    _auto_archive_done(db, project.id)

    tasks = db.query(Task).filter(
        Task.project_id == project.id,
        Task.status != TaskStatus.archived,
    ).order_by(Task.priority, Task.due_date).all()

    channels = db.query(Channel).filter_by(project_id=project.id).all()
    channel_map = {c.id: c for c in channels}

    # Build checklist summaries for all tasks
    checklist_summaries = {}
    for t in tasks:
        checklist_summaries[t.id] = get_checklist_summary(db, t.id)

    today_date = date.today()
    columns = {}
    for key, label in COLUMNS:
        col_tasks = [t for t in tasks if t.status.value == key]
        if key == "recurring":
            col_tasks = _sort_recurring(col_tasks, today_date)
        columns[key] = {
            "key": key,
            "label": label,
            "color": COLUMN_COLORS[key],
            "tasks": col_tasks,
        }

    blocked_by, blocks = _build_dep_map(tasks)
    task_map = {t.id: t for t in tasks}

    # Get metrics for monitoring modal dropdown
    metrics_list = db.query(Metric.metric_name).distinct().all()
    metric_names = sorted(set(m[0] for m in metrics_list))

    archived_count = db.query(Task).filter(
        Task.project_id == project.id,
        Task.status == TaskStatus.archived,
    ).count()

    return templates.TemplateResponse("tasks.html", {
        "request": request,
        "project": project,
        "columns": columns,
        "column_order": [k for k, _ in COLUMNS],
        "channels": channels,
        "channel_map": channel_map,
        "task_map": task_map,
        "blocked_by": blocked_by,
        "blocks": blocks,
        "checklist_summaries": checklist_summaries,
        "metric_names": metric_names,
        "archived_count": archived_count,
        "priorities": [(p.value, p.value.replace("_", " ").title()) for p in TaskPriority],
        "statuses": [(s.value, s.value.replace("_", " ").title()) for s in TaskStatus],
        "current_page": "tasks",
        "today": date.today(),
    })


@router.post("/move")
def move_task(
    task_id: int = Form(...),
    new_status: str = Form(...),
    db: Session = Depends(get_db),
):
    task = db.get(Task, task_id)
    if not task:
        return HTMLResponse("", status_code=404)

    old_status = task.status.value
    task.status = TaskStatus(new_status)
    if new_status == "done":
        task.completed_at = datetime.utcnow()
    elif task.completed_at and new_status != "done":
        task.completed_at = None
    _log_completion_history(task, old_status, new_status)
    task.updated_at = datetime.utcnow()

    # If a recurring task is moved to Done, create a new copy in Recurring
    if new_status == "done" and task.recurring_frequency:
        delta = timedelta(days=_freq_to_days(task.recurring_frequency))
        # Copy checklist items from the completed task
        old_checklist = db.query(ChecklistItem).filter_by(task_id=task.id).order_by(ChecklistItem.sort_order).all()
        new_task = Task(
            project_id=task.project_id,
            channel_id=task.channel_id,
            title=task.title,
            description=task.description,
            status=TaskStatus.recurring,
            priority=task.priority,
            assigned_to=task.assigned_to,
            recurring_frequency=task.recurring_frequency,
            recurring_schedule=task.recurring_schedule,
            recurring_next_due=date.today() + delta,
        )
        db.add(new_task)
        db.flush()  # get new_task.id
        for item in old_checklist:
            db.add(ChecklistItem(
                task_id=new_task.id,
                title=item.title,
                completed=False,
                sort_order=item.sort_order,
            ))
        # Keep the original as Done
        task.recurring_frequency = None  # detach recurrence from completed copy
        db.commit()
        return HTMLResponse("")

    db.commit()

    # If moving to done, return the monitoring prompt modal
    if new_status == "done":
        project = _get_project(db)
        channels = db.query(Channel).filter_by(project_id=project.id).all() if project else []
        metrics_list = db.query(Metric.metric_name).distinct().all()
        metric_names = sorted(set(m[0] for m in metrics_list))
        return HTMLResponse(f'''
        <div id="monitoring-prompt-{task_id}" class="fixed inset-0 bg-black/60 z-[60] flex items-center justify-center" onclick="if(event.target===this)this.remove()">
            <div class="bg-[#16162E] rounded-xl border border-[#1E1E3A] w-full max-w-md p-6 shadow-2xl" onclick="event.stopPropagation()">
                <h3 class="text-sm font-semibold mb-3">Does this need ongoing monitoring?</h3>
                <p class="text-xs text-[#6B6B8A] mb-4">Task: {task.title}</p>
                <div class="flex gap-3">
                    <button onclick="document.getElementById('monitoring-prompt-{task_id}').remove()"
                            class="flex-1 px-4 py-2 bg-[#1E1E3A] text-[#6B6B8A] rounded-lg text-sm hover:text-[#E8E8F0] transition-colors">
                        No, Archive
                    </button>
                    <button onclick="document.getElementById('monitoring-form-{task_id}').classList.remove('hidden'); this.parentElement.classList.add('hidden')"
                            class="flex-1 px-4 py-2 bg-[#F59E0B] text-black rounded-lg text-sm font-medium hover:bg-[#F59E0B]/80 transition-colors">
                        Yes, Monitor
                    </button>
                </div>
                <form id="monitoring-form-{task_id}" class="hidden mt-4 space-y-3"
                      hx-post="/tasks/{task_id}/set-monitoring" hx-swap="none"
                      hx-on::after-request="document.getElementById('monitoring-prompt-{task_id}').remove(); window.location.reload()">
                    <div>
                        <label class="text-xs text-[#6B6B8A] block mb-1">Metric to watch</label>
                        <input type="text" name="monitoring_metric" list="metric-options-{task_id}"
                               class="w-full bg-[#0B0B1A] border border-[#1E1E3A] rounded-lg px-3 py-2 text-sm text-[#E8E8F0]"
                               placeholder="e.g. open_rate, subscribers" required>
                        <datalist id="metric-options-{task_id}">
                            {"".join(f'<option value="{m}">' for m in metric_names)}
                        </datalist>
                    </div>
                    <div>
                        <label class="text-xs text-[#6B6B8A] block mb-1">Alert threshold</label>
                        <input type="text" name="monitoring_threshold"
                               class="w-full bg-[#0B0B1A] border border-[#1E1E3A] rounded-lg px-3 py-2 text-sm text-[#E8E8F0]"
                               placeholder="e.g. open_rate < 15% or subscribers < 100" required>
                    </div>
                    <div>
                        <label class="text-xs text-[#6B6B8A] block mb-1">Channel</label>
                        <select name="channel_id"
                                class="w-full bg-[#0B0B1A] border border-[#1E1E3A] rounded-lg px-3 py-2 text-sm text-[#E8E8F0]">
                            <option value="">None</option>
                            {"".join(f'<option value="{ch.id}">{ch.name}</option>' for ch in channels)}
                        </select>
                    </div>
                    <button type="submit"
                            class="w-full px-4 py-2 bg-[#F59E0B] text-black rounded-lg text-sm font-medium hover:bg-[#F59E0B]/80">
                        Start Monitoring
                    </button>
                </form>
            </div>
        </div>''')

    return HTMLResponse("")


@router.post("/{task_id}/set-monitoring")
def set_monitoring(
    task_id: int,
    monitoring_metric: str = Form(""),
    monitoring_threshold: str = Form(""),
    channel_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    task = db.get(Task, task_id)
    if not task:
        return HTMLResponse("", status_code=404)

    task.status = TaskStatus.monitoring
    task.monitoring_metric = monitoring_metric
    task.monitoring_threshold = monitoring_threshold
    if channel_id:
        task.channel_id = channel_id
    task.updated_at = datetime.utcnow()
    db.commit()
    return HTMLResponse("")


@router.post("/{task_id}/save-notes")
def save_task_notes(
    task_id: int,
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    task = db.get(Task, task_id)
    if not task:
        return HTMLResponse("Not found", status_code=404)
    task.description = description
    task.updated_at = datetime.utcnow()
    db.commit()
    return HTMLResponse('<span class="text-[10px] text-mcc-success">Saved</span>')


@router.get("/{task_id}/detail")
def task_detail(task_id: int, request: Request, db: Session = Depends(get_db)):
    """Expanded task card view with full details and checklist."""
    task = db.get(Task, task_id)
    if not task:
        return HTMLResponse("Not found", status_code=404)

    project = _get_project(db)
    channels = db.query(Channel).filter_by(project_id=project.id).all() if project else []
    channel_map = {c.id: c for c in channels}
    checklist = db.query(ChecklistItem).filter_by(task_id=task_id).order_by(ChecklistItem.sort_order).all()
    all_tasks = db.query(Task).filter(
        Task.project_id == project.id,
        Task.id != task_id,
    ).order_by(Task.title).all() if project else []

    resp = templates.TemplateResponse("partials/task_detail.html", {
        "request": request,
        "task": task,
        "channels": channels,
        "channel_map": channel_map,
        "checklist": checklist,
        "all_tasks": all_tasks,
        "priorities": [(p.value, p.value.replace("_", " ").title()) for p in TaskPriority],
        "statuses": [(s.value, s.value.replace("_", " ").title()) for s in TaskStatus],
        "today": date.today(),
    })
    resp.headers["Cache-Control"] = "no-store"
    return resp


@router.post("/create")
def create_task(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    status: str = Form("backlog"),
    priority: str = Form("medium"),
    assigned_to: str = Form("phil"),
    channel_id: Optional[int] = Form(None),
    due_date: Optional[str] = Form(None),
    start_date: Optional[str] = Form(None),
    estimated_hours: Optional[float] = Form(None),
    blocked_by: Optional[str] = Form(""),
    blocks: Optional[str] = Form(""),
    db: Session = Depends(get_db),
):
    project = _get_project(db)
    if not project:
        return HTMLResponse("No project", status_code=400)

    bb = [int(x.strip()) for x in blocked_by.split(",") if x.strip().isdigit()] if blocked_by else []
    bl = [int(x.strip()) for x in blocks.split(",") if x.strip().isdigit()] if blocks else []

    task = Task(
        project_id=project.id,
        channel_id=channel_id if channel_id and channel_id > 0 else None,
        title=title,
        description=description,
        status=TaskStatus(status),
        priority=TaskPriority(priority),
        assigned_to=assigned_to,
        due_date=date.fromisoformat(due_date) if due_date else None,
        start_date=date.fromisoformat(start_date) if start_date else None,
        estimated_hours=estimated_hours,
        blocked_by=bb,
        blocks=bl,
    )
    db.add(task)
    db.commit()

    checklist_summary = get_checklist_summary(db, task.id)

    return templates.TemplateResponse("partials/task_card.html", {
        "request": request,
        "task": task,
        "today": date.today(),
        "checklist_summaries": {task.id: checklist_summary},
    })


@router.get("/{task_id}/edit")
def edit_task_form(task_id: int, request: Request, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        return HTMLResponse("Not found", status_code=404)

    project = _get_project(db)
    channels = db.query(Channel).filter_by(project_id=project.id).all() if project else []
    all_tasks = db.query(Task).filter(
        Task.project_id == project.id,
        Task.id != task_id,
    ).order_by(Task.title).all() if project else []

    resp = templates.TemplateResponse("partials/task_edit_modal.html", {
        "request": request,
        "task": task,
        "channels": channels,
        "all_tasks": all_tasks,
        "priorities": [(p.value, p.value.replace("_", " ").title()) for p in TaskPriority],
        "statuses": [(s.value, s.value.replace("_", " ").title()) for s in TaskStatus],
        "today": date.today(),
    })
    resp.headers["Cache-Control"] = "no-store"
    return resp


@router.post("/{task_id}/update")
def update_task(
    task_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    status: str = Form("backlog"),
    priority: str = Form("medium"),
    assigned_to: str = Form("phil"),
    channel_id: Optional[int] = Form(None),
    due_date: Optional[str] = Form(None),
    start_date: Optional[str] = Form(None),
    estimated_hours: Optional[float] = Form(None),
    blocked_by: Optional[str] = Form(""),
    blocks: Optional[str] = Form(""),
    recurring_frequency: Optional[str] = Form(None),
    recurring_custom_days: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    task = db.get(Task, task_id)
    if not task:
        return HTMLResponse("Not found", status_code=404)

    old_status = task.status.value
    task.title = title
    task.description = description
    task.status = TaskStatus(status)
    task.priority = TaskPriority(priority)
    task.assigned_to = assigned_to
    task.channel_id = channel_id if channel_id and channel_id > 0 else None
    task.due_date = date.fromisoformat(due_date) if due_date else None
    task.start_date = date.fromisoformat(start_date) if start_date else None
    task.estimated_hours = estimated_hours
    task.blocked_by = [int(x.strip()) for x in blocked_by.split(",") if x.strip().isdigit()] if blocked_by else []
    task.blocks = [int(x.strip()) for x in blocks.split(",") if x.strip().isdigit()] if blocks else []
    task.updated_at = datetime.utcnow()

    # Save recurrence settings
    if recurring_frequency == "custom" and recurring_custom_days:
        task.recurring_frequency = str(recurring_custom_days)
    elif recurring_frequency and recurring_frequency not in ("", "custom"):
        task.recurring_frequency = recurring_frequency
    elif recurring_frequency == "":
        task.recurring_frequency = None

    # Auto-set next_due when switching to recurring with a frequency
    if status == "recurring" and task.recurring_frequency and not task.recurring_next_due:
        task.recurring_next_due = date.today() + timedelta(days=_freq_to_days(task.recurring_frequency))

    if status == "done" and not task.completed_at:
        task.completed_at = datetime.utcnow()
    elif status != "done":
        task.completed_at = None
    _log_completion_history(task, old_status, status)

    db.commit()

    checklist_summary = get_checklist_summary(db, task.id)

    return templates.TemplateResponse("partials/task_card.html", {
        "request": request,
        "task": task,
        "today": date.today(),
        "checklist_summaries": {task.id: checklist_summary},
    })


@router.post("/{task_id}/delete")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task:
        db.query(ChecklistItem).filter_by(task_id=task_id).delete()
        db.delete(task)
        db.commit()
    return HTMLResponse("")


@router.get("/{task_id}/deps")
def task_dependencies(task_id: int, db: Session = Depends(get_db)):
    """Return JSON of dependency IDs for hover highlighting."""
    task = db.get(Task, task_id)
    if not task:
        return {"blocked_by": [], "blocks": []}
    return {
        "blocked_by": task.blocked_by or [],
        "blocks": task.blocks or [],
    }


@router.get("/archive")
def archive_list(request: Request, q: str = "", db: Session = Depends(get_db)):
    """Return archived tasks as a searchable HTML partial."""
    project = _get_project(db)
    if not project:
        return HTMLResponse("")

    query = db.query(Task).filter(
        Task.project_id == project.id,
        Task.status == TaskStatus.archived,
    )
    if q.strip():
        query = query.filter(Task.title.ilike(f"%{q.strip()}%"))
    archived_tasks = query.order_by(Task.completed_at.desc()).all()

    rows = []
    for t in archived_tasks:
        completed_str = t.completed_at.strftime("%b %d, %Y") if t.completed_at else "—"
        priority_color = {
            "launch_critical": "text-mcc-critical",
            "high": "text-mcc-warning",
            "medium": "text-mcc-muted",
            "low": "text-mcc-muted/60",
            "cleanup": "text-mcc-muted/40",
        }.get(t.priority.value, "text-mcc-muted")
        rows.append(f'''
        <div class="flex items-center justify-between py-2 px-3 border-b border-mcc-border/50 hover:bg-mcc-bg/50 group">
            <div class="flex-1 min-w-0">
                <span class="text-xs font-medium cursor-pointer hover:text-mcc-accent" onclick="closeArchiveModal(); openDetailModal({t.id})">{t.title}</span>
                <div class="flex items-center gap-2 mt-0.5">
                    <span class="text-[10px] text-mcc-muted/60">Completed {completed_str}</span>
                    <span class="text-[10px] {priority_color} capitalize">{t.priority.value.replace("_", " ")}</span>
                </div>
            </div>
            <button hx-post="/tasks/{t.id}/unarchive" hx-swap="outerHTML" hx-target="closest div.flex"
                    class="text-[10px] px-2 py-1 rounded bg-mcc-border text-mcc-muted hover:text-mcc-text opacity-0 group-hover:opacity-100 transition-opacity">
                Restore
            </button>
        </div>''')

    count_text = f'{len(archived_tasks)} archived task{"s" if len(archived_tasks) != 1 else ""}'
    return HTMLResponse(f'''
    <div class="text-[10px] text-mcc-muted/60 px-3 py-1.5">{count_text}</div>
    {"".join(rows) if rows else '<div class="text-xs text-mcc-muted/60 px-3 py-6 text-center">No archived tasks found.</div>'}
    ''')


@router.post("/{task_id}/unarchive")
def unarchive_task(task_id: int, db: Session = Depends(get_db)):
    """Move an archived task back to Done."""
    task = db.get(Task, task_id)
    if not task:
        return HTMLResponse("", status_code=404)
    task.status = TaskStatus.done
    task.updated_at = datetime.utcnow()
    db.commit()
    return HTMLResponse('<div class="text-[10px] text-mcc-success px-3 py-2">Restored to Done</div>')
