"""Approval Queue — unified review queue for items awaiting Phil's approval."""
from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Project, ApprovalQueueItem, OutreachContact, AIInsight, ContentPiece,
    QueueItemType, QueueItemStatus, ContactStatus,
    ContentType, ContentStatus,
)

router = APIRouter(prefix="/queue")
templates = Jinja2Templates(directory="app/templates")


def get_pending_count(db: Session, project_id: int) -> int:
    return db.query(ApprovalQueueItem).filter_by(
        project_id=project_id, status=QueueItemStatus.pending,
    ).count()


@router.get("/badge", response_class=HTMLResponse)
def queue_badge(db: Session = Depends(get_db)):
    """Returns the queue count badge HTML for sidebar. Loaded via HTMX."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("")
    count = get_pending_count(db, project.id)
    if count == 0:
        return HTMLResponse("")
    return HTMLResponse(
        f'<span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-mcc-accent/20 text-mcc-accent">{count}</span>'
    )


@router.get("/", response_class=HTMLResponse)
def queue_index(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("queue.html", {
            "request": request, "project": None, "items": [],
            "current_page": "queue", "counts": {},
        })

    pid = project.id
    items = db.query(ApprovalQueueItem).filter_by(
        project_id=pid, status=QueueItemStatus.pending,
    ).order_by(ApprovalQueueItem.created_at.desc()).all()

    # Attach contact objects for outreach items
    for item in items:
        if item.contact_id:
            item._contact = db.get(OutreachContact, item.contact_id)
        else:
            item._contact = None

    # Counts by type
    counts = {}
    for t in QueueItemType:
        c = sum(1 for i in items if i.item_type == t)
        if c > 0:
            counts[t.value] = c

    return templates.TemplateResponse("queue.html", {
        "request": request,
        "project": project,
        "items": items,
        "counts": counts,
        "total": len(items),
        "current_page": "queue",
    })


@router.get("/panel", response_class=HTMLResponse)
def queue_panel(request: Request, db: Session = Depends(get_db)):
    """HTMX partial: collapsible queue panel for dashboard / daily ops."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse('<div class="text-xs text-mcc-muted py-2 text-center">No project</div>')

    items = db.query(ApprovalQueueItem).filter_by(
        project_id=project.id, status=QueueItemStatus.pending,
    ).order_by(ApprovalQueueItem.created_at.desc()).limit(10).all()

    for item in items:
        if item.contact_id:
            item._contact = db.get(OutreachContact, item.contact_id)
        else:
            item._contact = None

    if not items:
        return HTMLResponse(
            '<div class="text-xs text-mcc-muted py-4 text-center">Queue is clear. Nice work.</div>'
        )

    html_parts = []
    for item in items:
        html_parts.append(_render_queue_card(item))

    return HTMLResponse("\n".join(html_parts))


@router.post("/{item_id}/approve", response_class=HTMLResponse)
def approve_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ApprovalQueueItem, item_id)
    if not item:
        return HTMLResponse("")

    item.status = QueueItemStatus.approved
    item.acted_at = datetime.utcnow()

    # Execute the approved action
    if item.item_type == QueueItemType.outreach_followup and item.contact_id:
        contact = db.get(OutreachContact, item.contact_id)
        if contact:
            # Move draft to "ready" — append to outreach log for Phil to copy
            log_entry = f"[{datetime.utcnow().strftime('%b %d %Y')}] FOLLOW-UP APPROVED — ready to send:\n{item.draft_message}\n\n"
            contact.outreach_log = log_entry + (contact.outreach_log or "")

    elif item.item_type == QueueItemType.outreach_decline_check and item.contact_id:
        contact = db.get(OutreachContact, item.contact_id)
        if contact:
            contact.status = ContactStatus.declined
            contact.stage_changed_at = datetime.utcnow()

    elif item.item_type == QueueItemType.outreach_checkin and item.contact_id:
        contact = db.get(OutreachContact, item.contact_id)
        if contact:
            log_entry = f"[{datetime.utcnow().strftime('%b %d %Y')}] Check-in reminder acknowledged\n\n"
            contact.outreach_log = log_entry + (contact.outreach_log or "")

    elif item.item_type == QueueItemType.content_draft:
        # Create a ContentPiece in "scheduled" status for Phil to copy to Buffer
        piece = ContentPiece(
            project_id=item.project_id,
            title=item.draft_message[:100] if item.draft_message else item.title,
            series=item.content_series or "",
            content_type=ContentType.text_post,
            status=ContentStatus.scheduled,
            assigned_to="phil",
            platform_target=[item.content_platform or "x_twitter"],
            script_source=item.draft_message,
            notes=f"Pillar: {item.content_pillar}" if item.content_pillar else "",
        )
        db.add(piece)

    db.commit()

    label = {
        QueueItemType.outreach_followup: "Follow-up ready to send",
        QueueItemType.outreach_decline_check: "Moved to Declined",
        QueueItemType.outreach_checkin: "Check-in noted",
        QueueItemType.discovered_prospect: "Prospect kept",
        QueueItemType.ai_recommendation: "Acknowledged",
        QueueItemType.content_suggestion: "Approved",
        QueueItemType.content_draft: "Draft queued for posting",
    }.get(item.item_type, "Approved")

    return HTMLResponse(
        f'<div class="flex items-center gap-2 py-2 px-3 rounded-lg bg-mcc-success/10 border border-mcc-success/20">'
        f'<svg class="w-3.5 h-3.5 text-mcc-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
        f'<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>'
        f'<span class="text-xs text-mcc-success">{label}</span></div>'
    )


@router.post("/{item_id}/reject", response_class=HTMLResponse)
def reject_item(item_id: int, db: Session = Depends(get_db)):
    """Reject a content draft — logged so system learns what Phil doesn't want."""
    item = db.get(ApprovalQueueItem, item_id)
    if not item:
        return HTMLResponse("")

    item.status = QueueItemStatus.rejected
    item.acted_at = datetime.utcnow()
    db.commit()

    return HTMLResponse(
        '<div class="flex items-center gap-2 py-2 px-3 rounded-lg bg-mcc-critical/10 border border-mcc-critical/20">'
        '<span class="text-xs text-mcc-critical">Rejected — noted for future drafts</span></div>'
    )


@router.post("/{item_id}/skip", response_class=HTMLResponse)
def skip_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ApprovalQueueItem, item_id)
    if not item:
        return HTMLResponse("")

    item.status = QueueItemStatus.skipped
    item.acted_at = datetime.utcnow()
    db.commit()

    return HTMLResponse(
        '<div class="flex items-center gap-2 py-2 px-3 rounded-lg bg-mcc-bg border border-mcc-border">'
        '<span class="text-xs text-mcc-muted">Skipped</span></div>'
    )


@router.post("/{item_id}/edit", response_class=HTMLResponse)
def edit_item(
    item_id: int,
    draft_message: str = Form(""),
    db: Session = Depends(get_db),
):
    item = db.get(ApprovalQueueItem, item_id)
    if not item:
        return HTMLResponse("")

    if draft_message:
        item.draft_message = draft_message

    item.status = QueueItemStatus.approved
    item.acted_at = datetime.utcnow()

    # Apply edited draft
    if item.contact_id:
        contact = db.get(OutreachContact, item.contact_id)
        if contact:
            log_entry = f"[{datetime.utcnow().strftime('%b %d %Y')}] FOLLOW-UP APPROVED (edited) — ready to send:\n{item.draft_message}\n\n"
            contact.outreach_log = log_entry + (contact.outreach_log or "")

    db.commit()

    return HTMLResponse(
        '<div class="flex items-center gap-2 py-2 px-3 rounded-lg bg-mcc-success/10 border border-mcc-success/20">'
        '<svg class="w-3.5 h-3.5 text-mcc-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>'
        '<span class="text-xs text-mcc-success">Saved &amp; approved</span></div>'
    )


@router.get("/{item_id}/edit-form", response_class=HTMLResponse)
def edit_form(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ApprovalQueueItem, item_id)
    if not item:
        return HTMLResponse("")

    return HTMLResponse(f'''
        <form hx-post="/queue/{item.id}/edit" hx-target="#queue-item-{item.id}" hx-swap="outerHTML" class="space-y-2">
            <textarea name="draft_message" rows="4"
                class="w-full bg-mcc-bg border border-mcc-border rounded-lg px-3 py-2 text-xs text-mcc-text focus:border-mcc-accent/50 focus:outline-none resize-none"
            >{item.draft_message or item.preview}</textarea>
            <div class="flex items-center gap-2">
                <button type="submit" class="text-[10px] px-2 py-1 rounded bg-mcc-success/15 text-mcc-success hover:bg-mcc-success/25 font-medium transition-colors">
                    Save &amp; Approve
                </button>
                <button type="button" onclick="this.closest('form').outerHTML=''" class="text-[10px] px-2 py-1 rounded bg-mcc-bg text-mcc-muted hover:text-mcc-text font-medium transition-colors">
                    Cancel
                </button>
            </div>
        </form>
    ''')


def _render_queue_card(item: ApprovalQueueItem) -> str:
    """Render a single queue item card as HTML string."""
    type_colors = {
        "outreach_followup": ("text-purple-400", "bg-purple-500/10", "border-purple-500/20"),
        "outreach_decline_check": ("text-mcc-warning", "bg-mcc-warning/10", "border-mcc-warning/20"),
        "outreach_checkin": ("text-mcc-accent", "bg-mcc-accent/10", "border-mcc-accent/20"),
        "content_draft": ("text-blue-400", "bg-blue-500/10", "border-blue-500/20"),
        "content_suggestion": ("text-blue-400", "bg-blue-500/10", "border-blue-500/20"),
        "ai_recommendation": ("text-mcc-accent", "bg-mcc-accent/10", "border-mcc-accent/20"),
        "discovered_prospect": ("text-emerald-400", "bg-emerald-500/10", "border-emerald-500/20"),
    }
    text_color, bg_color, border_color = type_colors.get(
        item.item_type.value, ("text-mcc-muted", "bg-mcc-bg", "border-mcc-border")
    )

    type_label = item.item_type.value.replace("_", " ").title()
    age = ""
    if item.created_at:
        from datetime import datetime
        delta = datetime.utcnow() - item.created_at
        if delta.days > 0:
            age = f"{delta.days}d ago"
        elif delta.seconds >= 3600:
            age = f"{delta.seconds // 3600}h ago"
        else:
            age = "just now"

    # Contact link
    contact_link = ""
    if item.contact_id:
        contact_link = f'<a href="/pipelines/outreach" class="text-[10px] text-mcc-accent hover:text-mcc-accent/80 transition-colors">View contact</a>'

    # Approve label based on type
    approve_label = "Approve"
    if item.item_type == QueueItemType.outreach_decline_check:
        approve_label = "Yes, Decline"
    elif item.item_type == QueueItemType.outreach_checkin:
        approve_label = "Noted"

    # Edit button (only for items with draft messages)
    edit_btn = ""
    if item.draft_message:
        edit_btn = f'''<button hx-get="/queue/{item.id}/edit-form" hx-target="#queue-item-{item.id}" hx-swap="innerHTML"
                               class="text-[10px] px-2 py-1 rounded bg-mcc-bg text-mcc-muted hover:text-mcc-text font-medium transition-colors">Edit</button>'''

    # Reject button (only for content drafts)
    reject_btn = ""
    if item.item_type == QueueItemType.content_draft:
        reject_btn = f'''<button hx-post="/queue/{item.id}/reject" hx-target="#queue-item-{item.id}" hx-swap="outerHTML"
                                 class="text-[10px] px-2 py-1 rounded bg-mcc-critical/10 text-mcc-critical hover:bg-mcc-critical/20 font-medium transition-colors">Reject</button>'''

    # Content pillar badge
    pillar_badge = ""
    if item.content_pillar:
        pillar_badge = f'<span class="text-[9px] px-1.5 py-0.5 rounded bg-mcc-bg text-mcc-accent">{item.content_pillar}</span>'

    return f'''
    <div class="rounded-lg {bg_color} border {border_color} p-3 mb-2" id="queue-item-{item.id}">
        <div class="flex items-start justify-between gap-2 mb-1.5">
            <div class="flex items-center gap-2">
                <span class="text-[9px] uppercase font-semibold {text_color}">{item.source_label}</span>
                <span class="text-[9px] text-mcc-dim">{type_label}</span>
                {pillar_badge}
            </div>
            <span class="text-[9px] text-mcc-dim flex-shrink-0">{age}</span>
        </div>
        <div class="text-xs font-medium mb-1">{item.title}</div>
        <div class="text-[11px] text-mcc-muted leading-relaxed mb-2">{item.preview[:200]}</div>
        {contact_link}
        <div class="flex items-center gap-1.5 mt-2 pt-2 border-t border-mcc-border/30">
            <button hx-post="/queue/{item.id}/approve" hx-target="#queue-item-{item.id}" hx-swap="outerHTML"
                    class="text-[10px] px-2 py-1 rounded bg-mcc-success/15 text-mcc-success hover:bg-mcc-success/25 font-medium transition-colors">
                {approve_label}
            </button>
            {edit_btn}
            {reject_btn}
            <button hx-post="/queue/{item.id}/skip" hx-target="#queue-item-{item.id}" hx-swap="outerHTML"
                    class="text-[10px] px-2 py-1 rounded bg-mcc-bg text-mcc-muted hover:text-mcc-text font-medium transition-colors">Skip</button>
        </div>
    </div>'''
