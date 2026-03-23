from datetime import date, datetime
from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import (
    Project, Channel, Experiment,
    ExperimentTestType, ExperimentStatus, ExperimentWinner,
)

router = APIRouter(prefix="/experiments")
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def experiments_list(
    request: Request,
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("experiments.html", {
            "request": request, "project": None, "current_page": "experiments",
            "today": date.today(),
        })

    pid = project.id
    query = db.query(Experiment).filter_by(project_id=pid)
    if status:
        try:
            query = query.filter(Experiment.status == ExperimentStatus(status))
        except ValueError:
            pass

    experiments = query.order_by(Experiment.created_at.desc()).all()

    channels = db.query(Channel).filter_by(project_id=pid).all()
    channel_map = {c.id: c for c in channels}

    exp_data = []
    for exp in experiments:
        ch_name = channel_map[exp.channel_id].name if exp.channel_id and exp.channel_id in channel_map else "General"
        exp_data.append({"exp": exp, "channel_name": ch_name})

    # Stats
    total = len(experiments)
    running = sum(1 for e in experiments if e.status == ExperimentStatus.running)
    complete = sum(1 for e in experiments if e.status == ExperimentStatus.complete)

    return templates.TemplateResponse("experiments.html", {
        "request": request,
        "project": project,
        "exp_data": exp_data,
        "total": total,
        "running": running,
        "complete": complete,
        "channels": channels,
        "all_statuses": [(s.value, s.value.title()) for s in ExperimentStatus],
        "all_types": [(t.value, t.value.replace("_", " ").title()) for t in ExperimentTestType],
        "all_winners": [(w.value, w.value.title()) for w in ExperimentWinner],
        "filter_status": status or "",
        "current_page": "experiments",
        "today": date.today(),
    })


@router.get("/{exp_id}")
def experiment_detail(exp_id: int, request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    exp = db.get(Experiment, exp_id)
    if not exp:
        return HTMLResponse("Not found", status_code=404)

    channels = db.query(Channel).filter_by(project_id=project.id).all()
    channel_map = {c.id: c for c in channels}
    ch_name = channel_map[exp.channel_id].name if exp.channel_id and exp.channel_id in channel_map else "General"

    return templates.TemplateResponse("experiment_detail.html", {
        "request": request,
        "project": project,
        "exp": exp,
        "channel_name": ch_name,
        "all_statuses": [(s.value, s.value.title()) for s in ExperimentStatus],
        "all_winners": [(w.value, w.value.title()) for w in ExperimentWinner],
        "current_page": "experiments",
        "today": date.today(),
    })


@router.post("/create")
def create_experiment(
    hypothesis: str = Form(...),
    test_type: str = Form(...),
    variant_a: str = Form(""),
    variant_b: str = Form(""),
    success_metric: str = Form(""),
    channel_id: Optional[int] = Form(None),
    sample_target: Optional[int] = Form(None),
    duration_days: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("No project", status_code=400)

    exp = Experiment(
        project_id=project.id,
        hypothesis=hypothesis,
        test_type=ExperimentTestType(test_type),
        variant_a=variant_a,
        variant_b=variant_b,
        success_metric=success_metric,
        channel_id=channel_id if channel_id else None,
        sample_target=sample_target,
        duration_days=duration_days,
    )
    db.add(exp)
    db.commit()
    return RedirectResponse(url="/experiments/", status_code=303)


@router.post("/update/{exp_id}")
def update_experiment(
    exp_id: int,
    status: str = Form(...),
    winner: Optional[str] = Form(None),
    result_summary: str = Form(""),
    decision: str = Form(""),
    db: Session = Depends(get_db),
):
    exp = db.get(Experiment, exp_id)
    if not exp:
        return HTMLResponse("Not found", status_code=404)

    try:
        exp.status = ExperimentStatus(status)
    except ValueError:
        pass

    if winner:
        try:
            exp.winner = ExperimentWinner(winner)
        except ValueError:
            pass

    if result_summary:
        exp.result_summary = result_summary
    if decision:
        exp.decision = decision

    if status == "running" and not exp.started_at:
        exp.started_at = datetime.utcnow()
    if status == "complete" and not exp.completed_at:
        exp.completed_at = datetime.utcnow()

    db.commit()
    return RedirectResponse(url=f"/experiments/{exp_id}", status_code=303)


@router.post("/delete/{exp_id}")
def delete_experiment(exp_id: int, db: Session = Depends(get_db)):
    exp = db.get(Experiment, exp_id)
    if exp:
        db.delete(exp)
        db.commit()
    return RedirectResponse(url="/experiments/", status_code=303)
