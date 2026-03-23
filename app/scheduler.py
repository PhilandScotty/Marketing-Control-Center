"""APScheduler configuration — registers all integrations with refresh intervals."""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.integrations.convertkit import ConvertKitIntegration
from app.integrations.instantly import InstantlyIntegration
from app.integrations.ga4 import GA4Integration
from app.integrations.buffer import BufferIntegration
from app.integrations.stripe_integration import StripeIntegration
from app.integrations.ad_platforms import MetaAdsIntegration, RedditAdsIntegration, GoogleAdsIntegration
from app.integrations.engine import run_integration_sync
from app.ai.jobs import (
    deadline_enforcer_job, anomaly_detector_job, automation_health_job,
    ad_signal_job, gap_analyzer_job, weekly_digest_job,
    outreach_followup_job, content_pipeline_job, lead_scoring_job,
    channel_intelligence_job, channel_metric_monitor_job,
)
from app.status_export import status_export_job
from app.routes.strategy_export import strategy_export_job
from app.routes.website import website_intelligence_job
from app.routes.dashboard import morning_brief_job
from app.integrations.auto_metrics import social_metrics_job
from app.outreach_workflow import run_outreach_workflow
from app.content_prep import content_prep_job

logger = logging.getLogger("mcc.scheduler")

# All integration instances
INTEGRATIONS = [
    ConvertKitIntegration(),
    InstantlyIntegration(),
    GA4Integration(),
    BufferIntegration(),
    StripeIntegration(),
    MetaAdsIntegration(),
    RedditAdsIntegration(),
    GoogleAdsIntegration(),
]

scheduler = BackgroundScheduler()


def start_scheduler():
    """Register all configured integrations and start the scheduler."""
    registered = 0
    for integration in INTEGRATIONS:
        if integration.is_configured():
            scheduler.add_job(
                run_integration_sync,
                trigger=IntervalTrigger(hours=integration.refresh_interval_hours),
                args=[integration],
                id=f"integration_{integration.name}",
                name=f"Refresh {integration.name}",
                replace_existing=True,
                max_instances=1,
            )
            registered += 1
            logger.info(
                f"Scheduled {integration.name} every {integration.refresh_interval_hours}h"
            )
        else:
            logger.info(f"Skipping {integration.name} — not configured")

    # --- AI Scheduled Jobs ---
    ai_jobs = [
        ("ai_deadline_enforcer", deadline_enforcer_job, IntervalTrigger(hours=6)),
        ("ai_anomaly_detector", anomaly_detector_job, CronTrigger(hour=6)),
        ("ai_automation_health", automation_health_job, IntervalTrigger(hours=4)),
        ("ai_ad_signal", ad_signal_job, IntervalTrigger(hours=6)),
        ("ai_gap_analyzer", gap_analyzer_job, CronTrigger(day_of_week="sun", hour=6)),
        ("ai_weekly_digest", weekly_digest_job, CronTrigger(day_of_week="sun", hour=7)),
        ("ai_outreach_followup", outreach_followup_job, CronTrigger(hour=8)),
        ("ai_content_pipeline", content_pipeline_job, CronTrigger(hour=9)),
        ("ai_lead_scoring", lead_scoring_job, CronTrigger(day_of_week="sun", hour=5)),
        ("ai_channel_intelligence", channel_intelligence_job, CronTrigger(day_of_week="sun", hour=6, minute=30)),
        ("ai_channel_metric_monitor", channel_metric_monitor_job, IntervalTrigger(hours=6)),
        ("status_export", status_export_job, CronTrigger(hour=6, minute=0)),
        ("strategy_export", strategy_export_job, CronTrigger(day_of_week="sun", hour=6, minute=0)),
        ("website_intelligence", website_intelligence_job, CronTrigger(day_of_week="sun", hour=7, minute=30)),
        ("morning_brief", morning_brief_job, CronTrigger(hour=7, minute=0)),
        ("social_metrics", social_metrics_job, IntervalTrigger(hours=6)),
        ("outreach_workflow", run_outreach_workflow, CronTrigger(hour=8, minute=30)),
        ("content_prep", content_prep_job, CronTrigger(day_of_week="sat", hour=9)),
    ]

    for job_id, job_fn, trigger in ai_jobs:
        scheduler.add_job(
            job_fn,
            trigger=trigger,
            id=job_id,
            name=job_id.replace("_", " ").title(),
            replace_existing=True,
            max_instances=1,
        )
        registered += 1

    logger.info(f"Registered {len(ai_jobs)} AI scheduled jobs")

    if registered > 0:
        scheduler.start()
        logger.info(f"Scheduler started with {registered} job(s)")
    else:
        logger.info("No jobs configured — scheduler not started")


def stop_scheduler():
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def get_integration_status() -> list[dict]:
    """Return current status of all integrations."""
    status = []
    for integration in INTEGRATIONS:
        status.append({
            "name": integration.name,
            "configured": integration.is_configured(),
            "health": integration.get_health_status().value,
            "failures": integration._consecutive_failures,
            "interval_hours": integration.refresh_interval_hours,
        })
    return status
