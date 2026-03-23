"""External API endpoints — for Scotty and other automation tools."""
from datetime import date, datetime
from fastapi import APIRouter, Depends, Body
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models import (
    Project, Channel, Metric, Automation, MetricSource,
    AutomationHealth, AIInsight, InsightType, InsightSourceType, InsightSeverity,
    HealthStatus, Task, TaskStatus, EmailSequence, SubscriberSnapshot,
    SubscriberStage, AdCampaign, AutonomousTool,
)
from app.scheduler import get_integration_status
from app.routes.dashboard import calc_execution_score

router = APIRouter(prefix="/api")


class MetricRecord(BaseModel):
    channel_name: str
    metric_name: str
    value: float
    unit: str = "count"


class HeartbeatPayload(BaseModel):
    automation_name: str
    status: str = "running"
    message: Optional[str] = None


class BulkMetrics(BaseModel):
    metrics: list[MetricRecord]


@router.post("/metrics/record")
def api_record_metric(payload: MetricRecord, db: Session = Depends(get_db)):
    """Record a single metric from an external source (e.g., Scotty)."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return JSONResponse({"error": "No project"}, status_code=404)

    channel = db.query(Channel).filter(
        Channel.project_id == project.id,
        Channel.name == payload.channel_name,
    ).first()
    if not channel:
        return JSONResponse(
            {"error": f"Channel '{payload.channel_name}' not found"},
            status_code=404,
        )

    # Get previous value
    prev = db.query(Metric).filter_by(
        channel_id=channel.id,
        metric_name=payload.metric_name,
    ).order_by(Metric.recorded_at.desc()).first()

    metric = Metric(
        channel_id=channel.id,
        metric_name=payload.metric_name,
        metric_value=payload.value,
        previous_value=prev.metric_value if prev else None,
        unit=payload.unit,
        source=MetricSource.api,
    )
    db.add(metric)
    db.commit()

    return JSONResponse({
        "status": "ok",
        "metric_id": metric.id,
        "channel": channel.name,
        "metric": payload.metric_name,
        "value": payload.value,
    })


@router.post("/metrics/bulk")
def api_record_bulk(payload: BulkMetrics, db: Session = Depends(get_db)):
    """Record multiple metrics at once."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return JSONResponse({"error": "No project"}, status_code=404)

    channels = db.query(Channel).filter_by(project_id=project.id).all()
    channel_map = {c.name: c for c in channels}

    recorded = 0
    errors = []
    for m in payload.metrics:
        channel = channel_map.get(m.channel_name)
        if not channel:
            errors.append(f"Channel '{m.channel_name}' not found")
            continue

        prev = db.query(Metric).filter_by(
            channel_id=channel.id,
            metric_name=m.metric_name,
        ).order_by(Metric.recorded_at.desc()).first()

        metric = Metric(
            channel_id=channel.id,
            metric_name=m.metric_name,
            metric_value=m.value,
            previous_value=prev.metric_value if prev else None,
            unit=m.unit,
            source=MetricSource.api,
        )
        db.add(metric)
        recorded += 1

    db.commit()

    return JSONResponse({
        "status": "ok",
        "recorded": recorded,
        "errors": errors,
    })


@router.post("/automations/heartbeat")
def api_heartbeat(payload: HeartbeatPayload, db: Session = Depends(get_db)):
    """Record an automation heartbeat from Scotty or other tools."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return JSONResponse({"error": "No project"}, status_code=404)

    auto = db.query(Automation).filter(
        Automation.project_id == project.id,
        Automation.name == payload.automation_name,
    ).first()

    if not auto:
        return JSONResponse(
            {"error": f"Automation '{payload.automation_name}' not found"},
            status_code=404,
        )

    auto.last_confirmed_run = datetime.utcnow()

    try:
        auto.health = AutomationHealth(payload.status)
    except ValueError:
        auto.health = AutomationHealth.running

    # If reporting failure, check for consecutive failures pattern
    if payload.status == "failed":
        # Create insight on failure
        insight = AIInsight(
            project_id=project.id,
            insight_type=InsightType.stale_automation,
            source_type=InsightSourceType.automation,
            source_id=auto.id,
            title=f"Automation failed: {auto.name}",
            body=payload.message or f"Automation '{auto.name}' reported a failure.",
            severity=InsightSeverity.attention,
        )
        db.add(insight)

    db.commit()

    return JSONResponse({
        "status": "ok",
        "automation": auto.name,
        "health": auto.health.value,
        "last_run": auto.last_confirmed_run.isoformat(),
    })


@router.get("/status/summary")
def api_status_summary(db: Session = Depends(get_db)):
    """Full project status summary — JSON snapshot for export and integrations."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return JSONResponse({"error": "No project"}, status_code=404)

    pid = project.id
    today = date.today()

    # Execution score
    exec_score = calc_execution_score(db, pid)

    # Channel health
    channels = db.query(Channel).filter_by(project_id=pid).all()
    channel_summary = []
    for ch in channels:
        channel_summary.append({
            "name": ch.name,
            "type": ch.channel_type.value if ch.channel_type else None,
            "status": ch.status.value if ch.status else None,
            "health": ch.health.value if ch.health else "unknown",
            "automation_level": ch.automation_level.value if ch.automation_level else None,
        })

    # Task counts by status
    tasks = db.query(Task).filter_by(project_id=pid).all()
    task_counts = {}
    for t in tasks:
        s = t.status.value
        task_counts[s] = task_counts.get(s, 0) + 1

    # Overdue tasks
    overdue = [
        {
            "title": t.title,
            "priority": t.priority.value,
            "due_date": t.due_date.isoformat(),
            "days_overdue": (today - t.due_date).days,
            "assigned_to": t.assigned_to,
        }
        for t in tasks
        if t.due_date and t.due_date < today and t.status not in (TaskStatus.done, TaskStatus.archived, TaskStatus.recurring)
    ]
    overdue.sort(key=lambda x: x["days_overdue"], reverse=True)

    # Automation health
    automations = db.query(Automation).filter_by(project_id=pid).all()
    auto_summary = []
    for a in automations:
        auto_summary.append({
            "name": a.name,
            "platform": a.platform,
            "health": a.health.value if a.health else "unknown",
            "last_run": a.last_confirmed_run.isoformat() if a.last_confirmed_run else None,
        })

    # Subscriber count
    latest_snapshot = db.query(SubscriberSnapshot).filter_by(
        project_id=pid
    ).order_by(SubscriberSnapshot.snapshot_date.desc()).first()
    subscriber_count = latest_snapshot.total_count if latest_snapshot else 0

    # Sequences
    sequences = db.query(EmailSequence).filter_by(project_id=pid).all()
    seq_summary = [
        {"name": s.name, "status": s.status.value, "email_count": s.email_count}
        for s in sequences
    ]

    # Ad campaigns
    campaigns = db.query(AdCampaign).filter_by(project_id=pid).all()
    ad_summary = [
        {
            "name": c.campaign_name,
            "platform": c.platform.value,
            "status": c.status.value,
            "signal": c.signal.value if c.signal else "hold",
            "spend": float(c.spend_to_date or 0),
            "conversions": c.conversions or 0,
        }
        for c in campaigns
    ]

    # Recent AI insights (unacknowledged)
    insights = db.query(AIInsight).filter(
        AIInsight.project_id == pid,
        AIInsight.acknowledged == False,
    ).order_by(AIInsight.created_at.desc()).limit(10).all()
    insight_summary = [
        {
            "title": i.title,
            "severity": i.severity.value,
            "type": i.insight_type.value,
            "body": i.body[:200] if i.body else "",
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in insights
    ]

    # Connected tools
    tools = db.query(AutonomousTool).filter_by(project_id=pid, is_active=True).all()
    now = datetime.utcnow()
    tools_summary = []
    for t in tools:
        hours_since = None
        is_overdue = False
        if t.last_heartbeat:
            hours_since = round((now - t.last_heartbeat).total_seconds() / 3600, 1)
            if t.expected_heartbeat_hours and hours_since > t.expected_heartbeat_hours:
                is_overdue = True
        tools_summary.append({
            "name": t.name,
            "type": t.tool_type.value,
            "health": t.health.value,
            "last_heartbeat": t.last_heartbeat.isoformat() if t.last_heartbeat else None,
            "hours_since_heartbeat": hours_since,
            "is_overdue": is_overdue,
        })

    return JSONResponse({
        "project": project.name,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "launch_date": project.launch_date.isoformat() if project.launch_date else None,
        "days_to_launch": (project.launch_date - today).days if project.launch_date else None,
        "execution_score": exec_score,
        "channels": channel_summary,
        "tasks": {
            "total": len(tasks),
            "by_status": task_counts,
            "overdue": overdue,
        },
        "automations": auto_summary,
        "connected_tools": tools_summary,
        "subscribers": subscriber_count,
        "sequences": seq_summary,
        "ad_campaigns": ad_summary,
        "ai_insights": insight_summary,
    })


@router.get("/integrations/status")
def api_integration_status():
    """Get the status of all configured integrations."""
    return JSONResponse({"integrations": get_integration_status()})


@router.get("/health")
def api_health():
    """Simple health check endpoint."""
    return JSONResponse({"status": "ok", "service": "mcc"})
