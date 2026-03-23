"""Competitive intelligence — Competitor + CompetitorUpdate CRUD, comparison table."""
from datetime import date, datetime

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Project, Competitor, CompetitorUpdate, CompetitorUpdateType,
)

router = APIRouter(prefix="/competitors")
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def competitors_view(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("competitors.html", {
            "request": request, "project": None,
            "current_page": "competitors", "today": date.today(),
        })

    competitors = db.query(Competitor).filter_by(project_id=project.id).all()

    # Attach recent updates
    for comp in competitors:
        comp.recent_updates = db.query(CompetitorUpdate).filter_by(
            competitor_id=comp.id
        ).order_by(CompetitorUpdate.observed_at.desc()).limit(5).all()

    # Monthly review check
    needs_review = [
        c for c in competitors
        if c.last_checked and (date.today() - c.last_checked).days >= 30
    ]

    return templates.TemplateResponse("competitors.html", {
        "request": request,
        "project": project,
        "competitors": competitors,
        "needs_review": needs_review,
        "update_types": [t.value for t in CompetitorUpdateType],
        "current_page": "competitors",
        "today": date.today(),
    })


@router.post("/create")
def create_competitor(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    website: str = Form(""),
    pricing_summary: str = Form(""),
    positioning_summary: str = Form(""),
    strengths: str = Form(""),
    weaknesses: str = Form(""),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("")

    comp = Competitor(
        project_id=project.id,
        name=name,
        website=website,
        pricing_summary=pricing_summary,
        positioning_summary=positioning_summary,
        strengths=strengths,
        weaknesses=weaknesses,
    )
    db.add(comp)
    db.commit()

    return HTMLResponse('<script>window.location.href="/competitors";</script>')


@router.get("/{comp_id}")
def competitor_detail(comp_id: int, request: Request, db: Session = Depends(get_db)):
    comp = db.get(Competitor, comp_id)
    if not comp:
        return HTMLResponse("")

    project = db.query(Project).filter_by(slug="grindlab").first()
    updates = db.query(CompetitorUpdate).filter_by(
        competitor_id=comp.id
    ).order_by(CompetitorUpdate.observed_at.desc()).all()

    return templates.TemplateResponse("competitor_detail.html", {
        "request": request,
        "project": project,
        "competitor": comp,
        "updates": updates,
        "update_types": [t.value for t in CompetitorUpdateType],
        "current_page": "competitors",
        "today": date.today(),
    })


@router.post("/{comp_id}/update")
def update_competitor(
    comp_id: int,
    db: Session = Depends(get_db),
    pricing_summary: str = Form(""),
    positioning_summary: str = Form(""),
    strengths: str = Form(""),
    weaknesses: str = Form(""),
):
    comp = db.get(Competitor, comp_id)
    if not comp:
        return HTMLResponse("")

    comp.pricing_summary = pricing_summary
    comp.positioning_summary = positioning_summary
    comp.strengths = strengths
    comp.weaknesses = weaknesses
    comp.last_checked = date.today()
    db.commit()

    return HTMLResponse(
        f'<script>window.location.href="/competitors/{comp_id}";</script>'
    )


@router.post("/{comp_id}/add-update")
def add_competitor_update(
    comp_id: int,
    db: Session = Depends(get_db),
    update_type: str = Form(...),
    summary: str = Form(...),
    source_url: str = Form(""),
):
    comp = db.get(Competitor, comp_id)
    if not comp:
        return HTMLResponse("")

    try:
        utype = CompetitorUpdateType(update_type)
    except ValueError:
        utype = CompetitorUpdateType.other

    update = CompetitorUpdate(
        competitor_id=comp.id,
        update_type=utype,
        summary=summary,
        source_url=source_url if source_url else None,
    )
    db.add(update)
    comp.last_checked = date.today()
    db.commit()

    return HTMLResponse(
        f'<script>window.location.href="/competitors/{comp_id}";</script>'
    )


@router.post("/{comp_id}/delete")
def delete_competitor(comp_id: int, db: Session = Depends(get_db)):
    comp = db.get(Competitor, comp_id)
    if comp:
        db.query(CompetitorUpdate).filter_by(competitor_id=comp.id).delete()
        db.delete(comp)
        db.commit()
    return HTMLResponse('<script>window.location.href="/competitors";</script>')
