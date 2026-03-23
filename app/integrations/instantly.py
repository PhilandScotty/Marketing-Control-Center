"""Instantly.ai integration — cold outreach campaign analytics (API v2)."""
import logging
from app.config import INSTANTLY_API_KEY
from app.integrations.base import IntegrationBase, MetricReading

logger = logging.getLogger("mcc.integrations.instantly")

BASE_URL = "https://api.instantly.ai/api/v2"


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {INSTANTLY_API_KEY}"}


class InstantlyIntegration(IntegrationBase):
    name = "instantly"
    refresh_interval_hours = 6

    def is_configured(self) -> bool:
        return bool(INSTANTLY_API_KEY)

    async def connect(self) -> bool:
        resp = await self._request("GET", f"{BASE_URL}/campaigns",
                                   headers=_auth_headers())
        return resp.status_code == 200

    async def fetch_metrics(self) -> list[MetricReading]:
        metrics = []

        # Campaign analytics (single call returns all campaigns)
        resp = await self._request("GET", f"{BASE_URL}/campaigns/analytics",
                                   headers=_auth_headers())
        analytics = resp.json()
        if not isinstance(analytics, list):
            analytics = []

        active_campaigns = len(analytics)
        metrics.append(MetricReading(
            channel_name="Cold Email (Instantly)",
            metric_name="active_campaigns",
            value=float(active_campaigns),
            unit="campaigns",
        ))

        total_sent = 0
        total_contacted = 0
        total_opened = 0
        total_replied = 0
        total_bounced = 0
        total_leads = 0

        for camp in analytics:
            total_sent += camp.get("emails_sent_count", 0)
            total_contacted += camp.get("new_leads_contacted_count", 0)
            total_opened += camp.get("open_count_unique", 0)
            total_replied += camp.get("reply_count_unique", 0)
            total_bounced += camp.get("bounced_count", 0)
            total_leads += camp.get("leads_count", 0)

        metrics.extend([
            MetricReading("Cold Email (Instantly)", "emails_sent", float(total_sent), "emails"),
            MetricReading("Cold Email (Instantly)", "leads_contacted", float(total_contacted), "contacts"),
            MetricReading("Cold Email (Instantly)", "emails_opened", float(total_opened), "emails"),
            MetricReading("Cold Email (Instantly)", "emails_replied", float(total_replied), "emails"),
            MetricReading("Cold Email (Instantly)", "emails_bounced", float(total_bounced), "emails"),
            MetricReading("Cold Email (Instantly)", "leads_in_pipeline", float(total_leads), "leads"),
        ])

        if total_sent > 0:
            metrics.append(MetricReading(
                "Cold Email (Instantly)", "open_rate",
                round(total_opened / total_sent * 100, 1), "percent",
            ))
            metrics.append(MetricReading(
                "Cold Email (Instantly)", "reply_rate",
                round(total_replied / total_sent * 100, 1), "percent",
            ))

        logger.info(f"Instantly: {active_campaigns} campaigns, "
                     f"{total_sent} sent, {total_contacted} contacted, "
                     f"{total_opened} opened, {total_replied} replied")
        return metrics
