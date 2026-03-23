from datetime import date, timedelta
from decimal import Decimal
from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from app.database import get_db
from app.models import (
    Project, Channel, ChannelType, ChannelStatus,
    BudgetLineItem, BudgetMonthEntry, MonthlyRevenue,
    BudgetCategory,
)

router = APIRouter(prefix="/budget")
templates = Jinja2Templates(directory="app/templates")


def _month_start(y: int, m: int) -> date:
    return date(y, m, 1)


def _prev_month(d: date) -> date:
    if d.month == 1:
        return date(d.year - 1, 12, 1)
    return date(d.year, d.month - 1, 1)


def _next_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _ensure_month(db: Session, project_id: int, month: date):
    """Auto-generate entries for a month from recurring line items if none exist."""
    existing = db.query(BudgetMonthEntry).join(BudgetLineItem).filter(
        BudgetLineItem.project_id == project_id,
        BudgetMonthEntry.month == month,
    ).count()
    if existing > 0:
        return

    items = db.query(BudgetLineItem).filter(
        BudgetLineItem.project_id == project_id,
        BudgetLineItem.first_month <= month,
        (BudgetLineItem.ended_month.is_(None)) | (BudgetLineItem.ended_month > month),
    ).order_by(BudgetLineItem.sort_order).all()

    prev = _prev_month(month)
    for item in items:
        # For recurring items, carry forward budgeted from previous month or use default
        prev_entry = db.query(BudgetMonthEntry).filter_by(
            line_item_id=item.id, month=prev
        ).first()
        if prev_entry:
            budgeted = prev_entry.budgeted
        else:
            budgeted = item.default_amount

        db.add(BudgetMonthEntry(
            line_item_id=item.id,
            month=month,
            budgeted=budgeted,
            actual=0,
        ))
    db.commit()


def _get_month_data(db: Session, project_id: int, month: date) -> dict:
    """Build complete budget data for a given month."""
    _ensure_month(db, project_id, month)

    items = db.query(BudgetLineItem).filter(
        BudgetLineItem.project_id == project_id,
    ).order_by(BudgetLineItem.sort_order).all()

    channels = db.query(Channel).filter_by(project_id=project_id).all()
    channel_map = {c.id: c for c in channels}

    rows = []
    total_budgeted = Decimal(0)
    total_actual = Decimal(0)

    for item in items:
        entry = db.query(BudgetMonthEntry).filter_by(
            line_item_id=item.id, month=month
        ).first()

        # Skip items not active this month (no entry = not applicable)
        if not entry:
            # Check if item should appear (active this month)
            if item.first_month <= month and (item.ended_month is None or item.ended_month > month):
                # Create entry on the fly
                budgeted = item.default_amount
                entry = BudgetMonthEntry(
                    line_item_id=item.id, month=month,
                    budgeted=budgeted, actual=0,
                )
                db.add(entry)
                db.commit()
            else:
                continue

        budgeted = float(entry.budgeted)
        actual = float(entry.actual)
        variance = budgeted - actual

        # Lifespan label
        if item.ended_month:
            lifespan = f"{item.first_month.strftime('%b %Y')}–{item.ended_month.strftime('%b %Y')} (ended)"
        else:
            lifespan = f"Since {item.first_month.strftime('%b %Y')}"

        rows.append({
            "item": item,
            "entry": entry,
            "budgeted": budgeted,
            "actual": actual,
            "variance": variance,
            "channel_name": channel_map[item.channel_id].name if item.channel_id and item.channel_id in channel_map else None,
            "lifespan": lifespan,
            "auto_filled": getattr(entry, 'auto_filled', False) or False,
        })
        total_budgeted += Decimal(str(budgeted))
        total_actual += Decimal(str(actual))

    revenue = db.query(MonthlyRevenue).filter_by(
        project_id=project_id, month=month
    ).first()

    return {
        "rows": rows,
        "total_budgeted": float(total_budgeted),
        "total_actual": float(total_actual),
        "total_variance": float(total_budgeted - total_actual),
        "revenue": revenue,
    }


def _get_budget_summary(db: Session, project_id: int) -> dict:
    """Summary data for dashboard widget."""
    today = date.today()
    month = _month_start(today.year, today.month)
    data = _get_month_data(db, project_id, month)

    monthly_budget = float(db.query(Project).get(project_id).monthly_budget or 10000)
    total_budget = monthly_budget  # overall budget reference

    total_actual = data["total_actual"]
    total_budgeted = data["total_budgeted"]

    # Burn rate
    days_elapsed = max((today - month).days, 1)
    daily_burn = round(total_actual / days_elapsed, 2)
    months_remaining = round((total_budget - total_actual) / max(total_actual, 1), 1) if total_actual > 0 else 99

    # Revenue
    rev = data["revenue"]
    mrr = float(rev.mrr) if rev else 0
    total_subs = rev.total_subscribers if rev else 0
    profitable = mrr >= total_actual if mrr > 0 else False
    cost_per_sub = round(total_actual / max(total_subs, 1), 2) if total_subs > 0 else 0

    # Over-budget flags
    over_budget_items = [r for r in data["rows"] if r["variance"] < 0 and r["budgeted"] > 0
                         and abs(r["variance"]) > r["budgeted"] * 0.2]

    return {
        "month": month,
        "total_budgeted": total_budgeted,
        "total_actual": total_actual,
        "daily_burn": daily_burn,
        "months_remaining": months_remaining,
        "mrr": mrr,
        "profitable": profitable,
        "cost_per_sub": cost_per_sub,
        "over_budget_items": over_budget_items,
        "pct_used": round(total_actual / max(total_budgeted, 1) * 100) if total_budgeted > 0 else 0,
    }


@router.get("/")
def budget_view(
    request: Request,
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("budget.html", {
            "request": request, "project": None, "current_page": "budget",
            "today": date.today(),
        })

    pid = project.id
    today = date.today()

    # Determine which month to show
    if year and month:
        current_month = _month_start(year, month)
    else:
        current_month = _month_start(today.year, today.month)

    data = _get_month_data(db, pid, current_month)

    # Prev month data for trend arrows
    prev_m = _prev_month(current_month)
    prev_data = _get_month_data(db, pid, prev_m)
    prev_actual_map = {r["item"].id: r["actual"] for r in prev_data["rows"]}

    # Add trend to current rows
    for row in data["rows"]:
        prev_val = prev_actual_map.get(row["item"].id)
        if prev_val is not None and prev_val > 0:
            row["trend"] = "up" if row["actual"] > prev_val else ("down" if row["actual"] < prev_val else "flat")
            row["trend_pct"] = round((row["actual"] - prev_val) / prev_val * 100)
        else:
            row["trend"] = None
            row["trend_pct"] = 0

    # Revenue
    revenue = data["revenue"]

    # Burn rate & runway
    total_budget_pool = float(project.monthly_budget or 10000)
    total_actual = data["total_actual"]
    total_budgeted = data["total_budgeted"]

    days_elapsed = max((today - current_month).days, 1)
    nm = _next_month(current_month)
    days_in_month = (nm - current_month).days
    days_remaining = max((nm - today).days, 0)
    daily_burn = round(total_actual / days_elapsed, 2) if days_elapsed > 0 else 0
    projected_total = round(total_actual + (daily_burn * days_remaining), 2)
    months_remaining = round(total_budget_pool / max(total_actual, 1), 1) if total_actual > 0 else 99

    # Revenue metrics
    mrr = float(revenue.mrr) if revenue else 0
    total_subs = revenue.total_subscribers if revenue else 0
    profitable = mrr >= total_actual
    cost_per_sub = round(total_actual / max(total_subs, 1), 2) if total_subs > 0 else 0

    # Chart data: last 6 months spend vs revenue trend
    chart_months = []
    chart_spend = []
    chart_revenue = []
    chart_cumulative_spend = []
    chart_cumulative_budget = []
    cumulative_s = 0
    cumulative_b = 0
    m = current_month
    for _ in range(5):
        m = _prev_month(m)
    for i in range(6):
        md = _get_month_data(db, pid, m)
        rev = db.query(MonthlyRevenue).filter_by(project_id=pid, month=m).first()
        chart_months.append(m.strftime("%b %y"))
        chart_spend.append(md["total_actual"])
        chart_revenue.append(float(rev.mrr) if rev else 0)
        cumulative_s += md["total_actual"]
        cumulative_b += md["total_budgeted"]
        chart_cumulative_spend.append(round(cumulative_s, 2))
        chart_cumulative_budget.append(round(cumulative_b, 2))
        m = _next_month(m)

    # Available months for selector
    first_item = db.query(BudgetLineItem).filter_by(project_id=pid).order_by(
        BudgetLineItem.first_month
    ).first()
    start_month = first_item.first_month if first_item else current_month
    available_months = []
    m = start_month
    end = _next_month(_month_start(today.year, today.month))
    while m <= end:
        available_months.append(m)
        m = _next_month(m)

    channels = db.query(Channel).filter_by(project_id=pid).all()

    # Build category list: enum values + custom categories from existing items
    categories = [(c.value, c.value.replace("_", " ").title()) for c in BudgetCategory if c != BudgetCategory.other]
    custom_cats = db.query(BudgetLineItem.custom_category_name).filter(
        BudgetLineItem.project_id == pid,
        BudgetLineItem.category == BudgetCategory.other,
        BudgetLineItem.custom_category_name.isnot(None),
    ).distinct().all()
    for (name,) in custom_cats:
        if name:
            categories.append((f"custom:{name}", name))

    return templates.TemplateResponse("budget.html", {
        "request": request,
        "project": project,
        "current_month": current_month,
        "prev_month": _prev_month(current_month),
        "next_month": _next_month(current_month),
        "available_months": available_months,
        "rows": data["rows"],
        "total_budgeted": total_budgeted,
        "total_actual": total_actual,
        "total_variance": data["total_variance"],
        "revenue": revenue,
        "mrr": mrr,
        "total_subs": total_subs,
        "profitable": profitable,
        "cost_per_sub": cost_per_sub,
        "daily_burn": daily_burn,
        "projected_total": projected_total,
        "months_remaining": months_remaining,
        "days_remaining": days_remaining,
        "chart_months": chart_months,
        "chart_spend": chart_spend,
        "chart_revenue": chart_revenue,
        "chart_cumulative_spend": chart_cumulative_spend,
        "chart_cumulative_budget": chart_cumulative_budget,
        "channels": channels,
        "categories": categories,
        "current_page": "budget",
        "today": today,
    })


@router.post("/update-actuals")
def update_actuals(request: Request, db: Session = Depends(get_db)):
    """Bulk update actual amounts for a month — the fast-edit form."""
    import asyncio
    loop = asyncio.get_event_loop()
    # We need to parse the form data manually since it's dynamic keys
    # FastAPI Form() doesn't support dynamic field names well
    return HTMLResponse("", status_code=200)


@router.post("/update-entry/{entry_id}")
def update_entry(
    entry_id: int,
    actual: str = Form("0"),
    budgeted: str = Form("0"),
    db: Session = Depends(get_db),
):
    """Update a single month entry's actual and/or budgeted amount."""
    entry = db.get(BudgetMonthEntry, entry_id)
    if not entry:
        return HTMLResponse("Not found", status_code=404)

    try:
        entry.actual = Decimal(actual.replace(",", "").replace("$", ""))
    except Exception:
        pass
    try:
        new_budgeted = Decimal(budgeted.replace(",", "").replace("$", ""))
        entry.budgeted = new_budgeted
        # Also update the line item's default for future months
        item = db.get(BudgetLineItem, entry.line_item_id)
        if item:
            item.default_amount = new_budgeted
    except Exception:
        pass

    db.commit()
    return HTMLResponse('<span class="text-[10px] text-mcc-success">Saved</span>')


@router.post("/add-item")
def add_line_item(
    name: str = Form(...),
    category: str = Form("tools_services"),
    budgeted: str = Form("0"),
    is_recurring: bool = Form(False),
    channel_id: Optional[int] = Form(None),
    month_year: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Add a new budget line item."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("No project", status_code=400)

    today = date.today()
    if month_year:
        parts = month_year.split("-")
        month = _month_start(int(parts[0]), int(parts[1]))
    else:
        month = _month_start(today.year, today.month)

    try:
        amount = Decimal(budgeted.replace(",", "").replace("$", ""))
    except Exception:
        amount = Decimal(0)

    max_sort = db.query(func.max(BudgetLineItem.sort_order)).filter_by(
        project_id=project.id
    ).scalar() or 0

    # Handle custom categories (prefixed with "custom:")
    if category.startswith("custom:"):
        cat_enum = BudgetCategory.other
        custom_cat_name = category[7:]  # strip "custom:" prefix
    else:
        try:
            cat_enum = BudgetCategory(category)
        except ValueError:
            cat_enum = BudgetCategory.other
        custom_cat_name = None

    item = BudgetLineItem(
        project_id=project.id,
        name=name,
        category=cat_enum,
        custom_category_name=custom_cat_name,
        channel_id=channel_id if channel_id and channel_id > 0 else None,
        is_recurring=is_recurring,
        default_amount=amount,
        first_month=month,
        sort_order=max_sort + 1,
    )
    db.add(item)
    db.flush()

    entry = BudgetMonthEntry(
        line_item_id=item.id,
        month=month,
        budgeted=amount,
        actual=0,
    )
    db.add(entry)
    db.commit()

    return HTMLResponse(
        f'<script>window.location.href="/budget?year={month.year}&month={month.month}"</script>'
    )


@router.post("/toggle-recurring/{item_id}")
def toggle_recurring(item_id: int, db: Session = Depends(get_db)):
    """Toggle recurring status on a line item."""
    item = db.get(BudgetLineItem, item_id)
    if not item:
        return HTMLResponse("Not found", status_code=404)

    if item.is_recurring:
        # Deactivate: set ended_month to next month
        today = date.today()
        item.is_recurring = False
        item.ended_month = _next_month(_month_start(today.year, today.month))
    else:
        item.is_recurring = True
        item.ended_month = None

    db.commit()
    return HTMLResponse('<span class="text-[10px] text-mcc-success">Updated</span>')


@router.post("/delete-item/{item_id}")
def delete_line_item(item_id: int, db: Session = Depends(get_db)):
    """Delete a line item and all its month entries."""
    item = db.get(BudgetLineItem, item_id)
    if not item:
        return HTMLResponse("Not found", status_code=404)
    db.query(BudgetMonthEntry).filter_by(line_item_id=item_id).delete()
    db.delete(item)
    db.commit()
    return HTMLResponse("")


@router.post("/update-revenue")
def update_revenue(
    month_year: str = Form(...),
    mrr: str = Form("0"),
    new_subscribers: int = Form(0),
    churned_subscribers: int = Form(0),
    total_subscribers: int = Form(0),
    db: Session = Depends(get_db),
):
    """Update revenue data for a month."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("No project", status_code=400)

    parts = month_year.split("-")
    month = _month_start(int(parts[0]), int(parts[1]))

    try:
        mrr_val = Decimal(mrr.replace(",", "").replace("$", ""))
    except Exception:
        mrr_val = Decimal(0)

    rev = db.query(MonthlyRevenue).filter_by(
        project_id=project.id, month=month
    ).first()

    if rev:
        rev.mrr = mrr_val
        rev.new_subscribers = new_subscribers
        rev.churned_subscribers = churned_subscribers
        rev.total_subscribers = total_subscribers
    else:
        rev = MonthlyRevenue(
            project_id=project.id,
            month=month,
            mrr=mrr_val,
            new_subscribers=new_subscribers,
            churned_subscribers=churned_subscribers,
            total_subscribers=total_subscribers,
        )
        db.add(rev)

    db.commit()
    return HTMLResponse('<span class="text-[10px] text-mcc-success">Saved</span>')


@router.post("/add-category")
def add_category(
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    """Add a custom budget category by creating a placeholder line item record.
    Returns an <option> element for the dropdown."""
    name = name.strip()
    if not name:
        return HTMLResponse("Name required", status_code=400)
    val = f"custom:{name}"
    return HTMLResponse(
        f'<option value="{val}" selected>{name}</option>'
    )


@router.post("/add-channel")
def add_channel(
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    """Create a new channel and return an <option> element."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("No project", status_code=400)

    name = name.strip()
    if not name:
        return HTMLResponse("Name required", status_code=400)

    channel = Channel(
        project_id=project.id,
        name=name,
        channel_type=ChannelType.partnerships,
        status=ChannelStatus.planned,
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    return HTMLResponse(
        f'<option value="{channel.id}" selected>{channel.name}</option>'
    )


@router.get("/compare")
def compare_view(
    request: Request,
    db: Session = Depends(get_db),
):
    """3-month comparison view."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("No project")

    today = date.today()
    months = []
    m = _month_start(today.year, today.month)
    for _ in range(3):
        months.insert(0, m)
        m = _prev_month(m)

    comparison = []
    # Get all items
    items = db.query(BudgetLineItem).filter_by(
        project_id=project.id
    ).order_by(BudgetLineItem.sort_order).all()

    totals = {mo: {"budgeted": 0, "actual": 0} for mo in months}

    for item in items:
        row = {"item": item, "months": {}}
        for mo in months:
            entry = db.query(BudgetMonthEntry).filter_by(
                line_item_id=item.id, month=mo
            ).first()
            if entry:
                b = float(entry.budgeted)
                a = float(entry.actual)
                row["months"][mo] = {"budgeted": b, "actual": a, "variance": b - a}
                totals[mo]["budgeted"] += b
                totals[mo]["actual"] += a
            else:
                row["months"][mo] = None
        # Only include if at least one month has data
        if any(row["months"][mo] is not None for mo in months):
            comparison.append(row)

    html_rows = []
    for row in comparison:
        cells = f'<td class="px-3 py-2 text-xs font-medium">{row["item"].name}</td>'
        prev_actual = None
        for mo in months:
            d = row["months"][mo]
            if d:
                var = d["variance"]
                var_class = "text-mcc-success" if var > 0 else ("text-mcc-critical" if var < 0 else "text-mcc-muted")
                # Trend
                trend = ""
                if prev_actual is not None and prev_actual > 0:
                    if d["actual"] > prev_actual:
                        trend = '<span class="text-mcc-critical ml-1">↑</span>'
                    elif d["actual"] < prev_actual:
                        trend = '<span class="text-mcc-success ml-1">↓</span>'
                prev_actual = d["actual"]
                cells += f'''<td class="px-2 py-2 text-xs font-mono text-center">${d["budgeted"]:,.0f}</td>
                <td class="px-2 py-2 text-xs font-mono text-center">${d["actual"]:,.0f}{trend}</td>
                <td class="px-2 py-2 text-xs font-mono text-center {var_class}">{("+" if var > 0 else "")}{var:,.0f}</td>'''
            else:
                prev_actual = None
                cells += '<td class="px-2 py-2 text-xs text-mcc-muted text-center">—</td>' * 3
        html_rows.append(f"<tr class='border-b border-mcc-border/30'>{cells}</tr>")

    # Totals row
    total_cells = '<td class="px-3 py-2 text-xs font-bold">TOTAL</td>'
    for mo in months:
        b = totals[mo]["budgeted"]
        a = totals[mo]["actual"]
        v = b - a
        vc = "text-mcc-success" if v > 0 else ("text-mcc-critical" if v < 0 else "text-mcc-muted")
        total_cells += f'''<td class="px-2 py-2 text-xs font-mono font-bold text-center">${b:,.0f}</td>
        <td class="px-2 py-2 text-xs font-mono font-bold text-center">${a:,.0f}</td>
        <td class="px-2 py-2 text-xs font-mono font-bold text-center {vc}">{("+" if v > 0 else "")}{v:,.0f}</td>'''

    # Header
    header = '<th class="px-3 py-2 text-[10px] text-mcc-muted text-left">Line Item</th>'
    for mo in months:
        header += f'''<th colspan="3" class="px-2 py-2 text-[10px] text-mcc-accent text-center border-l border-mcc-border/30">{mo.strftime("%b %Y")}</th>'''
    subheader = '<th></th>'
    for _ in months:
        subheader += '''<th class="px-2 py-1 text-[9px] text-mcc-muted text-center border-l border-mcc-border/30">Budget</th>
        <th class="px-2 py-1 text-[9px] text-mcc-muted text-center">Actual</th>
        <th class="px-2 py-1 text-[9px] text-mcc-muted text-center">+/-</th>'''

    # Cumulative totals
    cum_spend = sum(totals[mo]["actual"] for mo in months)
    cum_budget = sum(totals[mo]["budgeted"] for mo in months)

    return HTMLResponse(f'''
    <div class="bg-mcc-card rounded-lg border border-mcc-border p-4">
        <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold">3-Month Comparison</h3>
            <div class="text-xs text-mcc-muted">
                Cumulative: <span class="font-mono">${cum_spend:,.0f}</span> spent of <span class="font-mono">${cum_budget:,.0f}</span> budgeted
            </div>
        </div>
        <div class="overflow-x-auto">
            <table class="w-full">
                <thead>
                    <tr class="border-b border-mcc-border">{header}</tr>
                    <tr class="border-b border-mcc-border/50">{subheader}</tr>
                </thead>
                <tbody>
                    {"".join(html_rows)}
                    <tr class="border-t-2 border-mcc-border">{total_cells}</tr>
                </tbody>
            </table>
        </div>
    </div>
    ''')
