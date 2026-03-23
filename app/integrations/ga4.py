"""Google Analytics 4 integration — pageviews, sessions, conversions, sources."""
import logging
from app.config import GA4_CREDENTIALS_PATH, GA4_PROPERTY_ID
from app.integrations.base import IntegrationBase, MetricReading

logger = logging.getLogger("mcc.integrations.ga4")

GA4_DATA_API = "https://analyticsdata.googleapis.com/v1beta"


class GA4Integration(IntegrationBase):
    name = "ga4"
    refresh_interval_hours = 6
    _access_token: str | None = None

    def is_configured(self) -> bool:
        return bool(GA4_CREDENTIALS_PATH and GA4_PROPERTY_ID)

    async def _get_access_token(self) -> str | None:
        """Get OAuth2 access token from service account credentials."""
        try:
            import json
            import time
            import base64
            import hashlib
            import hmac

            with open(GA4_CREDENTIALS_PATH) as f:
                creds = json.load(f)

            # Build JWT
            now = int(time.time())
            header = base64.urlsafe_b64encode(
                json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
            ).rstrip(b"=")
            payload = base64.urlsafe_b64encode(json.dumps({
                "iss": creds["client_email"],
                "scope": "https://www.googleapis.com/auth/analytics.readonly",
                "aud": creds["token_uri"],
                "iat": now,
                "exp": now + 3600,
            }).encode()).rstrip(b"=")

            # Sign with private key
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding

            private_key = serialization.load_pem_private_key(
                creds["private_key"].encode(), password=None,
            )
            message = header + b"." + payload
            signature = private_key.sign(message, padding.PKCS1v15(), hashes.SHA256())
            sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=")
            jwt_token = (header + b"." + payload + b"." + sig_b64).decode()

            # Exchange for access token
            resp = await self._request("POST", creds["token_uri"], json={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": jwt_token,
            })
            return resp.json().get("access_token")
        except ImportError:
            logger.warning("GA4: cryptography package not installed, skipping")
            return None
        except Exception as e:
            logger.error(f"GA4: Failed to get access token: {e}")
            return None

    async def connect(self) -> bool:
        self._access_token = await self._get_access_token()
        return self._access_token is not None

    async def fetch_metrics(self) -> list[MetricReading]:
        if not self._access_token:
            return []

        metrics = []
        property_id = GA4_PROPERTY_ID
        url = f"{GA4_DATA_API}/properties/{property_id}:runReport"
        headers = {"Authorization": f"Bearer {self._access_token}"}

        try:
            # Pageviews + Sessions (last 7 days)
            resp = await self._request("POST", url, headers=headers, json={
                "dateRanges": [{"startDate": "7daysAgo", "endDate": "today"}],
                "metrics": [
                    {"name": "screenPageViews"},
                    {"name": "sessions"},
                    {"name": "conversions"},
                    {"name": "activeUsers"},
                ],
            })
            data = resp.json()
            rows = data.get("rows", [])
            if rows:
                values = rows[0].get("metricValues", [])
                if len(values) >= 4:
                    metrics.extend([
                        MetricReading("SEO / Organic", "pageviews_7d", float(values[0]["value"]), "views"),
                        MetricReading("SEO / Organic", "sessions_7d", float(values[1]["value"]), "sessions"),
                        MetricReading("SEO / Organic", "conversions_7d", float(values[2]["value"]), "conversions"),
                        MetricReading("SEO / Organic", "active_users_7d", float(values[3]["value"]), "users"),
                    ])

            # Top traffic sources
            resp = await self._request("POST", url, headers=headers, json={
                "dateRanges": [{"startDate": "7daysAgo", "endDate": "today"}],
                "dimensions": [{"name": "sessionDefaultChannelGroup"}],
                "metrics": [{"name": "sessions"}],
                "limit": 5,
            })
            data = resp.json()
            for row in data.get("rows", []):
                source = row["dimensionValues"][0]["value"]
                sessions = float(row["metricValues"][0]["value"])
                metrics.append(MetricReading(
                    "SEO / Organic",
                    f"source_{source.lower().replace(' ', '_')}",
                    sessions,
                    "sessions",
                ))
        except Exception as e:
            logger.error(f"GA4: Failed to fetch metrics: {e}")

        return metrics
