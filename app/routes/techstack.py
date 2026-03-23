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
    Project, Tool, ToolCategory, ToolStatus, BillingCycle,
    BudgetLineItem, BudgetMonthEntry, BudgetCategory,
)

router = APIRouter(prefix="/techstack")
templates = Jinja2Templates(directory="app/templates")


def _month_start(y: int, m: int) -> date:
    return date(y, m, 1)


def _get_project(db: Session):
    return db.query(Project).filter_by(slug="grindlab").first()


def _budget_item_for_tool(db: Session, tool_id: int) -> BudgetLineItem | None:
    """Find the budget line item linked to a tech stack tool."""
    return db.query(BudgetLineItem).filter_by(tool_id=tool_id).first()


def _sync_budget_create(db: Session, project_id: int, tool: Tool):
    """Create a budget line item for a new tech stack tool (0 as placeholder if no cost)."""
    cost = float(tool.monthly_cost or 0)

    today = date.today()
    month = _month_start(today.year, today.month)

    max_sort = db.query(func.max(BudgetLineItem.sort_order)).filter_by(
        project_id=project_id
    ).scalar() or 0

    item = BudgetLineItem(
        project_id=project_id,
        name=tool.name,
        category=BudgetCategory.tools_services,
        tool_id=tool.id,
        is_recurring=True,
        default_amount=Decimal(str(cost)),
        first_month=month,
        sort_order=max_sort + 1,
    )
    db.add(item)
    db.flush()

    entry = BudgetMonthEntry(
        line_item_id=item.id,
        month=month,
        budgeted=Decimal(str(cost)),
        actual=0,
    )
    db.add(entry)


def _sync_budget_update(db: Session, tool: Tool):
    """Update the linked budget line item when a tool's cost changes."""
    item = _budget_item_for_tool(db, tool.id)
    new_cost = Decimal(str(float(tool.monthly_cost or 0)))

    if item is None:
        # Tool had no budget entry — create one (0 as placeholder if no cost)
        project = db.get(Project, tool.project_id)
        if project:
            _sync_budget_create(db, project.id, tool)
        return

    # Update name in case tool was renamed
    item.name = tool.name
    item.default_amount = new_cost

    # Update current and future month entries
    today = date.today()
    current_month = _month_start(today.year, today.month)
    entries = db.query(BudgetMonthEntry).filter(
        BudgetMonthEntry.line_item_id == item.id,
        BudgetMonthEntry.month >= current_month,
    ).all()
    for entry in entries:
        entry.budgeted = new_cost

    # If no entry for current month, create one
    if not any(e.month == current_month for e in entries):
        db.add(BudgetMonthEntry(
            line_item_id=item.id,
            month=current_month,
            budgeted=new_cost,
            actual=0,
        ))

    # Re-activate if previously ended
    if item.ended_month:
        item.ended_month = None
        item.is_recurring = True


def _sync_budget_deactivate(db: Session, tool_id: int):
    """Deactivate (not delete) the budget line item when a tool is removed."""
    item = _budget_item_for_tool(db, tool_id)
    if item:
        today = date.today()
        next_month = _month_start(today.year, today.month)
        if today.month == 12:
            next_month = _month_start(today.year + 1, 1)
        else:
            next_month = _month_start(today.year, today.month + 1)
        item.ended_month = next_month
        item.is_recurring = False


def _build_budget_link_map(db: Session, project_id: int) -> dict[int, int]:
    """Return {tool_id: budget_line_item_id} for tools with active budget links."""
    items = db.query(BudgetLineItem).filter(
        BudgetLineItem.project_id == project_id,
        BudgetLineItem.tool_id.isnot(None),
    ).all()
    return {item.tool_id: item.id for item in items if item.ended_month is None}


@router.get("/")
def techstack_view(request: Request, db: Session = Depends(get_db)):
    project = _get_project(db)
    if not project:
        return templates.TemplateResponse("techstack.html", {
            "request": request, "project": None, "current_page": "techstack",
            "today": date.today(),
        })

    pid = project.id
    today = date.today()
    tools = db.query(Tool).filter_by(project_id=pid).order_by(Tool.category, Tool.name).all()

    # Group by category
    by_category = {}
    for t in tools:
        cat = t.category.value
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(t)

    # Monthly cost total (active tools only)
    active_tools = [t for t in tools if t.status == ToolStatus.active]
    monthly_total = sum(float(t.monthly_cost or 0) for t in active_tools)

    # Gap flags: categories with no active tool
    all_categories = set(c.value for c in ToolCategory)
    active_categories = set(t.category.value for t in active_tools)
    gap_categories = all_categories - active_categories

    # Redundancy flags: categories with multiple active tools
    redundant_categories = []
    for cat, cat_tools in by_category.items():
        active_in_cat = [t for t in cat_tools if t.status == ToolStatus.active]
        if len(active_in_cat) > 1:
            redundant_categories.append({
                "category": cat,
                "tools": active_in_cat,
                "count": len(active_in_cat),
            })

    # Review reminders: not reviewed in 60+ days
    review_cutoff = today - timedelta(days=60)
    needs_review = [t for t in tools if t.last_reviewed and t.last_reviewed < review_cutoff]

    # Tools being evaluated
    evaluating = [t for t in tools if t.status == ToolStatus.evaluating]

    # Budget link map
    budget_links = _build_budget_link_map(db, pid)

    return templates.TemplateResponse("techstack.html", {
        "request": request,
        "project": project,
        "by_category": by_category,
        "monthly_total": monthly_total,
        "active_count": len(active_tools),
        "total_count": len(tools),
        "gap_categories": sorted(gap_categories),
        "redundant_categories": redundant_categories,
        "needs_review": needs_review,
        "evaluating": evaluating,
        "budget_links": budget_links,
        "category_labels": {c.value: c.value.replace("_", " ").title() for c in ToolCategory},
        "categories": [(c.value, c.value.replace("_", " ").title()) for c in ToolCategory],
        "statuses": [(s.value, s.value.capitalize()) for s in ToolStatus],
        "billing_cycles": [(b.value, b.value.replace("_", " ").title()) for b in BillingCycle],
        "current_page": "techstack",
        "today": today,
    })


@router.post("/add")
def add_tool(
    name: str = Form(...),
    category: str = Form("analytics"),
    purpose: str = Form(""),
    monthly_cost: str = Form("0"),
    billing_cycle: str = Form("monthly"),
    status: str = Form("active"),
    db: Session = Depends(get_db),
):
    project = _get_project(db)
    if not project:
        return HTMLResponse("No project", status_code=400)

    try:
        cost = Decimal(monthly_cost.replace(",", "").replace("$", ""))
    except Exception:
        cost = Decimal(0)

    try:
        cat = ToolCategory(category)
    except ValueError:
        cat = ToolCategory.analytics

    try:
        bc = BillingCycle(billing_cycle)
    except ValueError:
        bc = BillingCycle.monthly

    try:
        st = ToolStatus(status)
    except ValueError:
        st = ToolStatus.active

    tool = Tool(
        project_id=project.id,
        name=name,
        category=cat,
        purpose=purpose,
        monthly_cost=cost,
        billing_cycle=bc,
        status=st,
        last_reviewed=date.today(),
    )
    db.add(tool)
    db.flush()  # Get the tool.id

    # Budget sync: always create budget entry for active tools (0 as placeholder if no cost)
    if st == ToolStatus.active:
        _sync_budget_create(db, project.id, tool)

    db.commit()

    return HTMLResponse(
        f'<script>window.location.href="/techstack"</script>'
    )


@router.get("/{tool_id}/edit")
def edit_tool_form(tool_id: int, request: Request, db: Session = Depends(get_db)):
    tool = db.get(Tool, tool_id)
    if not tool:
        return HTMLResponse("Not found", status_code=404)

    budget_item = _budget_item_for_tool(db, tool_id)

    return templates.TemplateResponse("partials/techstack_edit_modal.html", {
        "request": request,
        "tool": tool,
        "budget_item": budget_item,
        "categories": [(c.value, c.value.replace("_", " ").title()) for c in ToolCategory],
        "statuses": [(s.value, s.value.capitalize()) for s in ToolStatus],
        "billing_cycles": [(b.value, b.value.replace("_", " ").title()) for b in BillingCycle],
    })


@router.post("/{tool_id}/update")
def update_tool(
    tool_id: int,
    name: str = Form(...),
    category: str = Form("analytics"),
    purpose: str = Form(""),
    monthly_cost: str = Form("0"),
    billing_cycle: str = Form("monthly"),
    status: str = Form("active"),
    db: Session = Depends(get_db),
):
    tool = db.get(Tool, tool_id)
    if not tool:
        return HTMLResponse("Not found", status_code=404)

    try:
        cost = Decimal(monthly_cost.replace(",", "").replace("$", ""))
    except Exception:
        cost = Decimal(0)

    old_status = tool.status
    old_cost = float(tool.monthly_cost or 0)

    tool.name = name
    try:
        tool.category = ToolCategory(category)
    except ValueError:
        pass
    tool.purpose = purpose
    tool.monthly_cost = cost
    try:
        tool.billing_cycle = BillingCycle(billing_cycle)
    except ValueError:
        pass
    try:
        tool.status = ToolStatus(status)
    except ValueError:
        pass
    tool.last_reviewed = date.today()

    # Budget sync logic
    new_status = tool.status
    new_cost = float(cost)

    if new_status == ToolStatus.active:
        # Active tool — sync budget
        _sync_budget_update(db, tool)
    elif old_status == ToolStatus.active and new_status != ToolStatus.active:
        # Tool was deactivated — deactivate budget
        _sync_budget_deactivate(db, tool_id)

    db.commit()

    return HTMLResponse(
        '<script>window.location.href="/techstack"</script>'
    )


@router.post("/{tool_id}/remove")
def remove_tool(tool_id: int, db: Session = Depends(get_db)):
    """Soft-remove: set status to deprecated and deactivate budget entry."""
    tool = db.get(Tool, tool_id)
    if not tool:
        return HTMLResponse("Not found", status_code=404)

    tool.status = ToolStatus.deprecated
    _sync_budget_deactivate(db, tool_id)
    db.commit()

    return HTMLResponse(
        '<script>window.location.href="/techstack"</script>'
    )


@router.post("/{tool_id}/delete")
def delete_tool(tool_id: int, db: Session = Depends(get_db)):
    """Hard delete a tool (only for tools with no budget history)."""
    tool = db.get(Tool, tool_id)
    if not tool:
        return HTMLResponse("Not found", status_code=404)

    # If there's a budget link, deactivate rather than delete
    budget_item = _budget_item_for_tool(db, tool_id)
    if budget_item:
        _sync_budget_deactivate(db, tool_id)
        tool.status = ToolStatus.deprecated
    else:
        db.delete(tool)

    db.commit()
    return HTMLResponse(
        '<script>window.location.href="/techstack"</script>'
    )
