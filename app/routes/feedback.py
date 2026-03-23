from datetime import date, datetime
from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import (
    Project, CustomerFeedback,
    FeedbackSource, FeedbackType, Sentiment,
)

router = APIRouter(prefix="/feedback")
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def feedback_list(
    request: Request,
    feedback_type: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    theme: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("feedback.html", {
            "request": request, "project": None, "current_page": "feedback",
            "today": date.today(),
        })

    pid = project.id
    query = db.query(CustomerFeedback).filter_by(project_id=pid)

    if feedback_type:
        try:
            query = query.filter(CustomerFeedback.feedback_type == FeedbackType(feedback_type))
        except ValueError:
            pass
    if sentiment:
        try:
            query = query.filter(CustomerFeedback.sentiment == Sentiment(sentiment))
        except ValueError:
            pass

    items = query.order_by(CustomerFeedback.created_at.desc()).all()

    # Filter by theme (JSON array contains)
    if theme:
        items = [i for i in items if i.themes and theme in i.themes]

    # Testimonial bank
    testimonials = db.query(CustomerFeedback).filter(
        CustomerFeedback.project_id == pid,
        CustomerFeedback.can_use_publicly == True,
    ).order_by(CustomerFeedback.created_at.desc()).all()

    # All unique themes for filter
    all_themes = set()
    all_feedback = db.query(CustomerFeedback).filter_by(project_id=pid).all()
    for f in all_feedback:
        if f.themes:
            for t in f.themes:
                all_themes.add(t)

    # Summary stats
    total = len(all_feedback)
    positive = sum(1 for f in all_feedback if f.sentiment == Sentiment.positive)
    negative = sum(1 for f in all_feedback if f.sentiment == Sentiment.negative)
    neutral = sum(1 for f in all_feedback if f.sentiment == Sentiment.neutral)

    # NPS scores
    nps_scores = [f.nps_score for f in all_feedback if f.nps_score is not None]
    avg_nps = round(sum(nps_scores) / len(nps_scores), 1) if nps_scores else None

    return templates.TemplateResponse("feedback.html", {
        "request": request,
        "project": project,
        "items": items,
        "testimonials": testimonials,
        "total": total,
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "avg_nps": avg_nps,
        "all_themes": sorted(all_themes),
        "all_types": [(t.value, t.value.replace("_", " ").title()) for t in FeedbackType],
        "all_sentiments": [(s.value, s.value.title()) for s in Sentiment],
        "all_sources": [(s.value, s.value.replace("_", " ").title()) for s in FeedbackSource],
        "filter_type": feedback_type or "",
        "filter_sentiment": sentiment or "",
        "filter_theme": theme or "",
        "current_page": "feedback",
        "today": date.today(),
    })


@router.get("/form")
def feedback_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("partials/feedback_form.html", {
        "request": request,
        "all_sources": [(s.value, s.value.replace("_", " ").title()) for s in FeedbackSource],
        "all_types": [(t.value, t.value.replace("_", " ").title()) for t in FeedbackType],
        "all_sentiments": [(s.value, s.value.title()) for s in Sentiment],
    })


@router.post("/create")
def create_feedback(
    source: str = Form(...),
    feedback_type: str = Form(...),
    content: str = Form(...),
    sentiment: str = Form("neutral"),
    themes: str = Form(""),
    can_use_publicly: bool = Form(False),
    customer_identifier: str = Form(""),
    nps_score: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse('<span class="text-mcc-critical text-xs">No project</span>')

    theme_list = [t.strip() for t in themes.split(",") if t.strip()] if themes else []

    fb = CustomerFeedback(
        project_id=project.id,
        source=FeedbackSource(source),
        feedback_type=FeedbackType(feedback_type),
        content=content,
        sentiment=Sentiment(sentiment),
        themes=theme_list,
        can_use_publicly=can_use_publicly,
        customer_identifier=customer_identifier if customer_identifier else None,
        nps_score=nps_score,
    )
    db.add(fb)
    db.commit()

    return RedirectResponse(url="/feedback/", status_code=303)


@router.post("/delete/{feedback_id}")
def delete_feedback(feedback_id: int, db: Session = Depends(get_db)):
    fb = db.get(CustomerFeedback, feedback_id)
    if fb:
        db.delete(fb)
        db.commit()
    return HTMLResponse('<span class="text-mcc-success text-[10px]">Deleted</span>')


@router.post("/toggle-public/{feedback_id}")
def toggle_public(feedback_id: int, db: Session = Depends(get_db)):
    fb = db.get(CustomerFeedback, feedback_id)
    if fb:
        fb.can_use_publicly = not fb.can_use_publicly
        db.commit()
        status = "public" if fb.can_use_publicly else "private"
    return HTMLResponse(f'<span class="text-mcc-success text-[10px]">Now {status}</span>')
