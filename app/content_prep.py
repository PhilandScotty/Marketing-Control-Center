"""Content Preparation — analyzes pillars and generates draft social posts for Approval Queue.

Runs weekly (Saturday) or on-demand via "Prepare Next Week" button.
All drafts require Phil's approval before anything posts.
"""
import json
import logging
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import (
    Project, ProjectStrategy, ContentPiece, ApprovalQueueItem, Metric,
    StrategySection, ContentStatus, QueueItemType, QueueItemStatus,
)
from app.ai.engine import simple_completion, is_configured as ai_configured

logger = logging.getLogger("mcc.content_prep")

# Default content pillars if strategy section is empty
DEFAULT_PILLARS = [
    {"name": "Study Science", "ratio": 25, "series": "Study Science Drop"},
    {"name": "Hand Analysis", "ratio": 20, "series": "Hand of the Week"},
    {"name": "Tool Walkthrough", "ratio": 15, "series": "Grindlab Feature Spotlight"},
    {"name": "Body at the Table", "ratio": 10, "series": "Table Observation"},
    {"name": "Poker Culture", "ratio": 20, "series": "The Grind"},
    {"name": "Product / CTA", "ratio": 10, "series": "Grindlab Updates"},
]


def _parse_pillars(strategy_content: str) -> list[dict]:
    """Try to extract pillar names/ratios from strategy text. Falls back to defaults."""
    if not strategy_content or len(strategy_content.strip()) < 20:
        return DEFAULT_PILLARS

    pillars = []
    for line in strategy_content.split("\n"):
        line = line.strip().strip("-*•")
        if not line:
            continue
        # Look for patterns like "Study Science (25%)" or "Study Science - 25%"
        for sep in ["(", "-", ":"]:
            if sep in line:
                parts = line.split(sep, 1)
                name = parts[0].strip()
                rest = parts[1].strip().rstrip("%)").strip()
                try:
                    ratio = int("".join(c for c in rest if c.isdigit())[:3])
                    pillars.append({"name": name, "ratio": ratio, "series": name})
                    break
                except (ValueError, IndexError):
                    pass

    return pillars if len(pillars) >= 3 else DEFAULT_PILLARS


def _get_recent_content_distribution(db, project_id: int, days: int = 14) -> dict:
    """Count content pieces by series/pillar published in last N days."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    pieces = db.query(ContentPiece).filter(
        ContentPiece.project_id == project_id,
        ContentPiece.status == ContentStatus.published,
        ContentPiece.published_at >= cutoff,
    ).all()

    dist = {}
    for p in pieces:
        key = p.series or "Uncategorized"
        dist[key] = dist.get(key, 0) + 1
    return dist


def _get_brand_voice(db, project_id: int) -> str:
    """Pull brand voice from strategy."""
    strat = db.query(ProjectStrategy).filter_by(
        project_id=project_id, section=StrategySection.voice,
    ).first()
    if strat and strat.content:
        return strat.content
    return (
        "Confident but not arrogant. Technical but accessible. "
        "Like a sharp friend at the poker table who knows their stuff. "
        "Tool language, not coach language. Direct and data-driven."
    )


async def generate_content_drafts(db=None, project_id: int = None):
    """Generate 5-7 draft social posts and place them in the Approval Queue.

    Returns the number of drafts created.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        if project_id is None:
            project = db.query(Project).filter_by(slug="grindlab").first()
            if not project:
                return 0
            project_id = project.id

        if not ai_configured():
            logger.info("Content prep: AI not configured, skipping")
            return 0

        # Check if there are already pending content drafts
        existing = db.query(ApprovalQueueItem).filter_by(
            project_id=project_id,
            item_type=QueueItemType.content_draft,
            status=QueueItemStatus.pending,
        ).count()
        if existing >= 5:
            logger.info(f"Content prep: {existing} drafts already pending, skipping")
            return 0

        # Get strategy data
        pillar_strat = db.query(ProjectStrategy).filter_by(
            project_id=project_id, section=StrategySection.pillars,
        ).first()
        pillars = _parse_pillars(pillar_strat.content if pillar_strat else "")

        brand_voice = _get_brand_voice(db, project_id)
        recent_dist = _get_recent_content_distribution(db, project_id)

        # Find underrepresented pillars
        total_recent = sum(recent_dist.values()) or 1
        gaps = []
        for p in pillars:
            actual_pct = (recent_dist.get(p["series"], 0) / total_recent) * 100 if total_recent > 1 else 0
            target_pct = p["ratio"]
            if actual_pct < target_pct * 0.5:  # below 50% of target ratio
                gaps.append(p["name"])

        # Build AI prompt
        pillar_summary = "\n".join(
            f"- {p['name']} ({p['ratio']}% target) — series: {p['series']} — "
            f"recent: {recent_dist.get(p['series'], 0)} posts"
            for p in pillars
        )

        prompt = f"""Generate exactly 6 draft social posts for Grindlab's X/Twitter account for next week.

CONTENT PILLARS (with target ratios):
{pillar_summary}

UNDERREPRESENTED PILLARS (prioritize these): {', '.join(gaps) if gaps else 'All balanced'}

BRAND VOICE:
{brand_voice}

CONTENT MIX:
- 60% Education (study tips, hand analysis, strategy concepts)
- 30% Entertainment (poker culture, relatable moments)
- 10% Promotion (product features, CTAs)

RULES:
- Each post must be under 280 characters
- Use the brand voice — direct, data-driven, slightly irreverent
- No banned words: guru, masterclass, crush, easy money, hack, revolutionary
- Tag each post with its content pillar and series name
- Include 1-2 relevant hashtags per post
- Vary post types: questions, stats, tips, observations, hot takes

Return as a JSON array with objects having these fields:
- "text": the post text (under 280 chars)
- "pillar": which content pillar it belongs to
- "series": which series (Study Science Drop, Table Observation, Hand of the Week, etc.)
- "platform": "x_twitter"
- "content_mix": "education", "entertainment", or "promotion"

Return ONLY the JSON array, no other text."""

        system = (
            "You are a social media content strategist for Grindlab, a poker study SaaS. "
            "You write posts that are sharp, data-driven, and resonate with serious recreational poker players. "
            "Always return valid JSON."
        )

        response = await simple_completion(prompt, system_override=system)

        # Parse JSON response
        try:
            # Strip markdown code blocks if present
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                text = text.rsplit("```", 1)[0]
            drafts = json.loads(text)
        except (json.JSONDecodeError, IndexError):
            logger.error(f"Content prep: Failed to parse AI response as JSON")
            return 0

        if not isinstance(drafts, list):
            return 0

        created = 0
        for draft in drafts[:7]:  # Cap at 7
            if not isinstance(draft, dict) or "text" not in draft:
                continue

            item = ApprovalQueueItem(
                project_id=project_id,
                item_type=QueueItemType.content_draft,
                source_label="Content Prep",
                title=f"Draft: {draft.get('series', 'Post')}",
                preview=draft["text"],
                draft_message=draft["text"],
                content_pillar=draft.get("pillar", ""),
                content_platform=draft.get("platform", "x_twitter"),
                content_series=draft.get("series", ""),
                action_url="/pipelines/content",
            )
            db.add(item)
            created += 1

        if created:
            db.commit()
            logger.info(f"Content prep: created {created} draft posts")

        return created

    except Exception as e:
        logger.error(f"Content prep failed: {e}")
        return 0
    finally:
        if close_db:
            db.close()


def content_prep_job():
    """Sync wrapper for APScheduler."""
    import asyncio
    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(asyncio.run, generate_content_drafts()).result()
            else:
                loop.run_until_complete(generate_content_drafts())
        except RuntimeError:
            asyncio.run(generate_content_drafts())
    except Exception as e:
        logger.error(f"Content prep job failed: {e}")
