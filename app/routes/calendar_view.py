from datetime import date, timedelta, datetime
from calendar import monthrange
from fastapi import APIRouter, Request, Depends, Query
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import (
    Project, Task, ContentPiece, EmailSequence, AdCampaign,
    TaskStatus, TaskPriority, ContentStatus, SequenceStatus, AdStatus,
)

router = APIRouter(prefix="/calendar")
templates = Jinja2Templates(directory="app/templates")

EVENT_COLORS = {
    "task": "#06B6D4",
    "content": "#164E63",
    "email": "#F59E0B",
    "ad": "#10B981",
    "milestone": "#6B6B8A",
}


@router.get("/")
def calendar_view(
    request: Request,
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    view: str = Query("month"),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("calendar.html", {
            "request": request, "project": None, "current_page": "calendar",
            "today": date.today(),
        })

    pid = project.id
    today = date.today()
    cal_year = year or today.year
    cal_month = month or today.month

    if view == "week":
        # Week view: show current week
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        range_start = week_start
        range_end = week_end
    else:
        # Month view
        _, days_in_month = monthrange(cal_year, cal_month)
        range_start = date(cal_year, cal_month, 1)
        range_end = date(cal_year, cal_month, days_in_month)

    # Collect events
    events = []

    # Launch-critical tasks with due dates
    tasks = db.query(Task).filter(
        Task.project_id == pid,
        Task.due_date >= range_start,
        Task.due_date <= range_end,
        Task.priority == TaskPriority.launch_critical,
    ).all()
    for t in tasks:
        events.append({
            "date": t.due_date,
            "title": t.title,
            "type": "task",
            "color": EVENT_COLORS["task"],
            "detail": f"Due: {t.assigned_to} | {t.priority.value.replace('_', ' ').title()}",
            "status": t.status.value,
        })

    # Content pieces with due dates or published dates
    content = db.query(ContentPiece).filter(
        ContentPiece.project_id == pid,
    ).all()
    for c in content:
        d = None
        if c.published_at and range_start <= c.published_at.date() <= range_end:
            d = c.published_at.date()
        elif c.due_date and range_start <= c.due_date <= range_end:
            d = c.due_date
        if d:
            events.append({
                "date": d,
                "title": c.title,
                "type": "content",
                "color": EVENT_COLORS["content"],
                "detail": f"{c.content_type.value.replace('_', ' ').title()} | {c.status.value.title()}",
                "status": c.status.value,
            })

    # Email sequences (show ones being built or recently reviewed)
    sequences = db.query(EmailSequence).filter(
        EmailSequence.project_id == pid,
        EmailSequence.last_reviewed >= range_start,
        EmailSequence.last_reviewed <= range_end,
    ).all()
    for s in sequences:
        if s.last_reviewed:
            events.append({
                "date": s.last_reviewed,
                "title": s.name,
                "type": "email",
                "color": EVENT_COLORS["email"],
                "detail": f"{s.email_count} emails | {s.status.value.replace('_', ' ').title()}",
                "status": s.status.value,
            })

    # Ad campaigns
    ads = db.query(AdCampaign).filter(
        AdCampaign.project_id == pid,
    ).all()
    for a in ads:
        if a.start_date and range_start <= a.start_date <= range_end:
            events.append({
                "date": a.start_date,
                "title": f"{a.campaign_name} (start)",
                "type": "ad",
                "color": EVENT_COLORS["ad"],
                "detail": f"{a.platform.value.title()} | Budget: ${a.daily_budget}/day",
                "status": a.status.value,
            })
        if a.end_date and range_start <= a.end_date <= range_end:
            events.append({
                "date": a.end_date,
                "title": f"{a.campaign_name} (end)",
                "type": "ad",
                "color": EVENT_COLORS["ad"],
                "detail": f"{a.platform.value.title()} | Spent: ${a.spend_to_date}",
                "status": a.status.value,
            })

    # Launch date as milestone
    if project.launch_date and range_start <= project.launch_date <= range_end:
        events.append({
            "date": project.launch_date,
            "title": "LAUNCH DAY",
            "type": "milestone",
            "color": EVENT_COLORS["milestone"],
            "detail": f"{project.name} launches!",
            "status": "launch",
        })

    # Group events by date
    events_by_date = {}
    for e in events:
        d = e["date"]
        if d not in events_by_date:
            events_by_date[d] = []
        events_by_date[d].append(e)

    # Build calendar grid (for month view)
    cal_grid = []
    if view == "month":
        first_day = date(cal_year, cal_month, 1)
        start_weekday = first_day.weekday()  # 0=Mon
        _, days_in_month = monthrange(cal_year, cal_month)

        # Pad with previous month days
        grid_start = first_day - timedelta(days=start_weekday)
        # 6 weeks to cover all months
        for week in range(6):
            row = []
            for day in range(7):
                d = grid_start + timedelta(days=week * 7 + day)
                row.append({
                    "date": d,
                    "day": d.day,
                    "in_month": d.month == cal_month,
                    "is_today": d == today,
                    "events": events_by_date.get(d, []),
                })
            cal_grid.append(row)
            # Stop if we've passed the month
            if row[-1]["date"].month != cal_month and week >= 4:
                break
    else:
        # Week view: single row
        row = []
        for day in range(7):
            d = range_start + timedelta(days=day)
            row.append({
                "date": d,
                "day": d.day,
                "in_month": True,
                "is_today": d == today,
                "events": events_by_date.get(d, []),
            })
        cal_grid.append(row)

    # Navigation
    if cal_month == 1:
        prev_year, prev_month = cal_year - 1, 12
    else:
        prev_year, prev_month = cal_year, cal_month - 1
    if cal_month == 12:
        next_year, next_month = cal_year + 1, 1
    else:
        next_year, next_month = cal_year, cal_month + 1

    month_name = date(cal_year, cal_month, 1).strftime("%B %Y")

    return templates.TemplateResponse("calendar.html", {
        "request": request,
        "project": project,
        "cal_grid": cal_grid,
        "month_name": month_name,
        "cal_year": cal_year,
        "cal_month": cal_month,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
        "view": view,
        "event_colors": EVENT_COLORS,
        "total_events": len(events),
        "current_page": "calendar",
        "today": today,
    })
