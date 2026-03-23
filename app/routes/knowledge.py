"""Knowledge base — CRUD for KnowledgeEntry with cross-project search."""
from datetime import date, datetime

from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import (
    Project, KnowledgeEntry, KnowledgeEntryType,
)

router = APIRouter(prefix="/knowledge")
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def knowledge_view(
    request: Request,
    db: Session = Depends(get_db),
    entry_type: str = "",
    search: str = "",
    confirmed_only: str = "",
):
    project = db.query(Project).filter_by(slug="grindlab").first()

    # Cross-project: entries with project_id=NULL or matching project
    q = db.query(KnowledgeEntry)
    if project:
        q = q.filter(or_(
            KnowledgeEntry.project_id == project.id,
            KnowledgeEntry.project_id.is_(None),
        ))

    if entry_type:
        try:
            q = q.filter(KnowledgeEntry.entry_type == KnowledgeEntryType(entry_type))
        except ValueError:
            pass

    if search:
        q = q.filter(or_(
            KnowledgeEntry.title.ilike(f"%{search}%"),
            KnowledgeEntry.body.ilike(f"%{search}%"),
        ))

    if confirmed_only == "true":
        q = q.filter(KnowledgeEntry.confirmed == True)

    entries = q.order_by(KnowledgeEntry.created_at.desc()).all()

    # Count by type
    type_counts = {}
    for t in KnowledgeEntryType:
        count = db.query(KnowledgeEntry).filter_by(entry_type=t).count()
        type_counts[t.value] = count

    # Unconfirmed AI entries
    unconfirmed = db.query(KnowledgeEntry).filter_by(
        auto_generated=True, confirmed=False
    ).count()

    return templates.TemplateResponse("knowledge.html", {
        "request": request,
        "project": project,
        "entries": entries,
        "type_counts": type_counts,
        "entry_types": [t.value for t in KnowledgeEntryType],
        "current_filter": entry_type,
        "current_search": search,
        "unconfirmed_count": unconfirmed,
        "current_page": "knowledge",
        "today": date.today(),
    })


@router.post("/create")
def create_entry(
    request: Request,
    db: Session = Depends(get_db),
    title: str = Form(...),
    body: str = Form(""),
    entry_type: str = Form("lesson"),
    tags: str = Form(""),
    is_global: str = Form(""),
):
    project = db.query(Project).filter_by(slug="grindlab").first()

    try:
        etype = KnowledgeEntryType(entry_type)
    except ValueError:
        etype = KnowledgeEntryType.lesson

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    entry = KnowledgeEntry(
        project_id=None if is_global else (project.id if project else None),
        entry_type=etype,
        title=title,
        body=body,
        tags=tag_list,
        source_project=project.slug if project and not is_global else "",
        confirmed=True,
    )
    db.add(entry)
    db.commit()

    return HTMLResponse(
        '<script>window.location.href="/knowledge";</script>'
    )


@router.get("/{entry_id}")
def view_entry(entry_id: int, request: Request, db: Session = Depends(get_db)):
    entry = db.get(KnowledgeEntry, entry_id)
    if not entry:
        return HTMLResponse("")

    project = db.query(Project).filter_by(slug="grindlab").first()

    return templates.TemplateResponse("knowledge_detail.html", {
        "request": request,
        "project": project,
        "entry": entry,
        "current_page": "knowledge",
        "today": date.today(),
    })


@router.post("/{entry_id}/update")
def update_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    title: str = Form(...),
    body: str = Form(""),
    tags: str = Form(""),
):
    entry = db.get(KnowledgeEntry, entry_id)
    if not entry:
        return HTMLResponse("")

    entry.title = title
    entry.body = body
    entry.tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    entry.updated_at = datetime.utcnow()
    db.commit()

    return HTMLResponse(
        f'<script>window.location.href="/knowledge/{entry_id}";</script>'
    )


@router.post("/{entry_id}/confirm")
def confirm_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.get(KnowledgeEntry, entry_id)
    if entry:
        entry.confirmed = True
        db.commit()
    return HTMLResponse('<span class="text-mcc-success text-xs">Confirmed</span>')


@router.post("/{entry_id}/delete")
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.get(KnowledgeEntry, entry_id)
    if entry:
        db.delete(entry)
        db.commit()
    return HTMLResponse('<script>window.location.href="/knowledge";</script>')
