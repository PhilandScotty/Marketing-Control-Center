"""Scheduled AI jobs — write AIInsight records based on data analysis."""
import asyncio
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import SessionLocal
from app.models import (
    Project, Channel, Task, Automation, ContentPiece, Metric,
    AdCampaign, OutreachContact, Tool, EmailSequence,
    BudgetAllocation, BudgetExpense, LeadScore, SubscriberEvent,
    AIInsight, InsightType, InsightSourceType, InsightSeverity,
    TaskStatus, TaskPriority, AutomationHealth, AutomationLevel, HealthStatus,
    ContentStatus, AdStatus, ChannelStatus, ToolStatus,
    LeadTier, SubscriberEventType,
)
from app.ai.engine import simple_completion, is_configured
from app.alerts import send_critical_alert, send_warning_alert, send_telegram

logger = logging.getLogger("mcc.ai.jobs")


def _get_project(db: Session):
    return db.query(Project).filter_by(slug="grindlab").first()


# --- Job 1: Deadline Enforcer (Every 6 hours) ---

def run_deadline_enforcer():
    """Check for upcoming/overdue tasks and dependency chains."""
    db = SessionLocal()
    try:
        project = _get_project(db)
        if not project:
            return
        pid = project.id
        today = date.today()

        tasks = db.query(Task).filter(
            Task.project_id == pid,
            Task.due_date.isnot(None),
            Task.status.notin_([TaskStatus.done, TaskStatus.archived, TaskStatus.recurring]),
        ).all()

        for task in tasks:
            days_until = (task.due_date - today).days

            # Skip recurring daily tasks — they belong on Daily Ops only.
            # Only surface as dashboard alert if overdue by more than 1 day.
            if task.recurring_schedule and days_until >= -1:
                continue

            # Already have an unresolved insight for this task? Update it.
            existing = db.query(AIInsight).filter(
                AIInsight.source_type == InsightSourceType.task,
                AIInsight.source_id == task.id,
                AIInsight.resolved_at.is_(None),
                AIInsight.dismissed_at.is_(None),
            ).first()
            if existing:
                # Update existing instead of creating duplicate
                if days_until < 0:
                    existing.title = f"OVERDUE: {task.title} ({abs(days_until)}d late)"
                    existing.acknowledged = False  # Re-surface
                continue

            if days_until < 0:
                # Overdue
                severity = InsightSeverity.urgent
                title = f"OVERDUE: {task.title} ({abs(days_until)}d late)"
                body = f"Task '{task.title}' was due {abs(days_until)} day(s) ago."
                why = f"Overdue tasks lower your execution score and may delay dependent work."
                action = f"Complete or reschedule this task. If blocked, update the status."

                # Check downstream dependencies
                if task.blocks:
                    severity = InsightSeverity.critical
                    blocked_tasks = db.query(Task).filter(Task.id.in_(task.blocks)).all()
                    blocked_names = [t.title for t in blocked_tasks]
                    body += f"\n\nThis blocks: {', '.join(blocked_names)}"
                    title = f"CRITICAL OVERDUE: {task.title} (blocks {len(blocked_names)} tasks)"
                    why = f"This blocks {len(blocked_names)} other task(s). The longer this stays overdue, the more your pipeline stalls."
                    action = f"Prioritize this immediately — it's holding up: {', '.join(blocked_names[:2])}."

            elif days_until <= 1:
                severity = InsightSeverity.attention
                title = f"Due tomorrow: {task.title}"
                body = f"Task '{task.title}' is due {'today' if days_until == 0 else 'tomorrow'}."
                why = "Approaching deadline — needs attention to stay on track."
                action = "Review and complete, or extend the deadline if needed."
            elif days_until <= 2:
                severity = InsightSeverity.info
                title = f"Due in 48h: {task.title}"
                body = f"Task '{task.title}' is due in {days_until} day(s)."
                why = "Heads up — this is coming up soon."
                action = "Plan time to work on this before the deadline."
            else:
                continue

            insight = AIInsight(
                project_id=pid,
                insight_type=InsightType.deadline_warning,
                source_type=InsightSourceType.task,
                source_id=task.id,
                title=title,
                body=body,
                severity=severity,
                why_it_matters=why,
                suggested_action=action,
                fix_url="/tasks",
                action_items=[f"Review task #{task.id}"],
            )
            db.add(insight)

        db.commit()
        logger.info("Deadline enforcer completed")
    finally:
        db.close()


# --- Job 2: Anomaly Detector (Daily 6AM) ---

def run_anomaly_detector():
    """Compare metrics to 7-day avg, flag >15% deviations."""
    db = SessionLocal()
    try:
        project = _get_project(db)
        if not project:
            return
        pid = project.id
        now = datetime.utcnow()
        seven_days_ago = now - timedelta(days=7)

        channels = db.query(Channel).filter_by(project_id=pid).all()

        for ch in channels:
            # Get distinct metric names for this channel
            metric_names = db.query(Metric.metric_name).filter(
                Metric.channel_id == ch.id,
                Metric.recorded_at >= seven_days_ago,
            ).distinct().all()

            for (mname,) in metric_names:
                # Get 7-day avg
                avg_val = db.query(func.avg(Metric.metric_value)).filter(
                    Metric.channel_id == ch.id,
                    Metric.metric_name == mname,
                    Metric.recorded_at >= seven_days_ago,
                ).scalar()

                if not avg_val or avg_val == 0:
                    continue

                # Get latest value
                latest = db.query(Metric).filter(
                    Metric.channel_id == ch.id,
                    Metric.metric_name == mname,
                ).order_by(Metric.recorded_at.desc()).first()

                if not latest:
                    continue

                pct_change = ((float(latest.metric_value) - float(avg_val)) / float(avg_val)) * 100

                if abs(pct_change) >= 15:
                    direction = "increased" if pct_change > 0 else "decreased"
                    severity = InsightSeverity.attention if abs(pct_change) >= 30 else InsightSeverity.info

                    if pct_change < -20:
                        why = f"A {abs(pct_change):.0f}% drop in {mname} could signal a problem with {ch.name} — investigate before it compounds."
                        action = f"Check {ch.name} for issues: API errors, content gaps, or algorithm changes."
                    elif pct_change > 20:
                        why = f"A {pct_change:.0f}% spike in {mname} — worth understanding what's working so you can replicate it."
                        action = f"Review recent activity on {ch.name} to identify what drove this growth."
                    else:
                        why = f"Notable change in {mname} — may need monitoring."
                        action = f"Keep an eye on {ch.name} metrics over the next few days."

                    insight = AIInsight(
                        project_id=pid,
                        insight_type=InsightType.anomaly,
                        source_type=InsightSourceType.channel,
                        source_id=ch.id,
                        title=f"{ch.name}: {mname} {direction} {abs(pct_change):.0f}%",
                        body=f"Latest: {float(latest.metric_value):.1f}, 7-day avg: {float(avg_val):.1f} ({pct_change:+.1f}%)",
                        severity=severity,
                        why_it_matters=why,
                        suggested_action=action,
                        fix_url="/channels",
                    )
                    db.add(insight)

        db.commit()
        logger.info("Anomaly detector completed")
    finally:
        db.close()


# --- Job 3: Automation Health Check (Every 4 hours) ---

def run_automation_health():
    """Check all automations for staleness."""
    db = SessionLocal()
    try:
        project = _get_project(db)
        if not project:
            return
        pid = project.id
        now = datetime.utcnow()

        automations = db.query(Automation).filter_by(project_id=pid).all()

        for auto in automations:
            if not auto.expected_run_interval_hours or not auto.last_confirmed_run:
                continue

            hours_since = (now - auto.last_confirmed_run).total_seconds() / 3600
            expected = auto.expected_run_interval_hours

            old_health = auto.health

            if hours_since > expected * 3:
                auto.health = AutomationHealth.failed
                if old_health != AutomationHealth.failed:
                    fail_msg = (f"Last run {hours_since:.0f}h ago (expected every {expected}h). "
                                f"This is {hours_since / expected:.1f}x the expected interval.")
                    insight = AIInsight(
                        project_id=pid,
                        insight_type=InsightType.stale_automation,
                        source_type=InsightSourceType.automation,
                        source_id=auto.id,
                        title=f"Automation FAILED: {auto.name}",
                        body=fail_msg,
                        severity=InsightSeverity.urgent,
                        why_it_matters=f"{auto.name} on {auto.platform} hasn't run in {hours_since:.0f}h. Automated workflows depending on it are not executing.",
                        suggested_action=f"Check {auto.platform} for errors. Re-run manually if needed, then verify the trigger is active.",
                        fix_url="/automations",
                        needs_clint=True,
                    )
                    db.add(insight)
                    # Level 2: Telegram alert for critical failures
                    send_critical_alert(
                        f"Automation FAILED: {auto.name}",
                        f"{fail_msg}\nPlatform: {auto.platform}",
                    )

            elif hours_since > expected * 1.5:
                auto.health = AutomationHealth.stale
                if old_health not in (AutomationHealth.stale, AutomationHealth.failed):
                    stale_msg = f"Last run {hours_since:.0f}h ago (expected every {expected}h)."
                    insight = AIInsight(
                        project_id=pid,
                        insight_type=InsightType.stale_automation,
                        source_type=InsightSourceType.automation,
                        source_id=auto.id,
                        title=f"Automation stale: {auto.name}",
                        body=stale_msg,
                        severity=InsightSeverity.attention,
                        why_it_matters=f"{auto.name} is running behind schedule. It may need a manual trigger or investigation.",
                        suggested_action=f"Check {auto.platform} to see if {auto.name} needs a manual kick or credential refresh.",
                        fix_url="/automations",
                    )
                    db.add(insight)
                    # Level 2: Telegram warning for stale automations
                    send_warning_alert(f"Automation stale: {auto.name}", stale_msg)

        db.commit()
        logger.info("Automation health check completed")
    finally:
        db.close()


# --- Job 4: Ad Signal Calculator (Every 6 hours) ---

def run_ad_signal_calculator():
    """Recalculate signals for all active ad campaigns."""
    db = SessionLocal()
    try:
        project = _get_project(db)
        if not project:
            return
        pid = project.id

        campaigns = db.query(AdCampaign).filter(
            AdCampaign.project_id == pid,
            AdCampaign.status == AdStatus.active,
        ).all()

        from app.routes.ads import _calc_signal
        for campaign in campaigns:
            old_signal = campaign.signal
            signal, reason = _calc_signal(campaign)
            campaign.signal = signal
            campaign.signal_reason = reason

            if signal != old_signal and signal.value in ("pause", "kill"):
                insight = AIInsight(
                    project_id=pid,
                    insight_type=InsightType.ad_signal,
                    source_type=InsightSourceType.ad_campaign,
                    source_id=campaign.id,
                    title=f"Ad signal: {signal.value.upper()} — {campaign.campaign_name}",
                    body=reason,
                    severity=InsightSeverity.attention if signal.value == "pause" else InsightSeverity.urgent,
                )
                db.add(insight)

        db.commit()
        logger.info("Ad signal calculator completed")
    finally:
        db.close()


# --- Job 5: Gap Analyzer (Weekly Sunday) ---

def run_gap_analyzer():
    """Structural + strategic gap analysis."""
    db = SessionLocal()
    try:
        project = _get_project(db)
        if not project:
            return
        pid = project.id
        today = date.today()
        gaps = []

        # Channels with no tasks
        channels = db.query(Channel).filter_by(project_id=pid).all()
        for ch in channels:
            task_count = db.query(Task).filter_by(project_id=pid, channel_id=ch.id).filter(
                Task.status.notin_([TaskStatus.done, TaskStatus.archived])
            ).count()
            if task_count == 0 and ch.status in (ChannelStatus.live, ChannelStatus.building):
                gaps.append(f"Channel '{ch.name}' ({ch.status.value}) has no active tasks")

        # Empty content pipeline stages
        for status in [ContentStatus.concept, ContentStatus.scripted, ContentStatus.filmed]:
            count = db.query(ContentPiece).filter_by(project_id=pid, status=status).count()
            if count == 0:
                gaps.append(f"Content pipeline: no pieces in '{status.value}' stage")

        # Overdue follow-ups
        overdue_contacts = db.query(OutreachContact).filter(
            OutreachContact.project_id == pid,
            OutreachContact.next_follow_up < today,
            OutreachContact.next_follow_up.isnot(None),
        ).count()
        if overdue_contacts > 0:
            gaps.append(f"{overdue_contacts} outreach contacts have overdue follow-ups")

        # Tool gaps
        from app.models import ToolCategory
        active_categories = set()
        tools = db.query(Tool).filter_by(project_id=pid, status=ToolStatus.active).all()
        for t in tools:
            active_categories.add(t.category.value)

        essential = {"email_marketing", "analytics", "payments"}
        missing = essential - active_categories
        for cat in missing:
            gaps.append(f"No active tool for essential category: {cat}")

        # Budget overruns
        allocations = db.query(BudgetAllocation).filter_by(project_id=pid).all()
        for alloc in allocations:
            month_start = today.replace(day=1)
            spent = db.query(func.sum(BudgetExpense.amount)).filter(
                BudgetExpense.project_id == pid,
                BudgetExpense.category == alloc.category,
                BudgetExpense.expense_date >= month_start,
            ).scalar() or 0

            if alloc.planned_monthly and float(spent) > float(alloc.planned_monthly):
                gaps.append(
                    f"Budget overrun: {alloc.category.value} — "
                    f"${float(spent):.0f} spent vs ${float(alloc.planned_monthly):.0f} planned"
                )

        if gaps:
            insight = AIInsight(
                project_id=pid,
                insight_type=InsightType.gap_analysis,
                source_type=InsightSourceType.general,
                title=f"Weekly Gap Analysis — {len(gaps)} issues found",
                body="\n".join(f"- {g}" for g in gaps),
                severity=InsightSeverity.attention if len(gaps) > 3 else InsightSeverity.info,
                action_items=gaps[:5],
            )
            db.add(insight)
            db.commit()

        logger.info(f"Gap analyzer completed: {len(gaps)} gaps found")
    finally:
        db.close()


# --- Job 6: Weekly Digest (Sunday 7AM) ---

def run_weekly_digest():
    """Generate full project summary. Uses AI if available, otherwise structured."""
    db = SessionLocal()
    try:
        project = _get_project(db)
        if not project:
            return
        pid = project.id

        from app.ai.tools import _get_weekly_summary
        summary = _get_weekly_summary(db, pid, {})

        body_lines = [
            f"**Execution Score: {summary['execution_score']}** ({summary['score_color']})",
            f"",
            f"**Tasks:** {summary['tasks']['done_this_week']} completed this week, "
            f"{summary['tasks']['overdue']} overdue, {summary['tasks']['total']} total",
            f"**Content:** {summary['content']['published_this_week']}/{summary['content']['target']} published this week",
            f"**Automations:** {summary['automations']['healthy']}/{summary['automations']['total']} healthy",
            f"**Channels:** {summary['channels']['live']}/{summary['channels']['total']} live",
        ]

        insight = AIInsight(
            project_id=pid,
            insight_type=InsightType.weekly_digest,
            source_type=InsightSourceType.general,
            title=f"Weekly Digest — Week of {summary['week_of']}",
            body="\n".join(body_lines),
            severity=InsightSeverity.info,
        )
        db.add(insight)
        db.commit()
        logger.info("Weekly digest generated")
    finally:
        db.close()


# --- Job 7: Outreach Follow-Up (Daily 8AM) ---

def run_outreach_followup():
    """Flag overdue contact follow-ups."""
    db = SessionLocal()
    try:
        project = _get_project(db)
        if not project:
            return
        pid = project.id
        today = date.today()

        overdue = db.query(OutreachContact).filter(
            OutreachContact.project_id == pid,
            OutreachContact.next_follow_up < today,
            OutreachContact.next_follow_up.isnot(None),
        ).all()

        if not overdue:
            return

        body_lines = []
        for c in overdue:
            days_late = (today - c.next_follow_up).days
            body_lines.append(f"- {c.name} ({c.platform}) — {days_late}d overdue, status: {c.status.value}")

        # Deduplicate: update existing unresolved follow-up insight
        existing = db.query(AIInsight).filter(
            AIInsight.project_id == pid,
            AIInsight.insight_type == InsightType.suggestion,
            AIInsight.title.like("Outreach: % overdue follow-ups"),
            AIInsight.resolved_at.is_(None),
            AIInsight.dismissed_at.is_(None),
        ).first()

        if existing:
            existing.title = f"Outreach: {len(overdue)} overdue follow-ups"
            existing.body = "\n".join(body_lines)
            existing.acknowledged = False
        else:
            insight = AIInsight(
                project_id=pid,
                insight_type=InsightType.suggestion,
                source_type=InsightSourceType.general,
                title=f"Outreach: {len(overdue)} overdue follow-ups",
                body="\n".join(body_lines),
                severity=InsightSeverity.attention,
                why_it_matters=f"Stale follow-ups lose momentum. These {len(overdue)} contacts may go cold if not re-engaged soon.",
                suggested_action=f"Spend 15-20 min today sending follow-up messages to the most promising contacts.",
                fix_url="/pipelines/outreach",
                action_items=[f"Follow up with {c.name}" for c in overdue[:5]],
            )
            db.add(insight)
        db.commit()
        logger.info(f"Outreach follow-up: {len(overdue)} overdue")
    finally:
        db.close()


# --- Job 8: Content Pipeline Check (Daily 9AM) ---

def run_content_pipeline_check():
    """Check content output vs weekly target."""
    db = SessionLocal()
    try:
        project = _get_project(db)
        if not project:
            return
        pid = project.id
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        weekly_target = 3

        published = db.query(ContentPiece).filter(
            ContentPiece.project_id == pid,
            ContentPiece.status == ContentStatus.published,
            ContentPiece.published_at >= datetime.combine(week_start, datetime.min.time()),
        ).count()

        days_left = 6 - today.weekday()  # days until Sunday

        if published >= weekly_target:
            return  # on track

        remaining = weekly_target - published
        severity = InsightSeverity.info

        if days_left <= 1 and remaining > 0:
            severity = InsightSeverity.attention
        if days_left == 0 and remaining > 0:
            severity = InsightSeverity.urgent

        # Check what's in pipeline
        in_progress = db.query(ContentPiece).filter(
            ContentPiece.project_id == pid,
            ContentPiece.status.in_([
                ContentStatus.scripted, ContentStatus.filmed,
                ContentStatus.with_editor, ContentStatus.edited,
                ContentStatus.scheduled,
            ]),
        ).count()

        insight = AIInsight(
            project_id=pid,
            insight_type=InsightType.bottleneck,
            source_type=InsightSourceType.content,
            title=f"Content: {published}/{weekly_target} published this week",
            body=f"{remaining} more needed, {days_left} days left. "
                 f"{in_progress} pieces currently in progress.",
            severity=severity,
            why_it_matters=f"Missing the weekly content target weakens your channel growth and audience engagement.",
            suggested_action=f"Review the {in_progress} pieces in progress and push the closest ones to published.",
            fix_url="/content",
        )
        db.add(insight)
        db.commit()
        logger.info(f"Content pipeline check: {published}/{weekly_target}")
    finally:
        db.close()


# --- Job 9: Channel Intelligence (Weekly Sunday 6:30 AM) ---

def run_channel_intelligence():
    """Weekly channel performance digest + metric drop alerts + stale nudges."""
    db = SessionLocal()
    try:
        project = _get_project(db)
        if not project:
            return
        pid = project.id
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)

        channels = db.query(Channel).filter_by(project_id=pid).all()
        live_channels = [ch for ch in channels if ch.status == ChannelStatus.live]

        grew = []
        declined = []
        needs_attention = []
        stale = []

        for ch in live_channels:
            metric_names = db.query(Metric.metric_name).filter(
                Metric.channel_id == ch.id,
            ).distinct().all()

            ch_grew = False
            ch_declined = False

            for (mname,) in metric_names:
                # This week's latest
                this_week = db.query(Metric).filter(
                    Metric.channel_id == ch.id,
                    Metric.metric_name == mname,
                    Metric.recorded_at >= week_ago,
                ).order_by(Metric.recorded_at.desc()).first()

                last_week = db.query(Metric).filter(
                    Metric.channel_id == ch.id,
                    Metric.metric_name == mname,
                    Metric.recorded_at >= two_weeks_ago,
                    Metric.recorded_at < week_ago,
                ).order_by(Metric.recorded_at.desc()).first()

                if this_week and last_week and float(last_week.metric_value) > 0:
                    pct = ((float(this_week.metric_value) - float(last_week.metric_value)) / float(last_week.metric_value)) * 100

                    if pct <= -20:
                        ch_declined = True
                        # Create metric drop alert
                        recent_alert = db.query(AIInsight).filter(
                            AIInsight.source_type == InsightSourceType.channel,
                            AIInsight.source_id == ch.id,
                            AIInsight.insight_type == InsightType.anomaly,
                            AIInsight.created_at >= now - timedelta(hours=24),
                        ).first()
                        if not recent_alert:
                            alert = AIInsight(
                                project_id=pid,
                                insight_type=InsightType.anomaly,
                                source_type=InsightSourceType.channel,
                                source_id=ch.id,
                                title=f"{ch.name}: {mname.replace('_', ' ')} dropped {abs(pct):.0f}% WoW",
                                body=f"{float(last_week.metric_value):,.0f} -> {float(this_week.metric_value):,.0f} ({pct:+.1f}%)",
                                severity=InsightSeverity.attention,
                                why_it_matters=f"A {abs(pct):.0f}% week-over-week decline in {mname.replace('_', ' ')} on {ch.name} could indicate a trend problem.",
                                suggested_action=f"Check {ch.name} for recent changes, content gaps, or external factors causing the drop.",
                                fix_url="/channels",
                            )
                            db.add(alert)
                            send_warning_alert(
                                f"Channel metric drop: {ch.name}",
                                f"{mname}: {float(last_week.metric_value):,.0f} -> {float(this_week.metric_value):,.0f} ({pct:+.1f}%)"
                            )
                    elif pct >= 10:
                        ch_grew = True

            if ch_grew and not ch_declined:
                grew.append(ch.name)
            elif ch_declined:
                declined.append(ch.name)

            # Check staleness
            latest = db.query(Metric).filter_by(channel_id=ch.id).order_by(
                Metric.recorded_at.desc()
            ).first()
            if latest:
                days_since = (now - latest.recorded_at).days
                if days_since >= 7:
                    stale.append(f"{ch.name} ({days_since}d)")
                    # Stale nudge alert
                    recent_nudge = db.query(AIInsight).filter(
                        AIInsight.source_type == InsightSourceType.channel,
                        AIInsight.source_id == ch.id,
                        AIInsight.insight_type == InsightType.suggestion,
                        AIInsight.created_at >= now - timedelta(days=3),
                    ).first()
                    if not recent_nudge:
                        nudge = AIInsight(
                            project_id=pid,
                            insight_type=InsightType.suggestion,
                            source_type=InsightSourceType.channel,
                            source_id=ch.id,
                            title=f"{ch.name} metrics haven't been updated in {days_since} days",
                            body=f"Last metric: {latest.metric_name} = {float(latest.metric_value):,.0f}",
                            severity=InsightSeverity.info,
                        )
                        db.add(nudge)
            elif ch.automation_level == AutomationLevel.manual:
                needs_attention.append(ch.name)

        # Build weekly digest
        body_lines = [
            f"**Weekly Channel Performance — {date.today().strftime('%b %d, %Y')}**",
            f"",
            f"Live channels: {len(live_channels)}/{len(channels)}",
        ]
        if grew:
            body_lines.append(f"Growing: {', '.join(grew)}")
        if declined:
            body_lines.append(f"Declining: {', '.join(declined)}")
        if stale:
            body_lines.append(f"Stale (7+ days): {', '.join(stale)}")
        if needs_attention:
            body_lines.append(f"No metrics ever recorded: {', '.join(needs_attention)}")

        # Focus recommendation
        if declined:
            body_lines.append(f"")
            body_lines.append(f"Priority: Investigate declining channels — {', '.join(declined)}")
        elif stale:
            body_lines.append(f"")
            body_lines.append(f"Priority: Update stale channel metrics — {', '.join(stale)}")

        digest = AIInsight(
            project_id=pid,
            insight_type=InsightType.weekly_digest,
            source_type=InsightSourceType.channel,
            title=f"Channel Performance Digest — Week of {date.today().strftime('%b %d')}",
            body="\n".join(body_lines),
            severity=InsightSeverity.info,
        )
        db.add(digest)
        db.commit()

        # Send to Telegram
        tg_msg = "<b>Channel Performance Digest</b>\n\n"
        tg_msg += f"Live: {len(live_channels)}/{len(channels)}\n"
        if grew:
            tg_msg += f"Growing: {', '.join(grew)}\n"
        if declined:
            tg_msg += f"Declining: {', '.join(declined)}\n"
        if stale:
            tg_msg += f"Stale: {', '.join(stale)}\n"
        send_telegram(tg_msg)

        logger.info(f"Channel intelligence completed: {len(grew)} growing, {len(declined)} declining, {len(stale)} stale")
    finally:
        db.close()


# --- Job 10: Channel Metric Drop Monitor (Every 6 hours) ---

def run_channel_metric_monitor():
    """Check for >20% drops in primary channel metrics and create dashboard alerts."""
    db = SessionLocal()
    try:
        project = _get_project(db)
        if not project:
            return
        pid = project.id
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)

        channels = db.query(Channel).filter_by(project_id=pid, status=ChannelStatus.live).all()

        for ch in channels:
            metric_names = db.query(Metric.metric_name).filter(
                Metric.channel_id == ch.id,
            ).distinct().all()

            for (mname,) in metric_names:
                this_week = db.query(Metric).filter(
                    Metric.channel_id == ch.id,
                    Metric.metric_name == mname,
                    Metric.recorded_at >= week_ago,
                ).order_by(Metric.recorded_at.desc()).first()

                last_week = db.query(Metric).filter(
                    Metric.channel_id == ch.id,
                    Metric.metric_name == mname,
                    Metric.recorded_at >= two_weeks_ago,
                    Metric.recorded_at < week_ago,
                ).order_by(Metric.recorded_at.desc()).first()

                if this_week and last_week and float(last_week.metric_value) > 0:
                    pct = ((float(this_week.metric_value) - float(last_week.metric_value)) / float(last_week.metric_value)) * 100

                    if pct <= -20:
                        # Check for recent duplicate
                        recent = db.query(AIInsight).filter(
                            AIInsight.source_type == InsightSourceType.channel,
                            AIInsight.source_id == ch.id,
                            AIInsight.insight_type == InsightType.anomaly,
                            AIInsight.created_at >= now - timedelta(hours=12),
                        ).first()
                        if not recent:
                            alert = AIInsight(
                                project_id=pid,
                                insight_type=InsightType.anomaly,
                                source_type=InsightSourceType.channel,
                                source_id=ch.id,
                                title=f"{ch.name}: {mname.replace('_', ' ')} dropped {abs(pct):.0f}%",
                                body=f"Week-over-week: {float(last_week.metric_value):,.0f} -> {float(this_week.metric_value):,.0f} ({pct:+.1f}%)",
                                severity=InsightSeverity.attention,
                                why_it_matters=f"Sustained metric drops on {ch.name} can compound — early investigation prevents bigger losses.",
                                suggested_action=f"Open {ch.name} and review recent activity, then check for API or platform issues.",
                                fix_url="/channels",
                                action_items=[f"Investigate {ch.name} {mname} drop"],
                            )
                            db.add(alert)

        db.commit()
        logger.info("Channel metric monitor completed")
    finally:
        db.close()


# --- Lead Score Calculation ---

def run_lead_scoring():
    """Weekly lead scoring pass per Section 4.21 rules."""
    db = SessionLocal()
    try:
        project = _get_project(db)
        if not project:
            return
        pid = project.id
        now = datetime.utcnow()

        # Get all subscriber events
        events = db.query(SubscriberEvent).filter_by(project_id=pid).all()

        # Group by email_hash
        by_hash = {}
        for e in events:
            by_hash.setdefault(e.email_hash, []).append(e)

        for email_hash, user_events in by_hash.items():
            score = 0

            for ev in user_events:
                if ev.event_type == SubscriberEventType.trial_start:
                    score += 5  # signed up
                elif ev.event_type == SubscriberEventType.convert_basic:
                    score += 15
                elif ev.event_type == SubscriberEventType.convert_premium:
                    score += 25

            # Decay for inactivity
            latest_event = max(user_events, key=lambda e: e.occurred_at)
            days_inactive = (now - latest_event.occurred_at).days
            if days_inactive >= 30:
                score -= 20
            elif days_inactive >= 14:
                score -= 10

            score = max(0, score)

            # Determine tier
            if score >= 50:
                tier = LeadTier.hot
            elif score >= 20:
                tier = LeadTier.warm
            elif score >= 5:
                tier = LeadTier.cool
            else:
                tier = LeadTier.cold

            # Upsert lead score
            existing = db.query(LeadScore).filter_by(
                project_id=pid, email_hash=email_hash
            ).first()

            if existing:
                existing.current_score = score
                existing.tier = tier
                existing.last_activity_at = latest_event.occurred_at
                existing.updated_at = now
            else:
                lead = LeadScore(
                    project_id=pid,
                    email_hash=email_hash,
                    current_score=score,
                    tier=tier,
                    source_channel_id=latest_event.source_channel_id,
                    last_activity_at=latest_event.occurred_at,
                )
                db.add(lead)

        db.commit()
        logger.info(f"Lead scoring completed: {len(by_hash)} leads scored")
    finally:
        db.close()


# --- Sync wrappers for APScheduler ---

def _sync_wrap(fn):
    """Wrapper that handles both sync and async event loops for APScheduler."""
    def wrapper():
        try:
            fn()
        except Exception as e:
            logger.error(f"AI job {fn.__name__} failed: {e}")
    return wrapper


deadline_enforcer_job = _sync_wrap(run_deadline_enforcer)
anomaly_detector_job = _sync_wrap(run_anomaly_detector)
automation_health_job = _sync_wrap(run_automation_health)
ad_signal_job = _sync_wrap(run_ad_signal_calculator)
gap_analyzer_job = _sync_wrap(run_gap_analyzer)
weekly_digest_job = _sync_wrap(run_weekly_digest)
outreach_followup_job = _sync_wrap(run_outreach_followup)
content_pipeline_job = _sync_wrap(run_content_pipeline_check)
lead_scoring_job = _sync_wrap(run_lead_scoring)
channel_intelligence_job = _sync_wrap(run_channel_intelligence)
channel_metric_monitor_job = _sync_wrap(run_channel_metric_monitor)
