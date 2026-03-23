"""Tool definitions and execution for AI chat."""
import json
import logging
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import SessionLocal
from app.models import (
    Project, Channel, Metric, Task, Automation, ContentPiece, AdCampaign,
    OutreachContact, SubscriberSnapshot, EmailSequence, Tool, Experiment,
    BudgetAllocation, BudgetExpense, PerformanceScore,
    TaskStatus, TaskPriority, AutomationHealth, HealthStatus,
    ContentStatus, ChannelStatus, AdStatus, SubscriberStage,
    ChannelType, AutomationLevel, ToolCategory, ToolStatus, BillingCycle,
    ContentType, ProductionLane, AdPlatform, AdObjective,
    AutomationType, HostingLocation, HealthCheckMethod,
    ContactType, ContactStatus, MetricSource,
)
from app.routes.dashboard import calc_execution_score

logger = logging.getLogger("mcc.ai.tools")


TOOL_DEFINITIONS = [
    {
        "name": "get_channel_metrics",
        "description": "Get recent metrics for a specific channel or all channels. Returns metric name, value, and change.",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_name": {"type": "string", "description": "Channel name to filter (optional, returns all if empty)"},
                "days": {"type": "integer", "description": "Number of days to look back", "default": 7},
            },
            "required": [],
        },
    },
    {
        "name": "get_task_list",
        "description": "Get tasks filtered by status, priority, or assignee.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status: backlog, this_week, in_progress, blocked, done"},
                "priority": {"type": "string", "description": "Filter by priority: launch_critical, high, medium, low"},
                "overdue_only": {"type": "boolean", "description": "Only show overdue tasks", "default": False},
            },
            "required": [],
        },
    },
    {
        "name": "create_task",
        "description": "Create a new task in the project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "priority": {"type": "string", "description": "Priority: launch_critical, high, medium, low", "default": "medium"},
                "due_date": {"type": "string", "description": "Due date in YYYY-MM-DD format"},
                "description": {"type": "string", "description": "Task description"},
                "assigned_to": {"type": "string", "description": "Assignee name", "default": "phil"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_task",
        "description": "Update a task's status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "Task ID"},
                "status": {"type": "string", "description": "New status: backlog, this_week, in_progress, blocked, done"},
            },
            "required": ["task_id", "status"],
        },
    },
    {
        "name": "record_metric",
        "description": "Record a metric value for a channel.",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_name": {"type": "string", "description": "Channel name"},
                "metric_name": {"type": "string", "description": "Metric name"},
                "value": {"type": "number", "description": "Metric value"},
                "unit": {"type": "string", "description": "Unit of measurement", "default": "count"},
            },
            "required": ["channel_name", "metric_name", "value"],
        },
    },
    {
        "name": "get_ad_campaigns",
        "description": "Get ad campaign data with signals and performance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status_filter": {"type": "string", "description": "Filter by status: active, paused, ended"},
            },
            "required": [],
        },
    },
    {
        "name": "get_execution_score",
        "description": "Get the current execution score with component breakdown.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_outreach_contacts",
        "description": "Get outreach contacts, optionally filtered by status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status_filter": {"type": "string", "description": "Filter by status"},
                "overdue_only": {"type": "boolean", "description": "Only show contacts with overdue follow-ups", "default": False},
            },
            "required": [],
        },
    },
    {
        "name": "get_automations",
        "description": "Get automations with health status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "health_filter": {"type": "string", "description": "Filter by health: running, stale, failed, paused"},
            },
            "required": [],
        },
    },
    {
        "name": "get_content_pipeline",
        "description": "Get content pieces in the pipeline, optionally filtered by status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status_filter": {"type": "string", "description": "Filter by status: concept, scripted, filmed, with_editor, edited, scheduled, published"},
            },
            "required": [],
        },
    },
    {
        "name": "get_subscriber_funnel",
        "description": "Get current subscriber counts by stage and recent events.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_tech_stack",
        "description": "Get tools in the tech stack, optionally filtered by category.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Filter by category"},
            },
            "required": [],
        },
    },
    {
        "name": "get_weekly_summary",
        "description": "Get a comprehensive weekly summary of all project metrics and status.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "generate_strategy_export",
        "description": "Generate a comprehensive strategy export markdown report. Use when the user says 'export for Claude', 'strategy export', 'generate strategy report', or wants a full project snapshot for analysis.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "track_entity",
        "description": "Start tracking a new entity (channel, tool, content, ad campaign, automation, outreach contact, or metric). Use this when the user mentions signing up for a new tool, starting a new channel, creating content, launching a campaign, setting up an automation, or meeting a new contact.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["channel", "tool", "content", "ad", "automation", "contact", "metric"],
                    "description": "Type of entity to track",
                },
                "name": {"type": "string", "description": "Name of the entity"},
                "subtype": {"type": "string", "description": "Subtype (e.g. channel_type=social, tool_category=scraping, content_type=short_video, ad_platform=meta, automation_type=cron_job, contact_type=influencer)"},
                "notes": {"type": "string", "description": "Additional context or notes"},
                "monthly_cost": {"type": "number", "description": "Monthly cost (for tools)"},
                "purpose": {"type": "string", "description": "Purpose or description"},
                "setup_tasks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of setup tasks to create",
                },
            },
            "required": ["entity_type", "name"],
        },
    },
    {
        "name": "stop_tracking",
        "description": "Stop tracking / deprecate an entity. Use when the user says they're dropping a tool, closing a channel, pausing a campaign, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["channel", "tool", "automation", "ad"],
                    "description": "Type of entity to stop tracking",
                },
                "name": {"type": "string", "description": "Name of the entity to stop tracking"},
            },
            "required": ["entity_type", "name"],
        },
    },
]


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool call and return the result as a string."""
    db = SessionLocal()
    try:
        project = db.query(Project).filter_by(slug="grindlab").first()
        if not project:
            return json.dumps({"error": "No project found"})

        pid = project.id
        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        result = handler(db, pid, tool_input)
        return json.dumps(result, default=str)
    finally:
        db.close()


def _get_channel_metrics(db: Session, pid: int, inputs: dict) -> dict:
    channels = db.query(Channel).filter_by(project_id=pid).all()
    channel_name = inputs.get("channel_name", "")
    days = inputs.get("days", 7)
    cutoff = datetime.utcnow() - timedelta(days=days)

    results = []
    for ch in channels:
        if channel_name and channel_name.lower() not in ch.name.lower():
            continue
        metrics = db.query(Metric).filter(
            Metric.channel_id == ch.id,
            Metric.recorded_at >= cutoff,
        ).order_by(Metric.recorded_at.desc()).all()

        seen = {}
        for m in metrics:
            if m.metric_name not in seen:
                seen[m.metric_name] = {
                    "name": m.metric_name,
                    "value": float(m.metric_value),
                    "previous": float(m.previous_value) if m.previous_value else None,
                    "unit": m.unit,
                    "recorded_at": m.recorded_at.isoformat(),
                }
        if seen or not channel_name:
            results.append({
                "channel": ch.name,
                "status": ch.status.value,
                "health": ch.health.value,
                "metrics": list(seen.values()),
            })

    return {"channels": results, "period_days": days}


def _get_task_list(db: Session, pid: int, inputs: dict) -> dict:
    q = db.query(Task).filter_by(project_id=pid)

    status = inputs.get("status")
    if status:
        try:
            q = q.filter(Task.status == TaskStatus(status))
        except ValueError:
            pass

    priority = inputs.get("priority")
    if priority:
        try:
            q = q.filter(Task.priority == TaskPriority(priority))
        except ValueError:
            pass

    if inputs.get("overdue_only"):
        q = q.filter(Task.due_date < date.today(), Task.status.notin_([TaskStatus.done, TaskStatus.archived, TaskStatus.recurring]))

    tasks = q.order_by(Task.due_date.asc().nullslast()).limit(50).all()
    return {
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status.value,
                "priority": t.priority.value,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "assigned_to": t.assigned_to,
                "overdue": t.due_date < date.today() if t.due_date else False,
            }
            for t in tasks
        ],
        "count": len(tasks),
    }


def _create_task(db: Session, pid: int, inputs: dict) -> dict:
    due = None
    if inputs.get("due_date"):
        try:
            due = date.fromisoformat(inputs["due_date"])
        except ValueError:
            pass

    try:
        priority = TaskPriority(inputs.get("priority", "medium"))
    except ValueError:
        priority = TaskPriority.medium

    task = Task(
        project_id=pid,
        title=inputs["title"],
        description=inputs.get("description", ""),
        priority=priority,
        due_date=due,
        assigned_to=inputs.get("assigned_to", "phil"),
        status=TaskStatus.backlog,
    )
    db.add(task)
    db.commit()
    return {"created": True, "task_id": task.id, "title": task.title}


def _update_task(db: Session, pid: int, inputs: dict) -> dict:
    task = db.get(Task, inputs["task_id"])
    if not task or task.project_id != pid:
        return {"error": "Task not found"}

    try:
        new_status = TaskStatus(inputs["status"])
    except ValueError:
        return {"error": f"Invalid status: {inputs['status']}"}

    task.status = new_status
    if new_status == TaskStatus.done:
        task.completed_at = datetime.utcnow()
    db.commit()
    return {"updated": True, "task_id": task.id, "new_status": new_status.value}


def _record_metric(db: Session, pid: int, inputs: dict) -> dict:
    from app.models import MetricSource

    channel = db.query(Channel).filter(
        Channel.project_id == pid,
        Channel.name == inputs["channel_name"],
    ).first()
    if not channel:
        return {"error": f"Channel '{inputs['channel_name']}' not found"}

    prev = db.query(Metric).filter_by(
        channel_id=channel.id,
        metric_name=inputs["metric_name"],
    ).order_by(Metric.recorded_at.desc()).first()

    metric = Metric(
        channel_id=channel.id,
        metric_name=inputs["metric_name"],
        metric_value=inputs["value"],
        previous_value=prev.metric_value if prev else None,
        unit=inputs.get("unit", "count"),
        source=MetricSource.api,
    )
    db.add(metric)
    db.commit()
    return {"recorded": True, "metric_id": metric.id}


def _get_ad_campaigns(db: Session, pid: int, inputs: dict) -> dict:
    q = db.query(AdCampaign).filter_by(project_id=pid)
    status_filter = inputs.get("status_filter")
    if status_filter:
        try:
            q = q.filter(AdCampaign.status == AdStatus(status_filter))
        except ValueError:
            pass

    campaigns = q.all()
    return {
        "campaigns": [
            {
                "id": c.id,
                "name": c.campaign_name,
                "platform": c.platform.value,
                "status": c.status.value,
                "signal": c.signal.value if c.signal else "hold",
                "spend": float(c.spend_to_date) if c.spend_to_date else 0,
                "budget": float(c.total_budget) if c.total_budget else 0,
                "impressions": c.impressions,
                "clicks": c.clicks,
                "ctr": float(c.ctr) if c.ctr else 0,
                "conversions": c.conversions,
                "cpl": float(c.cpl) if c.cpl else None,
            }
            for c in campaigns
        ],
        "count": len(campaigns),
    }


def _get_execution_score(db: Session, pid: int, inputs: dict) -> dict:
    return calc_execution_score(db, pid)


def _get_outreach_contacts(db: Session, pid: int, inputs: dict) -> dict:
    q = db.query(OutreachContact).filter_by(project_id=pid)
    if inputs.get("status_filter"):
        q = q.filter(OutreachContact.status == inputs["status_filter"])
    if inputs.get("overdue_only"):
        q = q.filter(
            OutreachContact.next_follow_up < date.today(),
            OutreachContact.next_follow_up.isnot(None),
        )

    contacts = q.limit(50).all()
    return {
        "contacts": [
            {
                "id": c.id,
                "name": c.name,
                "platform": c.platform,
                "status": c.status.value,
                "type": c.contact_type.value,
                "next_follow_up": c.next_follow_up.isoformat() if c.next_follow_up else None,
                "overdue": c.next_follow_up < date.today() if c.next_follow_up else False,
            }
            for c in contacts
        ],
        "count": len(contacts),
    }


def _get_automations(db: Session, pid: int, inputs: dict) -> dict:
    q = db.query(Automation).filter_by(project_id=pid)
    if inputs.get("health_filter"):
        try:
            q = q.filter(Automation.health == AutomationHealth(inputs["health_filter"]))
        except ValueError:
            pass

    autos = q.all()
    return {
        "automations": [
            {
                "id": a.id,
                "name": a.name,
                "type": a.automation_type.value,
                "health": a.health.value,
                "last_run": a.last_confirmed_run.isoformat() if a.last_confirmed_run else None,
                "schedule": a.schedule,
            }
            for a in autos
        ],
        "count": len(autos),
    }


def _get_content_pipeline(db: Session, pid: int, inputs: dict) -> dict:
    q = db.query(ContentPiece).filter_by(project_id=pid)
    if inputs.get("status_filter"):
        try:
            q = q.filter(ContentPiece.status == ContentStatus(inputs["status_filter"]))
        except ValueError:
            pass

    pieces = q.order_by(ContentPiece.due_date.asc().nullslast()).limit(50).all()
    return {
        "content": [
            {
                "id": p.id,
                "title": p.title,
                "type": p.content_type.value,
                "status": p.status.value,
                "assigned_to": p.assigned_to,
                "due_date": p.due_date.isoformat() if p.due_date else None,
            }
            for p in pieces
        ],
        "count": len(pieces),
    }


def _get_subscriber_funnel(db: Session, pid: int, inputs: dict) -> dict:
    latest_date = db.query(func.max(SubscriberSnapshot.snapshot_date)).filter_by(
        project_id=pid
    ).scalar()

    stages = {}
    if latest_date:
        snapshots = db.query(SubscriberSnapshot).filter_by(
            project_id=pid, snapshot_date=latest_date
        ).all()
        for s in snapshots:
            stages[s.stage.value] = {"count": s.count, "mrr": float(s.mrr) if s.mrr else 0}

    return {"snapshot_date": latest_date.isoformat() if latest_date else None, "stages": stages}


def _get_tech_stack(db: Session, pid: int, inputs: dict) -> dict:
    q = db.query(Tool).filter_by(project_id=pid)
    if inputs.get("category"):
        q = q.filter(Tool.category == inputs["category"])

    tools = q.all()
    return {
        "tools": [
            {
                "id": t.id,
                "name": t.name,
                "category": t.category.value,
                "status": t.status.value,
                "monthly_cost": float(t.monthly_cost) if t.monthly_cost else 0,
                "api_integrated": t.api_integrated,
            }
            for t in tools
        ],
        "count": len(tools),
    }


def _get_weekly_summary(db: Session, pid: int, inputs: dict) -> dict:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    exec_score = calc_execution_score(db, pid)

    # Task summary
    total_tasks = db.query(Task).filter_by(project_id=pid).count()
    done_this_week = db.query(Task).filter(
        Task.project_id == pid,
        Task.status.in_([TaskStatus.done, TaskStatus.archived]),
        Task.completed_at >= datetime.combine(week_start, datetime.min.time()),
    ).count()
    overdue = db.query(Task).filter(
        Task.project_id == pid,
        Task.due_date < today,
        Task.status.notin_([TaskStatus.done, TaskStatus.archived, TaskStatus.recurring]),
    ).count()

    # Content
    published_this_week = db.query(ContentPiece).filter(
        ContentPiece.project_id == pid,
        ContentPiece.status == ContentStatus.published,
        ContentPiece.published_at >= datetime.combine(week_start, datetime.min.time()),
    ).count()

    # Automations
    total_autos = db.query(Automation).filter_by(project_id=pid).count()
    healthy_autos = db.query(Automation).filter_by(
        project_id=pid, health=AutomationHealth.running
    ).count()

    # Channels
    total_channels = db.query(Channel).filter_by(project_id=pid).count()
    live_channels = db.query(Channel).filter_by(
        project_id=pid, status=ChannelStatus.live
    ).count()

    return {
        "week_of": week_start.isoformat(),
        "execution_score": exec_score["total"],
        "score_color": exec_score["color"],
        "tasks": {"total": total_tasks, "done_this_week": done_this_week, "overdue": overdue},
        "content": {"published_this_week": published_this_week, "target": 3},
        "automations": {"total": total_autos, "healthy": healthy_autos},
        "channels": {"total": total_channels, "live": live_channels},
    }


def _generate_strategy_export(db: Session, pid: int, inputs: dict) -> dict:
    from app.routes.strategy_export import generate_strategy_markdown, EXPORT_PATH
    import os

    md = generate_strategy_markdown(db)
    if not md:
        return {"error": "No project found"}

    # Save to file
    os.makedirs(os.path.dirname(EXPORT_PATH), exist_ok=True)
    with open(EXPORT_PATH, "w") as f:
        f.write(md)

    word_count = len(md.split())
    return {
        "generated": True,
        "word_count": word_count,
        "saved_to": EXPORT_PATH,
        "preview": md[:500] + "...",
        "message": f"Strategy export generated ({word_count} words). Saved to {EXPORT_PATH}. You can also view it at /strategy-export or copy it from there.",
    }


def _track_entity(db: Session, pid: int, inputs: dict) -> dict:
    entity_type = inputs["entity_type"]
    name = inputs["name"]
    subtype = inputs.get("subtype", "")
    notes = inputs.get("notes", "")
    created_id = None
    entity_label = entity_type

    if entity_type == "channel":
        try:
            ch_type = ChannelType(subtype) if subtype else ChannelType.content
        except ValueError:
            ch_type = ChannelType.content
        item = Channel(project_id=pid, name=name, channel_type=ch_type, status=ChannelStatus.planned,
                       automation_level=AutomationLevel.manual, owner="phil", notes=notes)
        db.add(item)
        db.commit()
        created_id = item.id
        entity_label = "Channel"

    elif entity_type == "tool":
        try:
            cat = ToolCategory(subtype) if subtype else ToolCategory.dev_tools
        except ValueError:
            cat = ToolCategory.dev_tools
        item = Tool(project_id=pid, name=name, category=cat, status=ToolStatus.active,
                    purpose=inputs.get("purpose", ""), monthly_cost=inputs.get("monthly_cost", 0),
                    billing_cycle=BillingCycle.monthly, notes=notes)
        db.add(item)
        db.commit()
        created_id = item.id
        entity_label = "Tool"

    elif entity_type == "content":
        try:
            ct = ContentType(subtype) if subtype else ContentType.short_video
        except ValueError:
            ct = ContentType.short_video
        item = ContentPiece(project_id=pid, title=name, content_type=ct, status=ContentStatus.concept,
                            assigned_to="phil", notes=notes)
        db.add(item)
        db.commit()
        created_id = item.id
        entity_label = "Content"

    elif entity_type == "ad":
        try:
            platform = AdPlatform(subtype) if subtype else AdPlatform.meta
        except ValueError:
            platform = AdPlatform.meta
        ch = db.query(Channel).filter_by(project_id=pid, channel_type=ChannelType.paid_ads).first()
        if not ch:
            ch = Channel(project_id=pid, name=f"{platform.value.title()} Ads", channel_type=ChannelType.paid_ads, status=ChannelStatus.planned)
            db.add(ch)
            db.commit()
        item = AdCampaign(project_id=pid, channel_id=ch.id, platform=platform, campaign_name=name,
                          status=AdStatus.draft, objective=AdObjective.traffic, daily_budget=0,
                          start_date=date.today(), notes=notes)
        db.add(item)
        db.commit()
        created_id = item.id
        entity_label = "Ad Campaign"

    elif entity_type == "automation":
        try:
            at = AutomationType(subtype) if subtype else AutomationType.cron_job
        except ValueError:
            at = AutomationType.cron_job
        item = Automation(project_id=pid, name=name, automation_type=at, health=AutomationHealth.unknown,
                          health_check_method=HealthCheckMethod.manual_confirm, hosting=HostingLocation.mac_mini,
                          owner="phil", notes=notes)
        db.add(item)
        db.commit()
        created_id = item.id
        entity_label = "Automation"

    elif entity_type == "contact":
        try:
            ct = ContactType(subtype) if subtype else ContactType.influencer
        except ValueError:
            ct = ContactType.influencer
        item = OutreachContact(project_id=pid, name=name, platform=inputs.get("purpose", ""),
                               contact_type=ct, status=ContactStatus.identified, notes=notes)
        db.add(item)
        db.commit()
        created_id = item.id
        entity_label = "Contact"

    elif entity_type == "metric":
        # Need a channel - find first one or return error
        ch = db.query(Channel).filter_by(project_id=pid).first()
        if not ch:
            return {"error": "No channels exist to attach a metric to"}
        item = Metric(channel_id=ch.id, metric_name=name, metric_value=0, unit="count", source=MetricSource.manual)
        db.add(item)
        db.commit()
        created_id = item.id
        entity_label = "Metric"

    else:
        return {"error": f"Unknown entity type: {entity_type}"}

    # Create setup tasks if provided
    setup_tasks = inputs.get("setup_tasks", [])
    task_ids = []
    for task_title in setup_tasks:
        task = Task(project_id=pid, title=f"[Setup] {task_title}",
                    description=f"Setup task for {entity_label}: {name}",
                    status=TaskStatus.this_week, priority=TaskPriority.high, assigned_to="phil")
        db.add(task)
        db.commit()
        task_ids.append(task.id)

    return {
        "tracked": True,
        "entity_type": entity_label,
        "name": name,
        "id": created_id,
        "setup_task_ids": task_ids,
    }


def _stop_tracking(db: Session, pid: int, inputs: dict) -> dict:
    entity_type = inputs["entity_type"]
    name = inputs["name"]

    if entity_type == "channel":
        item = db.query(Channel).filter(Channel.project_id == pid, Channel.name.ilike(f"%{name}%")).first()
        if item:
            item.status = ChannelStatus.deprecated
            db.commit()
            return {"stopped": True, "entity": "Channel", "name": item.name}

    elif entity_type == "tool":
        item = db.query(Tool).filter(Tool.project_id == pid, Tool.name.ilike(f"%{name}%")).first()
        if item:
            item.status = ToolStatus.deprecated
            db.commit()
            return {"stopped": True, "entity": "Tool", "name": item.name}

    elif entity_type == "automation":
        item = db.query(Automation).filter(Automation.project_id == pid, Automation.name.ilike(f"%{name}%")).first()
        if item:
            item.health = AutomationHealth.paused
            db.commit()
            return {"stopped": True, "entity": "Automation", "name": item.name}

    elif entity_type == "ad":
        item = db.query(AdCampaign).filter(AdCampaign.project_id == pid, AdCampaign.campaign_name.ilike(f"%{name}%")).first()
        if item:
            item.status = AdStatus.paused
            db.commit()
            return {"stopped": True, "entity": "Ad Campaign", "name": item.campaign_name}

    return {"error": f"Could not find {entity_type} matching '{name}'"}


TOOL_HANDLERS = {
    "get_channel_metrics": _get_channel_metrics,
    "get_task_list": _get_task_list,
    "create_task": _create_task,
    "update_task": _update_task,
    "record_metric": _record_metric,
    "get_ad_campaigns": _get_ad_campaigns,
    "get_execution_score": _get_execution_score,
    "get_outreach_contacts": _get_outreach_contacts,
    "get_automations": _get_automations,
    "get_content_pipeline": _get_content_pipeline,
    "get_subscriber_funnel": _get_subscriber_funnel,
    "get_tech_stack": _get_tech_stack,
    "get_weekly_summary": _get_weekly_summary,
    "generate_strategy_export": _generate_strategy_export,
    "track_entity": _track_entity,
    "stop_tracking": _stop_tracking,
}
