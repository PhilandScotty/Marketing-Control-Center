"""Global search — searches all entity types, returns grouped results."""
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import (
    Project, Channel, Task, Automation, ContentPiece, AdCampaign,
    OutreachContact, EmailSequence, Tool, Competitor,
    KnowledgeEntry, Experiment, CustomerFeedback, AIInsight,
)

router = APIRouter(prefix="/search")
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def search_results(
    request: Request,
    q: str = Query(""),
    db: Session = Depends(get_db),
):
    """Search all entity types and return grouped results."""
    if not q or len(q) < 2:
        return templates.TemplateResponse("partials/search_results.html", {
            "request": request,
            "query": q,
            "groups": [],
            "total": 0,
        })

    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("partials/search_results.html", {
            "request": request, "query": q, "groups": [], "total": 0,
        })

    pid = project.id
    term = f"%{q}%"
    groups = []

    # Tasks
    tasks = db.query(Task).filter(
        Task.project_id == pid,
        or_(Task.title.ilike(term), Task.description.ilike(term)),
    ).limit(10).all()
    if tasks:
        groups.append({
            "type": "Tasks",
            "icon": "check-square",
            "results": [{"id": t.id, "title": t.title, "url": "/tasks/", "subtitle": f"{t.status.value} / {t.priority.value}"} for t in tasks],
        })

    # Channels
    channels = db.query(Channel).filter(
        Channel.project_id == pid,
        Channel.name.ilike(term),
    ).limit(10).all()
    if channels:
        groups.append({
            "type": "Channels",
            "icon": "grid",
            "results": [{"id": c.id, "title": c.name, "url": "/", "subtitle": f"{c.status.value} / {c.health.value}"} for c in channels],
        })

    # Content
    content = db.query(ContentPiece).filter(
        ContentPiece.project_id == pid,
        or_(ContentPiece.title.ilike(term), ContentPiece.series.ilike(term)),
    ).limit(10).all()
    if content:
        groups.append({
            "type": "Content",
            "icon": "film",
            "results": [{"id": c.id, "title": c.title, "url": "/pipelines/content", "subtitle": c.status.value} for c in content],
        })

    # Automations
    autos = db.query(Automation).filter(
        Automation.project_id == pid,
        Automation.name.ilike(term),
    ).limit(10).all()
    if autos:
        groups.append({
            "type": "Automations",
            "icon": "cpu",
            "results": [{"id": a.id, "title": a.name, "url": "/automations/", "subtitle": a.health.value} for a in autos],
        })

    # Outreach
    contacts = db.query(OutreachContact).filter(
        OutreachContact.project_id == pid,
        or_(OutreachContact.name.ilike(term), OutreachContact.platform.ilike(term)),
    ).limit(10).all()
    if contacts:
        groups.append({
            "type": "Outreach",
            "icon": "users",
            "results": [{"id": c.id, "title": c.name, "url": "/pipelines/outreach", "subtitle": f"{c.platform} / {c.status.value}"} for c in contacts],
        })

    # Ad Campaigns
    ads = db.query(AdCampaign).filter(
        AdCampaign.project_id == pid,
        AdCampaign.campaign_name.ilike(term),
    ).limit(10).all()
    if ads:
        groups.append({
            "type": "Ad Campaigns",
            "icon": "megaphone",
            "results": [{"id": a.id, "title": a.campaign_name, "url": "/ads/", "subtitle": f"{a.platform.value} / {a.signal.value if a.signal else 'hold'}"} for a in ads],
        })

    # Email Sequences
    seqs = db.query(EmailSequence).filter(
        EmailSequence.project_id == pid,
        EmailSequence.name.ilike(term),
    ).limit(10).all()
    if seqs:
        groups.append({
            "type": "Sequences",
            "icon": "mail",
            "results": [{"id": s.id, "title": s.name, "url": "/pipelines/email", "subtitle": s.status.value} for s in seqs],
        })

    # Tools
    tools = db.query(Tool).filter(
        Tool.project_id == pid,
        or_(Tool.name.ilike(term), Tool.purpose.ilike(term)),
    ).limit(10).all()
    if tools:
        groups.append({
            "type": "Tech Stack",
            "icon": "wrench",
            "results": [{"id": t.id, "title": t.name, "url": "/techstack/", "subtitle": t.category.value} for t in tools],
        })

    # Competitors
    comps = db.query(Competitor).filter(
        Competitor.project_id == pid,
        Competitor.name.ilike(term),
    ).limit(10).all()
    if comps:
        groups.append({
            "type": "Competitors",
            "icon": "eye",
            "results": [{"id": c.id, "title": c.name, "url": f"/competitors/{c.id}", "subtitle": c.website} for c in comps],
        })

    # Knowledge
    entries = db.query(KnowledgeEntry).filter(
        or_(KnowledgeEntry.title.ilike(term), KnowledgeEntry.body.ilike(term)),
    ).limit(10).all()
    if entries:
        groups.append({
            "type": "Knowledge",
            "icon": "book",
            "results": [{"id": e.id, "title": e.title, "url": f"/knowledge/{e.id}", "subtitle": e.entry_type.value} for e in entries],
        })

    # Experiments
    exps = db.query(Experiment).filter(
        Experiment.project_id == pid,
        Experiment.hypothesis.ilike(term),
    ).limit(10).all()
    if exps:
        groups.append({
            "type": "Experiments",
            "icon": "flask",
            "results": [{"id": e.id, "title": e.hypothesis[:80], "url": f"/experiments/{e.id}", "subtitle": e.status.value} for e in exps],
        })

    # AI Insights
    insights = db.query(AIInsight).filter(
        AIInsight.project_id == pid,
        or_(AIInsight.title.ilike(term), AIInsight.body.ilike(term)),
    ).limit(10).all()
    if insights:
        groups.append({
            "type": "AI Insights",
            "icon": "lightbulb",
            "results": [{"id": i.id, "title": i.title, "url": "/", "subtitle": f"{i.severity.value} / {i.insight_type.value}"} for i in insights],
        })

    total = sum(len(g["results"]) for g in groups)

    return templates.TemplateResponse("partials/search_results.html", {
        "request": request,
        "query": q,
        "groups": groups,
        "total": total,
    })
