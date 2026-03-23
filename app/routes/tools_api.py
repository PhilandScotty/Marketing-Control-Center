"""Autonomous Tools Inbound API — authenticated endpoints for external bots."""
from datetime import datetime
from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models import (
    AutonomousTool, AutonomousToolHealth, ToolMetricLog, ToolAlert,
    AIInsight, InsightType, InsightSourceType, InsightSeverity, Project,
)

router = APIRouter(prefix="/api/tools")


def _get_tool_by_key(api_key: str, db: Session) -> AutonomousTool | None:
    if not api_key:
        return None
    return db.query(AutonomousTool).filter_by(api_key=api_key, is_active=True).first()


class HeartbeatPayload(BaseModel):
    status: str = "online"
    message: Optional[str] = None


class ToolMetricPayload(BaseModel):
    metric_name: str
    value: float
    unit: str = "count"
    context: Optional[dict] = None


class BulkToolMetrics(BaseModel):
    metrics: list[ToolMetricPayload]


class ToolAlertPayload(BaseModel):
    severity: str = "info"
    title: str
    body: Optional[str] = None
    create_insight: bool = True


@router.post("/heartbeat")
def tool_heartbeat(
    payload: HeartbeatPayload,
    x_api_key: str = Header(None),
    db: Session = Depends(get_db),
):
    tool = _get_tool_by_key(x_api_key, db)
    if not tool:
        return JSONResponse({"error": "Invalid or missing API key"}, status_code=401)

    tool.last_heartbeat = datetime.utcnow()
    tool.last_heartbeat_message = payload.message
    tool.total_heartbeats = (tool.total_heartbeats or 0) + 1

    try:
        tool.health = AutonomousToolHealth(payload.status)
    except ValueError:
        tool.health = AutonomousToolHealth.online

    db.commit()

    return JSONResponse({
        "status": "ok",
        "tool": tool.name,
        "health": tool.health.value,
        "heartbeat_count": tool.total_heartbeats,
    })


@router.post("/metrics")
def tool_metrics(
    payload: BulkToolMetrics,
    x_api_key: str = Header(None),
    db: Session = Depends(get_db),
):
    tool = _get_tool_by_key(x_api_key, db)
    if not tool:
        return JSONResponse({"error": "Invalid or missing API key"}, status_code=401)

    recorded = 0
    for m in payload.metrics:
        log = ToolMetricLog(
            tool_id=tool.id,
            metric_name=m.metric_name,
            metric_value=m.value,
            unit=m.unit,
            context=m.context,
        )
        db.add(log)
        recorded += 1

    tool.total_metrics = (tool.total_metrics or 0) + recorded
    tool.last_heartbeat = datetime.utcnow()
    db.commit()

    return JSONResponse({
        "status": "ok",
        "tool": tool.name,
        "recorded": recorded,
    })


@router.post("/alert")
def tool_alert(
    payload: ToolAlertPayload,
    x_api_key: str = Header(None),
    db: Session = Depends(get_db),
):
    tool = _get_tool_by_key(x_api_key, db)
    if not tool:
        return JSONResponse({"error": "Invalid or missing API key"}, status_code=401)

    try:
        severity = InsightSeverity(payload.severity)
    except ValueError:
        severity = InsightSeverity.info

    alert = ToolAlert(
        tool_id=tool.id,
        severity=severity,
        title=payload.title,
        body=payload.body or "",
    )
    db.add(alert)
    tool.total_alerts = (tool.total_alerts or 0) + 1
    tool.last_heartbeat = datetime.utcnow()

    # Optionally create an AI insight for dashboard visibility
    if payload.create_insight:
        project = db.get(Project, tool.project_id)
        if project:
            insight = AIInsight(
                project_id=project.id,
                insight_type=InsightType.stale_automation,
                source_type=InsightSourceType.tool,
                source_id=tool.id,
                title=f"[{tool.name}] {payload.title}",
                body=payload.body or "",
                severity=severity,
            )
            db.add(insight)

    db.commit()

    return JSONResponse({
        "status": "ok",
        "tool": tool.name,
        "alert_id": alert.id,
        "severity": severity.value,
    })


@router.get("/status")
def tools_status(db: Session = Depends(get_db)):
    """Public endpoint: list all registered tools and their health."""
    tools = db.query(AutonomousTool).filter_by(is_active=True).all()
    now = datetime.utcnow()

    result = []
    for t in tools:
        hours_since = None
        is_overdue = False
        if t.last_heartbeat:
            hours_since = round((now - t.last_heartbeat).total_seconds() / 3600, 1)
            if t.expected_heartbeat_hours and hours_since > t.expected_heartbeat_hours:
                is_overdue = True

        result.append({
            "name": t.name,
            "type": t.tool_type.value,
            "health": t.health.value,
            "last_heartbeat": t.last_heartbeat.isoformat() if t.last_heartbeat else None,
            "hours_since_heartbeat": hours_since,
            "is_overdue": is_overdue,
            "total_heartbeats": t.total_heartbeats,
            "total_metrics": t.total_metrics,
            "total_alerts": t.total_alerts,
        })

    return JSONResponse({"tools": result})
