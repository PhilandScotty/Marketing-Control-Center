"""Project wizard — 7-step guided project creation with AI assistance."""
from datetime import date, datetime
import json

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Project, Channel, Tool, Task, Automation, EmailSequence,
    OnboardingMilestone, BudgetAllocation,
    ChannelType, ChannelStatus, AutomationLevel,
    ToolCategory, BillingCycle, ToolStatus,
    TaskStatus, TaskPriority,
    AutomationType, AutomationHealth,
    SequenceType, SequenceStatus,
    BudgetCategory,
)

router = APIRouter(prefix="/wizard")
templates = Jinja2Templates(directory="app/templates")

WIZARD_STEPS = [
    {"step": 1, "key": "product", "title": "Product Definition", "description": "Name, slug, launch date, budget, description"},
    {"step": 2, "key": "channels", "title": "Channel Selection", "description": "Choose marketing channels to activate"},
    {"step": 3, "key": "tools", "title": "Tool Stack", "description": "Select tools for each channel"},
    {"step": 4, "key": "milestones", "title": "Milestones", "description": "Set key milestones and launch date"},
    {"step": 5, "key": "tasks", "title": "Task Generation", "description": "Generate initial tasks from patterns"},
    {"step": 6, "key": "automations", "title": "Automation Planning", "description": "Plan automations and sequences"},
    {"step": 7, "key": "review", "title": "Review & Launch", "description": "Review everything and create project"},
]


@router.get("/")
def wizard_start(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    return templates.TemplateResponse("wizard.html", {
        "request": request,
        "project": project,
        "steps": WIZARD_STEPS,
        "current_step": 1,
        "current_page": "projects",
        "today": date.today(),
    })


@router.get("/step/{step_num}")
def wizard_step(step_num: int, request: Request, db: Session = Depends(get_db)):
    if step_num < 1 or step_num > 7:
        step_num = 1

    project = db.query(Project).filter_by(slug="grindlab").first()

    # For step 2, get channel types
    channel_types = [t.value for t in ChannelType]
    tool_categories = [t.value for t in ToolCategory]
    budget_categories = [t.value for t in BudgetCategory]

    # For template system: list existing projects as template sources
    existing_projects = db.query(Project).all()

    return templates.TemplateResponse("partials/wizard_step.html", {
        "request": request,
        "project": project,
        "steps": WIZARD_STEPS,
        "current_step": step_num,
        "step_info": WIZARD_STEPS[step_num - 1],
        "channel_types": channel_types,
        "tool_categories": tool_categories,
        "budget_categories": budget_categories,
        "existing_projects": existing_projects,
    })


@router.post("/create-project")
def create_project_from_wizard(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    slug: str = Form(...),
    launch_date: str = Form(""),
    monthly_budget: float = Form(0),
    notes: str = Form(""),
    channels_json: str = Form("[]"),
    tools_json: str = Form("[]"),
    tasks_json: str = Form("[]"),
    automations_json: str = Form("[]"),
    budget_json: str = Form("[]"),
):
    """Create a fully populated project from wizard data."""
    # Check slug uniqueness
    existing = db.query(Project).filter_by(slug=slug).first()
    if existing:
        return HTMLResponse(
            f'<div class="text-red-400 text-sm">Slug "{slug}" already exists</div>'
        )

    # Parse launch date
    ld = None
    if launch_date:
        try:
            ld = date.fromisoformat(launch_date)
        except ValueError:
            pass

    project = Project(
        name=name,
        slug=slug,
        launch_date=ld,
        monthly_budget=monthly_budget,
        notes=notes,
    )
    db.add(project)
    db.flush()
    pid = project.id

    # Channels
    try:
        channels_data = json.loads(channels_json)
        for ch in channels_data:
            channel = Channel(
                project_id=pid,
                name=ch.get("name", ""),
                channel_type=ChannelType(ch.get("type", "content")),
                status=ChannelStatus.planned,
                owner="phil",
            )
            db.add(channel)
    except (json.JSONDecodeError, ValueError):
        pass

    # Tools
    try:
        tools_data = json.loads(tools_json)
        for t in tools_data:
            tool = Tool(
                project_id=pid,
                name=t.get("name", ""),
                category=ToolCategory(t.get("category", "dev_tools")),
                status=ToolStatus.planned,
            )
            db.add(tool)
    except (json.JSONDecodeError, ValueError):
        pass

    # Tasks
    try:
        tasks_data = json.loads(tasks_json)
        for t in tasks_data:
            task = Task(
                project_id=pid,
                title=t.get("title", ""),
                description=t.get("description", ""),
                priority=TaskPriority(t.get("priority", "medium")),
                status=TaskStatus.backlog,
            )
            db.add(task)
    except (json.JSONDecodeError, ValueError):
        pass

    # Budget allocations
    try:
        budget_data = json.loads(budget_json)
        for b in budget_data:
            alloc = BudgetAllocation(
                project_id=pid,
                category=BudgetCategory(b.get("category", "reserve")),
                planned_monthly=b.get("amount", 0),
                period_start=date.today(),
            )
            db.add(alloc)
    except (json.JSONDecodeError, ValueError):
        pass

    db.commit()

    return HTMLResponse(f'<script>window.location.href="/";</script>')


@router.post("/create-from-template")
def create_from_template(
    request: Request,
    db: Session = Depends(get_db),
    source_slug: str = Form(...),
    name: str = Form(...),
    slug: str = Form(...),
    launch_date: str = Form(""),
    monthly_budget: float = Form(0),
):
    """Create a new project by cloning an existing one as a template."""
    source = db.query(Project).filter_by(slug=source_slug).first()
    if not source:
        return HTMLResponse('<div class="text-red-400">Source project not found</div>')

    existing = db.query(Project).filter_by(slug=slug).first()
    if existing:
        return HTMLResponse(f'<div class="text-red-400">Slug "{slug}" already exists</div>')

    ld = None
    if launch_date:
        try:
            ld = date.fromisoformat(launch_date)
        except ValueError:
            pass

    project = Project(
        name=name,
        slug=slug,
        launch_date=ld,
        monthly_budget=monthly_budget,
    )
    db.add(project)
    db.flush()
    pid = project.id

    # Clone channels
    for ch in db.query(Channel).filter_by(project_id=source.id).all():
        new_ch = Channel(
            project_id=pid,
            name=ch.name,
            channel_type=ch.channel_type,
            status=ChannelStatus.planned,
            automation_level=ch.automation_level,
            owner=ch.owner,
            daily_actions=ch.daily_actions,
            auto_actions=ch.auto_actions,
        )
        db.add(new_ch)

    # Clone tools
    for t in db.query(Tool).filter_by(project_id=source.id).all():
        new_t = Tool(
            project_id=pid,
            name=t.name,
            category=t.category,
            purpose=t.purpose,
            monthly_cost=t.monthly_cost,
            billing_cycle=t.billing_cycle,
            status=ToolStatus.planned,
        )
        db.add(new_t)

    # Clone automations (as templates)
    for a in db.query(Automation).filter_by(project_id=source.id).all():
        new_a = Automation(
            project_id=pid,
            name=a.name,
            automation_type=a.automation_type,
            platform=a.platform,
            schedule=a.schedule,
            expected_run_interval_hours=a.expected_run_interval_hours,
            owner=a.owner,
        )
        db.add(new_a)

    # Clone budget allocations
    for b in db.query(BudgetAllocation).filter_by(project_id=source.id).all():
        new_b = BudgetAllocation(
            project_id=pid,
            category=b.category,
            planned_monthly=b.planned_monthly,
            period_start=date.today(),
        )
        db.add(new_b)

    # Clone onboarding milestones
    for m in db.query(OnboardingMilestone).filter_by(project_id=source.id).all():
        new_m = OnboardingMilestone(
            project_id=pid,
            name=m.name,
            description=m.description,
            target_days_from_start=m.target_days_from_start,
            display_order=m.display_order,
        )
        db.add(new_m)

    db.commit()

    return HTMLResponse(f'<script>window.location.href="/";</script>')
