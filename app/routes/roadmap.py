from datetime import date, timedelta
from fastapi import APIRouter, Request, Depends, Query
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
import json

from app.database import get_db
from app.models import (
    Project, Channel, Task, TaskStatus, TaskPriority,
)

router = APIRouter(prefix="/roadmap")
templates = Jinja2Templates(directory="app/templates")


def _find_critical_path(tasks: list, task_map: dict) -> set:
    """Find the longest dependency chain to launch (tasks with latest due dates)."""
    memo = {}

    def chain_length(tid):
        if tid in memo:
            return memo[tid]
        t = task_map.get(tid)
        if not t:
            return 0
        blocks_ids = t.blocks or []
        if not blocks_ids:
            memo[tid] = 1
            return 1
        max_child = 0
        for b in blocks_ids:
            if int(b) in task_map:
                max_child = max(max_child, chain_length(int(b)))
        memo[tid] = 1 + max_child
        return memo[tid]

    for t in tasks:
        chain_length(t.id)

    if not memo:
        return set()

    max_len = max(memo.values())
    critical = set()

    def trace(tid, depth):
        if tid not in task_map:
            return
        if memo.get(tid, 0) < max_len - depth:
            return
        critical.add(tid)
        t = task_map[tid]
        for b in (t.blocks or []):
            trace(int(b), depth + 1)

    roots = [t.id for t in tasks if not (t.blocked_by or [])]
    for r in roots:
        if memo.get(r, 0) == max_len:
            trace(r, 0)

    return critical


@router.get("/")
def roadmap_view(
    request: Request,
    channel_id: Optional[int] = Query(None),
    assignee: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("roadmap.html", {
            "request": request, "project": None, "current_page": "roadmap",
            "today": date.today(),
        })

    query = db.query(Task).filter(
        Task.project_id == project.id,
        Task.status.notin_([TaskStatus.done, TaskStatus.archived]),
    )
    if channel_id:
        query = query.filter(Task.channel_id == channel_id)
    if assignee:
        query = query.filter(Task.assigned_to == assignee)
    if priority:
        query = query.filter(Task.priority == TaskPriority(priority))

    tasks = query.order_by(Task.due_date, Task.priority).all()
    channels = db.query(Channel).filter_by(project_id=project.id).all()

    task_map = {t.id: t for t in tasks}
    critical_path = _find_critical_path(tasks, task_map)

    today = date.today()
    launch = project.launch_date or (today + timedelta(days=30))
    timeline_start = today - timedelta(days=3)
    timeline_end = launch + timedelta(days=7)
    total_days = (timeline_end - timeline_start).days or 1

    # Build task bars for the timeline
    task_bars = []
    for t in tasks:
        t_start = t.start_date or (t.due_date - timedelta(days=3) if t.due_date else today)
        t_end = t.due_date or (t_start + timedelta(days=3))
        if t_end < t_start:
            t_end = t_start + timedelta(days=1)

        left_pct = max(0, ((t_start - timeline_start).days / total_days) * 100)
        width_pct = max(1, ((t_end - t_start).days / total_days) * 100)
        is_overdue = t.due_date and t.due_date < today
        is_critical = t.id in critical_path

        task_bars.append({
            "id": t.id,
            "title": t.title,
            "priority": t.priority.value,
            "assigned_to": t.assigned_to,
            "start": t_start.isoformat(),
            "end": t_end.isoformat(),
            "left_pct": round(left_pct, 2),
            "width_pct": round(min(width_pct, 100 - left_pct), 2),
            "is_overdue": is_overdue,
            "is_critical": is_critical,
            "status": t.status.value,
            "blocked_by": [int(x) for x in (t.blocked_by or []) if x],
            "blocks": [int(x) for x in (t.blocks or []) if x],
            "due_date": t.due_date.isoformat() if t.due_date else None,
        })

    today_pct = round(((today - timeline_start).days / total_days) * 100, 2)
    launch_pct = round(((launch - timeline_start).days / total_days) * 100, 2)

    # Date markers for the axis
    markers = []
    d = timeline_start
    while d <= timeline_end:
        pct = round(((d - timeline_start).days / total_days) * 100, 2)
        markers.append({"date": d.strftime("%b %d"), "pct": pct, "is_today": d == today})
        d += timedelta(days=7)

    assignees = sorted(set(t.assigned_to for t in tasks if t.assigned_to))
    priorities = [(p.value, p.value.replace("_", " ").title()) for p in TaskPriority]

    return templates.TemplateResponse("roadmap.html", {
        "request": request,
        "project": project,
        "task_bars": task_bars,
        "task_bars_json": json.dumps(task_bars),
        "today_pct": today_pct,
        "launch_pct": launch_pct,
        "markers": markers,
        "channels": channels,
        "assignees": assignees,
        "priorities": priorities,
        "filter_channel": channel_id,
        "filter_assignee": assignee,
        "filter_priority": priority,
        "current_page": "roadmap",
        "today": date.today(),
    })
