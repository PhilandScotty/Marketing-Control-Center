"""Retention/engagement view — segment distribution, trends, churn insights."""
from datetime import date, datetime, timedelta
from collections import defaultdict

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import (
    Project, SubscriberSnapshot, SubscriberEvent, SubscriberStage,
    SubscriberEventType, LeadScore, LeadTier,
)

router = APIRouter(prefix="/retention")
templates = Jinja2Templates(directory="app/templates")

SEGMENT_RULES = {
    "power": {"label": "Power Users", "color": "#06B6D4", "description": "Paid + active in last 7 days"},
    "active": {"label": "Active", "color": "#10B981", "description": "Active in last 14 days"},
    "at_risk": {"label": "At Risk", "color": "#F59E0B", "description": "No activity in 14-30 days"},
    "dormant": {"label": "Dormant", "color": "#6B6B8A", "description": "No activity in 30-60 days"},
    "churned": {"label": "Churned", "color": "#EF4444", "description": "Churned or 60+ days inactive"},
}


@router.get("/")
def retention_view(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("retention.html", {
            "request": request, "project": None,
            "current_page": "subscribers", "today": date.today(),
        })

    pid = project.id
    now = datetime.utcnow()

    # Segment distribution from lead scores
    segments = {}
    lead_scores = db.query(LeadScore).filter_by(project_id=pid).all()

    segment_counts = defaultdict(int)
    for ls in lead_scores:
        days_inactive = (now - ls.last_activity_at).days if ls.last_activity_at else 999

        if ls.tier in (LeadTier.hot,) and days_inactive <= 7:
            segment_counts["power"] += 1
        elif days_inactive <= 14:
            segment_counts["active"] += 1
        elif days_inactive <= 30:
            segment_counts["at_risk"] += 1
        elif days_inactive <= 60:
            segment_counts["dormant"] += 1
        else:
            segment_counts["churned"] += 1

    total_leads = max(len(lead_scores), 1)
    for seg_key, meta in SEGMENT_RULES.items():
        count = segment_counts.get(seg_key, 0)
        segments[seg_key] = {
            **meta,
            "count": count,
            "pct": round((count / total_leads) * 100, 1) if count else 0,
        }

    # Stage distribution from snapshots
    latest_date = db.query(func.max(SubscriberSnapshot.snapshot_date)).filter_by(
        project_id=pid
    ).scalar()

    stage_data = []
    if latest_date:
        snapshots = db.query(SubscriberSnapshot).filter_by(
            project_id=pid, snapshot_date=latest_date
        ).all()
        for s in snapshots:
            stage_data.append({
                "stage": s.stage.value,
                "count": s.count,
                "mrr": float(s.mrr) if s.mrr else 0,
            })

    # Trend data: last 8 weeks of snapshots
    eight_weeks_ago = date.today() - timedelta(weeks=8)
    trend_snapshots = db.query(SubscriberSnapshot).filter(
        SubscriberSnapshot.project_id == pid,
        SubscriberSnapshot.snapshot_date >= eight_weeks_ago,
    ).order_by(SubscriberSnapshot.snapshot_date.asc()).all()

    trend_dates = sorted(set(s.snapshot_date.isoformat() for s in trend_snapshots))
    trend_by_stage = defaultdict(dict)
    for s in trend_snapshots:
        trend_by_stage[s.stage.value][s.snapshot_date.isoformat()] = s.count

    # Recent churn events
    churn_events = db.query(SubscriberEvent).filter(
        SubscriberEvent.project_id == pid,
        SubscriberEvent.event_type == SubscriberEventType.churn,
    ).order_by(SubscriberEvent.occurred_at.desc()).limit(20).all()

    # Churn rate (last 30 days)
    thirty_days_ago = now - timedelta(days=30)
    recent_churns = db.query(SubscriberEvent).filter(
        SubscriberEvent.project_id == pid,
        SubscriberEvent.event_type == SubscriberEventType.churn,
        SubscriberEvent.occurred_at >= thirty_days_ago,
    ).count()

    return templates.TemplateResponse("retention.html", {
        "request": request,
        "project": project,
        "segments": segments,
        "segment_rules": SEGMENT_RULES,
        "stage_data": stage_data,
        "trend_dates": trend_dates,
        "trend_by_stage": dict(trend_by_stage),
        "churn_events": churn_events,
        "recent_churns": recent_churns,
        "total_leads": len(lead_scores),
        "current_page": "subscribers",
        "today": date.today(),
    })
