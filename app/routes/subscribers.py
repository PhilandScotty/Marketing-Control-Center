from datetime import date
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import (
    Project, SubscriberSnapshot, SubscriberEvent, Metric,
    SubscriberStage, Channel,
)

router = APIRouter(prefix="/subscribers")
templates = Jinja2Templates(directory="app/templates")

STAGE_DISPLAY = {
    "waitlist_lead": {"label": "Waitlist / Lead", "color": "#6B6B8A"},
    "free_trial_active": {"label": "Free Trial (Active)", "color": "#164E63"},
    "free_trial_expired": {"label": "Free Trial (Expired)", "color": "#F59E0B"},
    "paid_basic": {"label": "Paid Basic", "color": "#10B981"},
    "paid_premium": {"label": "Paid Premium", "color": "#06B6D4"},
    "churned": {"label": "Churned", "color": "#EF4444"},
    "paused": {"label": "Paused", "color": "#3A3A5A"},
}


@router.get("/")
def subscribers_view(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("subscribers.html", {
            "request": request, "project": None, "current_page": "subscribers",
            "today": date.today(),
        })

    pid = project.id

    # Get latest snapshot per stage
    latest_date = db.query(func.max(SubscriberSnapshot.snapshot_date)).filter_by(
        project_id=pid
    ).scalar()

    stages = []
    total_subs = 0
    if latest_date:
        snapshots = db.query(SubscriberSnapshot).filter_by(
            project_id=pid, snapshot_date=latest_date
        ).all()
        for snap in snapshots:
            stage_info = STAGE_DISPLAY.get(snap.stage.value, {})
            stages.append({
                "stage": snap.stage.value,
                "label": stage_info.get("label", snap.stage.value),
                "color": stage_info.get("color", "#8B8B9E"),
                "count": snap.count,
                "mrr": float(snap.mrr) if snap.mrr else 0,
            })
            total_subs += snap.count
    else:
        # No snapshot data yet — show email subscriber count from metrics as waitlist
        email_channel = db.query(Channel).filter(
            Channel.project_id == pid,
            Channel.name.ilike("%email nurture%"),
        ).first()
        if email_channel:
            latest_metric = db.query(Metric).filter(
                Metric.channel_id == email_channel.id,
                Metric.metric_name == "subscribers",
            ).order_by(Metric.recorded_at.desc()).first()
            if latest_metric:
                count = int(latest_metric.metric_value)
                stages.append({
                    "stage": "waitlist_lead",
                    "label": "Waitlist / Lead",
                    "color": "#8B8B9E",
                    "count": count,
                    "mrr": 0,
                })
                total_subs = count

        # Fill remaining stages with zero
        for stage_key, info in STAGE_DISPLAY.items():
            if not any(s["stage"] == stage_key for s in stages):
                stages.append({
                    "stage": stage_key,
                    "label": info["label"],
                    "color": info["color"],
                    "count": 0,
                    "mrr": 0,
                })

    # Sort by funnel order
    stage_order = list(STAGE_DISPLAY.keys())
    stages.sort(key=lambda s: stage_order.index(s["stage"]) if s["stage"] in stage_order else 99)

    # Recent events
    recent_events = db.query(SubscriberEvent).filter_by(
        project_id=pid
    ).order_by(SubscriberEvent.occurred_at.desc()).limit(20).all()

    # Total MRR
    total_mrr = sum(s["mrr"] for s in stages)

    return templates.TemplateResponse("subscribers.html", {
        "request": request,
        "project": project,
        "stages": stages,
        "total_subs": total_subs,
        "total_mrr": total_mrr,
        "recent_events": recent_events,
        "current_page": "subscribers",
        "today": date.today(),
    })
