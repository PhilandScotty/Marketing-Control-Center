"""Stripe integration — MRR, subscriptions, trial-to-paid rate, churn."""
import logging
from app.config import STRIPE_API_KEY
from app.integrations.base import IntegrationBase, MetricReading

logger = logging.getLogger("mcc.integrations.stripe")

BASE_URL = "https://api.stripe.com/v1"


class StripeIntegration(IntegrationBase):
    name = "stripe"
    refresh_interval_hours = 4

    def is_configured(self) -> bool:
        return bool(STRIPE_API_KEY)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {STRIPE_API_KEY}"}

    async def connect(self) -> bool:
        resp = await self._request("GET", f"{BASE_URL}/balance", headers=self._headers())
        return resp.status_code == 200

    async def fetch_metrics(self) -> list[MetricReading]:
        metrics = []
        headers = self._headers()

        try:
            # Active subscriptions
            resp = await self._request("GET", f"{BASE_URL}/subscriptions", headers=headers, params={
                "status": "active", "limit": 100,
            })
            subs_data = resp.json()
            active_subs = subs_data.get("data", [])

            # Calculate MRR
            mrr = 0.0
            for sub in active_subs:
                for item in sub.get("items", {}).get("data", []):
                    price = item.get("price", {})
                    amount = price.get("unit_amount", 0) / 100  # cents to dollars
                    interval = price.get("recurring", {}).get("interval", "month")
                    if interval == "year":
                        amount = amount / 12
                    elif interval == "week":
                        amount = amount * 4.33
                    mrr += amount

            metrics.extend([
                MetricReading("Payments", "active_subscriptions", float(len(active_subs)), "subscriptions"),
                MetricReading("Payments", "mrr", round(mrr, 2), "dollars"),
                MetricReading("Payments", "arr", round(mrr * 12, 2), "dollars"),
            ])

            # Trialing subscriptions
            resp = await self._request("GET", f"{BASE_URL}/subscriptions", headers=headers, params={
                "status": "trialing", "limit": 100,
            })
            trials = resp.json().get("data", [])
            metrics.append(MetricReading("Payments", "trialing", float(len(trials)), "subscriptions"))

            # Trial-to-paid rate (past_due or canceled after trial = failed)
            total_trial_eligible = len(active_subs) + len(trials)
            if total_trial_eligible > 0:
                trial_to_paid = round(len(active_subs) / total_trial_eligible * 100, 1)
                metrics.append(MetricReading("Payments", "trial_to_paid_rate", trial_to_paid, "percent"))

            # Canceled recently (churn proxy)
            resp = await self._request("GET", f"{BASE_URL}/subscriptions", headers=headers, params={
                "status": "canceled", "limit": 100,
            })
            canceled = resp.json().get("data", [])
            metrics.append(MetricReading("Payments", "canceled_subscriptions", float(len(canceled)), "subscriptions"))

            # Churn rate
            total_ever = len(active_subs) + len(canceled)
            if total_ever > 0:
                churn_rate = round(len(canceled) / total_ever * 100, 1)
                metrics.append(MetricReading("Payments", "churn_rate", churn_rate, "percent"))

        except Exception as e:
            logger.error(f"Stripe: Failed to fetch metrics: {e}")

        return metrics
