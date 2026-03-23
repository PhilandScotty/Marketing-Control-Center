"""Auto-populate metrics — pulls data from configured APIs and fills channel metrics + budget actuals.

Hooks into existing integration refresh cycles via post_integration_sync().
Also provides a standalone weekly job for Reddit scraping.
"""
import logging
from datetime import date, datetime
from decimal import Decimal

import httpx
from sqlalchemy.orm import Session

from app.config import (
    YOUTUBE_API_KEY, YOUTUBE_CHANNEL_ID,
    BUFFER_ACCESS_TOKEN,
    REDDIT_USERNAME,
)
from app.database import SessionLocal
from app.models import (
    Project, Channel, Metric, MetricSource,
    BudgetLineItem, BudgetMonthEntry,
)

logger = logging.getLogger("mcc.auto_metrics")

# Fixed monthly costs for auto-fill (line item name -> actual amount)
FIXED_SUBSCRIPTIONS = {
    "ConvertKit": Decimal("79"),
    "Buffer": Decimal("30"),
    "Instantly": Decimal("97"),
    "Railway": Decimal("5"),
    "X Premium": Decimal("4"),
}


# ---------------------------------------------------------------------------
# Metric recording helper
# ---------------------------------------------------------------------------

def _record_metric(db: Session, channel_id: int, metric_name: str, value: float, unit: str = "count"):
    """Record a metric for a channel, setting previous_value from the last reading."""
    prev = db.query(Metric).filter_by(
        channel_id=channel_id, metric_name=metric_name,
    ).order_by(Metric.recorded_at.desc()).first()

    metric = Metric(
        channel_id=channel_id,
        metric_name=metric_name,
        metric_value=value,
        previous_value=prev.metric_value if prev else None,
        unit=unit,
        source=MetricSource.api,
    )
    db.add(metric)
    logger.info(f"Auto-metric: {metric_name}={value} for channel_id={channel_id}")


# ---------------------------------------------------------------------------
# YouTube subscriber count via Data API v3
# ---------------------------------------------------------------------------

async def fetch_youtube_subscribers() -> int | None:
    """Fetch subscriber count from YouTube Data API."""
    if not YOUTUBE_API_KEY or not YOUTUBE_CHANNEL_ID:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={
                    "part": "statistics",
                    "id": YOUTUBE_CHANNEL_ID,
                    "key": YOUTUBE_API_KEY,
                },
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            if items:
                stats = items[0].get("statistics", {})
                return int(stats.get("subscriberCount", 0))
    except Exception as e:
        logger.error(f"YouTube API error: {e}")
    return None


# ---------------------------------------------------------------------------
# Buffer social metrics (followers, post count per service)
# ---------------------------------------------------------------------------

async def fetch_buffer_social_metrics() -> list[dict]:
    """Fetch follower counts and post counts from Buffer GraphQL API."""
    if not BUFFER_ACCESS_TOKEN:
        return []

    headers = {
        "Authorization": f"Bearer {BUFFER_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    results = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Get org ID
            resp = await client.post(
                "https://api.buffer.com",
                headers=headers,
                json={"query": "{ account { organizations { id } } }"},
            )
            data = resp.json().get("data", {})
            orgs = data.get("account", {}).get("organizations", [])
            if not orgs:
                return []
            org_id = orgs[0]["id"]

            # Get channels with follower counts
            resp = await client.post(
                "https://api.buffer.com",
                headers=headers,
                json={"query": '{ channels(input: { organizationId: "%s" }) { id name service serverUrl } }' % org_id},
            )
            channels = resp.json().get("data", {}).get("channels", [])
            if not isinstance(channels, list):
                return []

            # Get sent post counts per channel
            resp = await client.post(
                "https://api.buffer.com",
                headers=headers,
                json={"query": '''
                    { posts(input: { organizationId: "%s", filter: { status: [sent] } }) {
                        edges { node { channelId } }
                    } }
                ''' % org_id},
            )
            sent_edges = resp.json().get("data", {}).get("posts", {}).get("edges", [])
            from collections import Counter
            sent_by_ch = Counter(e["node"]["channelId"] for e in sent_edges)

            for ch in channels:
                service = ch.get("service", "").lower()
                ch_id = ch["id"]
                results.append({
                    "service": service,
                    "name": ch.get("name", service),
                    "channel_id": ch_id,
                    "sent_posts": sent_by_ch.get(ch_id, 0),
                })

    except Exception as e:
        logger.error(f"Buffer social metrics error: {e}")

    return results


# ---------------------------------------------------------------------------
# Reddit karma scrape (public JSON, no auth needed)
# ---------------------------------------------------------------------------

async def fetch_reddit_karma() -> dict | None:
    """Fetch karma from Reddit public profile JSON."""
    if not REDDIT_USERNAME:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://www.reddit.com/user/{REDDIT_USERNAME}/about.json",
                headers={"User-Agent": "MCC/1.0 (Marketing Command Center)"},
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return {
                "link_karma": data.get("link_karma", 0),
                "comment_karma": data.get("comment_karma", 0),
                "total_karma": data.get("total_karma", 0),
            }
    except Exception as e:
        logger.error(f"Reddit karma fetch error: {e}")
    return None


# ---------------------------------------------------------------------------
# Budget auto-fill for fixed subscriptions
# ---------------------------------------------------------------------------

def auto_fill_budget_actuals(db: Session, project_id: int):
    """Auto-fill monthly actuals for fixed subscription costs."""
    today = date.today()
    month = today.replace(day=1)

    items = db.query(BudgetLineItem).filter_by(
        project_id=project_id, is_recurring=True,
    ).all()

    for item in items:
        fixed_amount = FIXED_SUBSCRIPTIONS.get(item.name)
        if fixed_amount is None:
            continue

        entry = db.query(BudgetMonthEntry).filter_by(
            line_item_id=item.id, month=month,
        ).first()

        if not entry:
            continue

        # Only auto-fill if actual is still 0 or was previously auto-filled
        if float(entry.actual) == 0 or entry.auto_filled:
            entry.actual = fixed_amount
            entry.auto_filled = True
            entry.auto_filled_at = datetime.utcnow()
            logger.info(f"Budget auto-fill: {item.name} = ${float(fixed_amount):.0f} for {month}")

    db.commit()


# ---------------------------------------------------------------------------
# Post-integration sync hook
# ---------------------------------------------------------------------------

async def post_integration_sync(integration_name: str, db: Session, project_id: int):
    """Called after each integration refresh to auto-populate related channel metrics.

    This hooks into existing scheduler cycles — no new timers.
    """
    channels = {c.name: c for c in db.query(Channel).filter_by(project_id=project_id).all()}

    if integration_name == "convertkit":
        # Kit subscriber count is already recorded by the ConvertKit integration
        # as "email_subscribers" on "Email Nurture (Kit)" channel.
        # Auto-fill budget actuals for fixed subscriptions on each convertkit cycle.
        auto_fill_budget_actuals(db, project_id)

    elif integration_name == "buffer":
        # Pull social metrics from Buffer for X/Twitter, Instagram, TikTok
        buffer_metrics = await fetch_buffer_social_metrics()
        service_to_channel = {
            "twitter": channels.get("X/Twitter"),
            "instagram": channels.get("Instagram"),
            "tiktok": channels.get("TikTok"),
            "linkedin": channels.get("LinkedIn"),
        }
        for bm in buffer_metrics:
            channel = service_to_channel.get(bm["service"])
            if channel:
                if bm["sent_posts"] > 0:
                    _record_metric(db, channel.id, "posts_published", float(bm["sent_posts"]), "posts")
        db.commit()

    elif integration_name == "youtube":
        # YouTube subscribers
        yt_channel = channels.get("YouTube")
        if yt_channel:
            subs = await fetch_youtube_subscribers()
            if subs is not None:
                _record_metric(db, yt_channel.id, "youtube_subscribers", float(subs), "subscribers")
                db.commit()


# ---------------------------------------------------------------------------
# Standalone weekly job for Reddit + YouTube (runs on existing scheduler)
# ---------------------------------------------------------------------------

async def run_social_metrics_refresh():
    """Refresh metrics that don't have dedicated integrations: YouTube subs, Reddit karma."""
    db = SessionLocal()
    try:
        project = db.query(Project).filter_by(slug="grindlab").first()
        if not project:
            return
        pid = project.id
        channels = {c.name: c for c in db.query(Channel).filter_by(project_id=pid).all()}

        # YouTube subscribers
        yt_channel = channels.get("YouTube")
        if yt_channel:
            subs = await fetch_youtube_subscribers()
            if subs is not None:
                _record_metric(db, yt_channel.id, "youtube_subscribers", float(subs), "subscribers")

        # Reddit karma
        reddit_channel = channels.get("Reddit Engagement")
        if reddit_channel:
            karma = await fetch_reddit_karma()
            if karma:
                _record_metric(db, reddit_channel.id, "total_karma", float(karma["total_karma"]), "karma")
                _record_metric(db, reddit_channel.id, "comment_karma", float(karma["comment_karma"]), "karma")

        # Auto-fill budget actuals
        auto_fill_budget_actuals(db, pid)

        db.commit()
        logger.info("Social metrics refresh completed")
    except Exception as e:
        logger.error(f"Social metrics refresh failed: {e}")
    finally:
        db.close()


def social_metrics_job():
    """Sync wrapper for APScheduler."""
    import asyncio
    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(asyncio.run, run_social_metrics_refresh()).result()
            else:
                loop.run_until_complete(run_social_metrics_refresh())
        except RuntimeError:
            asyncio.run(run_social_metrics_refresh())
    except Exception as e:
        logger.error(f"Social metrics job failed: {e}")
