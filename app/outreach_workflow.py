"""Outreach Workflow Assist — auto-drafts follow-ups, surfaces reminders in Approval Queue.

Runs on scheduler. All actions require Phil's explicit approval.
"""
import logging
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import (
    Project, OutreachContact, ApprovalQueueItem,
    ContactStatus, QueueItemType, QueueItemStatus,
)

logger = logging.getLogger("mcc.outreach_workflow")

FOLLOWUP_TEMPLATE = (
    "Hey {name}, just bumping this in case it got buried. "
    "No pressure \u2014 if the timing\u2019s not right, totally get it. "
    "The offer for a free account stands whenever you\u2019re curious. \u2014 Phil"
)


def _has_pending_item(db, contact_id: int, item_type: QueueItemType) -> bool:
    """Check if a pending queue item already exists for this contact + type."""
    return db.query(ApprovalQueueItem).filter_by(
        contact_id=contact_id,
        item_type=item_type,
        status=QueueItemStatus.pending,
    ).first() is not None


def run_outreach_workflow():
    """Scan contacts and create queue items for follow-ups, decline checks, check-ins."""
    db = SessionLocal()
    try:
        project = db.query(Project).filter_by(slug="grindlab").first()
        if not project:
            return
        pid = project.id
        now = datetime.utcnow()
        today = now.date()
        created = 0

        contacts = db.query(OutreachContact).filter_by(project_id=pid).all()

        for contact in contacts:
            stage_date = (
                contact.stage_changed_at
                or (datetime.combine(contact.last_contact_date, datetime.min.time()) if contact.last_contact_date else None)
            )
            if not stage_date:
                continue

            days_in_stage = (now - stage_date).days

            # --- 1. Contacted for 7+ days, no follow-up drafted yet ---
            if (
                contact.status == ContactStatus.contacted
                and days_in_stage >= 7
                and not contact.followup_drafted_at
                and not _has_pending_item(db, contact.id, QueueItemType.outreach_followup)
            ):
                draft = FOLLOWUP_TEMPLATE.format(name=contact.name.split()[0])
                item = ApprovalQueueItem(
                    project_id=pid,
                    item_type=QueueItemType.outreach_followup,
                    source_label="Outreach",
                    title=f"Follow-up draft for {contact.name}",
                    preview=draft,
                    draft_message=draft,
                    contact_id=contact.id,
                    action_url="/pipelines/outreach",
                )
                db.add(item)
                contact.followup_drafted_at = now
                created += 1

            # --- 2. Contacted for 14+ days after follow-up → decline check ---
            if (
                contact.status == ContactStatus.contacted
                and days_in_stage >= 14
                and contact.followup_drafted_at
                and not _has_pending_item(db, contact.id, QueueItemType.outreach_decline_check)
            ):
                item = ApprovalQueueItem(
                    project_id=pid,
                    item_type=QueueItemType.outreach_decline_check,
                    source_label="Outreach",
                    title=f"No response from {contact.name} after follow-up",
                    preview=f"{contact.name} ({contact.platform}) has been in Contacted for {days_in_stage} days with no response after follow-up. Move to Declined?",
                    contact_id=contact.id,
                    action_url="/pipelines/outreach",
                )
                db.add(item)
                created += 1

            # --- 3. In Conversation for 14+ days → check-in reminder ---
            if (
                contact.status == ContactStatus.in_conversation
                and days_in_stage >= 14
                and not _has_pending_item(db, contact.id, QueueItemType.outreach_checkin)
            ):
                item = ApprovalQueueItem(
                    project_id=pid,
                    item_type=QueueItemType.outreach_checkin,
                    source_label="Outreach",
                    title=f"Check in with {contact.name}?",
                    preview=f"{contact.name} ({contact.platform}) has been in conversation for {days_in_stage} days. Time for a check-in?",
                    contact_id=contact.id,
                    action_url="/pipelines/outreach",
                )
                db.add(item)
                created += 1

        if created:
            db.commit()
            logger.info(f"Outreach workflow: created {created} queue items")
        else:
            logger.info("Outreach workflow: no new items to create")

    except Exception as e:
        logger.error(f"Outreach workflow failed: {e}")
    finally:
        db.close()
