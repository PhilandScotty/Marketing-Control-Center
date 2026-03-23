#!/usr/bin/env python3
"""MCC management commands."""
import sys
from datetime import date, datetime
from decimal import Decimal

from app.database import get_db, init_db
from app.models import (
    Project, Channel, Task, TaskStatus, Automation, AutomationHealth,
    EmailSequence, SubscriberSnapshot, AdCampaign, AIInsight,
    AutonomousTool,
    Tool, ContentPiece, OutreachContact, Competitor, CompetitorUpdate,
    OnboardingMilestone, BudgetAllocation, BudgetExpense, Experiment,
    KnowledgeEntry, ProjectStrategy, Metric, CustomerFeedback,
)
from app.routes.dashboard import calc_execution_score


def get_status_data():
    """Gather full project status from the database."""
    init_db()
    db = next(get_db())
    try:
        project = db.query(Project).filter_by(slug="grindlab").first()
        if not project:
            return None

        pid = project.id
        today = date.today()

        exec_score = calc_execution_score(db, pid)

        channels = db.query(Channel).filter_by(project_id=pid).all()
        tasks = db.query(Task).filter_by(project_id=pid).all()
        automations = db.query(Automation).filter_by(project_id=pid).all()
        sequences = db.query(EmailSequence).filter_by(project_id=pid).all()
        campaigns = db.query(AdCampaign).filter_by(project_id=pid).all()

        overdue = [
            t for t in tasks
            if t.due_date and t.due_date < today
            and t.status not in (TaskStatus.done, TaskStatus.archived, TaskStatus.recurring)
        ]
        overdue.sort(key=lambda t: t.due_date)

        latest_snapshot = db.query(SubscriberSnapshot).filter_by(
            project_id=pid
        ).order_by(SubscriberSnapshot.snapshot_date.desc()).first()

        insights = db.query(AIInsight).filter(
            AIInsight.project_id == pid,
            AIInsight.acknowledged == False,
        ).order_by(AIInsight.created_at.desc()).limit(10).all()

        connected_tools = db.query(AutonomousTool).filter_by(
            project_id=pid, is_active=True
        ).all()

        task_counts = {}
        for t in tasks:
            s = t.status.value
            task_counts[s] = task_counts.get(s, 0) + 1

        return {
            "project": project,
            "today": today,
            "exec_score": exec_score,
            "channels": channels,
            "tasks": tasks,
            "task_counts": task_counts,
            "overdue": overdue,
            "automations": automations,
            "sequences": sequences,
            "campaigns": campaigns,
            "subscriber_count": latest_snapshot.total_count if latest_snapshot else 0,
            "insights": insights,
            "connected_tools": connected_tools,
        }
    finally:
        db.close()


def render_markdown(data):
    """Render project status as a human-readable markdown document."""
    p = data["project"]
    today = data["today"]
    score = data["exec_score"]
    days_to_launch = (p.launch_date - today).days if p.launch_date else "?"

    lines = []
    lines.append(f"# {p.name} — MCC Status Report")
    lines.append(f"")
    lines.append(f"**Generated:** {today.strftime('%B %d, %Y')} at {datetime.now().strftime('%I:%M %p')}")
    if p.launch_date:
        lines.append(f"**Launch Date:** {p.launch_date.strftime('%B %d, %Y')} (T-{days_to_launch} days)")
    lines.append("")

    # Execution Score
    lines.append("---")
    lines.append("")
    lines.append(f"## Execution Score: {score['total']}/100")
    lines.append("")
    lines.append("| Component | Score | Weight |")
    lines.append("|-----------|-------|--------|")
    for key, comp in score["components"].items():
        bar = "+" * (comp["score"] // 10) + "-" * (10 - comp["score"] // 10)
        lines.append(f"| {key.title()} | {comp['score']} [{bar}] | {comp['weight']}% |")
    lines.append("")

    # Overdue Tasks
    if data["overdue"]:
        lines.append("## Overdue Tasks")
        lines.append("")
        for t in data["overdue"]:
            days = (today - t.due_date).days
            lines.append(f"- **{t.title}** — {days}d overdue (due {t.due_date.strftime('%b %d')}, {t.priority.value}, {t.assigned_to or 'unassigned'})")
        lines.append("")
    else:
        lines.append("## Overdue Tasks")
        lines.append("")
        lines.append("None — all caught up.")
        lines.append("")

    # Task Summary
    lines.append("## Tasks")
    lines.append("")
    lines.append(f"**Total:** {len(data['tasks'])}")
    lines.append("")
    for status, count in sorted(data["task_counts"].items()):
        lines.append(f"- {status.replace('_', ' ').title()}: {count}")
    lines.append("")

    # Channel Health
    lines.append("## Channel Health")
    lines.append("")
    lines.append("| Channel | Status | Health | Automation |")
    lines.append("|---------|--------|--------|------------|")
    for ch in data["channels"]:
        health_icon = {"healthy": "OK", "warning": "WARN", "critical": "CRIT", "stale": "STALE"}.get(
            ch.health.value if ch.health else "unknown", "?"
        )
        lines.append(f"| {ch.name} | {ch.status.value if ch.status else '?'} | {health_icon} | {ch.automation_level.value if ch.automation_level else '?'} |")
    lines.append("")

    # Automations
    lines.append("## Automations")
    lines.append("")
    healthy = sum(1 for a in data["automations"] if a.health == AutomationHealth.running)
    stale = sum(1 for a in data["automations"] if a.health == AutomationHealth.stale)
    failed = sum(1 for a in data["automations"] if a.health == AutomationHealth.failed)
    lines.append(f"**{len(data['automations'])} total** — {healthy} running, {stale} stale, {failed} failed")
    lines.append("")
    problem_autos = [a for a in data["automations"] if a.health in (AutomationHealth.stale, AutomationHealth.failed)]
    if problem_autos:
        for a in problem_autos:
            lines.append(f"- **{a.name}** ({a.platform}) — {a.health.value}")
        lines.append("")

    # Subscribers
    lines.append("## Subscribers")
    lines.append("")
    lines.append(f"**Total:** {data['subscriber_count']}")
    lines.append("")

    # Email Sequences
    lines.append("## Email Sequences")
    lines.append("")
    for s in data["sequences"]:
        lines.append(f"- {s.name}: {s.status.value} ({s.email_count} emails)")
    lines.append("")

    # Ad Campaigns
    if data["campaigns"]:
        lines.append("## Ad Campaigns")
        lines.append("")
        lines.append("| Campaign | Platform | Status | Signal | Spend | Conversions |")
        lines.append("|----------|----------|--------|--------|-------|-------------|")
        for c in data["campaigns"]:
            lines.append(
                f"| {c.campaign_name} | {c.platform.value} | {c.status.value} | "
                f"{c.signal.value if c.signal else 'hold'} | ${float(c.spend_to_date or 0):.2f} | {c.conversions or 0} |"
            )
        lines.append("")

    # Connected Tools
    if data.get("connected_tools"):
        lines.append("## Connected Tools")
        lines.append("")
        from datetime import datetime as _dt
        now = _dt.utcnow()
        for t in data["connected_tools"]:
            hours_ago = ""
            if t.last_heartbeat:
                h = round((now - t.last_heartbeat).total_seconds() / 3600, 1)
                hours_ago = f" — last heartbeat {h}h ago"
            lines.append(f"- **{t.name}** ({t.platform}) — {t.health.value}{hours_ago}")
        lines.append("")

    # AI Insights
    if data["insights"]:
        lines.append("## AI Insights (Unacknowledged)")
        lines.append("")
        for i in data["insights"]:
            severity_tag = i.severity.value.upper()
            lines.append(f"- [{severity_tag}] **{i.title}**")
            if i.body:
                body_preview = i.body[:150].replace("\n", " ")
                lines.append(f"  {body_preview}")
        lines.append("")

    lines.append("---")
    lines.append(f"*Generated by Marketing Command Center — localhost:5050*")

    return "\n".join(lines)


def cmd_export_status():
    """Export project status as markdown to stdout."""
    data = get_status_data()
    if not data:
        print("Error: No project found.", file=sys.stderr)
        sys.exit(1)
    print(render_markdown(data))


def _py_repr(val):
    """Convert a Python value to its repr for seed file generation."""
    import enum as _enum
    if val is None:
        return "None"
    if isinstance(val, bool):
        return repr(val)
    if isinstance(val, _enum.Enum):
        return f"{type(val).__name__}.{val.name}"
    if isinstance(val, (int, float)):
        return repr(val)
    if isinstance(val, Decimal):
        return str(val)
    if isinstance(val, str):
        return repr(val)
    if isinstance(val, datetime):
        return f"datetime({val.year}, {val.month}, {val.day}, {val.hour}, {val.minute}, {val.second})"
    if isinstance(val, date):
        return f"date({val.year}, {val.month}, {val.day})"
    if isinstance(val, (list, dict)):
        return repr(val)
    return repr(val)


def _export_model_rows(db, model_class, project_id, indent="    ", fk_field="project_id"):
    """Generate seed code for all rows of a model belonging to a project."""
    rows = db.query(model_class).filter(
        getattr(model_class, fk_field) == project_id
    ).all()
    if not rows:
        return []

    table_name = model_class.__tablename__
    class_name = model_class.__name__

    # Get column names, skip id and project_id
    skip_cols = {"id", "project_id", "created_at", "updated_at"}
    columns = [c.name for c in model_class.__table__.columns if c.name not in skip_cols]

    lines = []
    lines.append(f"{indent}# --- {class_name} ({len(rows)}) ---")
    lines.append(f"{indent}{table_name}_data = [")
    for row in rows:
        fields = {}
        for col in columns:
            val = getattr(row, col)
            if val is not None:
                fields[col] = _py_repr(val)
        field_strs = [f'"{k}": {v}' for k, v in fields.items()]
        lines.append(f"{indent}    {{{', '.join(field_strs)}}},")
    lines.append(f"{indent}]")
    lines.append(f"{indent}for d in {table_name}_data:")
    lines.append(f"{indent}    db.add({class_name}(project_id=pid, **d))")
    lines.append("")
    return lines


def cmd_export_seed(project_slug):
    """Export a project's current state as a seed file."""
    init_db()
    db = next(get_db())
    try:
        project = db.query(Project).filter_by(slug=project_slug).first()
        if not project:
            print(f"Error: Project '{project_slug}' not found.", file=sys.stderr)
            sys.exit(1)

        pid = project.id

        # Collect all enum types used
        enum_imports = set()

        lines = []
        lines.append(f'"""Seed file for {project.name} — auto-exported from MCC."""')
        lines.append("import uuid")
        lines.append("from datetime import date, datetime")

        # We'll fill imports after scanning
        import_placeholder_idx = len(lines)
        lines.append("")  # placeholder for imports
        lines.append("")
        lines.append("")

        # seed function
        func_name = f"seed_{project_slug}"
        lines.append(f"def {func_name}(db):")
        lines.append(f'    existing = db.query(Project).filter_by(slug="{project_slug}").first()')
        lines.append("    if existing:")
        lines.append("        return")
        lines.append("")

        # Project
        proj_fields = {
            "name": repr(project.name),
            "slug": repr(project.slug),
            "status": repr(project.status.value) if project.status else repr("active"),
        }
        if project.launch_date:
            proj_fields["launch_date"] = _py_repr(project.launch_date)
        if project.monthly_budget:
            proj_fields["monthly_budget"] = str(project.monthly_budget)
        if project.notes:
            proj_fields["notes"] = repr(project.notes)

        lines.append("    project = Project(")
        for k, v in proj_fields.items():
            lines.append(f"        {k}={v},")
        lines.append("    )")
        lines.append("    db.add(project)")
        lines.append("    db.flush()")
        lines.append("    pid = project.id")
        lines.append("")

        # Export each model type
        model_groups = [
            Channel, Tool, Task, Automation, EmailSequence, AdCampaign,
            ContentPiece, OutreachContact, Competitor, OnboardingMilestone,
            BudgetAllocation, BudgetExpense, Experiment, KnowledgeEntry,
            ProjectStrategy, CustomerFeedback, AutonomousTool,
        ]

        for model_cls in model_groups:
            # Check if model has project_id column
            if not hasattr(model_cls, "project_id"):
                continue
            model_lines = _export_model_rows(db, model_cls, pid)
            if model_lines:
                lines.extend(model_lines)
                # Scan for enum references
                for ml in model_lines:
                    for word in ml.split():
                        if "." in word and word[0].isupper():
                            enum_name = word.split(".")[0].rstrip(",(){}\"'")
                            if enum_name and enum_name[0].isupper():
                                enum_imports.add(enum_name)

        lines.append("    db.commit()")
        lines.append("")

        # Build the import line
        # Always need Project
        all_model_names = {"Project"}
        for model_cls in model_groups:
            if hasattr(model_cls, "project_id"):
                rows = db.query(model_cls).filter_by(project_id=pid).count()
                if rows > 0:
                    all_model_names.add(model_cls.__name__)

        all_imports = sorted(all_model_names | enum_imports)
        import_line = f"from app.models import (\n    {', '.join(all_imports)},\n)"
        lines[import_placeholder_idx] = import_line

        print("\n".join(lines))

    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python manage.py <command>")
        print("Commands:")
        print("  export-status                     Output project status as markdown")
        print("  export-seed --project <slug>      Export project as a seed file")
        sys.exit(1)

    command = sys.argv[1]

    if command == "export-status":
        cmd_export_status()
    elif command == "export-seed":
        if "--project" in sys.argv:
            idx = sys.argv.index("--project")
            if idx + 1 < len(sys.argv):
                cmd_export_seed(sys.argv[idx + 1])
            else:
                print("Error: --project requires a slug argument", file=sys.stderr)
                sys.exit(1)
        else:
            print("Error: export-seed requires --project <slug>", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)
