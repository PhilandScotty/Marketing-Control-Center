"""ConvertKit integration — subscriber counts, sequence stats."""
import logging
from app.config import CONVERTKIT_API_SECRET
from app.integrations.base import IntegrationBase, MetricReading

logger = logging.getLogger("mcc.integrations.convertkit")

BASE_URL = "https://api.convertkit.com/v3"


class ConvertKitIntegration(IntegrationBase):
    name = "convertkit"
    refresh_interval_hours = 4

    def is_configured(self) -> bool:
        return bool(CONVERTKIT_API_SECRET)

    async def connect(self) -> bool:
        resp = await self._request("GET", f"{BASE_URL}/account", params={
            "api_secret": CONVERTKIT_API_SECRET,
        })
        return resp.status_code == 200

    async def fetch_metrics(self) -> list[MetricReading]:
        metrics = []

        # Total subscribers
        resp = await self._request("GET", f"{BASE_URL}/subscribers", params={
            "api_secret": CONVERTKIT_API_SECRET,
            "page": 1,
        })
        data = resp.json()
        total = data.get("total_subscribers", 0)
        metrics.append(MetricReading(
            channel_name="Email Nurture (Kit)",
            metric_name="email_subscribers",
            value=float(total),
            unit="subscribers",
        ))

        # Forms (landing page conversions)
        resp = await self._request("GET", f"{BASE_URL}/forms", params={
            "api_secret": CONVERTKIT_API_SECRET,
        })
        forms = resp.json().get("forms", [])
        total_form_subs = sum(f.get("total_subscriptions", 0) for f in forms)
        metrics.append(MetricReading(
            channel_name="Email Nurture (Kit)",
            metric_name="form_signups_total",
            value=float(total_form_subs),
            unit="signups",
        ))

        # Sequences
        resp = await self._request("GET", f"{BASE_URL}/sequences", params={
            "api_secret": CONVERTKIT_API_SECRET,
        })
        sequences = resp.json().get("courses", [])
        metrics.append(MetricReading(
            channel_name="Email Nurture (Kit)",
            metric_name="active_sequences",
            value=float(len(sequences)),
            unit="sequences",
        ))

        return metrics
