from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AIInsight, Task, TaskStatus, TaskPriority

router = APIRouter(prefix="/ai")


@router.post("/insights/{insight_id}/resolve")
def resolve_insight(insight_id: int, db: Session = Depends(get_db)):
    insight = db.get(AIInsight, insight_id)
    if insight:
        insight.acknowledged = True
        insight.resolved_at = datetime.utcnow()
        db.commit()
    return HTMLResponse(
        '<div class="text-[10px] text-mcc-success py-1 text-center">Resolved</div>'
    )


@router.post("/insights/{insight_id}/dismiss")
def dismiss_insight(insight_id: int, db: Session = Depends(get_db)):
    insight = db.get(AIInsight, insight_id)
    if insight:
        insight.dismissed_at = datetime.utcnow()
        insight.acknowledged = True
        db.commit()
    return HTMLResponse("")


@router.post("/insights/{insight_id}/snooze")
def snooze_insight(
    insight_id: int,
    hours: int = Form(24),
    db: Session = Depends(get_db),
):
    insight = db.get(AIInsight, insight_id)
    if insight:
        insight.snoozed_until = datetime.utcnow() + timedelta(hours=hours)
        insight.acknowledged = True
        db.commit()
    label = {24: "24h", 48: "48h", 168: "7d"}.get(hours, f"{hours}h")
    return HTMLResponse(
        f'<div class="text-[10px] text-mcc-warning py-1 text-center">Snoozed {label}</div>'
    )


@router.post("/insights/{insight_id}/create-task")
def insight_create_task(insight_id: int, db: Session = Depends(get_db)):
    """Create a task from an AI insight."""
    insight = db.get(AIInsight, insight_id)
    if not insight:
        return HTMLResponse("<span class='text-red-400'>Not found</span>")

    task = Task(
        project_id=insight.project_id,
        title=f"[AI] {insight.title[:150]}",
        description=insight.body,
        status=TaskStatus.backlog,
        priority=TaskPriority.high if insight.severity.value in ("urgent", "critical") else TaskPriority.medium,
    )
    db.add(task)
    insight.acknowledged = True
    db.commit()

    return HTMLResponse(
        f'<span class="text-mcc-success text-xs">Task #{task.id} created</span>'
    )


@router.post("/insights/{insight_id}/create-task-clint")
def insight_create_task_clint(insight_id: int, db: Session = Depends(get_db)):
    """Create a task from an AI insight, assigned to Clint."""
    insight = db.get(AIInsight, insight_id)
    if not insight:
        return HTMLResponse("<span class='text-red-400'>Not found</span>")

    desc = insight.body
    if insight.suggested_action:
        desc += f"\n\nSuggested action: {insight.suggested_action}"

    task = Task(
        project_id=insight.project_id,
        title=f"[Clint] {insight.title[:140]}",
        description=desc,
        status=TaskStatus.backlog,
        priority=TaskPriority.high if insight.severity.value in ("urgent", "critical") else TaskPriority.medium,
        assigned_to="clint",
    )
    db.add(task)
    insight.acknowledged = True
    db.commit()

    return HTMLResponse(
        f'<span class="text-mcc-success text-xs">Task #{task.id} assigned to Clint</span>'
    )
