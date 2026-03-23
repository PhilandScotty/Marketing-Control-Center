from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Metric, Channel, MetricSource

router = APIRouter(prefix="/metrics")
templates = Jinja2Templates(directory="app/templates")


@router.post("/record")
def record_metric(
    request: Request,
    channel_id: int = Form(...),
    metric_name: str = Form(...),
    metric_value: float = Form(...),
    unit: str = Form("count"),
    db: Session = Depends(get_db),
):
    # Find previous value for this metric
    prev = db.query(Metric).filter_by(
        channel_id=channel_id,
        metric_name=metric_name,
    ).order_by(Metric.recorded_at.desc()).first()

    metric = Metric(
        channel_id=channel_id,
        metric_name=metric_name,
        metric_value=metric_value,
        previous_value=prev.metric_value if prev else None,
        unit=unit,
        source=MetricSource.manual,
        recorded_at=datetime.utcnow(),
    )
    db.add(metric)
    db.commit()

    channel = db.query(Channel).get(channel_id)

    return templates.TemplateResponse("partials/metric_saved.html", {
        "request": request,
        "metric": metric,
        "channel": channel,
    })


@router.get("/form")
def metric_form(request: Request, db: Session = Depends(get_db)):
    """Return the metric entry form partial."""
    channels = db.query(Channel).all()
    return templates.TemplateResponse("partials/metric_form.html", {
        "request": request,
        "channels": channels,
    })
