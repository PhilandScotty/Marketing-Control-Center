"""Universal 'Track Something' wizard — create any trackable entity from one entry point."""
import logging
from datetime import date, datetime

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Project, Channel, ChannelType, ChannelStatus, AutomationLevel,
    Tool, ToolCategory, ToolStatus, BillingCycle,
    Task, TaskStatus, TaskPriority,
    Automation, AutomationType, AutomationHealth, HostingLocation, HealthCheckMethod,
    ContentPiece, ContentType, ProductionLane, ContentStatus,
    AdCampaign, AdPlatform, AdStatus, AdObjective,
    OutreachContact, ContactType, ContactStatus,
    Metric, MetricSource,
)

logger = logging.getLogger("mcc.routes.track")

router = APIRouter(prefix="/track")
templates = Jinja2Templates(directory="app/templates")

# Entity type definitions for the wizard
ENTITY_TYPES = [
    {
        "key": "channel",
        "label": "Channel",
        "icon": "M13 10V3L4 14h7v7l9-11h-7z",
        "description": "A marketing channel (social, email, SEO, etc.)",
        "color": "#06B6D4",
    },
    {
        "key": "metric",
        "label": "Metric",
        "icon": "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
        "description": "A KPI or metric to monitor over time",
        "color": "#10B981",
    },
    {
        "key": "tool",
        "label": "Tool / Service",
        "icon": "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z",
        "description": "Software, SaaS tool, or service you're using",
        "color": "#8B5CF6",
    },
    {
        "key": "content",
        "label": "Content",
        "icon": "M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z",
        "description": "A content piece in your pipeline",
        "color": "#F59E0B",
    },
    {
        "key": "ad",
        "label": "Ad Campaign",
        "icon": "M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z",
        "description": "A paid advertising campaign",
        "color": "#EF4444",
    },
    {
        "key": "automation",
        "label": "Automation",
        "icon": "M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15",
        "description": "A recurring automation, bot, or scheduled job",
        "color": "#EC4899",
    },
    {
        "key": "contact",
        "label": "Outreach Contact",
        "icon": "M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z",
        "description": "An influencer, partner, or outreach prospect",
        "color": "#14B8A6",
    },
]


@router.get("/wizard")
def track_wizard(request: Request, db: Session = Depends(get_db)):
    """Render the track wizard step 1 (entity type selection)."""
    return templates.TemplateResponse("partials/track_wizard.html", {
        "request": request,
        "step": 1,
        "entity_types": ENTITY_TYPES,
    })


@router.get("/wizard/step2/{entity_type}")
def track_wizard_step2(entity_type: str, request: Request, db: Session = Depends(get_db)):
    """Render step 2 fields for the chosen entity type."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    channels = db.query(Channel).filter_by(project_id=project.id).all() if project else []

    context = {
        "request": request,
        "step": 2,
        "entity_type": entity_type,
        "channels": channels,
        "channel_types": [(ct.value, ct.value.replace("_", " ").title()) for ct in ChannelType],
        "tool_categories": [(tc.value, tc.value.replace("_", " ").title()) for tc in ToolCategory],
        "content_types": [(ct.value, ct.value.replace("_", " ").title()) for ct in ContentType],
        "ad_platforms": [(ap.value, ap.value.replace("_", " ").title()) for ap in AdPlatform],
        "automation_types": [(at.value, at.value.replace("_", " ").title()) for at in AutomationType],
        "contact_types": [(ct.value, ct.value.replace("_", " ").title()) for ct in ContactType],
        "priorities": [(p.value, p.value.replace("_", " ").title()) for p in TaskPriority],
    }

    # Smart defaults based on entity type
    entity_info = next((e for e in ENTITY_TYPES if e["key"] == entity_type), None)
    context["entity_info"] = entity_info

    return templates.TemplateResponse("partials/track_wizard.html", context)


@router.post("/create")
async def track_create(request: Request, db: Session = Depends(get_db)):
    """Create the tracked entity and optional setup tasks."""
    form = await request.form()
    entity_type = form.get("entity_type")
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse('<div class="text-red-400">No project loaded</div>')

    pid = project.id
    created_item = None
    redirect_url = "/"
    setup_tasks_text = form.get("setup_tasks", "").strip()

    if entity_type == "channel":
        try:
            ch_type = ChannelType(form.get("channel_type", "content"))
        except ValueError:
            ch_type = ChannelType.content

        item = Channel(
            project_id=pid,
            name=form.get("name", "New Channel"),
            channel_type=ch_type,
            status=ChannelStatus(form.get("status", "planned")),
            automation_level=AutomationLevel.manual,
            owner="phil",
            notes=form.get("notes", ""),
        )
        db.add(item)
        db.commit()
        created_item = {"type": "Channel", "name": item.name, "id": item.id}
        redirect_url = f"/channels/{item.id}"

    elif entity_type == "metric":
        channel_id = form.get("channel_id")
        if not channel_id:
            return HTMLResponse('<div class="text-red-400">Please select a channel for this metric</div>')

        metric = Metric(
            channel_id=int(channel_id),
            metric_name=form.get("name", "New Metric"),
            metric_value=float(form.get("initial_value", 0)),
            unit=form.get("unit", "count"),
            source=MetricSource.manual,
        )
        db.add(metric)
        db.commit()
        created_item = {"type": "Metric", "name": metric.metric_name, "id": metric.id}
        redirect_url = "/metrics"

    elif entity_type == "tool":
        try:
            cat = ToolCategory(form.get("category", "dev_tools"))
        except ValueError:
            cat = ToolCategory.dev_tools

        item = Tool(
            project_id=pid,
            name=form.get("name", "New Tool"),
            category=cat,
            purpose=form.get("purpose", ""),
            monthly_cost=float(form.get("monthly_cost", 0)),
            billing_cycle=BillingCycle(form.get("billing_cycle", "monthly")),
            status=ToolStatus(form.get("status", "active")),
            notes=form.get("notes", ""),
        )
        db.add(item)
        db.commit()
        created_item = {"type": "Tool", "name": item.name, "id": item.id}
        redirect_url = "/techstack"

    elif entity_type == "content":
        try:
            ct = ContentType(form.get("content_type", "short_video"))
        except ValueError:
            ct = ContentType.short_video

        item = ContentPiece(
            project_id=pid,
            title=form.get("name", "New Content"),
            content_type=ct,
            status=ContentStatus.concept,
            assigned_to=form.get("assigned_to", "phil"),
            due_date=date.fromisoformat(form["due_date"]) if form.get("due_date") else None,
            notes=form.get("notes", ""),
        )
        db.add(item)
        db.commit()
        created_item = {"type": "Content", "name": item.title, "id": item.id}
        redirect_url = "/pipelines/content"

    elif entity_type == "ad":
        try:
            platform = AdPlatform(form.get("platform", "meta"))
        except ValueError:
            platform = AdPlatform.meta

        channel_id = form.get("channel_id")
        if not channel_id:
            # Find or create a paid ads channel
            ch = db.query(Channel).filter_by(project_id=pid, channel_type=ChannelType.paid_ads).first()
            if not ch:
                ch = Channel(project_id=pid, name=f"{platform.value.title()} Ads", channel_type=ChannelType.paid_ads, status=ChannelStatus.planned)
                db.add(ch)
                db.commit()
            channel_id = ch.id

        item = AdCampaign(
            project_id=pid,
            channel_id=int(channel_id),
            platform=platform,
            campaign_name=form.get("name", "New Campaign"),
            status=AdStatus.draft,
            objective=AdObjective(form.get("objective", "traffic")),
            daily_budget=float(form.get("daily_budget", 0)),
            start_date=date.fromisoformat(form["start_date"]) if form.get("start_date") else date.today(),
            notes=form.get("notes", ""),
        )
        db.add(item)
        db.commit()
        created_item = {"type": "Ad Campaign", "name": item.campaign_name, "id": item.id}
        redirect_url = "/ads"

    elif entity_type == "automation":
        try:
            at = AutomationType(form.get("automation_type", "cron_job"))
        except ValueError:
            at = AutomationType.cron_job

        item = Automation(
            project_id=pid,
            name=form.get("name", "New Automation"),
            automation_type=at,
            platform=form.get("platform", ""),
            schedule=form.get("schedule", ""),
            health=AutomationHealth.unknown,
            health_check_method=HealthCheckMethod.manual_confirm,
            hosting=HostingLocation.mac_mini,
            owner="phil",
            notes=form.get("notes", ""),
        )
        db.add(item)
        db.commit()
        created_item = {"type": "Automation", "name": item.name, "id": item.id}
        redirect_url = "/automations"

    elif entity_type == "contact":
        try:
            ct = ContactType(form.get("contact_type", "influencer"))
        except ValueError:
            ct = ContactType.influencer

        item = OutreachContact(
            project_id=pid,
            name=form.get("name", "New Contact"),
            platform=form.get("platform_name", ""),
            contact_type=ct,
            status=ContactStatus.identified,
            audience_size=int(form.get("audience_size", 0)) if form.get("audience_size") else None,
            notes=form.get("notes", ""),
        )
        db.add(item)
        db.commit()
        created_item = {"type": "Contact", "name": item.name, "id": item.id}
        redirect_url = "/outreach"

    # Create setup tasks if requested
    if setup_tasks_text and created_item:
        for line in setup_tasks_text.split("\n"):
            line = line.strip().lstrip("- ").strip()
            if line:
                task = Task(
                    project_id=pid,
                    title=f"[Setup] {line}",
                    description=f"Setup task for {created_item['type']}: {created_item['name']}",
                    status=TaskStatus.this_week,
                    priority=TaskPriority.high,
                    assigned_to="phil",
                )
                db.add(task)
        db.commit()

    if not created_item:
        return HTMLResponse('<div class="text-red-400">Unknown entity type</div>')

    # Return success HTML with redirect
    return HTMLResponse(f'''
    <div class="text-center py-6">
        <div class="w-12 h-12 rounded-full bg-mcc-success/20 flex items-center justify-center mx-auto mb-3">
            <svg class="w-6 h-6 text-mcc-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
            </svg>
        </div>
        <h3 class="text-sm font-semibold mb-1">Now Tracking: {created_item["name"]}</h3>
        <p class="text-xs text-mcc-muted mb-4">{created_item["type"]} added to your project</p>
        <div class="flex gap-2 justify-center">
            <a href="{redirect_url}" class="px-4 py-2 bg-mcc-accent text-white rounded-lg text-xs font-medium hover:bg-mcc-accent/80">
                Go to {created_item["type"]}
            </a>
            <button onclick="closeTrackModal()" class="px-4 py-2 bg-mcc-border text-mcc-text rounded-lg text-xs hover:bg-mcc-border/80">
                Close
            </button>
        </div>
    </div>
    ''')


# --- Stop Tracking ---

@router.get("/stop")
def stop_tracking_list(request: Request, db: Session = Depends(get_db)):
    """Show active trackable items that can be deprecated/stopped."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse('<div class="text-mcc-muted p-4">No project loaded</div>')

    pid = project.id
    items = []

    for ch in db.query(Channel).filter(Channel.project_id == pid, Channel.status != ChannelStatus.deprecated).all():
        items.append({"type": "channel", "id": ch.id, "name": ch.name, "detail": f"{ch.channel_type.value} — {ch.status.value}"})

    for t in db.query(Tool).filter(Tool.project_id == pid, Tool.status != ToolStatus.deprecated).all():
        items.append({"type": "tool", "id": t.id, "name": t.name, "detail": f"{t.category.value} — ${float(t.monthly_cost)}/mo"})

    for a in db.query(Automation).filter(Automation.project_id == pid, Automation.health != AutomationHealth.paused).all():
        items.append({"type": "automation", "id": a.id, "name": a.name, "detail": f"{a.automation_type.value}"})

    for ad in db.query(AdCampaign).filter(AdCampaign.project_id == pid, AdCampaign.status.in_([AdStatus.active, AdStatus.scheduled, AdStatus.draft])).all():
        items.append({"type": "ad", "id": ad.id, "name": ad.campaign_name, "detail": f"{ad.platform.value}"})

    return templates.TemplateResponse("partials/track_stop.html", {
        "request": request,
        "items": items,
    })


@router.post("/stop/{entity_type}/{entity_id}")
def stop_tracking(entity_type: str, entity_id: int, request: Request, db: Session = Depends(get_db)):
    """Deprecate/pause an entity."""
    if entity_type == "channel":
        item = db.get(Channel, entity_id)
        if item:
            item.status = ChannelStatus.deprecated
            db.commit()
    elif entity_type == "tool":
        item = db.get(Tool, entity_id)
        if item:
            item.status = ToolStatus.deprecated
            db.commit()
    elif entity_type == "automation":
        item = db.get(Automation, entity_id)
        if item:
            item.health = AutomationHealth.paused
            db.commit()
    elif entity_type == "ad":
        item = db.get(AdCampaign, entity_id)
        if item:
            item.status = AdStatus.paused
            db.commit()

    # Re-render the stop list
    return stop_tracking_list(request, db)
