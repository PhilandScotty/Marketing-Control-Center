"""Launch template routes — save, view, edit, and apply project templates."""
from datetime import date, datetime, timedelta
import json

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import (
    Project, Task, Channel, ChecklistItem,
    LaunchTemplate, TemplateTask,
    TaskStatus, TaskPriority,
)

router = APIRouter(prefix="/templates")
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def list_templates(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    all_templates = db.query(LaunchTemplate).order_by(LaunchTemplate.created_at.desc()).all()

    template_details = []
    for t in all_templates:
        task_count = db.query(TemplateTask).filter_by(template_id=t.id).count()
        template_details.append({"template": t, "task_count": task_count})

    return templates.TemplateResponse("templates.html", {
        "request": request,
        "project": project,
        "templates": template_details,
        "current_page": "templates",
        "today": date.today(),
    })


@router.get("/{template_id}")
def view_template(template_id: int, request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    tmpl = db.get(LaunchTemplate, template_id)
    if not tmpl:
        return HTMLResponse("Template not found", status_code=404)

    tasks = db.query(TemplateTask).filter_by(template_id=template_id).order_by(
        TemplateTask.relative_day, TemplateTask.priority
    ).all()

    return templates.TemplateResponse("template_detail.html", {
        "request": request,
        "project": project,
        "tmpl": tmpl,
        "tasks": tasks,
        "priorities": [(p.value, p.value.replace("_", " ").title()) for p in TaskPriority],
        "current_page": "templates",
        "today": date.today(),
    })


@router.post("/save-from-project")
def save_template_from_project(
    name: str = Form(...),
    description: str = Form(""),
    project_slug: str = Form("grindlab"),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter_by(slug=project_slug).first()
    if not project:
        return HTMLResponse("Project not found", status_code=404)

    tmpl = LaunchTemplate(
        name=name,
        description=description,
        created_from_project_id=project.id,
    )
    db.add(tmpl)
    db.flush()

    # Calculate relative days from launch date
    launch = project.launch_date or date.today()

    tasks = db.query(Task).filter_by(project_id=project.id).all()
    for task in tasks:
        if task.status == TaskStatus.recurring:
            continue  # Skip recurring for templates

        relative_day = 0
        if task.due_date:
            relative_day = (task.due_date - launch).days

        # Get checklist items
        checklist = db.query(ChecklistItem).filter_by(task_id=task.id).order_by(
            ChecklistItem.sort_order
        ).all()
        checklist_titles = [c.title for c in checklist]

        channel = None
        if task.channel_id:
            ch = db.query(Channel).get(task.channel_id)
            if ch:
                channel = ch.channel_type.value if ch.channel_type else None

        tt = TemplateTask(
            template_id=tmpl.id,
            title=task.title,
            description=task.description,
            relative_day=relative_day,
            priority=task.priority,
            assigned_role=task.assigned_to or "founder",
            channel_type=channel,
            checklist_items=checklist_titles,
            dependencies=[],
        )
        db.add(tt)

    db.commit()
    return HTMLResponse(f'<script>window.location.href="/templates/{tmpl.id}";</script>')


@router.post("/apply/{template_id}")
def apply_template(
    template_id: int,
    project_slug: str = Form(...),
    launch_date: str = Form(""),
    db: Session = Depends(get_db),
):
    tmpl = db.get(LaunchTemplate, template_id)
    if not tmpl:
        return HTMLResponse("Template not found", status_code=404)

    project = db.query(Project).filter_by(slug=project_slug).first()
    if not project:
        return HTMLResponse("Project not found", status_code=404)

    ld = project.launch_date or date.today()
    if launch_date:
        try:
            ld = date.fromisoformat(launch_date)
        except ValueError:
            pass

    template_tasks = db.query(TemplateTask).filter_by(template_id=template_id).all()

    # Map channels by type
    channels = db.query(Channel).filter_by(project_id=project.id).all()
    channel_by_type = {}
    for ch in channels:
        if ch.channel_type:
            channel_by_type[ch.channel_type.value] = ch

    for tt in template_tasks:
        due = ld + timedelta(days=tt.relative_day)
        channel_id = None
        if tt.channel_type and tt.channel_type in channel_by_type:
            channel_id = channel_by_type[tt.channel_type].id

        task = Task(
            project_id=project.id,
            channel_id=channel_id,
            title=tt.title,
            description=tt.description,
            status=TaskStatus.backlog,
            priority=tt.priority,
            assigned_to=tt.assigned_role,
            due_date=due,
        )
        db.add(task)
        db.flush()

        # Create checklist items
        for i, item_title in enumerate(tt.checklist_items or []):
            ci = ChecklistItem(
                task_id=task.id,
                title=item_title,
                sort_order=i,
            )
            db.add(ci)

    db.commit()
    return HTMLResponse(f'<script>window.location.href="/tasks";</script>')


@router.post("/{template_id}/add-task")
def add_template_task(
    template_id: int,
    title: str = Form(...),
    description: str = Form(""),
    relative_day: int = Form(0),
    priority: str = Form("medium"),
    assigned_role: str = Form("founder"),
    db: Session = Depends(get_db),
):
    tt = TemplateTask(
        template_id=template_id,
        title=title,
        description=description,
        relative_day=relative_day,
        priority=TaskPriority(priority),
        assigned_role=assigned_role,
    )
    db.add(tt)
    db.commit()
    return HTMLResponse(f'<script>window.location.href="/templates/{template_id}";</script>')


@router.post("/{template_id}/delete-task/{task_id}")
def delete_template_task(template_id: int, task_id: int, db: Session = Depends(get_db)):
    tt = db.get(TemplateTask, task_id)
    if tt and tt.template_id == template_id:
        db.delete(tt)
        db.commit()
    return HTMLResponse(f'<script>window.location.href="/templates/{template_id}";</script>')


@router.post("/{template_id}/delete")
def delete_template(template_id: int, db: Session = Depends(get_db)):
    tmpl = db.get(LaunchTemplate, template_id)
    if tmpl:
        db.query(TemplateTask).filter_by(template_id=template_id).delete()
        db.delete(tmpl)
        db.commit()
    return HTMLResponse('<script>window.location.href="/templates";</script>')
