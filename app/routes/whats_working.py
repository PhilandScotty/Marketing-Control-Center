from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import (
    Project, Channel, ContentPiece, ContentTag, PerformanceScore,
    SubscriberEvent, BudgetExpense, SubscriberEventType,
    TagDimension, ContentType,
)

router = APIRouter(prefix="/whats-working")
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def whats_working(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("whats_working.html", {
            "request": request, "project": None, "current_page": "whats_working",
            "today": date.today(),
        })

    pid = project.id

    # --- Messaging Leaderboard: content ranked by PerformanceScore ---
    scores = db.query(PerformanceScore).filter(
        PerformanceScore.content_piece_id.isnot(None),
    ).order_by(PerformanceScore.engagement_score.desc()).limit(20).all()

    leaderboard = []
    for s in scores:
        piece = db.get(ContentPiece, s.content_piece_id)
        if piece and piece.project_id == pid:
            tags = db.query(ContentTag).filter_by(content_piece_id=piece.id).all()
            tag_map = {}
            for t in tags:
                tag_map.setdefault(t.tag_dimension.value, []).append(t.tag_value)
            leaderboard.append({
                "piece": piece,
                "score": s,
                "tags": tag_map,
            })

    # --- Cross-channel pattern: tag dimension breakdown ---
    all_tags = db.query(ContentTag).filter(
        ContentTag.content_piece_id.isnot(None),
    ).all()

    # Filter to this project's content
    project_content_ids = set(
        p.id for p in db.query(ContentPiece).filter_by(project_id=pid).all()
    )
    all_tags = [t for t in all_tags if t.content_piece_id in project_content_ids]

    tag_patterns = {}
    for dim in TagDimension:
        dim_tags = [t for t in all_tags if t.tag_dimension == dim]
        if dim_tags:
            value_counts = {}
            for t in dim_tags:
                value_counts[t.tag_value] = value_counts.get(t.tag_value, 0) + 1
            sorted_vals = sorted(value_counts.items(), key=lambda x: x[1], reverse=True)
            tag_patterns[dim.value] = sorted_vals[:5]

    # --- Channel ROI Attribution ---
    channels = db.query(Channel).filter_by(project_id=pid).all()
    channel_roi = []

    for ch in channels:
        # Events attributed to this channel
        events = db.query(SubscriberEvent).filter_by(
            project_id=pid,
            source_channel_id=ch.id,
        ).all()

        leads = sum(1 for e in events if e.event_type == SubscriberEventType.trial_start)
        trials = leads  # trial_start = trial
        conversions = sum(1 for e in events if e.event_type in (
            SubscriberEventType.convert_basic, SubscriberEventType.convert_premium
        ))

        # Spend on this channel
        spend = float(db.query(func.sum(BudgetExpense.amount)).filter(
            BudgetExpense.project_id == pid,
        ).scalar() or 0)
        # Approximate per-channel spend from channel total_spend_to_date
        ch_spend = float(ch.total_spend_to_date or 0)

        mrr = float(ch.attributed_mrr or 0)
        cac = round(ch_spend / conversions, 2) if conversions > 0 else 0
        ltv_cac = round((mrr * 12) / cac, 1) if cac > 0 else 0

        channel_roi.append({
            "channel": ch,
            "leads": leads,
            "trials": trials,
            "conversions": conversions,
            "mrr": mrr,
            "spend": ch_spend,
            "cac": cac,
            "ltv_cac": ltv_cac,
        })

    # Sort by conversions desc
    channel_roi.sort(key=lambda x: x["conversions"], reverse=True)

    return templates.TemplateResponse("whats_working.html", {
        "request": request,
        "project": project,
        "leaderboard": leaderboard,
        "tag_patterns": tag_patterns,
        "channel_roi": channel_roi,
        "current_page": "whats_working",
        "today": date.today(),
    })
