from datetime import date, datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from app.database import get_db
from app.models import (
    Project, Channel, AdCampaign, AdBrief, Metric, ContentPiece,
    ProjectStrategy, BudgetLineItem, BudgetMonthEntry, BudgetCategory,
    AdPlatform, AdStatus, AdSignal, AdObjective,
    StrategySection, ContentStatus,
)

router = APIRouter(prefix="/ads")
templates = Jinja2Templates(directory="app/templates")

DEFAULT_CPL_TARGET = 10.0

# Map ad platforms to channel name patterns
PLATFORM_CHANNEL_MAP = {
    "reddit": ["Reddit"],
    "meta": ["Instagram", "Facebook"],
    "youtube": ["YouTube"],
    "x_twitter": ["X/Twitter", "Twitter"],
    "google": ["Google"],
    "tiktok": ["TikTok"],
}


def _calc_signal(ad: AdCampaign, cpl_target: float = DEFAULT_CPL_TARGET) -> tuple:
    """Calculate ad signal per spec Section 4.7 rules."""
    spend = float(ad.spend_to_date or 0)
    impressions = ad.impressions or 0
    clicks = ad.clicks or 0
    conversions = ad.conversions or 0
    total_budget = float(ad.total_budget or 0)
    cpl = float(ad.cpl or 0)
    ctr = float(ad.ctr or 0)

    if impressions < 100 or spend < 10:
        return AdSignal.hold, "Insufficient data (need 100+ impressions and $10+ spend)"

    conv_rate = (conversions / clicks * 100) if clicks > 0 else 0
    budget_pct = (spend / total_budget * 100) if total_budget > 0 else 0

    if (budget_pct > 50 and conversions == 0) or (cpl > cpl_target * 3 and conversions > 0):
        reason = []
        if budget_pct > 50 and conversions == 0:
            reason.append(f"Spent {budget_pct:.0f}% of budget with 0 conversions")
        if cpl > cpl_target * 3 and conversions > 0:
            reason.append(f"CPL ${cpl:.2f} is {cpl/cpl_target:.1f}x target")
        return AdSignal.kill, ". ".join(reason)

    if (cpl > cpl_target * 2 and conversions > 0) or ctr < 0.5 or (conv_rate < 1 and clicks > 10):
        reason = []
        if cpl > cpl_target * 2 and conversions > 0:
            reason.append(f"CPL ${cpl:.2f} is {cpl/cpl_target:.1f}x target")
        if ctr < 0.5:
            reason.append(f"CTR {ctr:.2f}% below 0.5% floor")
        if conv_rate < 1 and clicks > 10:
            reason.append(f"Conv rate {conv_rate:.1f}% below 1% threshold")
        return AdSignal.pause, ". ".join(reason)

    if cpl > cpl_target and cpl <= cpl_target * 1.4:
        return AdSignal.optimize, f"CPL ${cpl:.2f} above target but within 40% — optimize"

    if cpl < cpl_target and conv_rate > 1 and budget_pct < 50:
        return AdSignal.scale, f"CPL ${cpl:.2f} under target, {conv_rate:.1f}% conv rate, {budget_pct:.0f}% budget used"

    return AdSignal.hold, f"CPL ${cpl:.2f} within acceptable range"


def _get_top_organic_posts(db: Session, pid: int, platform: str, limit: int = 5) -> list[dict]:
    """Get top-performing organic content for a platform by engagement metrics."""
    channel_names = PLATFORM_CHANNEL_MAP.get(platform, [])
    if not channel_names:
        return []

    channels = db.query(Channel).filter(
        Channel.project_id == pid,
        Channel.name.in_(channel_names),
    ).all()

    if not channels:
        return []

    results = []
    for ch in channels:
        metrics = db.query(Metric).filter(
            Metric.channel_id == ch.id,
        ).order_by(Metric.metric_value.desc()).limit(limit * 2).all()

        for m in metrics:
            results.append({
                "channel": ch.name,
                "metric": m.metric_name,
                "value": float(m.metric_value),
                "unit": m.unit or "count",
                "date": m.recorded_at.strftime("%b %d") if m.recorded_at else "",
            })

    # Also check published content targeting this platform
    pieces = db.query(ContentPiece).filter(
        ContentPiece.project_id == pid,
        ContentPiece.status == ContentStatus.published,
    ).order_by(ContentPiece.published_at.desc()).limit(20).all()

    for p in pieces:
        targets = p.platform_target or []
        platform_match = any(
            pname.lower() in (t.lower() for t in targets)
            for pname in channel_names
        )
        if platform_match and p.performance:
            perf = p.performance if isinstance(p.performance, dict) else {}
            results.append({
                "channel": "Content",
                "metric": p.title[:60],
                "value": perf.get("engagement", perf.get("views", 0)),
                "unit": "engagement",
                "date": p.published_at.strftime("%b %d") if p.published_at else "",
                "is_content": True,
                "title": p.title,
                "script": p.script_source or "",
            })

    results.sort(key=lambda x: x["value"], reverse=True)
    return results[:limit]


def _get_customer_profile(db: Session, pid: int) -> str:
    """Pull customer profile from strategy."""
    strat = db.query(ProjectStrategy).filter_by(
        project_id=pid, section=StrategySection.customer,
    ).first()
    return strat.content if strat and strat.content else ""


def _get_ad_budget(db: Session, pid: int, platform: str) -> dict:
    """Get available budget from Budget Tracker for paid advertising."""
    month = date.today().replace(day=1)
    items = db.query(BudgetLineItem).filter(
        BudgetLineItem.project_id == pid,
        BudgetLineItem.category == BudgetCategory.paid_advertising,
    ).all()

    total_budgeted = Decimal("0")
    total_spent = Decimal("0")
    for item in items:
        entry = db.query(BudgetMonthEntry).filter_by(
            line_item_id=item.id, month=month,
        ).first()
        if entry:
            total_budgeted += entry.budgeted or Decimal("0")
            total_spent += entry.actual or Decimal("0")

    return {
        "budgeted": float(total_budgeted),
        "spent": float(total_spent),
        "available": float(total_budgeted - total_spent),
    }


@router.get("/")
def ads_dashboard(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("ads.html", {
            "request": request, "project": None, "current_page": "ads",
            "today": date.today(),
        })

    pid = project.id

    # --- Campaign Tracker (existing) ---
    campaigns = db.query(AdCampaign).filter_by(project_id=pid).order_by(
        AdCampaign.status, AdCampaign.start_date.desc()
    ).all()

    channels = db.query(Channel).filter_by(project_id=pid).all()
    channel_map = {c.id: c for c in channels}

    ad_data = []
    for ad in campaigns:
        signal, reason = _calc_signal(ad)
        if ad.signal != signal:
            ad.signal = signal
            ad.signal_reason = reason

        # Pacing indicator
        pacing = "on_track"
        if ad.total_budget and float(ad.total_budget) > 0 and ad.start_date:
            days_total = (ad.end_date - ad.start_date).days if ad.end_date else 30
            days_elapsed = max((date.today() - ad.start_date).days, 1)
            expected_pct = (days_elapsed / max(days_total, 1)) * 100
            actual_pct = (float(ad.spend_to_date or 0) / float(ad.total_budget)) * 100
            if actual_pct > expected_pct * 1.2:
                pacing = "overspending"
            elif actual_pct < expected_pct * 0.5:
                pacing = "underspending"

        # CPA vs target
        cpa_status = "ok"
        if ad.cpl and float(ad.cpl) > DEFAULT_CPL_TARGET * 1.5:
            cpa_status = "high"
        elif ad.cpl and float(ad.cpl) < DEFAULT_CPL_TARGET:
            cpa_status = "good"

        ad_data.append({
            "ad": ad,
            "channel_name": channel_map.get(ad.channel_id, type('', (), {'name': 'Unknown'})).name,
            "signal": signal,
            "reason": reason,
            "pacing": pacing,
            "cpa_status": cpa_status,
        })
    db.commit()

    # Summary stats
    active_ads = [a for a in campaigns if a.status == AdStatus.active]
    total_daily = sum(float(a.daily_budget or 0) for a in active_ads)
    total_conversions = sum(a.conversions or 0 for a in active_ads)
    total_spend = sum(float(a.spend_to_date or 0) for a in campaigns)
    blended_cpl = round(total_spend / total_conversions, 2) if total_conversions > 0 else 0

    if active_ads:
        earliest = min(a.start_date for a in active_ads)
        days_elapsed = max((date.today() - earliest).days, 1)
        burn_rate = round(total_spend / days_elapsed, 2)
    else:
        burn_rate = 0

    # --- Saved Briefs ---
    briefs = db.query(AdBrief).filter_by(project_id=pid).order_by(
        AdBrief.created_at.desc()
    ).all()

    # Budget line items for linking
    budget_items = db.query(BudgetLineItem).filter(
        BudgetLineItem.project_id == pid,
        BudgetLineItem.category == BudgetCategory.paid_advertising,
    ).all()

    return templates.TemplateResponse("ads.html", {
        "request": request,
        "project": project,
        "ad_data": ad_data,
        "total_daily": total_daily,
        "total_conversions": total_conversions,
        "total_spend": total_spend,
        "blended_cpl": blended_cpl,
        "burn_rate": burn_rate,
        "active_count": len(active_ads),
        "briefs": briefs,
        "budget_items": budget_items,
        "platforms": [(p.value, p.value.replace("_", " ").title()) for p in AdPlatform],
        "channels": channels,
        "channel_map": channel_map,
        "current_page": "ads",
        "today": date.today(),
    })


@router.get("/prepare/{platform}", response_class=HTMLResponse)
def prepare_campaign(platform: str, request: Request, db: Session = Depends(get_db)):
    """Load campaign preparation data for a specific platform."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse('<div class="text-red-400">No project</div>')

    pid = project.id

    top_posts = _get_top_organic_posts(db, pid, platform)
    customer_profile = _get_customer_profile(db, pid)
    ad_budget = _get_ad_budget(db, pid, platform)

    platform_label = platform.replace("_", " ").title()

    budget_items = db.query(BudgetLineItem).filter(
        BudgetLineItem.project_id == pid,
        BudgetLineItem.category == BudgetCategory.paid_advertising,
    ).all()

    return templates.TemplateResponse("partials/ad_brief_form.html", {
        "request": request,
        "platform": platform,
        "platform_label": platform_label,
        "top_posts": top_posts,
        "customer_profile": customer_profile,
        "ad_budget": ad_budget,
        "budget_items": budget_items,
    })


@router.post("/brief/save", response_class=HTMLResponse)
def save_brief(
    request: Request,
    db: Session = Depends(get_db),
    platform: str = Form(...),
    title: str = Form(...),
    creative_text: str = Form(""),
    targeting_notes: str = Form(""),
    recommended_budget: float = Form(0),
    suggested_duration_days: int = Form(14),
    budget_line_item_id: Optional[int] = Form(None),
    notes: str = Form(""),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse('<span class="text-red-400">No project</span>')

    brief = AdBrief(
        project_id=project.id,
        platform=AdPlatform(platform),
        title=title,
        creative_text=creative_text,
        targeting_notes=targeting_notes,
        recommended_budget=Decimal(str(recommended_budget)),
        suggested_duration_days=suggested_duration_days,
        budget_line_item_id=budget_line_item_id if budget_line_item_id else None,
        notes=notes,
    )
    db.add(brief)
    db.commit()

    return HTMLResponse(
        f'<div class="text-mcc-success text-xs py-2">'
        f'Brief saved! <a href="/ads" class="text-mcc-accent hover:underline">Back to Ads</a></div>'
    )


@router.post("/campaign/add", response_class=HTMLResponse)
def add_campaign(
    request: Request,
    db: Session = Depends(get_db),
    campaign_name: str = Form(...),
    platform: str = Form(...),
    channel_id: int = Form(0),
    objective: str = Form("traffic"),
    daily_budget: float = Form(0),
    total_budget: float = Form(0),
    start_date: str = Form(...),
    end_date: str = Form(""),
    creative_notes: str = Form(""),
    notes: str = Form(""),
):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse('<span class="text-red-400">No project</span>')

    campaign = AdCampaign(
        project_id=project.id,
        channel_id=channel_id if channel_id else None,
        platform=AdPlatform(platform),
        campaign_name=campaign_name,
        objective=AdObjective(objective),
        daily_budget=Decimal(str(daily_budget)),
        total_budget=Decimal(str(total_budget)) if total_budget else None,
        start_date=date.fromisoformat(start_date),
        end_date=date.fromisoformat(end_date) if end_date else None,
        creative_notes=creative_notes,
        notes=notes,
        status=AdStatus.active,
    )
    db.add(campaign)
    db.commit()

    return HTMLResponse(
        '<div class="text-mcc-success text-xs py-2">'
        'Campaign added! <a href="/ads" class="text-mcc-accent hover:underline">Refresh</a></div>',
        headers={"HX-Redirect": "/ads"},
    )


@router.post("/campaign/{campaign_id}/update", response_class=HTMLResponse)
def update_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    spend_to_date: Optional[float] = Form(None),
    impressions: Optional[int] = Form(None),
    clicks: Optional[int] = Form(None),
    conversions: Optional[int] = Form(None),
    cpl: Optional[float] = Form(None),
    status: Optional[str] = Form(None),
):
    campaign = db.get(AdCampaign, campaign_id)
    if not campaign:
        return HTMLResponse('<span class="text-red-400">Not found</span>')

    if spend_to_date is not None:
        campaign.spend_to_date = Decimal(str(spend_to_date))
    if impressions is not None:
        campaign.impressions = impressions
    if clicks is not None:
        campaign.clicks = clicks
    if conversions is not None:
        campaign.conversions = conversions
    if cpl is not None:
        campaign.cpl = Decimal(str(cpl))
    if status:
        campaign.status = AdStatus(status)

    # Recalculate CTR
    if campaign.impressions and campaign.clicks:
        campaign.ctr = Decimal(str(round(campaign.clicks / campaign.impressions * 100, 2)))

    # Recalculate CPL if not provided
    if cpl is None and campaign.conversions and campaign.spend_to_date:
        campaign.cpl = Decimal(str(round(float(campaign.spend_to_date) / campaign.conversions, 2)))

    db.commit()
    return HTMLResponse('<span class="text-mcc-success text-xs">Updated</span>')
