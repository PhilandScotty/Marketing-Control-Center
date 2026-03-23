"""GA4 analytics queries for the Website page — traffic, pages, sources, UTMs, real-time."""
import logging
from datetime import date, timedelta
from app.config import GA4_CREDENTIALS_PATH, GA4_PROPERTY_ID
from app.integrations.ga4 import GA4Integration

logger = logging.getLogger("mcc.integrations.ga4_analytics")

GA4_DATA_API = "https://analyticsdata.googleapis.com/v1beta"


def is_ga4_configured() -> bool:
    return bool(GA4_CREDENTIALS_PATH and GA4_PROPERTY_ID)


async def _get_client():
    """Return authenticated GA4Integration instance or None."""
    client = GA4Integration()
    if not client.is_configured():
        return None
    connected = await client.connect()
    if not connected:
        return None
    return client


async def _run_report(client: GA4Integration, body: dict) -> dict:
    property_id = GA4_PROPERTY_ID
    url = f"{GA4_DATA_API}/properties/{property_id}:runReport"
    headers = {"Authorization": f"Bearer {client._access_token}"}
    resp = await client._request("POST", url, headers=headers, json=body)
    return resp.json()


async def _run_realtime_report(client: GA4Integration, body: dict) -> dict:
    property_id = GA4_PROPERTY_ID
    url = f"{GA4_DATA_API}/properties/{property_id}:runRealtimeReport"
    headers = {"Authorization": f"Bearer {client._access_token}"}
    resp = await client._request("POST", url, headers=headers, json=body)
    return resp.json()


async def fetch_traffic_overview() -> dict | None:
    """Section 1: Traffic overview — visitors today/week/month, sources, landing pages, bounce rate."""
    client = await _get_client()
    if not client:
        return None

    result = {}
    try:
        today = date.today()

        # -- Visitors today --
        data = await _run_report(client, {
            "dateRanges": [{"startDate": "today", "endDate": "today"}],
            "metrics": [
                {"name": "activeUsers"},
                {"name": "newUsers"},
                {"name": "sessions"},
                {"name": "bounceRate"},
            ],
        })
        rows = data.get("rows", [])
        if rows:
            vals = rows[0].get("metricValues", [])
            result["visitors_today"] = int(float(vals[0]["value"])) if len(vals) > 0 else 0
            result["new_users_today"] = int(float(vals[1]["value"])) if len(vals) > 1 else 0
            result["sessions_today"] = int(float(vals[2]["value"])) if len(vals) > 2 else 0
            result["bounce_rate_today"] = round(float(vals[3]["value"]) * 100, 1) if len(vals) > 3 else 0
        else:
            result["visitors_today"] = 0
            result["new_users_today"] = 0
            result["sessions_today"] = 0
            result["bounce_rate_today"] = 0

        # -- Visitors yesterday (for trend) --
        yesterday = today - timedelta(days=1)
        data = await _run_report(client, {
            "dateRanges": [{"startDate": yesterday.isoformat(), "endDate": yesterday.isoformat()}],
            "metrics": [{"name": "activeUsers"}],
        })
        rows = data.get("rows", [])
        result["visitors_yesterday"] = int(float(rows[0]["metricValues"][0]["value"])) if rows else 0

        # -- Visitors this week --
        week_start = today - timedelta(days=today.weekday())
        data = await _run_report(client, {
            "dateRanges": [{"startDate": week_start.isoformat(), "endDate": "today"}],
            "metrics": [{"name": "activeUsers"}, {"name": "newUsers"}],
        })
        rows = data.get("rows", [])
        if rows:
            vals = rows[0].get("metricValues", [])
            result["visitors_week"] = int(float(vals[0]["value"])) if len(vals) > 0 else 0
            result["new_users_week"] = int(float(vals[1]["value"])) if len(vals) > 1 else 0
        else:
            result["visitors_week"] = 0
            result["new_users_week"] = 0

        # -- Visitors this month --
        month_start = today.replace(day=1)
        data = await _run_report(client, {
            "dateRanges": [{"startDate": month_start.isoformat(), "endDate": "today"}],
            "metrics": [{"name": "activeUsers"}, {"name": "newUsers"}],
        })
        rows = data.get("rows", [])
        if rows:
            vals = rows[0].get("metricValues", [])
            result["visitors_month"] = int(float(vals[0]["value"])) if len(vals) > 0 else 0
            result["new_users_month"] = int(float(vals[1]["value"])) if len(vals) > 1 else 0
        else:
            result["visitors_month"] = 0
            result["new_users_month"] = 0

        result["returning_today"] = max(0, result["visitors_today"] - result["new_users_today"])

        # -- Top traffic sources --
        data = await _run_report(client, {
            "dateRanges": [{"startDate": "30daysAgo", "endDate": "today"}],
            "dimensions": [{"name": "sessionDefaultChannelGroup"}],
            "metrics": [{"name": "sessions"}],
            "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
            "limit": 10,
        })
        total_sessions = 0
        sources = []
        for row in data.get("rows", []):
            name = row["dimensionValues"][0]["value"]
            sessions = int(float(row["metricValues"][0]["value"]))
            total_sessions += sessions
            sources.append({"name": name, "sessions": sessions})
        for s in sources:
            s["pct"] = round((s["sessions"] / total_sessions * 100), 1) if total_sessions else 0
        result["traffic_sources"] = sources

        # -- Top landing pages --
        data = await _run_report(client, {
            "dateRanges": [{"startDate": "30daysAgo", "endDate": "today"}],
            "dimensions": [{"name": "landingPagePlusQueryString"}],
            "metrics": [{"name": "sessions"}],
            "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
            "limit": 10,
        })
        landing_pages = []
        for row in data.get("rows", []):
            page = row["dimensionValues"][0]["value"]
            sessions = int(float(row["metricValues"][0]["value"]))
            landing_pages.append({"page": page, "sessions": sessions})
        result["landing_pages"] = landing_pages

        return result
    except Exception as e:
        logger.error(f"GA4 traffic overview failed: {e}")
        return None


async def fetch_page_performance() -> list | None:
    """Section 2: Page performance table."""
    client = await _get_client()
    if not client:
        return None

    try:
        data = await _run_report(client, {
            "dateRanges": [{"startDate": "30daysAgo", "endDate": "today"}],
            "dimensions": [{"name": "pagePath"}],
            "metrics": [
                {"name": "screenPageViews"},
                {"name": "sessions"},
                {"name": "averageSessionDuration"},
                {"name": "bounceRate"},
            ],
            "orderBys": [{"metric": {"metricName": "screenPageViews"}, "desc": True}],
            "limit": 20,
        })

        conversion_map = {
            "/": "Waitlist signup",
            "/leakfinder": "Quiz completion",
            "/thank-you": "—",
            "/login": "Login",
        }

        pages = []
        for row in data.get("rows", []):
            path = row["dimensionValues"][0]["value"]
            vals = row["metricValues"]
            pages.append({
                "page": path,
                "views": int(float(vals[0]["value"])),
                "unique_views": int(float(vals[1]["value"])),
                "avg_time": round(float(vals[2]["value"]), 1),
                "bounce_rate": round(float(vals[3]["value"]) * 100, 1),
                "conversion_action": conversion_map.get(path, "—"),
            })
        return pages
    except Exception as e:
        logger.error(f"GA4 page performance failed: {e}")
        return None


async def fetch_source_detail() -> list | None:
    """Section 3: Traffic source detail — source/medium with landing pages and engagement."""
    client = await _get_client()
    if not client:
        return None

    try:
        data = await _run_report(client, {
            "dateRanges": [{"startDate": "30daysAgo", "endDate": "today"}],
            "dimensions": [
                {"name": "sessionSource"},
                {"name": "sessionMedium"},
                {"name": "landingPagePlusQueryString"},
            ],
            "metrics": [
                {"name": "sessions"},
                {"name": "activeUsers"},
                {"name": "averageSessionDuration"},
                {"name": "bounceRate"},
            ],
            "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
            "limit": 50,
        })

        # Group by source/medium
        grouped = {}
        for row in data.get("rows", []):
            dims = row["dimensionValues"]
            source = dims[0]["value"]
            medium = dims[1]["value"]
            page = dims[2]["value"]
            vals = row["metricValues"]
            key = f"{source} / {medium}"
            if key not in grouped:
                grouped[key] = {
                    "source": source,
                    "medium": medium,
                    "total_sessions": 0,
                    "total_users": 0,
                    "pages": [],
                }
            entry = grouped[key]
            sessions = int(float(vals[0]["value"]))
            entry["total_sessions"] += sessions
            entry["total_users"] += int(float(vals[1]["value"]))
            entry["pages"].append({
                "page": page,
                "sessions": sessions,
                "avg_time": round(float(vals[2]["value"]), 1),
                "bounce_rate": round(float(vals[3]["value"]) * 100, 1),
            })

        # Sort by total sessions
        result = sorted(grouped.values(), key=lambda x: x["total_sessions"], reverse=True)
        return result
    except Exception as e:
        logger.error(f"GA4 source detail failed: {e}")
        return None


async def fetch_utm_dashboard() -> list | None:
    """Section 4: UTM tracking dashboard."""
    client = await _get_client()
    if not client:
        return None

    try:
        data = await _run_report(client, {
            "dateRanges": [{"startDate": "30daysAgo", "endDate": "today"}],
            "dimensions": [
                {"name": "sessionCampaignName"},
                {"name": "sessionSource"},
                {"name": "sessionMedium"},
            ],
            "metrics": [
                {"name": "sessions"},
                {"name": "activeUsers"},
                {"name": "bounceRate"},
            ],
            "dimensionFilter": {
                "notExpression": {
                    "filter": {
                        "fieldName": "sessionCampaignName",
                        "stringFilter": {"value": "(not set)", "matchType": "EXACT"},
                    }
                }
            },
            "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
            "limit": 30,
        })

        campaigns = []
        for row in data.get("rows", []):
            dims = row["dimensionValues"]
            vals = row["metricValues"]
            campaigns.append({
                "campaign": dims[0]["value"],
                "source": dims[1]["value"],
                "medium": dims[2]["value"],
                "sessions": int(float(vals[0]["value"])),
                "users": int(float(vals[1]["value"])),
                "bounce_rate": round(float(vals[2]["value"]) * 100, 1),
            })
        return campaigns
    except Exception as e:
        logger.error(f"GA4 UTM dashboard failed: {e}")
        return None


async def fetch_conversion_funnel() -> dict | None:
    """Section 6: Conversion funnel — landing → quiz start → quiz complete → email → signup."""
    client = await _get_client()
    if not client:
        return None

    try:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        prev_week_start = week_start - timedelta(days=7)
        prev_week_end = week_start - timedelta(days=1)

        async def _funnel_for_range(start: str, end: str) -> dict:
            # Total landing page visitors
            data = await _run_report(client, {
                "dateRanges": [{"startDate": start, "endDate": end}],
                "metrics": [{"name": "activeUsers"}],
            })
            rows = data.get("rows", [])
            landing_visitors = int(float(rows[0]["metricValues"][0]["value"])) if rows else 0

            # Leakfinder page visitors (proxy for quiz starts)
            data = await _run_report(client, {
                "dateRanges": [{"startDate": start, "endDate": end}],
                "dimensions": [{"name": "pagePath"}],
                "metrics": [{"name": "activeUsers"}],
                "dimensionFilter": {
                    "filter": {
                        "fieldName": "pagePath",
                        "stringFilter": {"value": "/leakfinder", "matchType": "BEGINS_WITH"},
                    }
                },
            })
            rows = data.get("rows", [])
            quiz_starts = sum(int(float(r["metricValues"][0]["value"])) for r in rows)

            # Event-based metrics: quiz completion, email signup, etc.
            event_counts = {}
            for event_name in ["quiz_complete", "email_signup", "onboarding_complete", "hand_recorded"]:
                data = await _run_report(client, {
                    "dateRanges": [{"startDate": start, "endDate": end}],
                    "dimensions": [{"name": "eventName"}],
                    "metrics": [{"name": "eventCount"}],
                    "dimensionFilter": {
                        "filter": {
                            "fieldName": "eventName",
                            "stringFilter": {"value": event_name, "matchType": "EXACT"},
                        }
                    },
                })
                rows = data.get("rows", [])
                event_counts[event_name] = int(float(rows[0]["metricValues"][0]["value"])) if rows else 0

            # Thank-you page visitors (fallback for email capture if no event)
            data = await _run_report(client, {
                "dateRanges": [{"startDate": start, "endDate": end}],
                "dimensions": [{"name": "pagePath"}],
                "metrics": [{"name": "activeUsers"}],
                "dimensionFilter": {
                    "filter": {
                        "fieldName": "pagePath",
                        "stringFilter": {"value": "/thank-you", "matchType": "EXACT"},
                    }
                },
            })
            rows = data.get("rows", [])
            thank_you_visitors = int(float(rows[0]["metricValues"][0]["value"])) if rows else 0

            quiz_completions = event_counts.get("quiz_complete", 0) or event_counts.get("hand_recorded", 0)
            email_captures = event_counts.get("email_signup", 0) or thank_you_visitors
            signups = event_counts.get("onboarding_complete", 0)

            return {
                "landing_visitors": landing_visitors,
                "quiz_starts": quiz_starts,
                "quiz_completions": quiz_completions,
                "email_captures": email_captures,
                "signups": signups,
            }

        this_week = await _funnel_for_range(week_start.isoformat(), "today")
        prev_week = await _funnel_for_range(prev_week_start.isoformat(), prev_week_end.isoformat())

        # Build funnel stages with conversion rates
        stages = []
        stage_keys = [
            ("landing_visitors", "Landing Page Visitors"),
            ("quiz_starts", "Leak Finder Quiz Starts"),
            ("quiz_completions", "Quiz Completions"),
            ("email_captures", "Email Captured"),
            ("signups", "Waitlist / Trial Signup"),
        ]

        for i, (key, label) in enumerate(stage_keys):
            current_val = this_week[key]
            prev_val = prev_week[key]
            prev_stage_val = this_week[stage_keys[i - 1][0]] if i > 0 else None

            stage = {
                "label": label,
                "key": key,
                "count": current_val,
                "prev_count": prev_val,
            }

            if prev_stage_val and prev_stage_val > 0:
                stage["conversion_rate"] = round(current_val / prev_stage_val * 100, 1)
                stage["dropoff_pct"] = round((1 - current_val / prev_stage_val) * 100, 1)
            else:
                stage["conversion_rate"] = None
                stage["dropoff_pct"] = None

            # Week-over-week diff
            stage["wow_diff"] = current_val - prev_val

            stages.append(stage)

        # Post-launch placeholders
        stages.append({
            "label": "Trial Started",
            "key": "trial_started",
            "count": None,
            "prev_count": None,
            "conversion_rate": None,
            "dropoff_pct": None,
            "wow_diff": None,
            "post_launch": True,
        })
        stages.append({
            "label": "Paid Subscriber",
            "key": "paid_subscriber",
            "count": None,
            "prev_count": None,
            "conversion_rate": None,
            "dropoff_pct": None,
            "wow_diff": None,
            "post_launch": True,
        })

        return {"stages": stages, "period": "This week"}
    except Exception as e:
        logger.error(f"GA4 conversion funnel failed: {e}")
        return None


async def fetch_realtime() -> dict | None:
    """Section 5: Real-time active users and pages."""
    client = await _get_client()
    if not client:
        return None

    try:
        data = await _run_realtime_report(client, {
            "metrics": [{"name": "activeUsers"}],
            "dimensions": [{"name": "unifiedScreenName"}],
        })

        active_total = 0
        pages = []
        for row in data.get("rows", []):
            page = row["dimensionValues"][0]["value"]
            users = int(float(row["metricValues"][0]["value"]))
            active_total += users
            pages.append({"page": page, "users": users})

        return {"active_users": active_total, "pages": pages}
    except Exception as e:
        logger.error(f"GA4 realtime failed: {e}")
        return None


async def fetch_dashboard_widget() -> dict | None:
    """Lightweight query for the dashboard widget."""
    client = await _get_client()
    if not client:
        return None

    try:
        result = {}
        today = date.today()
        yesterday = today - timedelta(days=1)

        # Visitors today
        data = await _run_report(client, {
            "dateRanges": [{"startDate": "today", "endDate": "today"}],
            "metrics": [{"name": "activeUsers"}],
        })
        rows = data.get("rows", [])
        result["visitors_today"] = int(float(rows[0]["metricValues"][0]["value"])) if rows else 0

        # Visitors yesterday
        data = await _run_report(client, {
            "dateRanges": [{"startDate": yesterday.isoformat(), "endDate": yesterday.isoformat()}],
            "metrics": [{"name": "activeUsers"}],
        })
        rows = data.get("rows", [])
        result["visitors_yesterday"] = int(float(rows[0]["metricValues"][0]["value"])) if rows else 0

        # Top source today
        data = await _run_report(client, {
            "dateRanges": [{"startDate": "today", "endDate": "today"}],
            "dimensions": [{"name": "sessionDefaultChannelGroup"}],
            "metrics": [{"name": "sessions"}],
            "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
            "limit": 1,
        })
        rows = data.get("rows", [])
        result["top_source"] = rows[0]["dimensionValues"][0]["value"] if rows else "—"

        return result
    except Exception as e:
        logger.error(f"GA4 dashboard widget failed: {e}")
        return None
