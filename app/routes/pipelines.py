import csv
import io
import logging
from datetime import date, datetime
from fastapi import APIRouter, Request, Depends, Form, Query, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional

import httpx

from app.config import YOUTUBE_API_KEY
from app.database import get_db
from app.config import HUNTER_API_KEY
from app.models import (
    Project, Channel, EmailSequence, ContentPiece, OutreachContact,
    OnboardingMilestone, OnboardingProgress, ApprovalQueueItem,
    SequenceType, SequenceStatus, ContentType, ContentStatus,
    ProductionLane, ContactType, ContactStatus,
    QueueItemType, QueueItemStatus,
)

logger = logging.getLogger("mcc.pipelines")

router = APIRouter(prefix="/pipelines")
templates = Jinja2Templates(directory="app/templates")

CONTENT_COLUMNS = [
    ("concept", "Concept"),
    ("scripted", "Scripted"),
    ("filmed", "Filmed"),
    ("with_editor", "With Editor"),
    ("edited", "Edited"),
    ("scheduled", "Scheduled"),
    ("published", "Published"),
]

OUTREACH_COLUMNS = [
    ("identified", "Identified"),
    ("contacted", "Contacted"),
    ("responded", "Responded"),
    ("in_conversation", "In Conversation"),
    ("committed", "Committed"),
    ("active", "Active"),
    ("declined", "Declined"),
]


# ── Duplicate Detection ──────────────────────────────────────────

def _normalize_name(name: str) -> str:
    """Collapse whitespace, lowercase, strip for comparison."""
    import re
    return re.sub(r"\s+", " ", name.strip().lower())


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (0 if ca == cb else 1)))
        prev = curr
    return prev[-1]


def _normalize_youtube_url(url: str) -> str | None:
    """Extract a canonical YouTube channel identifier from various URL forms."""
    if not url:
        return None
    url = url.strip().lower()
    # Remove protocol/www
    for prefix in ("https://", "http://", "www."):
        url = url.removeprefix(prefix)
    # Normalize youtube.com/@handle → @handle
    for prefix in ("youtube.com/", "m.youtube.com/"):
        if url.startswith(prefix):
            url = url[len(prefix):]
    url = url.rstrip("/")
    return url or None


def _find_duplicate(
    db: Session,
    project_id: int,
    name: str,
    youtube_channel: str | None = None,
    contact_email: str | None = None,
    exclude_id: int | None = None,
) -> "OutreachContact | None":
    """Check for existing contact matching name (fuzzy), YouTube URL, or email.
    Returns the first matching contact or None."""
    contacts = db.query(OutreachContact).filter_by(project_id=project_id).all()

    norm_name = _normalize_name(name)
    norm_yt = _normalize_youtube_url(youtube_channel)
    norm_email = contact_email.strip().lower() if contact_email else None

    for c in contacts:
        if exclude_id and c.id == exclude_id:
            continue

        # Email match (exact, case-insensitive)
        if norm_email and c.contact_email:
            if c.contact_email.strip().lower() == norm_email:
                return c

        # YouTube channel match
        if norm_yt and c.youtube_channel:
            if _normalize_youtube_url(c.youtube_channel) == norm_yt:
                return c

        # Name match: case-insensitive exact or Levenshtein ≤ 2
        c_norm = _normalize_name(c.name)
        if c_norm == norm_name:
            return c
        if _levenshtein(c_norm, norm_name) <= 2:
            return c

    return None


def _find_all_duplicate_groups(db: Session, project_id: int) -> list[list["OutreachContact"]]:
    """Scan all contacts and return groups of potential duplicates."""
    contacts = db.query(OutreachContact).filter_by(project_id=project_id).order_by(
        OutreachContact.id
    ).all()

    # Build indexes
    by_email: dict[str, list] = {}
    by_yt: dict[str, list] = {}
    by_name: dict[str, list] = {}

    for c in contacts:
        if c.contact_email:
            key = c.contact_email.strip().lower()
            by_email.setdefault(key, []).append(c)
        if c.youtube_channel:
            key = _normalize_youtube_url(c.youtube_channel)
            if key:
                by_yt.setdefault(key, []).append(c)
        by_name.setdefault(_normalize_name(c.name), []).append(c)

    # Collect groups via union-find on contact IDs
    parent: dict[int, int] = {c.id: c.id for c in contacts}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Exact email match
    for group in by_email.values():
        if len(group) >= 2:
            for c in group[1:]:
                union(group[0].id, c.id)

    # Exact YouTube URL match
    for group in by_yt.values():
        if len(group) >= 2:
            for c in group[1:]:
                union(group[0].id, c.id)

    # Exact name match (normalized)
    for group in by_name.values():
        if len(group) >= 2:
            for c in group[1:]:
                union(group[0].id, c.id)

    # Fuzzy name match (Levenshtein ≤ 2) — O(n^2) but n is small (≤200)
    for i, a in enumerate(contacts):
        for b in contacts[i + 1:]:
            if find(a.id) == find(b.id):
                continue
            if _levenshtein(_normalize_name(a.name), _normalize_name(b.name)) <= 2:
                union(a.id, b.id)

    # Collect groups
    groups_map: dict[int, list] = {}
    for c in contacts:
        root = find(c.id)
        groups_map.setdefault(root, []).append(c)

    return [g for g in groups_map.values() if len(g) >= 2]


def _merge_contacts(db: Session, keep: "OutreachContact", remove: "OutreachContact"):
    """Merge remove into keep: fill empty fields from remove, preserve history, delete remove."""
    # Fill empty fields from the contact being removed
    for field in (
        "contact_email", "twitter_handle", "instagram_handle",
        "website_url", "youtube_channel", "commission_tier", "referral_link",
    ):
        if not getattr(keep, field) and getattr(remove, field):
            setattr(keep, field, getattr(remove, field))

    if not keep.audience_size and remove.audience_size:
        keep.audience_size = remove.audience_size

    # Preserve pipeline stage and notes from removed contact
    merge_note_parts = []
    merge_note_parts.append(
        f"[Merged #{remove.id}] Was: {remove.status.value.replace('_', ' ').title()}"
    )
    if remove.notes:
        merge_note_parts.append(f"Notes: {remove.notes}")
    if remove.outreach_log:
        merge_note_parts.append(f"Log: {remove.outreach_log}")

    merge_note = " | ".join(merge_note_parts)
    if keep.notes:
        keep.notes = keep.notes + "\n\n" + merge_note
    else:
        keep.notes = merge_note

    keep.updated_at = datetime.utcnow() if hasattr(keep, 'updated_at') else None
    db.delete(remove)


# --- Email Sequences ---
@router.get("/email")
def email_sequences(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("email_sequences.html", {
            "request": request, "project": None, "current_page": "email",
            "today": date.today(),
        })

    sequences = db.query(EmailSequence).filter_by(
        project_id=project.id
    ).order_by(EmailSequence.status, EmailSequence.name).all()

    # Group by status for pipeline view
    by_status = {}
    for s in SequenceStatus:
        items = [seq for seq in sequences if seq.status == s]
        if items:
            by_status[s.value] = items

    # Stats
    total_emails = sum(s.email_count for s in sequences)
    live_count = sum(1 for s in sequences if s.status == SequenceStatus.live)
    avg_open = None
    rates = [float(s.open_rate) for s in sequences if s.open_rate]
    if rates:
        avg_open = round(sum(rates) / len(rates), 1)

    return templates.TemplateResponse("email_sequences.html", {
        "request": request,
        "project": project,
        "sequences": sequences,
        "by_status": by_status,
        "total_emails": total_emails,
        "live_count": live_count,
        "avg_open": avg_open,
        "current_page": "email",
        "today": date.today(),
    })


# --- Content Pipeline ---
@router.get("/content")
def content_pipeline(
    request: Request,
    series: Optional[str] = Query(None),
    content_type: Optional[str] = Query(None),
    assignee: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("content_pipeline.html", {
            "request": request, "project": None, "current_page": "content",
            "today": date.today(),
        })

    pid = project.id
    query = db.query(ContentPiece).filter_by(project_id=pid)

    if series:
        query = query.filter(ContentPiece.series == series)
    if content_type:
        try:
            query = query.filter(ContentPiece.content_type == ContentType(content_type))
        except ValueError:
            pass
    if assignee:
        query = query.filter(ContentPiece.assigned_to == assignee)

    pieces = query.order_by(ContentPiece.due_date).all()

    # Build kanban columns
    columns = {}
    for status_val, label in CONTENT_COLUMNS:
        status = ContentStatus(status_val)
        columns[status_val] = {
            "label": label,
            "pieces": [p for p in pieces if p.status == status],
        }

    # Filter options
    all_series = sorted(set(p.series for p in db.query(ContentPiece).filter_by(project_id=pid).all() if p.series))
    all_assignees = sorted(set(p.assigned_to for p in db.query(ContentPiece).filter_by(project_id=pid).all() if p.assigned_to))

    # Weekly target (content published this week)
    today = date.today()
    week_start = today - __import__("datetime").timedelta(days=today.weekday())
    published_this_week = sum(
        1 for p in pieces
        if p.status == ContentStatus.published and p.published_at
        and p.published_at.date() >= week_start
    )

    # Cross-post tracker: pieces with multiple platform targets
    cross_posts = [p for p in pieces if p.platform_target and len(p.platform_target) > 1]

    # Content draft stats from Approval Queue
    drafts_pending = db.query(ApprovalQueueItem).filter_by(
        project_id=pid, item_type=QueueItemType.content_draft, status=QueueItemStatus.pending,
    ).count()
    drafts_approved = db.query(ApprovalQueueItem).filter(
        ApprovalQueueItem.project_id == pid,
        ApprovalQueueItem.item_type == QueueItemType.content_draft,
        ApprovalQueueItem.status == QueueItemStatus.approved,
        ApprovalQueueItem.acted_at >= datetime.combine(week_start, datetime.min.time()),
    ).count()
    # Find pillar gaps
    drafts_by_pillar = {}
    pending_drafts = db.query(ApprovalQueueItem).filter_by(
        project_id=pid, item_type=QueueItemType.content_draft, status=QueueItemStatus.pending,
    ).all()
    for d in pending_drafts:
        if d.content_pillar:
            drafts_by_pillar[d.content_pillar] = drafts_by_pillar.get(d.content_pillar, 0) + 1

    return templates.TemplateResponse("content_pipeline.html", {
        "request": request,
        "project": project,
        "columns": columns,
        "column_defs": CONTENT_COLUMNS,
        "total_pieces": len(pieces),
        "all_series": all_series,
        "all_content_types": [(t.value, t.value.replace("_", " ").title()) for t in ContentType],
        "all_assignees": all_assignees,
        "filter_series": series or "",
        "filter_type": content_type or "",
        "filter_assignee": assignee or "",
        "published_this_week": published_this_week,
        "cross_posts": cross_posts,
        "drafts_pending": drafts_pending,
        "drafts_approved": drafts_approved,
        "current_page": "content",
        "today": today,
    })


@router.post("/content/prepare-next-week", response_class=HTMLResponse)
async def prepare_next_week(request: Request, db: Session = Depends(get_db)):
    """Generate content drafts for next week and place in Approval Queue."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse('<span class="text-red-400 text-xs">No project</span>')

    from app.content_prep import generate_content_drafts
    count = await generate_content_drafts(db=db, project_id=project.id)

    if count > 0:
        return HTMLResponse(
            f'<span class="text-mcc-success text-xs">{count} drafts created — '
            f'<a href="/queue" class="text-mcc-accent hover:underline">review in Queue</a></span>'
        )
    return HTMLResponse(
        '<span class="text-mcc-warning text-xs">No drafts generated — check AI config or existing drafts</span>'
    )


@router.post("/content/move/{piece_id}")
def move_content(piece_id: int, status: str = Form(...), db: Session = Depends(get_db)):
    piece = db.get(ContentPiece, piece_id)
    if piece:
        try:
            piece.status = ContentStatus(status)
            if status == "published" and not piece.published_at:
                piece.published_at = datetime.utcnow()
            db.commit()
        except ValueError:
            pass
    return HTMLResponse('<span class="text-mcc-success text-[10px]">Moved</span>')


# --- Outreach Pipeline ---
@router.get("/outreach")
def outreach_pipeline(
    request: Request,
    contact_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("outreach_pipeline.html", {
            "request": request, "project": None, "current_page": "outreach",
            "today": date.today(),
        })

    pid = project.id
    today = date.today()

    query = db.query(OutreachContact).filter_by(project_id=pid)
    if contact_type:
        try:
            query = query.filter(OutreachContact.contact_type == ContactType(contact_type))
        except ValueError:
            pass

    contacts = query.order_by(OutreachContact.next_follow_up).all()

    # Build kanban columns
    columns = {}
    for status_val, label in OUTREACH_COLUMNS:
        status = ContactStatus(status_val)
        col_contacts = [c for c in contacts if c.status == status]
        columns[status_val] = {
            "label": label,
            "contacts": col_contacts,
        }

    # Overdue follow-ups
    overdue_followups = [
        c for c in contacts
        if c.next_follow_up and c.next_follow_up < today
        and c.status.value not in ("active", "declined", "ghosted")
    ]

    # Count discovered prospects still in Identified
    discovered_count = sum(
        1 for c in contacts
        if getattr(c, 'is_discovered', False) and c.is_discovered
        and c.status == ContactStatus.identified
    )

    return templates.TemplateResponse("outreach_pipeline.html", {
        "request": request,
        "project": project,
        "columns": columns,
        "column_defs": OUTREACH_COLUMNS,
        "total_contacts": len(contacts),
        "discovered_count": discovered_count,
        "overdue_followups": overdue_followups,
        "all_contact_types": [(t.value, t.value.replace("_", " ").title()) for t in ContactType],
        "filter_type": contact_type or "",
        "current_page": "outreach",
        "today": today,
    })


@router.post("/outreach/move/{contact_id}")
def move_outreach(contact_id: int, status: str = Form(...), db: Session = Depends(get_db)):
    contact = db.get(OutreachContact, contact_id)
    if contact:
        try:
            new_status = ContactStatus(status)
            if contact.status != new_status:
                contact.status = new_status
                contact.stage_changed_at = datetime.utcnow()
            db.commit()
        except ValueError:
            pass
    return HTMLResponse('<span class="text-mcc-success text-[10px]">Moved</span>')


# --- Contact CRUD ---

NEXT_STATUS = {
    "identified": "contacted",
    "contacted": "responded",
    "responded": "in_conversation",
    "in_conversation": "committed",
    "committed": "active",
}

PLATFORMS = ["YouTube", "Twitter/X", "Instagram", "TikTok", "Podcast", "LinkedIn", "Discord", "Other"]


import re


def _parse_youtube_channel(raw: str) -> tuple[str, str]:
    """Parse a YouTube channel input into (lookup_type, value).

    Accepts:
      - Channel ID: UC... (24 chars starting with UC)
      - Handle: @handle
      - URL: youtube.com/@handle, youtube.com/c/name, youtube.com/channel/UCxxx
      - Plain name: falls back to search

    Returns: ("id", "UCxxx") or ("handle", "@handle") or ("search", "name")
    """
    raw = raw.strip()

    # Strip full YouTube URLs down to the path component
    url_match = re.match(
        r'(?:https?://)?(?:www\.)?youtube\.com/(.+)', raw, re.IGNORECASE
    )
    if url_match:
        path = url_match.group(1).strip("/")
        # youtube.com/channel/UCxxx
        ch_match = re.match(r'channel/(UC[\w-]+)', path)
        if ch_match:
            return ("id", ch_match.group(1))
        # youtube.com/@handle
        if path.startswith("@"):
            return ("handle", path.split("/")[0])
        # youtube.com/c/channelname
        c_match = re.match(r'c/([^/]+)', path)
        if c_match:
            return ("handle", "@" + c_match.group(1))
        # youtube.com/somename (legacy vanity)
        return ("handle", "@" + path.split("/")[0])

    # Bare @handle
    if raw.startswith("@"):
        return ("handle", raw.split("/")[0].split("?")[0])

    # Channel ID pattern (starts with UC, typically 24 chars)
    if re.match(r'^UC[\w-]{20,}$', raw):
        return ("id", raw)

    # Fallback: treat as search query
    return ("search", raw)


def _enrich_youtube(youtube_channel: str | None, fallback_name: str) -> dict:
    """Look up a YouTube channel and return enrichment data.

    Uses youtube_channel field for direct lookup when available,
    falls back to searching by name.
    Returns empty dict on any failure.
    """
    if not YOUTUBE_API_KEY:
        logger.warning("YOUTUBE_API_KEY not configured, skipping enrichment")
        return {}

    lookup_input = youtube_channel if youtube_channel else fallback_name
    lookup_type, lookup_value = _parse_youtube_channel(lookup_input)

    try:
        with httpx.Client(timeout=5.0) as client:
            channel_id = None

            if lookup_type == "id":
                channel_id = lookup_value

            elif lookup_type == "handle":
                # Use forHandle parameter (works with @handle)
                handle = lookup_value.lstrip("@")
                resp = client.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    params={
                        "part": "id",
                        "forHandle": handle,
                        "key": YOUTUBE_API_KEY,
                    },
                )
                resp.raise_for_status()
                items = resp.json().get("items", [])
                if items:
                    channel_id = items[0]["id"]
                else:
                    # Handle not found, fall back to search
                    lookup_type = "search"
                    lookup_value = handle

            if lookup_type == "search":
                # Search costs 100 quota units vs 1 for direct lookup
                search_resp = client.get(
                    "https://www.googleapis.com/youtube/v3/search",
                    params={
                        "part": "snippet",
                        "type": "channel",
                        "q": lookup_value,
                        "maxResults": 1,
                        "key": YOUTUBE_API_KEY,
                    },
                )
                search_resp.raise_for_status()
                items = search_resp.json().get("items", [])
                if not items:
                    return {}
                channel_id = items[0]["snippet"]["channelId"]

            if not channel_id:
                return {}

            # Fetch full channel details (1 quota unit)
            ch_resp = client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={
                    "part": "snippet,statistics,brandingSettings",
                    "id": channel_id,
                    "key": YOUTUBE_API_KEY,
                },
            )
            ch_resp.raise_for_status()
            ch_items = ch_resp.json().get("items", [])
            if not ch_items:
                return {}

            channel = ch_items[0]
            snippet = channel.get("snippet", {})
            stats = channel.get("statistics", {})
            branding = channel.get("brandingSettings", {}).get("channel", {})

            result = {}

            # Subscriber count
            sub_count = stats.get("subscriberCount")
            if sub_count:
                try:
                    result["audience_size"] = int(sub_count)
                except (ValueError, TypeError):
                    pass

            # Channel description -> notes
            description = snippet.get("description", "").strip()
            if description:
                if len(description) > 500:
                    description = description[:497] + "..."
                result["notes"] = f"[YouTube] {description}"

            # Custom URL -> website
            custom_url = snippet.get("customUrl", "")
            if custom_url:
                if custom_url.startswith("@"):
                    result["website_url"] = f"https://youtube.com/{custom_url}"
                else:
                    result["website_url"] = f"https://youtube.com/c/{custom_url}"

            # Branding keywords
            keywords = branding.get("keywords", "")
            if keywords and "notes" in result:
                result["notes"] += f"\nKeywords: {keywords[:200]}"

            return result

    except httpx.TimeoutException:
        logger.error(f"YouTube API timeout enriching '{lookup_input}'")
        return {}
    except Exception as e:
        logger.error(f"YouTube API error enriching '{lookup_input}': {e}")
        return {}


def _apply_enrichment(contact, enrichment: dict):
    """Apply enrichment data to a contact, never overwriting user-entered values."""
    if not enrichment:
        return

    if enrichment.get("audience_size") and not contact.audience_size:
        contact.audience_size = enrichment["audience_size"]

    if enrichment.get("website_url") and not contact.website_url:
        contact.website_url = enrichment["website_url"]

    if enrichment.get("contact_email") and not contact.contact_email:
        contact.contact_email = enrichment["contact_email"]

    if enrichment.get("notes"):
        if not contact.notes:
            contact.notes = enrichment["notes"]
        else:
            # Append enrichment notes below user notes
            contact.notes = contact.notes + "\n\n" + enrichment["notes"]


def _contact_card_html(contact, today):
    """Render a single contact card as HTML string."""
    next_stage = NEXT_STATUS.get(contact.status.value)
    arrow_btn = ""
    if next_stage:
        arrow_btn = (
            f'<button class="advance-btn absolute top-1 right-1 w-5 h-5 rounded flex items-center justify-center '
            f'text-[10px] text-mcc-muted hover:text-mcc-accent hover:bg-mcc-card transition-colors" '
            f'hx-post="/pipelines/outreach/advance/{contact.id}" hx-target="closest .outreach-card" '
            f'hx-swap="outerHTML" title="Move to {next_stage.replace("_"," ").title()}">'
            f'&rarr;</button>'
        )

    audience = ""
    if contact.audience_size:
        audience = f'<span class="text-[10px] font-mono text-mcc-muted">{contact.audience_size:,}</span>'

    followup = ""
    if contact.next_follow_up:
        css = "text-mcc-muted"
        if contact.next_follow_up < today:
            css = "text-mcc-critical"
        elif contact.next_follow_up == today:
            css = "text-mcc-warning"
        followup = (
            f'<div class="text-[9px] mt-1 font-mono {css}">'
            f'Follow-up: {contact.next_follow_up.strftime("%b %d")}</div>'
        )

    notes_html = ""
    if contact.notes:
        from markupsafe import escape
        notes_html = f'<div class="text-[9px] text-mcc-muted mt-1 truncate">{escape(contact.notes)}</div>'

    ct_label = contact.contact_type.value.replace("_", " ").title()

    enrich_btn = ""
    if contact.platform == "YouTube":
        enrich_btn = (
            f'<button class="enrich-btn absolute top-1 right-7 w-5 h-5 rounded flex items-center justify-center '
            f'text-[10px] text-mcc-muted hover:text-mcc-accent hover:bg-mcc-card transition-colors" '
            f'hx-post="/pipelines/outreach/enrich/{contact.id}" hx-target="closest .outreach-card" '
            f'hx-swap="outerHTML" hx-indicator="closest .outreach-card" '
            f'onclick="event.stopPropagation()" title="Re-enrich from YouTube">'
            f'&#x1f504;</button>'
        )

    # Discovered badge + accept/dismiss buttons
    discovered_html = ""
    if getattr(contact, 'is_discovered', False) and contact.is_discovered:
        disc_date = ""
        if contact.discovered_at:
            disc_date = contact.discovered_at.strftime("%b %d")
        discovered_html = (
            f'<div class="flex items-center gap-1 mt-1.5 mb-1">'
            f'<span class="text-[8px] px-1.5 py-0.5 rounded-full bg-cyan-500/15 text-cyan-400 font-medium">'
            f'Discovered{" " + disc_date if disc_date else ""}</span>'
            f'<button class="accept-btn text-[9px] px-1.5 py-0.5 rounded bg-mcc-success/15 text-mcc-success hover:bg-mcc-success/30 transition-colors" '
            f'hx-post="/pipelines/outreach/accept/{contact.id}" hx-target="closest .outreach-card" '
            f'hx-swap="outerHTML" onclick="event.stopPropagation()" title="Keep this prospect">Keep</button>'
            f'<button class="dismiss-btn text-[9px] px-1.5 py-0.5 rounded bg-mcc-critical/15 text-mcc-critical hover:bg-mcc-critical/30 transition-colors" '
            f'hx-post="/pipelines/outreach/dismiss/{contact.id}" hx-target="closest .outreach-card" '
            f'hx-swap="outerHTML" onclick="event.stopPropagation()" title="Dismiss (won\'t resurface)">Dismiss</button>'
            f'</div>'
        )

    # Find Email button (shown when no email on file)
    find_email_html = ""
    if not contact.contact_email:
        find_email_html = (
            f'<div class="mt-1">'
            f'<button class="find-email-btn text-[9px] px-1.5 py-0.5 rounded bg-mcc-card text-mcc-muted '
            f'hover:text-mcc-accent hover:bg-mcc-card/80 transition-colors border border-mcc-border/50" '
            f'hx-post="/pipelines/outreach/find-email/{contact.id}" hx-target="closest .outreach-card .find-email-result" '
            f'hx-swap="innerHTML" onclick="event.stopPropagation()" title="Search for contact email">'
            f'Find Email</button>'
            f'<div class="find-email-result mt-1"></div>'
            f'</div>'
        )

    border_class = ""
    if getattr(contact, 'is_discovered', False) and contact.is_discovered:
        border_class = " border border-cyan-500/20"

    return (
        f'<div class="bg-mcc-bg rounded-lg p-2.5 cursor-move outreach-card relative{border_class}" data-id="{contact.id}" '
        f'onclick="openEditContact({contact.id})" style="cursor:pointer">'
        f'{enrich_btn}{arrow_btn}'
        f'<div class="text-xs font-medium mb-1">{contact.name}</div>'
        f'<div class="flex items-center justify-between mb-1">'
        f'<span class="text-[10px] text-mcc-muted">{contact.platform}</span>'
        f'{audience}</div>'
        f'<span class="text-[9px] px-1.5 py-0.5 rounded bg-mcc-card text-mcc-muted">{ct_label}</span>'
        f'{discovered_html}'
        f'{followup}{notes_html}'
        f'{find_email_html}'
        f'</div>'
    )


@router.post("/outreach/add")
def add_contact(
    request: Request,
    name: str = Form(...),
    platform: str = Form(...),
    contact_type: str = Form("influencer"),
    audience_size: Optional[int] = Form(None),
    contact_email: Optional[str] = Form(None),
    twitter_handle: Optional[str] = Form(None),
    instagram_handle: Optional[str] = Form(None),
    website_url: Optional[str] = Form(None),
    youtube_channel: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("No project", status_code=400)

    # Duplicate detection
    dup = _find_duplicate(
        db, project.id, name.strip(),
        youtube_channel=youtube_channel.strip() if youtube_channel else None,
        contact_email=contact_email.strip() if contact_email else None,
    )
    if dup:
        from markupsafe import escape
        logger.info("Duplicate skipped: '%s' matches existing '%s' (#%d)", name.strip(), dup.name, dup.id)
        return HTMLResponse(
            f'<div class="dup-toast fixed bottom-4 right-4 z-[70] bg-mcc-warning/15 border border-mcc-warning/40 '
            f'rounded-lg px-4 py-3 shadow-lg text-xs max-w-sm animate-slide-up" '
            f'onclick="this.remove()" style="animation: slideUp .3s ease-out">'
            f'<div class="font-semibold text-mcc-warning mb-0.5">Duplicate skipped</div>'
            f'<div class="text-mcc-text">{escape(name.strip())}</div>'
            f'<div class="text-mcc-muted mt-0.5">Already exists as <strong>{escape(dup.name)}</strong> (#{dup.id})</div>'
            f'</div>'
        )

    contact = OutreachContact(
        project_id=project.id,
        name=name.strip(),
        platform=platform,
        contact_type=ContactType(contact_type),
        status=ContactStatus.identified,
        audience_size=audience_size,
        contact_email=contact_email.strip() if contact_email else None,
        twitter_handle=twitter_handle.strip() if twitter_handle else None,
        instagram_handle=instagram_handle.strip() if instagram_handle else None,
        website_url=website_url.strip() if website_url else None,
        youtube_channel=youtube_channel.strip() if youtube_channel else None,
        notes=notes.strip() if notes else "",
    )

    # Auto-enrich based on platform
    if platform == "YouTube":
        enrichment = _enrich_youtube(contact.youtube_channel, name.strip())
        _apply_enrichment(contact, enrichment)

    db.add(contact)
    db.commit()
    db.refresh(contact)

    return HTMLResponse(_contact_card_html(contact, date.today()))


@router.get("/outreach/contact/{contact_id}")
def get_contact(contact_id: int, request: Request, db: Session = Depends(get_db)):
    contact = db.get(OutreachContact, contact_id)
    if not contact:
        return HTMLResponse("Not found", status_code=404)

    platforms_html = "".join(
        f'<option value="{p}" {"selected" if contact.platform == p else ""}>{p}</option>'
        for p in PLATFORMS
    )
    types_html = "".join(
        f'<option value="{t.value}" {"selected" if contact.contact_type == t else ""}>'
        f'{t.value.replace("_"," ").title()}</option>'
        for t in ContactType
    )
    stages_html = "".join(
        f'<option value="{s.value}" {"selected" if contact.status == s else ""}>'
        f'{s.value.replace("_"," ").title()}</option>'
        for s in ContactStatus
    )

    last_date = contact.last_contact_date.isoformat() if contact.last_contact_date else ""
    follow_date = contact.next_follow_up.isoformat() if contact.next_follow_up else ""

    return HTMLResponse(f'''
    <h3 class="text-sm font-semibold mb-4">Edit Contact</h3>
    <form hx-post="/pipelines/outreach/update/{contact.id}" hx-target="#contact-modal-content" hx-swap="innerHTML">
        <div class="space-y-3">
            <div>
                <label class="text-xs text-mcc-muted block mb-1">Name *</label>
                <input type="text" name="name" value="{contact.name}" class="mcc-input w-full text-xs" required>
            </div>
            <div class="grid grid-cols-2 gap-3">
                <div>
                    <label class="text-xs text-mcc-muted block mb-1">Platform *</label>
                    <select name="platform" class="mcc-select w-full text-xs">{platforms_html}</select>
                </div>
                <div>
                    <label class="text-xs text-mcc-muted block mb-1">Type</label>
                    <select name="contact_type" class="mcc-select w-full text-xs">{types_html}</select>
                </div>
            </div>
            <div class="grid grid-cols-2 gap-3">
                <div>
                    <label class="text-xs text-mcc-muted block mb-1">Stage</label>
                    <select name="status" class="mcc-select w-full text-xs">{stages_html}</select>
                </div>
                <div>
                    <label class="text-xs text-mcc-muted block mb-1">Audience Size</label>
                    <input type="number" name="audience_size" value="{contact.audience_size or ''}" class="mcc-input w-full text-xs">
                </div>
            </div>
            <div id="edit-yt-channel-row" style="display:{'block' if contact.platform == 'YouTube' else 'none'}">
                <label class="text-xs text-mcc-muted block mb-1">YouTube Channel</label>
                <input type="text" name="youtube_channel" value="{contact.youtube_channel or ''}" class="mcc-input w-full text-xs" placeholder="@handle, channel URL, or channel ID">
                <div class="text-[9px] text-mcc-muted mt-0.5">Used for enrichment lookup (more accurate than name search)</div>
            </div>
            <div>
                <label class="text-xs text-mcc-muted block mb-1">Email</label>
                <input type="email" name="contact_email" value="{contact.contact_email or ''}" class="mcc-input w-full text-xs">
            </div>
            <div class="grid grid-cols-2 gap-3">
                <div>
                    <label class="text-xs text-mcc-muted block mb-1">Twitter/X</label>
                    <input type="text" name="twitter_handle" value="{contact.twitter_handle or ''}" class="mcc-input w-full text-xs" placeholder="@handle">
                </div>
                <div>
                    <label class="text-xs text-mcc-muted block mb-1">Instagram</label>
                    <input type="text" name="instagram_handle" value="{contact.instagram_handle or ''}" class="mcc-input w-full text-xs" placeholder="@handle">
                </div>
            </div>
            <div>
                <label class="text-xs text-mcc-muted block mb-1">Website</label>
                <input type="text" name="website_url" value="{contact.website_url or ''}" class="mcc-input w-full text-xs">
            </div>
            <div class="grid grid-cols-2 gap-3">
                <div>
                    <label class="text-xs text-mcc-muted block mb-1">Last Contacted</label>
                    <input type="date" name="last_contact_date" value="{last_date}" class="mcc-input w-full text-xs">
                </div>
                <div>
                    <label class="text-xs text-mcc-muted block mb-1">Next Follow-up</label>
                    <input type="date" name="next_follow_up" value="{follow_date}" class="mcc-input w-full text-xs">
                </div>
            </div>
            <div>
                <label class="text-xs text-mcc-muted block mb-1">Notes</label>
                <textarea name="notes" rows="2" class="mcc-input w-full text-xs">{contact.notes or ''}</textarea>
            </div>
            <div>
                <label class="text-xs text-mcc-muted block mb-1">Outreach Log (new entry appended with timestamp)</label>
                <textarea name="new_log_entry" rows="2" class="mcc-input w-full text-xs" placeholder="Add a note about this outreach attempt..."></textarea>
                {"" if not contact.outreach_log else '<div class="mt-2 max-h-32 overflow-y-auto text-[10px] text-mcc-muted bg-mcc-bg rounded p-2 whitespace-pre-wrap">' + (contact.outreach_log or '') + '</div>'}
            </div>
            <div class="flex gap-2 pt-2">
                <button type="submit" class="flex-1 bg-mcc-accent text-white text-xs py-2 rounded hover:bg-mcc-accent/80 transition-colors">
                    Save Changes
                </button>
                <button type="button" onclick="closeContactModal()" class="flex-1 bg-mcc-card text-mcc-muted text-xs py-2 rounded border border-mcc-border hover:text-white transition-colors">
                    Cancel
                </button>
            </div>
        </div>
    </form>
    ''')


@router.post("/outreach/update/{contact_id}")
def update_contact(
    contact_id: int,
    name: str = Form(...),
    platform: str = Form(...),
    contact_type: str = Form("influencer"),
    status: str = Form("identified"),
    audience_size: Optional[int] = Form(None),
    contact_email: Optional[str] = Form(None),
    twitter_handle: Optional[str] = Form(None),
    instagram_handle: Optional[str] = Form(None),
    website_url: Optional[str] = Form(None),
    youtube_channel: Optional[str] = Form(None),
    last_contact_date: Optional[str] = Form(None),
    next_follow_up: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    new_log_entry: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    contact = db.get(OutreachContact, contact_id)
    if not contact:
        return HTMLResponse("Not found", status_code=404)

    contact.name = name.strip()
    contact.platform = platform
    contact.contact_type = ContactType(contact_type)
    contact.status = ContactStatus(status)
    contact.audience_size = audience_size
    contact.contact_email = contact_email.strip() if contact_email else None
    contact.twitter_handle = twitter_handle.strip() if twitter_handle else None
    contact.instagram_handle = instagram_handle.strip() if instagram_handle else None
    contact.website_url = website_url.strip() if website_url else None
    contact.youtube_channel = youtube_channel.strip() if youtube_channel else None
    contact.notes = notes.strip() if notes else ""

    if last_contact_date:
        contact.last_contact_date = date.fromisoformat(last_contact_date)
    else:
        contact.last_contact_date = None

    if next_follow_up:
        contact.next_follow_up = date.fromisoformat(next_follow_up)
    else:
        contact.next_follow_up = None

    if new_log_entry and new_log_entry.strip():
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"[{timestamp}] {new_log_entry.strip()}"
        if contact.outreach_log:
            contact.outreach_log = entry + "\n" + contact.outreach_log
        else:
            contact.outreach_log = entry

    db.commit()

    return HTMLResponse('''
        <div class="text-center py-8">
            <div class="text-mcc-success text-sm font-medium mb-2">Contact updated</div>
            <p class="text-xs text-mcc-muted mb-4">Reload the page to see changes in the board.</p>
            <button onclick="closeContactModal(); location.reload();"
                class="bg-mcc-accent text-white text-xs px-4 py-2 rounded hover:bg-mcc-accent/80 transition-colors">
                Done
            </button>
        </div>
    ''')


@router.post("/outreach/advance/{contact_id}")
def advance_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.get(OutreachContact, contact_id)
    if not contact:
        return HTMLResponse("Not found", status_code=404)

    current = contact.status.value
    next_status = NEXT_STATUS.get(current)
    if next_status:
        contact.status = ContactStatus(next_status)
        contact.stage_changed_at = datetime.utcnow()
        if next_status == "contacted":
            contact.last_contact_date = date.today()

        # Auto-accept discovered prospect on advance
        if getattr(contact, 'is_discovered', False) and contact.is_discovered:
            contact.is_discovered = False
            if contact.platform == "YouTube":
                enrichment = _enrich_youtube(contact.youtube_channel, contact.name)
                _apply_enrichment(contact, enrichment)

        db.commit()

    return HTMLResponse(_contact_card_html(contact, date.today()))


@router.post("/outreach/enrich/{contact_id}")
def enrich_contact(contact_id: int, db: Session = Depends(get_db)):
    """Re-enrich an existing contact from its platform API."""
    contact = db.get(OutreachContact, contact_id)
    if not contact:
        return HTMLResponse("Not found", status_code=404)

    enrichment = {}
    if contact.platform == "YouTube":
        enrichment = _enrich_youtube(contact.youtube_channel, contact.name)

    if enrichment:
        _apply_enrichment(contact, enrichment)
        db.commit()
        db.refresh(contact)

    return HTMLResponse(_contact_card_html(contact, date.today()))


@router.get("/outreach/youtube-ids")
def youtube_contact_ids(db: Session = Depends(get_db)):
    """Return JSON list of YouTube contact IDs for bulk enrichment."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return []
    contacts = db.query(OutreachContact).filter_by(
        project_id=project.id, platform="YouTube"
    ).all()
    return [
        {"id": c.id, "has_audience": c.audience_size is not None and c.audience_size > 0}
        for c in contacts
    ]


@router.post("/outreach/import-csv")
async def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("No project", status_code=400)

    contents = await file.read()
    text = contents.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    imported = 0
    skipped = 0
    errors = []

    field_map = {
        "name": "name", "platform": "platform", "subscriber_count": "audience_size",
        "audience_size": "audience_size", "followers": "audience_size",
        "type": "contact_type", "contact_type": "contact_type",
        "contact_email": "contact_email", "email": "contact_email",
        "twitter": "twitter_handle", "twitter_handle": "twitter_handle",
        "instagram": "instagram_handle", "instagram_handle": "instagram_handle",
        "website": "website_url", "website_url": "website_url",
        "description": "notes", "notes": "notes",
    }

    valid_types = {t.value for t in ContactType}

    for i, row in enumerate(reader):
        mapped = {}
        for csv_col, val in row.items():
            key = csv_col.strip().lower().replace(" ", "_")
            if key in field_map:
                mapped[field_map[key]] = val.strip() if val else None

        name = mapped.get("name")
        platform = mapped.get("platform", "Other")
        if not name:
            errors.append(f"Row {i+1}: missing name")
            continue

        dup = _find_duplicate(
            db, project.id, name,
            youtube_channel=mapped.get("website_url"),  # CSVs sometimes put YT URL here
            contact_email=mapped.get("contact_email"),
        )
        if dup:
            skipped += 1
            continue

        ct = mapped.get("contact_type", "influencer")
        if ct not in valid_types:
            ct = "influencer"

        audience = None
        if mapped.get("audience_size"):
            try:
                audience = int(mapped["audience_size"].replace(",", ""))
            except (ValueError, AttributeError):
                pass

        contact = OutreachContact(
            project_id=project.id,
            name=name,
            platform=platform,
            audience_size=audience,
            contact_type=ContactType(ct),
            status=ContactStatus.identified,
            contact_email=mapped.get("contact_email"),
            twitter_handle=mapped.get("twitter_handle"),
            instagram_handle=mapped.get("instagram_handle"),
            website_url=mapped.get("website_url"),
            notes=mapped.get("notes", ""),
        )
        db.add(contact)
        imported += 1

    db.commit()

    skip_msg = f", {skipped} duplicates skipped" if skipped else ""
    err_msg = f", {len(errors)} errors" if errors else ""
    error_details = ""
    if errors:
        error_details = '<div class="mt-2 text-[10px] text-mcc-muted">' + "<br>".join(errors[:10]) + "</div>"

    return HTMLResponse(f'''
        <div class="text-center py-8">
            <div class="text-mcc-success text-sm font-medium mb-2">{imported} contacts imported</div>
            <p class="text-xs text-mcc-muted mb-4">{imported} added{skip_msg}{err_msg}</p>
            {error_details}
            <button onclick="closeContactModal(); location.reload();"
                class="bg-mcc-accent text-white text-xs px-4 py-2 rounded hover:bg-mcc-accent/80 transition-colors">
                Done
            </button>
        </div>
    ''')


@router.post("/outreach/import-preview")
async def import_preview(
    file: UploadFile = File(...),
):
    contents = await file.read()
    text = contents.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    rows = []
    for i, row in enumerate(reader):
        if i >= 5:
            break
        rows.append(row)

    total_lines = text.count("\n")

    if not rows:
        return HTMLResponse('<div class="text-xs text-mcc-critical">No data found in CSV</div>')

    headers = list(rows[0].keys())
    header_html = "".join(f'<th class="px-2 py-1 text-left text-[10px] text-mcc-muted">{h}</th>' for h in headers)
    body_html = ""
    for row in rows:
        cells = "".join(f'<td class="px-2 py-1 text-[10px] truncate max-w-[120px]">{row.get(h,"")}</td>' for h in headers)
        body_html += f"<tr class='border-t border-mcc-border'>{cells}</tr>"

    return HTMLResponse(f'''
        <div class="mb-3">
            <div class="text-xs text-mcc-muted mb-2">Preview (first 5 of ~{total_lines} rows):</div>
            <div class="overflow-x-auto">
                <table class="w-full"><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>
            </div>
        </div>
        <div class="flex gap-2">
            <button type="button" onclick="submitCsvImport()" class="flex-1 bg-mcc-accent text-white text-xs py-2 rounded hover:bg-mcc-accent/80">
                Import All
            </button>
            <button type="button" onclick="closeContactModal()" class="flex-1 bg-mcc-card text-mcc-muted text-xs py-2 rounded border border-mcc-border hover:text-white">
                Cancel
            </button>
        </div>
    ''')


# ── Outreach Duplicate Sweep & Merge ──────────────────────────────

@router.get("/outreach/find-duplicates")
def find_duplicates(request: Request, db: Session = Depends(get_db)):
    """Scan all contacts and return duplicate groups in a modal."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("No project", status_code=400)

    groups = _find_all_duplicate_groups(db, project.id)

    if not groups:
        return HTMLResponse(
            '<div class="text-center py-12">'
            '<div class="text-mcc-success text-sm font-semibold mb-2">No duplicates found</div>'
            '<div class="text-xs text-mcc-muted">All 133 contacts are unique.</div>'
            '</div>'
        )

    from markupsafe import escape

    html_groups = []
    for i, group in enumerate(groups):
        cards = []
        for c in group:
            # Score: count non-empty useful fields
            score = sum(1 for f in (
                c.contact_email, c.audience_size, c.youtube_channel,
                c.twitter_handle, c.instagram_handle, c.website_url,
                c.notes, c.outreach_log, c.commission_tier,
            ) if f)
            stage = c.status.value.replace("_", " ").title()
            aud = f'{c.audience_size:,}' if c.audience_size else '—'
            email = escape(c.contact_email) if c.contact_email else '—'
            yt = escape(c.youtube_channel or '—')
            notes_preview = escape((c.notes or '')[:80])
            notes_div = f'<div class="text-mcc-muted mt-1 truncate">{notes_preview}</div>' if notes_preview else ''

            cards.append(
                f'<div class="bg-mcc-bg rounded-lg p-3 flex-1 min-w-0">'
                f'<div class="flex items-center justify-between mb-2">'
                f'<span class="text-xs font-semibold">{escape(c.name)}</span>'
                f'<span class="text-[9px] px-1.5 py-0.5 rounded bg-mcc-card text-mcc-muted">#{c.id}</span>'
                f'</div>'
                f'<div class="space-y-1 text-[10px]">'
                f'<div class="flex justify-between"><span class="text-mcc-muted">Stage</span><span>{stage}</span></div>'
                f'<div class="flex justify-between"><span class="text-mcc-muted">Platform</span><span>{c.platform}</span></div>'
                f'<div class="flex justify-between"><span class="text-mcc-muted">Audience</span><span class="font-mono">{aud}</span></div>'
                f'<div class="flex justify-between"><span class="text-mcc-muted">Email</span><span class="truncate max-w-[140px]">{email}</span></div>'
                f'<div class="flex justify-between"><span class="text-mcc-muted">YouTube</span><span class="truncate max-w-[140px]">{yt}</span></div>'
                f'<div class="flex justify-between"><span class="text-mcc-muted">Data score</span><span class="font-mono">{score}/9</span></div>'
                f'{notes_div}'
                f'</div></div>'
            )

        # Determine which has more data (for auto-merge suggestion)
        scored = sorted(group, key=lambda c: sum(1 for f in (
            c.contact_email, c.audience_size, c.youtube_channel,
            c.twitter_handle, c.instagram_handle, c.website_url,
            c.notes, c.outreach_log, c.commission_tier,
        ) if f), reverse=True)
        keep_id = scored[0].id
        remove_id = scored[1].id

        html_groups.append(
            f'<div class="border border-mcc-border rounded-lg p-4 mb-4" id="dup-group-{i}">'
            f'<div class="text-[10px] text-mcc-muted uppercase tracking-wide mb-3">Duplicate Group {i+1}</div>'
            f'<div class="flex gap-3 mb-3">{"".join(cards)}</div>'
            f'<div class="flex items-center gap-2">'
            f'<button hx-post="/pipelines/outreach/merge-duplicates" '
            f'hx-vals=\'{{"keep_id": {keep_id}, "remove_id": {remove_id}}}\' '
            f'hx-target="#dup-group-{i}" hx-swap="outerHTML" '
            f'class="text-[10px] px-3 py-1.5 rounded bg-mcc-accent text-white hover:bg-mcc-accent/80 transition-colors">'
            f'Merge (keep #{keep_id})</button>'
            f'<button onclick="document.getElementById(\'dup-group-{i}\').remove()" '
            f'class="text-[10px] px-3 py-1.5 rounded border border-mcc-border text-mcc-muted hover:text-white transition-colors">'
            f'Keep Both</button>'
            f'<span class="text-[9px] text-mcc-muted ml-2">Keeps the record with more data, merges missing fields from the other.</span>'
            f'</div></div>'
        )

    return HTMLResponse(
        f'<div class="mb-4">'
        f'<div class="text-sm font-semibold mb-1">Found {len(groups)} duplicate group{"s" if len(groups) != 1 else ""}</div>'
        f'<div class="text-xs text-mcc-muted mb-4">Review each group. Merge combines data into the richer record.</div>'
        f'</div>'
        f'<div id="dup-results">{"".join(html_groups)}</div>'
    )


@router.post("/outreach/merge-duplicates")
def merge_duplicates(
    keep_id: int = Form(...),
    remove_id: int = Form(...),
    db: Session = Depends(get_db),
):
    """Merge two duplicate contacts: keep one, absorb the other."""
    keep = db.get(OutreachContact, keep_id)
    remove = db.get(OutreachContact, remove_id)
    if not keep or not remove:
        return HTMLResponse(
            '<div class="text-xs text-mcc-critical py-2">Contact not found</div>'
        )

    from markupsafe import escape
    removed_name = remove.name
    _merge_contacts(db, keep, remove)
    db.commit()

    logger.info("Merged outreach contact #%d into #%d (%s)", remove_id, keep_id, keep.name)

    return HTMLResponse(
        f'<div class="border border-mcc-success/30 bg-mcc-success/5 rounded-lg p-3 mb-4">'
        f'<div class="text-xs text-mcc-success font-medium">Merged #{remove_id} ({escape(removed_name)}) into #{keep_id} ({escape(keep.name)})</div>'
        f'<div class="text-[10px] text-mcc-muted mt-0.5">Missing fields were copied over. Removed contact\'s stage and notes preserved.</div>'
        f'</div>'
    )


# --- Onboarding Journey ---
@router.get("/onboarding")
def onboarding_journey(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("onboarding.html", {
            "request": request, "project": None, "current_page": "onboarding",
            "today": date.today(),
        })

    pid = project.id

    milestones = db.query(OnboardingMilestone).filter_by(
        project_id=pid
    ).order_by(OnboardingMilestone.display_order).all()

    # Get all progress records
    progress = db.query(OnboardingProgress).filter_by(project_id=pid).all()

    # Get unique subscribers
    subscribers = set(p.subscriber_hash for p in progress)
    total_subscribers = len(subscribers) if subscribers else 0

    # Build funnel: for each milestone, % of subscribers who completed it
    funnel = []
    for ms in milestones:
        ms_progress = [p for p in progress if p.milestone_id == ms.id]
        completed_count = sum(1 for p in ms_progress if p.completed)
        total_tracked = len(set(p.subscriber_hash for p in ms_progress))

        pct = round((completed_count / total_subscribers * 100), 1) if total_subscribers > 0 else 0

        # Average days to complete
        completion_times = []
        for p in ms_progress:
            if p.completed and p.completed_at and p.created_at:
                delta = (p.completed_at - p.created_at).total_seconds() / 86400
                completion_times.append(delta)
        avg_days = round(sum(completion_times) / len(completion_times), 1) if completion_times else None

        funnel.append({
            "milestone": ms,
            "completed": completed_count,
            "tracked": total_tracked,
            "pct": pct,
            "avg_days": avg_days,
            "target_days": ms.target_days_from_start,
        })

    return templates.TemplateResponse("onboarding.html", {
        "request": request,
        "project": project,
        "milestones": milestones,
        "funnel": funnel,
        "total_subscribers": total_subscribers,
        "current_page": "onboarding",
        "today": date.today(),
    })
