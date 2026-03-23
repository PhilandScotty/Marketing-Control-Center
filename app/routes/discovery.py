"""Discover Similar — outreach prospect discovery engine.

Analyzes existing contacts, searches YouTube API (+ web fallbacks),
scores results, and inserts new prospects into the Identified column.
"""

import logging
import re
from collections import Counter
from datetime import datetime, date
from typing import Optional

import httpx
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.config import YOUTUBE_API_KEY, HUNTER_API_KEY
from app.database import get_db
from app.models import (
    Project, OutreachContact, DismissedProspect,
    ContactType, ContactStatus,
)

logger = logging.getLogger("mcc.discovery")

router = APIRouter(prefix="/pipelines")


# ── Analysis Engine ──────────────────────────────────────────────

POKER_QUERIES = [
    "poker strategy", "poker coaching", "poker study",
    "live poker", "poker tips", "poker training",
    "poker mental game", "poker session review",
    "poker vlog", "poker hand analysis", "GTO poker",
    "poker bankroll",
]


def _analyze_existing_contacts(db: Session, project_id: int) -> dict:
    """Build a prospect profile from existing contacts."""
    contacts = db.query(OutreachContact).filter(
        OutreachContact.project_id == project_id,
        OutreachContact.is_discovered == False,
    ).all()

    if not contacts:
        return {
            "keywords": POKER_QUERIES,
            "min_subs": 1000, "max_subs": 500000,
            "platforms": Counter({"YouTube": 1}),
            "types": Counter({"influencer": 1}),
            "names": set(),
            "youtube_channels": set(),
        }

    # Extract keywords from notes/descriptions
    all_text = " ".join(c.notes or "" for c in contacts).lower()
    keyword_counts = Counter()
    for q in POKER_QUERIES:
        if q.lower() in all_text:
            keyword_counts[q] += 1

    # Always include base queries
    keywords = POKER_QUERIES[:]

    # Subscriber ranges
    sizes = [c.audience_size for c in contacts if c.audience_size]
    if sizes:
        min_subs = max(1000, min(sizes) // 2)
        max_subs = min(500000, max(sizes) * 2)
    else:
        min_subs, max_subs = 1000, 500000

    # Platform distribution
    platforms = Counter(c.platform for c in contacts)

    # Type distribution
    types = Counter(c.contact_type.value for c in contacts)

    # Existing names and YT channel IDs for dedup
    names = {c.name.lower().strip() for c in contacts}
    yt_channels = set()
    for c in contacts:
        if c.youtube_channel:
            yt_channels.add(c.youtube_channel.lower().strip())

    return {
        "keywords": keywords,
        "min_subs": min_subs,
        "max_subs": max_subs,
        "platforms": platforms,
        "types": types,
        "names": names,
        "youtube_channels": yt_channels,
    }


def _get_dismissed_set(db: Session, project_id: int) -> set:
    """Get set of dismissed prospect identifiers."""
    dismissed = db.query(DismissedProspect).filter_by(project_id=project_id).all()
    result = set()
    for d in dismissed:
        result.add(d.name.lower().strip())
        if d.youtube_channel_id:
            result.add(d.youtube_channel_id.lower())
        if d.external_id:
            result.add(d.external_id.lower())
    return result


def _classify_type(description: str) -> ContactType:
    """Auto-classify based on description keywords."""
    desc = description.lower()
    coach_words = ["coach", "training", "teach", "lesson", "course",
                   "instructor", "education", "learn", "academy", "school"]
    entertainment_words = ["vlog", "entertainment", "fun", "lifestyle",
                           "travel", "adventure", "challenge"]

    coach_score = sum(1 for w in coach_words if w in desc)
    entertainment_score = sum(1 for w in entertainment_words if w in desc)

    if coach_score > entertainment_score:
        return ContactType.coach
    if entertainment_score > coach_score:
        return ContactType.ambassador_prospect
    return ContactType.influencer


def _alignment_score(channel: dict, profile: dict) -> int:
    """Score 0-100 how well a prospect matches the existing contact profile."""
    score = 50  # base

    subs = channel.get("subscriber_count", 0)
    if profile["min_subs"] <= subs <= profile["max_subs"]:
        score += 20
    elif subs > profile["max_subs"]:
        score += 5  # still relevant, just bigger
    else:
        score -= 10

    desc = (channel.get("description", "") + " " + channel.get("title", "")).lower()
    keyword_hits = sum(1 for q in profile["keywords"] if q.lower() in desc)
    score += min(keyword_hits * 5, 25)

    # Bonus for 10K-200K sweet spot
    if 10000 <= subs <= 200000:
        score += 5

    return max(0, min(100, score))


# ── YouTube Discovery ────────────────────────────────────────────

def _search_youtube(profile: dict, dismissed: set, max_results_per_query: int = 10) -> list:
    """Search YouTube Data API for channels matching the prospect profile."""
    if not YOUTUBE_API_KEY:
        logger.warning("YOUTUBE_API_KEY not configured, skipping YouTube discovery")
        return []

    discovered = []
    seen_ids = set()

    with httpx.Client(timeout=10.0) as client:
        for query in profile["keywords"][:8]:  # limit queries to conserve quota
            try:
                resp = client.get(
                    "https://www.googleapis.com/youtube/v3/search",
                    params={
                        "part": "snippet",
                        "type": "channel",
                        "q": query,
                        "maxResults": max_results_per_query,
                        "key": YOUTUBE_API_KEY,
                    },
                )
                resp.raise_for_status()
                items = resp.json().get("items", [])

                # Collect channel IDs for batch detail lookup
                channel_ids = []
                for item in items:
                    ch_id = item["snippet"]["channelId"]
                    if ch_id in seen_ids:
                        continue
                    if ch_id.lower() in dismissed:
                        continue
                    seen_ids.add(ch_id)
                    channel_ids.append(ch_id)

                if not channel_ids:
                    continue

                # Batch fetch channel details
                detail_resp = client.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    params={
                        "part": "snippet,statistics",
                        "id": ",".join(channel_ids[:50]),
                        "key": YOUTUBE_API_KEY,
                    },
                )
                detail_resp.raise_for_status()
                detail_items = detail_resp.json().get("items", [])

                for ch in detail_items:
                    ch_id = ch["id"]
                    snippet = ch.get("snippet", {})
                    stats = ch.get("statistics", {})

                    title = snippet.get("title", "")
                    description = snippet.get("description", "")
                    custom_url = snippet.get("customUrl", "")

                    try:
                        sub_count = int(stats.get("subscriberCount", 0))
                    except (ValueError, TypeError):
                        sub_count = 0

                    # Filter: 1K-500K subscribers
                    if sub_count < 1000 or sub_count > 500000:
                        continue

                    # Skip if name matches existing contact
                    if title.lower().strip() in profile["names"]:
                        continue
                    if title.lower().strip() in dismissed:
                        continue

                    # Skip if YT channel matches existing
                    if custom_url and custom_url.lower() in profile["youtube_channels"]:
                        continue
                    if ch_id.lower() in profile.get("youtube_channels", set()):
                        continue

                    contact_type = _classify_type(description)
                    score = _alignment_score(
                        {"subscriber_count": sub_count, "description": description, "title": title},
                        profile,
                    )

                    discovered.append({
                        "name": title,
                        "platform": "YouTube",
                        "audience_size": sub_count,
                        "contact_type": contact_type,
                        "youtube_channel_id": ch_id,
                        "youtube_handle": custom_url or "",
                        "description": description[:500] if description else "",
                        "website_url": f"https://youtube.com/{custom_url}" if custom_url else "",
                        "alignment_score": score,
                        "source": "youtube_api",
                    })

            except httpx.TimeoutException:
                logger.warning(f"YouTube search timeout for query: {query}")
            except Exception as e:
                logger.warning(f"YouTube search error for '{query}': {e}")

    # Sort by alignment score descending, deduplicate
    discovered.sort(key=lambda x: x["alignment_score"], reverse=True)
    return discovered


# ── "Find Email" via Hunter.io ────────────────────────────────────

def _find_email_hunter(domain: str) -> dict:
    """Search Hunter.io for emails on a domain."""
    if not HUNTER_API_KEY:
        return {"error": "HUNTER_API_KEY not configured"}

    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(
                "https://api.hunter.io/v2/domain-search",
                params={
                    "domain": domain,
                    "api_key": HUNTER_API_KEY,
                    "limit": 5,
                },
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            emails = data.get("emails", [])
            if emails:
                return {
                    "emails": [
                        {"email": e["value"], "type": e.get("type", ""), "confidence": e.get("confidence", 0)}
                        for e in emails[:5]
                    ]
                }
            return {"emails": [], "message": "No emails found"}
    except Exception as e:
        return {"error": str(e)}


# ── Main Discovery Run ───────────────────────────────────────────

def _run_discovery(db: Session, project_id: int) -> dict:
    """Run the full discovery engine. Returns summary stats."""
    profile = _analyze_existing_contacts(db, project_id)
    dismissed = _get_dismissed_set(db, project_id)

    # Also exclude existing contacts by name
    existing = db.query(OutreachContact).filter_by(project_id=project_id).all()
    existing_names = {c.name.lower().strip() for c in existing}
    existing_yt = set()
    for c in existing:
        if c.youtube_channel:
            existing_yt.add(c.youtube_channel.lower().strip())

    # Merge into dismissed set for dedup
    all_excluded = dismissed | existing_names | existing_yt | profile.get("youtube_channels", set())

    # YouTube Discovery
    yt_results = _search_youtube(profile, all_excluded)

    # Filter out any remaining duplicates against DB
    new_prospects = []
    for r in yt_results:
        name_lower = r["name"].lower().strip()
        yt_id = r.get("youtube_channel_id", "").lower()

        if name_lower in existing_names or name_lower in dismissed:
            continue
        if yt_id and yt_id in all_excluded:
            continue

        # Check DB directly for any close match
        db_match = db.query(OutreachContact).filter(
            OutreachContact.project_id == project_id,
            OutreachContact.name.ilike(f"%{r['name'][:30]}%"),
        ).first()
        if db_match:
            continue

        new_prospects.append(r)
        existing_names.add(name_lower)

    # Insert into database
    added = 0
    for p in new_prospects[:25]:  # cap at 25 per run
        contact = OutreachContact(
            project_id=project_id,
            name=p["name"],
            platform=p["platform"],
            audience_size=p["audience_size"],
            contact_type=p["contact_type"],
            status=ContactStatus.identified,
            notes=f"[Discovered] {p['description']}" if p.get("description") else "",
            website_url=p.get("website_url") or None,
            youtube_channel=p.get("youtube_handle") or p.get("youtube_channel_id") or None,
            is_discovered=True,
            discovered_at=datetime.utcnow(),
            discovery_source=p.get("source", "youtube_api"),
        )
        db.add(contact)
        added += 1

    db.commit()

    skipped_sources = []
    if not HUNTER_API_KEY:
        skipped_sources.append("Hunter.io (no API key)")
    skipped_sources.append("Twitter/X (no API key)")

    return {
        "youtube_found": len(yt_results),
        "added": added,
        "total_searched": len(profile["keywords"][:8]),
        "skipped_sources": skipped_sources,
    }


# ── Routes ────────────────────────────────────────────────────────

@router.post("/outreach/discover")
def discover_similar(db: Session = Depends(get_db)):
    """Run discovery engine and return results summary."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("No project", status_code=400)

    result = _run_discovery(db, project.id)

    skipped_html = ""
    if result["skipped_sources"]:
        items = "".join(f"<li>{s}</li>" for s in result["skipped_sources"])
        skipped_html = f'<div class="text-[9px] text-mcc-muted mt-2">Skipped: <ul class="list-disc pl-4">{items}</ul></div>'

    return HTMLResponse(f'''
        <div class="text-center py-4">
            <div class="text-mcc-success text-sm font-medium mb-1">
                Discovery Complete
            </div>
            <div class="text-xs text-mcc-muted mb-2">
                Found {result["youtube_found"]} YouTube prospects, added {result["added"]} new
            </div>
            <div class="text-[10px] text-mcc-muted">
                Searched {result["total_searched"]} keyword queries
            </div>
            {skipped_html}
            <button onclick="closeDiscoverModal(); location.reload();"
                class="mt-3 bg-mcc-accent text-white text-xs px-4 py-2 rounded hover:bg-mcc-accent/80 transition-colors">
                View Results
            </button>
        </div>
    ''')


@router.post("/outreach/dismiss/{contact_id}")
def dismiss_prospect(contact_id: int, db: Session = Depends(get_db)):
    """Dismiss an auto-discovered prospect — move to declined and prevent re-surfacing."""
    contact = db.get(OutreachContact, contact_id)
    if not contact:
        return HTMLResponse("Not found", status_code=404)

    # Record in dismissed_prospects for future dedup
    dismissed = DismissedProspect(
        project_id=contact.project_id,
        name=contact.name,
        platform=contact.platform,
        youtube_channel_id=contact.youtube_channel or None,
        external_id=None,
        reason="Auto-discovered -- dismissed",
    )
    db.add(dismissed)

    # Move contact to declined
    contact.status = ContactStatus.declined
    contact.notes = (contact.notes or "") + "\n[Dismissed from auto-discovery]"
    db.commit()

    return HTMLResponse('<span class="text-[10px] text-mcc-muted">Dismissed</span>')


@router.post("/outreach/accept/{contact_id}")
def accept_prospect(contact_id: int, db: Session = Depends(get_db)):
    """Accept a discovered prospect — remove discovered badge and trigger enrichment."""
    contact = db.get(OutreachContact, contact_id)
    if not contact:
        return HTMLResponse("Not found", status_code=404)

    contact.is_discovered = False

    # Trigger YouTube enrichment if applicable
    if contact.platform == "YouTube":
        from app.routes.pipelines import _enrich_youtube, _apply_enrichment
        enrichment = _enrich_youtube(contact.youtube_channel, contact.name)
        _apply_enrichment(contact, enrichment)

    db.commit()
    db.refresh(contact)

    # Return updated card
    from app.routes.pipelines import _contact_card_html
    return HTMLResponse(_contact_card_html(contact, date.today()))


@router.post("/outreach/find-email/{contact_id}")
def find_email(contact_id: int, db: Session = Depends(get_db)):
    """Try to find email for a contact via Hunter.io or fallback."""
    contact = db.get(OutreachContact, contact_id)
    if not contact:
        return HTMLResponse("Not found", status_code=404)

    # Try Hunter.io if we have a website
    if contact.website_url and HUNTER_API_KEY:
        # Extract domain from URL
        url = contact.website_url
        domain_match = re.match(r'https?://(?:www\.)?([^/]+)', url)
        if domain_match:
            domain = domain_match.group(1)
            # Skip youtube.com domains
            if "youtube.com" not in domain:
                result = _find_email_hunter(domain)
                if result.get("emails"):
                    best = result["emails"][0]
                    contact.contact_email = best["email"]
                    db.commit()
                    return HTMLResponse(f'''
                        <div class="text-xs text-mcc-success">
                            Found: {best["email"]}
                            <span class="text-[9px] text-mcc-muted">({best["confidence"]}% confidence)</span>
                        </div>
                    ''')

    # Fallback: Google search link
    search_name = contact.name.replace(" ", "+")
    google_url = f"https://www.google.com/search?q={search_name}+poker+email+contact"

    no_hunter = "" if HUNTER_API_KEY else '<div class="text-[9px] text-mcc-muted mt-1">HUNTER_API_KEY not configured</div>'

    return HTMLResponse(f'''
        <div class="text-xs">
            <div class="text-mcc-warning mb-1">No email found automatically</div>
            {no_hunter}
            <a href="{google_url}" target="_blank" rel="noopener"
               class="text-mcc-accent hover:underline text-[10px]">
                Search Google for contact info &rarr;
            </a>
        </div>
    ''')


def get_discovered_count(db: Session, project_id: int) -> int:
    """Get count of discovered prospects added this week."""
    from datetime import timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    return db.query(OutreachContact).filter(
        OutreachContact.project_id == project_id,
        OutreachContact.is_discovered == True,
        OutreachContact.discovered_at >= week_ago,
        OutreachContact.status == ContactStatus.identified,
    ).count()
