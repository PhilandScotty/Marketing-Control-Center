"""Partner dashboard — PartnerView CRUD, token generation, read-only views."""
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Project, PartnerView, Channel, Task, Automation, ContentPiece,
    AdCampaign, EmailSequence, Metric, SubscriberSnapshot,
    TaskStatus, AutomationHealth, HealthStatus, ContentStatus,
)
from app.routes.dashboard import calc_execution_score

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Preset configurations: which components each preset can see
PRESETS = {
    "full_readonly": {
        "label": "Full Read-Only",
        "components": ["dashboard", "channels", "tasks", "content", "ads", "automations", "subscribers", "budget"],
    },
    "technical_cofounder": {
        "label": "Technical Co-Founder",
        "components": ["dashboard", "tasks", "automations", "techstack", "budget"],
    },
    "editor": {
        "label": "Editor / Content Partner",
        "components": ["content", "tasks"],
    },
    "investor": {
        "label": "Investor",
        "components": ["dashboard", "subscribers", "budget", "ads"],
    },
    "affiliate": {
        "label": "Affiliate / Ambassador",
        "components": ["dashboard", "subscribers"],
    },
}


@router.get("/partners")
def partners_view(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("partners.html", {
            "request": request, "project": None,
            "current_page": "settings", "today": date.today(),
        })

    views = db.query(PartnerView).filter_by(project_id=project.id).all()

    return templates.TemplateResponse("partners.html", {
        "request": request,
        "project": project,
        "partner_views": views,
        "presets": PRESETS,
        "current_page": "settings",
        "today": date.today(),
    })


@router.post("/partners/create")
def create_partner(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    preset: str = Form("full_readonly"),
    banner_text: str = Form(""),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("")

    token = uuid.uuid4().hex[:16]

    pv = PartnerView(
        project_id=project.id,
        name=name,
        token=token,
        preset=preset,
        banner_text=banner_text if banner_text else None,
    )
    db.add(pv)
    db.commit()

    return HTMLResponse('<script>window.location.href="/partners";</script>')


@router.post("/partners/{pv_id}/toggle")
def toggle_partner(pv_id: int, db: Session = Depends(get_db)):
    pv = db.get(PartnerView, pv_id)
    if pv:
        pv.is_active = not pv.is_active
        db.commit()
    return HTMLResponse(
        f'<span class="text-xs {'text-mcc-success' if pv and pv.is_active else 'text-mcc-muted'}">'
        f'{"Active" if pv and pv.is_active else "Disabled"}</span>'
    )


@router.post("/partners/{pv_id}/delete")
def delete_partner(pv_id: int, db: Session = Depends(get_db)):
    pv = db.get(PartnerView, pv_id)
    if pv:
        db.delete(pv)
        db.commit()
    return HTMLResponse('<script>window.location.href="/partners";</script>')


# --- Read-only partner view route ---

@router.get("/partner/{token}")
def partner_dashboard(token: str, request: Request, db: Session = Depends(get_db)):
    pv = db.query(PartnerView).filter_by(token=token, is_active=True).first()
    if not pv:
        return HTMLResponse(
            '<div style="background:#0F0F23;color:#F0F0F0;min-height:100vh;display:flex;align-items:center;'
            'justify-content:center;font-family:sans-serif;">'
            '<div style="text-align:center"><h1>Access Denied</h1>'
            '<p style="color:#8B8B9E">This partner link is invalid or has been disabled.</p></div></div>',
            status_code=404,
        )

    # Update last accessed
    pv.last_accessed = datetime.utcnow()
    db.commit()

    project = db.query(Project).filter_by(id=pv.project_id).first()
    if not project:
        return HTMLResponse("Project not found", status_code=404)

    pid = project.id
    preset_config = PRESETS.get(pv.preset, PRESETS["full_readonly"])
    components = preset_config["components"]

    # Gather data for visible components
    data = {"components": components}

    if "dashboard" in components:
        data["exec_score"] = calc_execution_score(db, pid)
        data["channels"] = db.query(Channel).filter_by(project_id=pid).all()

    if "tasks" in components:
        data["tasks"] = db.query(Task).filter(
            Task.project_id == pid,
            Task.status.notin_([TaskStatus.done, TaskStatus.archived]),
        ).order_by(Task.due_date.asc().nullslast()).limit(30).all()

    if "content" in components:
        data["content"] = db.query(ContentPiece).filter(
            ContentPiece.project_id == pid,
            ContentPiece.status != ContentStatus.published,
        ).order_by(ContentPiece.due_date.asc().nullslast()).all()

    if "automations" in components:
        data["automations"] = db.query(Automation).filter_by(project_id=pid).all()

    if "ads" in components:
        data["ads"] = db.query(AdCampaign).filter_by(project_id=pid).all()

    if "subscribers" in components:
        from sqlalchemy import func
        latest_date = db.query(func.max(SubscriberSnapshot.snapshot_date)).filter_by(
            project_id=pid
        ).scalar()
        data["subscriber_snapshots"] = []
        if latest_date:
            data["subscriber_snapshots"] = db.query(SubscriberSnapshot).filter_by(
                project_id=pid, snapshot_date=latest_date
            ).all()

    return templates.TemplateResponse("partner_view.html", {
        "request": request,
        "project": project,
        "partner_view": pv,
        "data": data,
        "today": date.today(),
    })
