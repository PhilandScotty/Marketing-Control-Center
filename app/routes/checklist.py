"""Checklist item routes — HTMX-driven subtask management within task cards."""
from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import ChecklistItem, Task, TaskStatus

router = APIRouter(prefix="/checklist")
templates = Jinja2Templates(directory="app/templates")


@router.post("/add/{task_id}")
def add_checklist_item(
    task_id: int,
    title: str = Form(...),
    db: Session = Depends(get_db),
):
    max_order = db.query(ChecklistItem).filter_by(task_id=task_id).count()
    item = ChecklistItem(task_id=task_id, title=title, sort_order=max_order)
    db.add(item)
    db.commit()
    return _render_checklist(task_id, db)


@router.post("/toggle/{item_id}")
def toggle_checklist_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ChecklistItem, item_id)
    if not item:
        return HTMLResponse("", status_code=404)

    item.completed = not item.completed
    item.completed_at = datetime.utcnow() if item.completed else None
    db.commit()

    # Check if all items completed
    items = db.query(ChecklistItem).filter_by(task_id=item.task_id).all()
    all_done = len(items) > 0 and all(i.completed for i in items)
    completed = sum(1 for i in items if i.completed)
    total = len(items)

    task = db.get(Task, item.task_id)

    html = _checklist_html(items, task)
    if all_done and task and task.status not in (TaskStatus.done, TaskStatus.archived, TaskStatus.monitoring):
        html += f'''
        <div id="auto-move-prompt" class="mt-3 p-3 bg-mcc-success/10 border border-mcc-success/30 rounded-lg">
            <p class="text-xs text-mcc-success font-medium mb-2">All subtasks done. Move to Done?</p>
            <div class="flex gap-2">
                <button hx-post="/tasks/move" hx-vals='{{"task_id": {item.task_id}, "new_status": "done"}}'
                        hx-target="[data-task-id='{item.task_id}']" hx-swap="outerHTML"
                        class="px-3 py-1 bg-mcc-success text-white text-xs rounded-lg hover:bg-mcc-success/80">
                    Yes, Done
                </button>
                <button onclick="this.closest('#auto-move-prompt').remove()"
                        class="px-3 py-1 bg-mcc-border text-mcc-muted text-xs rounded-lg hover:text-mcc-text">
                    Not Yet
                </button>
            </div>
        </div>'''
    return HTMLResponse(html)


@router.post("/delete/{item_id}")
def delete_checklist_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ChecklistItem, item_id)
    if not item:
        return HTMLResponse("", status_code=404)
    task_id = item.task_id
    db.delete(item)
    db.commit()
    return _render_checklist(task_id, db)


def _render_checklist(task_id: int, db: Session) -> HTMLResponse:
    items = db.query(ChecklistItem).filter_by(task_id=task_id).order_by(ChecklistItem.sort_order).all()
    task = db.get(Task, task_id)
    return HTMLResponse(_checklist_html(items, task))


def _checklist_html(items: list, task=None) -> str:
    if not items:
        return '<div class="text-xs text-mcc-muted py-1">No checklist items</div>'
    completed = sum(1 for i in items if i.completed)
    total = len(items)
    pct = int((completed / total) * 100) if total > 0 else 0
    html = f'''
    <div class="mb-2">
        <div class="flex items-center justify-between text-[10px] text-mcc-muted mb-1">
            <span>{completed}/{total} completed</span>
            <span>{pct}%</span>
        </div>
        <div class="w-full h-1.5 bg-mcc-bg rounded-full overflow-hidden">
            <div class="h-full rounded-full transition-all duration-300
                {"bg-mcc-success" if pct == 100 else "bg-mcc-accent"}"
                 style="width: {pct}%"></div>
        </div>
    </div>'''
    for item in items:
        checked = "checked" if item.completed else ""
        line_through = "line-through text-mcc-muted" if item.completed else ""
        html += f'''
        <div class="flex items-center gap-2 py-1 group">
            <input type="checkbox" {checked}
                   hx-post="/checklist/toggle/{item.id}"
                   hx-target="#checklist-{item.task_id}"
                   hx-swap="innerHTML"
                   class="w-3.5 h-3.5 rounded accent-mcc-accent cursor-pointer">
            <span class="text-xs flex-1 {line_through}">{item.title}</span>
            <button hx-post="/checklist/delete/{item.id}"
                    hx-target="#checklist-{item.task_id}"
                    hx-swap="innerHTML"
                    class="hidden group-hover:block text-mcc-muted hover:text-mcc-critical text-xs px-1">&times;</button>
        </div>'''
    return html


def get_checklist_summary(db: Session, task_id: int) -> dict:
    """Get checklist progress for a task card."""
    items = db.query(ChecklistItem).filter_by(task_id=task_id).all()
    if not items:
        return {"total": 0, "completed": 0, "pct": 0}
    completed = sum(1 for i in items if i.completed)
    return {
        "total": len(items),
        "completed": completed,
        "pct": int((completed / len(items)) * 100),
    }
