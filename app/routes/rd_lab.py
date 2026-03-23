"""R&D Lab — Strategic Brain command center in MCC.

Reads from / writes to the external rd_ideas.db managed by the nightly
Strategic Brain pipeline. Uses raw sqlite3 (not SQLAlchemy) to stay
decoupled from MCC's own ORM models.
"""
import json
import logging
import os
import sqlite3
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project, Task, TaskStatus, TaskPriority

logger = logging.getLogger("mcc.rd_lab")

router = APIRouter(prefix="/rd-lab")
templates = Jinja2Templates(directory="app/templates")

RD_DB_PATH = os.path.expanduser("~/clawd/projects/grindlab/rd_ideas.db")
RD_METRICS_PATH = os.path.expanduser("~/clawd/projects/grindlab/rd_metrics.json")
MODEL_STATS_PATH = os.path.expanduser("~/clawd/projects/grindlab/model_stats.json")
TASTE_PROFILE_PATH = os.path.expanduser("~/clawd/projects/grindlab/taste_profile.txt")

RATING_TAGS_POSITIVE = [
    "actionable", "novel", "high-leverage", "cheap", "compounds",
    "road-trip-fit", "brand-fit", "good-timing", "fills-gap",
    "low-risk", "scalable", "data-driven",
]
RATING_TAGS_NEGATIVE = [
    "vague", "expensive", "off-brand", "already-tried", "needs-dev",
    "wrong-audience", "boring", "too-slow", "bad-timing",
    "needs-scale", "generic-saas", "wrong-channel",
]
RATING_TAGS_NEUTRAL = [
    "needs-refinement", "revisit-later", "clint-required",
    "post-launch", "interesting-but",
]

AREA_LABELS = {
    "product": "Product",
    "growth": "Growth",
    "community": "Community",
    "partnerships": "Partnerships",
    "content": "Content",
    "wildcard": "Wildcard",
}

AREA_COLORS = {
    "product": "#8B5CF6",
    "growth": "#10B981",
    "community": "#F59E0B",
    "partnerships": "#06B6D4",
    "content": "#EC4899",
    "wildcard": "#EF4444",
}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_rd_db():
    """Get a sqlite3 connection to rd_ideas.db with row_factory."""
    conn = sqlite3.connect(RD_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _load_json_file(path: str, default=None):
    """Safely load a JSON file, returning default on failure."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def _load_text_file(path: str) -> str:
    """Safely load a text file."""
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return ""


def _save_json_file(path: str, data):
    """Save data as formatted JSON."""
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
def rd_lab_page(
    request: Request,
    tab: str = Query("brief"),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    conn = _get_rd_db()
    cur = conn.cursor()

    # --- Growth Model (latest snapshot) ---
    cur.execute("SELECT * FROM growth_snapshots ORDER BY snapshot_date DESC LIMIT 1")
    snapshot = cur.fetchone()

    # Historical snapshots for trajectory chart
    cur.execute(
        "SELECT snapshot_date, total_subscribers, monthly_growth_rate, projected_10k_date, mode "
        "FROM growth_snapshots ORDER BY snapshot_date ASC"
    )
    snapshot_history = [dict(r) for r in cur.fetchall()]

    # --- Tonight's Brief (latest run) ---
    cur.execute("SELECT * FROM run_log ORDER BY run_date DESC LIMIT 1")
    latest_run = cur.fetchone()

    tonight_ideas = []
    the_one_thing = None
    supporting = []
    if latest_run:
        run_date = latest_run["run_date"]
        # The One Thing
        if latest_run["the_one_thing_id"]:
            cur.execute("SELECT * FROM ideas WHERE id = ?", (latest_run["the_one_thing_id"],))
            the_one_thing = cur.fetchone()
        # Other ideas from same run date with run_rank
        cur.execute(
            "SELECT * FROM ideas WHERE date(created_at) = ? AND run_rank IS NOT NULL "
            "AND id != ? ORDER BY run_rank ASC",
            (run_date, latest_run["the_one_thing_id"] or 0),
        )
        supporting = [dict(r) for r in cur.fetchall()]

    # --- Unrated ideas ---
    cur.execute(
        "SELECT * FROM ideas WHERE phil_rating IS NULL AND status = 'proposed' "
        "ORDER BY created_at DESC"
    )
    unrated = [dict(r) for r in cur.fetchall()]

    # --- Testing ideas (outcomes tracker) ---
    cur.execute(
        "SELECT i.*, o.id as outcome_id FROM ideas i "
        "LEFT JOIN outcomes o ON o.idea_id = i.id "
        "WHERE i.status = 'testing' ORDER BY i.updated_at DESC"
    )
    testing = [dict(r) for r in cur.fetchall()]

    # --- Outcomes summary ---
    cur.execute(
        "SELECT COUNT(*) as total, "
        "AVG(cost_per_paid) as avg_cac, "
        "SUM(CASE WHEN outcome_rating >= 4 THEN 1 ELSE 0 END) as wins, "
        "SUM(CASE WHEN outcome_rating <= 2 THEN 1 ELSE 0 END) as losses, "
        "MIN(cost_per_paid) as best_cac, MAX(cost_per_paid) as worst_cac "
        "FROM outcomes WHERE outcome_rating IS NOT NULL"
    )
    outcome_summary = dict(cur.fetchone())
    total_outcomes = outcome_summary["total"] or 0
    outcome_summary["win_rate"] = (
        round(outcome_summary["wins"] / total_outcomes * 100)
        if total_outcomes > 0 else 0
    )

    # Completed outcomes with idea info
    cur.execute(
        "SELECT o.*, i.title as idea_title, i.area, i.source_model "
        "FROM outcomes o JOIN ideas i ON o.idea_id = i.id "
        "ORDER BY o.created_at DESC"
    )
    completed_outcomes = [dict(r) for r in cur.fetchall()]

    # --- Idea Archive ---
    cur.execute("SELECT * FROM ideas ORDER BY created_at DESC")
    all_ideas = [dict(r) for r in cur.fetchall()]

    # Archive filters
    statuses = sorted(set(i["status"] for i in all_ideas))
    areas = sorted(set(i["area"] for i in all_ideas))
    models = sorted(set(i["source_model"] for i in all_ideas if i["source_model"]))

    # --- Strategic Reviews ---
    cur.execute("SELECT * FROM strategic_reviews ORDER BY review_month DESC")
    reviews = [dict(r) for r in cur.fetchall()]

    # --- Intelligence: Model Stats ---
    model_stats = _load_json_file(MODEL_STATS_PATH, {})

    # --- Taste Profile ---
    taste_profile = _load_text_file(TASTE_PROFILE_PATH)
    cur.execute("SELECT * FROM taste_log ORDER BY generated_date DESC LIMIT 5")
    taste_history = [dict(r) for r in cur.fetchall()]

    # --- rd_metrics.json for Settings ---
    rd_metrics = _load_json_file(RD_METRICS_PATH, {})

    # --- Funnel from snapshot ---
    funnel_data = []
    if snapshot and snapshot["funnel_snapshot"]:
        try:
            funnel_data = json.loads(snapshot["funnel_snapshot"])
        except (json.JSONDecodeError, TypeError):
            pass

    # --- Self-awareness flags ---
    self_awareness = ""
    if snapshot and snapshot["self_awareness"]:
        self_awareness = snapshot["self_awareness"]

    # --- Channel targets from rd_metrics ---
    channel_targets = rd_metrics.get("growth_model", {}).get("channels", {})

    conn.close()

    return templates.TemplateResponse("rd_lab.html", {
        "request": request,
        "project": project,
        "current_page": "rd_lab",
        "today": date.today(),
        "tab": tab,
        # Growth Model
        "snapshot": dict(snapshot) if snapshot else None,
        "snapshot_history": snapshot_history,
        "funnel_data": funnel_data,
        "channel_targets": channel_targets,
        # Tonight's Brief
        "latest_run": dict(latest_run) if latest_run else None,
        "the_one_thing": dict(the_one_thing) if the_one_thing else None,
        "supporting": supporting,
        "self_awareness": self_awareness,
        # Rating
        "unrated": unrated,
        "rating_tags_positive": RATING_TAGS_POSITIVE,
        "rating_tags_negative": RATING_TAGS_NEGATIVE,
        "rating_tags_neutral": RATING_TAGS_NEUTRAL,
        # Outcomes
        "testing": testing,
        "outcome_summary": outcome_summary,
        "completed_outcomes": completed_outcomes,
        # Archive
        "all_ideas": all_ideas,
        "filter_statuses": statuses,
        "filter_areas": areas,
        "filter_models": models,
        "area_labels": AREA_LABELS,
        "area_colors": AREA_COLORS,
        # Reviews
        "reviews": reviews,
        # Intelligence
        "model_stats": model_stats,
        "taste_profile": taste_profile,
        "taste_history": taste_history,
        # Settings
        "rd_metrics": rd_metrics,
    })


# ---------------------------------------------------------------------------
# Rating endpoint
# ---------------------------------------------------------------------------

@router.post("/rate/{idea_id}", response_class=HTMLResponse)
def rate_idea(
    idea_id: int,
    phil_rating: int = Form(...),
    plan_quality: Optional[int] = Form(None),
    phil_notes: str = Form(""),
    rating_tags: str = Form(""),
):
    conn = _get_rd_db()
    cur = conn.cursor()
    status = "review"
    if phil_rating >= 4:
        status = "review"
    elif phil_rating <= 2:
        status = "discarded"
    cur.execute(
        "UPDATE ideas SET phil_rating = ?, plan_quality = ?, phil_notes = ?, "
        "rating_tags = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (phil_rating, plan_quality, phil_notes, rating_tags, status, idea_id),
    )
    conn.commit()
    conn.close()
    return HTMLResponse(
        '<div class="text-mcc-success text-xs py-1">Rated</div>',
        headers={"HX-Trigger": "ideaRated"},
    )


# ---------------------------------------------------------------------------
# Status update
# ---------------------------------------------------------------------------

@router.post("/status/{idea_id}", response_class=HTMLResponse)
def update_idea_status(idea_id: int, status: str = Form(...)):
    valid = {"proposed", "review", "testing", "completed", "discarded", "refined"}
    if status not in valid:
        return HTMLResponse('<span class="text-red-400 text-xs">Invalid status</span>')
    conn = _get_rd_db()
    conn.execute(
        "UPDATE ideas SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, idea_id),
    )
    conn.commit()
    conn.close()
    return HTMLResponse(
        f'<span class="text-mcc-success text-xs">→ {status}</span>',
        headers={"HX-Trigger": "ideaUpdated"},
    )


# ---------------------------------------------------------------------------
# Outcome entry
# ---------------------------------------------------------------------------

@router.post("/outcome/{idea_id}", response_class=HTMLResponse)
def record_outcome(
    idea_id: int,
    trials_generated: int = Form(0),
    paid_conversions: int = Form(0),
    cost_dollars: float = Form(0),
    time_invested_hours: float = Form(0),
    lesson: str = Form(""),
    outcome_rating: int = Form(3),
    should_repeat: int = Form(0),
    channel_attributed: str = Form(""),
):
    conn = _get_rd_db()
    cur = conn.cursor()

    # Compute cost metrics
    cost_per_trial = round(cost_dollars / trials_generated, 2) if trials_generated > 0 else None
    cost_per_paid = round(cost_dollars / paid_conversions, 2) if paid_conversions > 0 else None

    cur.execute(
        "INSERT INTO outcomes (idea_id, trials_generated, paid_conversions, cost_dollars, "
        "time_invested_hours, cost_per_trial, cost_per_paid, lesson, outcome_rating, "
        "should_repeat, channel_attributed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (idea_id, trials_generated, paid_conversions, cost_dollars,
         time_invested_hours, cost_per_trial, cost_per_paid, lesson,
         outcome_rating, should_repeat, channel_attributed),
    )
    # Mark idea as completed
    cur.execute(
        "UPDATE ideas SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (idea_id,),
    )
    conn.commit()
    conn.close()
    return HTMLResponse(
        '<div class="text-mcc-success text-xs py-1">Outcome recorded</div>',
        headers={"HX-Trigger": "outcomeRecorded"},
    )


# ---------------------------------------------------------------------------
# Approve to Task bridge
# ---------------------------------------------------------------------------

@router.post("/approve-task/{idea_id}", response_class=HTMLResponse)
def approve_to_task(idea_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse('<span class="text-red-400 text-xs">No project</span>')

    conn = _get_rd_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,))
    idea = cur.fetchone()
    if not idea:
        conn.close()
        return HTMLResponse('<span class="text-red-400 text-xs">Idea not found</span>')

    # Build task description from idea fields
    desc_parts = [idea["description"]]
    if idea["hypothesis"]:
        desc_parts.append(f"\nHypothesis: {idea['hypothesis']}")
    if idea["execution_plan"]:
        desc_parts.append(f"\nExecution Plan:\n{idea['execution_plan']}")
    if idea["metrics_to_watch"]:
        desc_parts.append(f"\nMetrics: {idea['metrics_to_watch']}")
    if idea["creative_brief"]:
        desc_parts.append(f"\nCreative Brief:\n{idea['creative_brief']}")

    task = Task(
        project_id=project.id,
        title=f"[R&D] {idea['title'][:150]}",
        description="\n".join(desc_parts),
        status=TaskStatus.backlog,
        priority=TaskPriority.medium,
        assigned_to="phil",
    )
    db.add(task)
    db.commit()

    # Mark idea as testing in rd_ideas.db
    cur.execute(
        "UPDATE ideas SET status = 'testing', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (idea_id,),
    )
    conn.commit()
    conn.close()

    return HTMLResponse(
        f'<span class="text-mcc-success text-xs">Task #{task.id} created</span>',
    )


# ---------------------------------------------------------------------------
# Settings — save rd_metrics.json sections
# ---------------------------------------------------------------------------

@router.post("/settings/metrics", response_class=HTMLResponse)
def save_metrics(
    kit_total: int = Form(0),
    kit_weekly_growth: int = Form(0),
    active_trials: int = Form(0),
    trial_starts_weekly: int = Form(0),
    total_paid_subscribers: int = Form(0),
    mrr: float = Form(0),
):
    data = _load_json_file(RD_METRICS_PATH, {})
    m = data.setdefault("metrics", {})
    m.setdefault("subscribers", {})["kit_total"] = kit_total
    m["subscribers"]["kit_weekly_growth"] = kit_weekly_growth
    m.setdefault("trials", {})["active_trials"] = active_trials
    m["trials"]["trial_starts_weekly"] = trial_starts_weekly
    m.setdefault("paid", {})["total_paid_subscribers"] = total_paid_subscribers
    m["paid"]["mrr"] = mrr
    data["last_updated"] = str(date.today())
    _save_json_file(RD_METRICS_PATH, data)
    return HTMLResponse('<span class="text-mcc-success text-xs">Metrics saved</span>')


@router.post("/settings/channels", response_class=HTMLResponse)
async def save_channel_targets(request: Request):
    form_data = await request.form()

    data = _load_json_file(RD_METRICS_PATH, {})
    gm = data.setdefault("growth_model", {})
    channels = gm.setdefault("channels", {})
    for key in channels:
        t = form_data.get(f"{key}_target")
        if t is not None:
            channels[key]["target_subscribers"] = int(t)
        c = form_data.get(f"{key}_current")
        if c is not None:
            channels[key]["current_subscribers"] = int(c)
        p = form_data.get(f"{key}_pace")
        if p is not None:
            channels[key]["current_monthly_pace"] = int(p)
    data["last_updated"] = str(date.today())
    _save_json_file(RD_METRICS_PATH, data)
    return HTMLResponse('<span class="text-mcc-success text-xs">Channel targets saved</span>')


@router.post("/settings/focus", response_class=HTMLResponse)
def save_focus(this_week_focus: str = Form("")):
    data = _load_json_file(RD_METRICS_PATH, {})
    data["this_week_focus"] = this_week_focus
    data["last_updated"] = str(date.today())
    _save_json_file(RD_METRICS_PATH, data)
    return HTMLResponse('<span class="text-mcc-success text-xs">Focus saved</span>')


@router.post("/settings/road-trip", response_class=HTMLResponse)
def save_road_trip(
    current_city: str = Form(""),
    current_room: str = Form(""),
    days_at_current: int = Form(0),
    next_stop: str = Form(""),
    next_stop_date: str = Form(""),
    rooms_visited_total: int = Form(0),
    contacts_made_total: int = Form(0),
    notes: str = Form(""),
):
    data = _load_json_file(RD_METRICS_PATH, {})
    rt = data.setdefault("road_trip", {})
    rt["current_city"] = current_city or None
    rt["current_room"] = current_room or None
    rt["days_at_current"] = days_at_current
    rt["next_stop"] = next_stop
    rt["next_stop_date"] = next_stop_date
    rt["rooms_visited_total"] = rooms_visited_total
    rt["contacts_made_total"] = contacts_made_total
    rt["notes"] = notes
    data["last_updated"] = str(date.today())
    _save_json_file(RD_METRICS_PATH, data)
    return HTMLResponse('<span class="text-mcc-success text-xs">Road trip saved</span>')


@router.post("/settings/outreach", response_class=HTMLResponse)
def save_outreach(
    influencer_pitches_sent: int = Form(0),
    influencer_responses: int = Form(0),
    influencer_deals_closed: int = Form(0),
    coach_pitches_sent: int = Form(0),
    coach_responses: int = Form(0),
    coach_deals_closed: int = Form(0),
):
    data = _load_json_file(RD_METRICS_PATH, {})
    op = data.setdefault("outreach_pipeline", {})
    op["influencer_pitches_sent"] = influencer_pitches_sent
    op["influencer_responses"] = influencer_responses
    op["influencer_deals_closed"] = influencer_deals_closed
    op["coach_pitches_sent"] = coach_pitches_sent
    op["coach_responses"] = coach_responses
    op["coach_deals_closed"] = coach_deals_closed
    data["last_updated"] = str(date.today())
    _save_json_file(RD_METRICS_PATH, data)
    return HTMLResponse('<span class="text-mcc-success text-xs">Outreach saved</span>')


# ---------------------------------------------------------------------------
# HTMX partials — idea detail expand
# ---------------------------------------------------------------------------

@router.get("/idea/{idea_id}", response_class=HTMLResponse)
def idea_detail(idea_id: int):
    conn = _get_rd_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,))
    idea = cur.fetchone()
    if not idea:
        conn.close()
        return HTMLResponse('<div class="text-red-400 text-xs p-2">Not found</div>')

    idea = dict(idea)

    # Get outcome if exists
    cur.execute("SELECT * FROM outcomes WHERE idea_id = ?", (idea_id,))
    outcome = cur.fetchone()
    conn.close()

    # Build detail HTML
    sections = []

    if idea.get("hypothesis"):
        sections.append(f'<div class="mb-2"><span class="text-mcc-muted text-[10px] uppercase tracking-wider">Hypothesis</span><p class="text-xs mt-0.5">{idea["hypothesis"]}</p></div>')

    if idea.get("evolution_trail"):
        sections.append(f'<div class="mb-2"><span class="text-mcc-muted text-[10px] uppercase tracking-wider">Evolution</span><p class="text-xs mt-0.5 whitespace-pre-wrap">{idea["evolution_trail"]}</p></div>')

    if idea.get("execution_plan"):
        sections.append(f'<div class="mb-2"><span class="text-mcc-muted text-[10px] uppercase tracking-wider">Execution Plan</span><p class="text-xs mt-0.5 whitespace-pre-wrap">{idea["execution_plan"]}</p></div>')

    if idea.get("creative_brief"):
        sections.append(f'<div class="mb-2"><span class="text-mcc-muted text-[10px] uppercase tracking-wider">Creative Brief</span><p class="text-xs mt-0.5 whitespace-pre-wrap">{idea["creative_brief"]}</p></div>')

    if idea.get("content_pipeline"):
        sections.append(f'<div class="mb-2"><span class="text-mcc-muted text-[10px] uppercase tracking-wider">Content Pipeline</span><p class="text-xs mt-0.5 whitespace-pre-wrap">{idea["content_pipeline"]}</p></div>')

    if idea.get("metrics_to_watch"):
        sections.append(f'<div class="mb-2"><span class="text-mcc-muted text-[10px] uppercase tracking-wider">Metrics to Watch</span><p class="text-xs mt-0.5">{idea["metrics_to_watch"]}</p></div>')

    if idea.get("phil_notes"):
        sections.append(f'<div class="mb-2"><span class="text-mcc-muted text-[10px] uppercase tracking-wider">Phil\'s Notes</span><p class="text-xs mt-0.5">{idea["phil_notes"]}</p></div>')

    if outcome:
        outcome = dict(outcome)
        sections.append(
            f'<div class="mb-2 p-2 rounded bg-mcc-surface border border-mcc-border">'
            f'<span class="text-mcc-muted text-[10px] uppercase tracking-wider">Outcome</span>'
            f'<div class="grid grid-cols-4 gap-2 mt-1 text-xs">'
            f'<div><span class="text-mcc-muted">Trials:</span> {outcome["trials_generated"]}</div>'
            f'<div><span class="text-mcc-muted">Paid:</span> {outcome["paid_conversions"]}</div>'
            f'<div><span class="text-mcc-muted">Cost:</span> ${outcome["cost_dollars"]:.0f}</div>'
            f'<div><span class="text-mcc-muted">Rating:</span> {outcome["outcome_rating"]}/5</div>'
            f'</div>'
            f'<p class="text-xs mt-1">{outcome["lesson"]}</p>'
            f'</div>'
        )

    html = f'<div class="px-3 py-2 space-y-1 border-t border-mcc-border/50 bg-mcc-bg/50">{"".join(sections)}</div>'
    return HTMLResponse(html)
