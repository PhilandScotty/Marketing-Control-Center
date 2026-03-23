"""Autonomous Tool management — registry UI, add/edit/delete."""
import uuid
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Project, AutonomousTool, AutonomousToolType, AutonomousToolHealth,
    ToolMetricLog, ToolAlert,
)

router = APIRouter(prefix="/tools")
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def tools_registry(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("tools_registry.html", {
            "request": request, "project": None, "current_page": "tools",
            "today": date.today(),
        })

    tools = db.query(AutonomousTool).filter_by(
        project_id=project.id, is_active=True
    ).order_by(AutonomousTool.name).all()

    now = datetime.utcnow()
    tool_data = []
    for t in tools:
        hours_since = None
        is_overdue = False
        if t.last_heartbeat:
            hours_since = round((now - t.last_heartbeat).total_seconds() / 3600, 1)
            if t.expected_heartbeat_hours and hours_since > t.expected_heartbeat_hours:
                is_overdue = True

        tool_data.append({
            "tool": t,
            "hours_since": hours_since,
            "is_overdue": is_overdue,
        })

    health_counts = {"online": 0, "degraded": 0, "offline": 0, "unknown": 0}
    for t in tools:
        health_counts[t.health.value] = health_counts.get(t.health.value, 0) + 1

    return templates.TemplateResponse("tools_registry.html", {
        "request": request,
        "project": project,
        "tool_data": tool_data,
        "health_counts": health_counts,
        "total": len(tools),
        "tool_types": [e.value for e in AutonomousToolType],
        "current_page": "tools",
        "today": date.today(),
    })


@router.post("/add")
def add_tool(
    name: str = Form(...),
    tool_type: str = Form("bot"),
    platform: str = Form(""),
    workspace_path: str = Form(""),
    api_endpoint: str = Form(""),
    expected_heartbeat_hours: int = Form(None),
    owner: str = Form("phil"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return RedirectResponse("/tools", status_code=303)

    api_key = uuid.uuid4().hex

    try:
        tt = AutonomousToolType(tool_type)
    except ValueError:
        tt = AutonomousToolType.bot

    tool = AutonomousTool(
        project_id=project.id,
        name=name,
        tool_type=tt,
        platform=platform,
        workspace_path=workspace_path or None,
        api_endpoint=api_endpoint or None,
        expected_heartbeat_hours=expected_heartbeat_hours,
        owner=owner,
        notes=notes,
        api_key=api_key,
    )
    db.add(tool)
    db.commit()

    return RedirectResponse(f"/tools/{tool.id}", status_code=303)


@router.get("/{tool_id}")
def tool_detail(tool_id: int, request: Request, db: Session = Depends(get_db)):
    tool = db.get(AutonomousTool, tool_id)
    if not tool:
        return RedirectResponse("/tools", status_code=303)

    project = db.get(Project, tool.project_id)

    # Recent metrics
    recent_metrics = db.query(ToolMetricLog).filter_by(
        tool_id=tool.id
    ).order_by(ToolMetricLog.recorded_at.desc()).limit(50).all()

    # Recent alerts
    recent_alerts = db.query(ToolAlert).filter_by(
        tool_id=tool.id
    ).order_by(ToolAlert.created_at.desc()).limit(20).all()

    # Heartbeat status
    now = datetime.utcnow()
    hours_since = None
    is_overdue = False
    if tool.last_heartbeat:
        hours_since = round((now - tool.last_heartbeat).total_seconds() / 3600, 1)
        if tool.expected_heartbeat_hours and hours_since > tool.expected_heartbeat_hours:
            is_overdue = True

    return templates.TemplateResponse("tool_detail.html", {
        "request": request,
        "project": project,
        "tool": tool,
        "recent_metrics": recent_metrics,
        "recent_alerts": recent_alerts,
        "hours_since": hours_since,
        "is_overdue": is_overdue,
        "tool_types": [e.value for e in AutonomousToolType],
        "current_page": "tools",
        "today": date.today(),
    })


@router.post("/{tool_id}/edit")
def edit_tool(
    tool_id: int,
    name: str = Form(...),
    tool_type: str = Form("bot"),
    platform: str = Form(""),
    workspace_path: str = Form(""),
    api_endpoint: str = Form(""),
    expected_heartbeat_hours: int = Form(None),
    owner: str = Form("phil"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    tool = db.get(AutonomousTool, tool_id)
    if not tool:
        return RedirectResponse("/tools", status_code=303)

    tool.name = name
    try:
        tool.tool_type = AutonomousToolType(tool_type)
    except ValueError:
        pass
    tool.platform = platform
    tool.workspace_path = workspace_path or None
    tool.api_endpoint = api_endpoint or None
    tool.expected_heartbeat_hours = expected_heartbeat_hours
    tool.owner = owner
    tool.notes = notes
    db.commit()

    return RedirectResponse(f"/tools/{tool_id}", status_code=303)


@router.post("/{tool_id}/delete")
def delete_tool(tool_id: int, db: Session = Depends(get_db)):
    tool = db.get(AutonomousTool, tool_id)
    if tool:
        tool.is_active = False
        db.commit()
    return RedirectResponse("/tools", status_code=303)


@router.post("/{tool_id}/regenerate-key")
def regenerate_key(tool_id: int, db: Session = Depends(get_db)):
    tool = db.get(AutonomousTool, tool_id)
    if tool:
        tool.api_key = uuid.uuid4().hex
        db.commit()
    return RedirectResponse(f"/tools/{tool_id}", status_code=303)


@router.post("/alerts/{alert_id}/ack")
def ack_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(ToolAlert, alert_id)
    if alert:
        alert.acknowledged = True
        db.commit()
    return HTMLResponse('<span class="text-[10px] text-mcc-muted">Acknowledged</span>')
