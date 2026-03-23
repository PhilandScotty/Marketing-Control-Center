from datetime import date, datetime, timedelta
from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Project, Channel, Automation, AutonomousTool, AutonomousToolHealth,
    AutomationType, AutomationHealth, HealthCheckMethod,
)

router = APIRouter(prefix="/automations")
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def automations_list(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("automations.html", {
            "request": request, "project": None, "current_page": "automations",
            "today": date.today(),
        })

    pid = project.id
    now = datetime.utcnow()

    automations = db.query(Automation).filter_by(project_id=pid).order_by(
        Automation.health, Automation.name
    ).all()

    channels = db.query(Channel).filter_by(project_id=pid).all()
    channel_map = {c.id: c for c in channels}

    # Build timeline and health data
    auto_data = []
    for auto in automations:
        next_expected = None
        if auto.last_confirmed_run and auto.expected_run_interval_hours:
            next_expected = auto.last_confirmed_run + timedelta(hours=auto.expected_run_interval_hours)

        hours_since_run = None
        if auto.last_confirmed_run:
            hours_since_run = round((now - auto.last_confirmed_run).total_seconds() / 3600, 1)

        is_overdue = False
        if next_expected and now > next_expected:
            is_overdue = True

        ch_name = channel_map[auto.channel_id].name if auto.channel_id and auto.channel_id in channel_map else "General"

        auto_data.append({
            "auto": auto,
            "channel_name": ch_name,
            "next_expected": next_expected,
            "hours_since_run": hours_since_run,
            "is_overdue": is_overdue,
        })

    # Summary counts
    health_counts = {h.value: 0 for h in AutomationHealth}
    for a in automations:
        health_counts[a.health.value] = health_counts.get(a.health.value, 0) + 1

    # Connected tools
    tools = db.query(AutonomousTool).filter_by(
        project_id=pid, is_active=True
    ).all()
    connected_tools = []
    for t in tools:
        hours_since = None
        if t.last_heartbeat:
            hours_since = round((now - t.last_heartbeat).total_seconds() / 3600, 1)
        connected_tools.append({"tool": t, "hours_since": hours_since})

    return templates.TemplateResponse("automations.html", {
        "request": request,
        "project": project,
        "auto_data": auto_data,
        "health_counts": health_counts,
        "total": len(automations),
        "connected_tools": connected_tools,
        "now": now,
        "current_page": "automations",
        "today": date.today(),
    })


@router.post("/confirm-run/{auto_id}")
def confirm_run(auto_id: int, db: Session = Depends(get_db)):
    auto = db.get(Automation, auto_id)
    if auto:
        auto.last_confirmed_run = datetime.utcnow()
        auto.health = AutomationHealth.running
        db.commit()
    return HTMLResponse(
        f'<span class="text-mcc-success text-[10px]">Confirmed {datetime.utcnow().strftime("%b %d %H:%M")}</span>'
    )


@router.post("/set-health/{auto_id}")
def set_health(auto_id: int, health: str = Form(...), db: Session = Depends(get_db)):
    auto = db.get(Automation, auto_id)
    if auto:
        try:
            auto.health = AutomationHealth(health)
        except ValueError:
            pass
        db.commit()
    return HTMLResponse(
        f'<span class="text-[10px] text-mcc-success">Updated</span>'
    )
