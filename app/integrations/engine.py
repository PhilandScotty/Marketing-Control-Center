"""Integration engine — runs integrations and saves metrics to DB."""
import asyncio
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    Project, Channel, Metric, MetricSource, Automation, AutomationHealth,
    AIInsight, InsightType, InsightSourceType, InsightSeverity, HealthStatus,
)
from app.integrations.base import IntegrationBase, MetricReading
from app.integrations.auto_metrics import post_integration_sync

logger = logging.getLogger("mcc.integrations.engine")


def _save_metrics(db: Session, project_id: int, readings: list[MetricReading]):
    """Save metric readings to the database."""
    channels = db.query(Channel).filter_by(project_id=project_id).all()
    channel_map = {c.name: c for c in channels}
    # Also allow lookup by integration_key for resilience
    for c in channels:
        if c.integration_key and c.integration_key not in channel_map:
            channel_map[c.integration_key] = c

    for reading in readings:
        channel = channel_map.get(reading.channel_name)
        if not channel:
            logger.warning(f"Channel not found for metric: {reading.channel_name}")
            continue

        # Get previous value
        prev = db.query(Metric).filter_by(
            channel_id=channel.id,
            metric_name=reading.metric_name,
        ).order_by(Metric.recorded_at.desc()).first()

        metric = Metric(
            channel_id=channel.id,
            metric_name=reading.metric_name,
            metric_value=reading.value,
            previous_value=prev.metric_value if prev else None,
            unit=reading.unit,
            source=MetricSource.api,
        )
        db.add(metric)

    db.commit()


def _check_health_degradation(db: Session, project_id: int, integration: IntegrationBase):
    """If 3+ consecutive failures, set channel health to warning and create/update insight."""
    if integration._consecutive_failures < 3:
        return

    fix_urls = {
        "buffer": "https://login.buffer.com/signin",
        "convertkit": "https://app.convertkit.com/account/edit",
        "instantly": "https://app.instantly.ai/app/settings",
        "stripe": "https://dashboard.stripe.com/apikeys",
    }

    # Find channels that match this integration
    channels = db.query(Channel).filter_by(project_id=project_id).all()
    for ch in channels:
        if ch.integration_key == integration.name:
            ch.health = HealthStatus.warning
            ch.health_reason = f"{integration.name} disconnected — {integration._consecutive_failures} consecutive failures"

            # Deduplicate: find existing unresolved insight for this integration
            existing = db.query(AIInsight).filter(
                AIInsight.project_id == project_id,
                AIInsight.source_type == InsightSourceType.channel,
                AIInsight.source_id == ch.id,
                AIInsight.insight_type == InsightType.stale_automation,
                AIInsight.resolved_at.is_(None),
                AIInsight.dismissed_at.is_(None),
            ).first()

            if existing:
                # Update existing instead of creating duplicate
                existing.title = f"{integration.name} disconnected — {integration._consecutive_failures} consecutive failures"
                existing.body = (f"The {integration.name} API has failed {integration._consecutive_failures} times in a row. "
                                 f"Metrics for {ch.name} are not updating.")
                existing.acknowledged = False  # Re-surface it
            else:
                insight = AIInsight(
                    project_id=project_id,
                    insight_type=InsightType.stale_automation,
                    source_type=InsightSourceType.channel,
                    source_id=ch.id,
                    title=f"{integration.name} disconnected — {integration._consecutive_failures} consecutive failures",
                    body=f"The {integration.name} API has failed {integration._consecutive_failures} times in a row. "
                         f"Metrics for {ch.name} are not updating.",
                    why_it_matters=f"Channel metrics for {ch.name} are stale. Dashboard data and alerts may be inaccurate.",
                    suggested_action=f"Reconnect in {integration.name} settings — check API key is valid and service is up (~2 min).",
                    fix_url=fix_urls.get(integration.name, "/channels"),
                    severity=InsightSeverity.attention,
                )
                db.add(insight)

    db.commit()


async def run_integration(integration: IntegrationBase):
    """Run a single integration and persist results."""
    logger.info(f"Running integration: {integration.name}")
    result = await integration.run()

    db = SessionLocal()
    try:
        project = db.query(Project).filter_by(slug="grindlab").first()
        if not project:
            return

        if result.success and result.metrics:
            _save_metrics(db, project.id, result.metrics)
            logger.info(f"{integration.name}: Saved {len(result.metrics)} metrics")

            # Clear warning/critical health on channels linked to this integration
            linked = db.query(Channel).filter_by(
                project_id=project.id, integration_key=integration.name,
            ).all()
            for ch in linked:
                if ch.health in (HealthStatus.warning, HealthStatus.critical):
                    ch.health = HealthStatus.healthy
                    ch.health_reason = None
                    logger.info(f"Restored {ch.name} health to healthy after successful {integration.name} sync")
            db.commit()

            # Hook: auto-populate related channel metrics and budget actuals
            try:
                await post_integration_sync(integration.name, db, project.id)
            except Exception as e:
                logger.warning(f"Post-sync hook for {integration.name} failed: {e}")
        elif not result.success:
            logger.warning(f"{integration.name}: Failed — {result.error}")
            _check_health_degradation(db, project.id, integration)
    finally:
        db.close()


def run_integration_sync(integration: IntegrationBase):
    """Synchronous wrapper for APScheduler."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context — create a task
            asyncio.ensure_future(run_integration(integration))
        else:
            loop.run_until_complete(run_integration(integration))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_integration(integration))
