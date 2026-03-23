"""Ad platform integration stubs — Meta, Reddit, Google Ads.

Framework ready — implement API calls when keys become available.
Each follows the IntegrationBase pattern with graceful skip when unconfigured.
"""
import logging
from app.config import META_ADS_ACCESS_TOKEN, REDDIT_ADS_TOKEN, GOOGLE_ADS_CREDENTIALS
from app.integrations.base import IntegrationBase, MetricReading

logger = logging.getLogger("mcc.integrations.ad_platforms")


class MetaAdsIntegration(IntegrationBase):
    name = "meta_ads"
    refresh_interval_hours = 6

    def is_configured(self) -> bool:
        return bool(META_ADS_ACCESS_TOKEN)

    async def connect(self) -> bool:
        # Meta Marketing API: GET /me?access_token=...
        resp = await self._request(
            "GET", "https://graph.facebook.com/v18.0/me",
            params={"access_token": META_ADS_ACCESS_TOKEN},
        )
        return resp.status_code == 200

    async def fetch_metrics(self) -> list[MetricReading]:
        # TODO: Implement when Meta Ads API key is available
        # Endpoints:
        # GET /act_{ad_account_id}/campaigns?fields=name,status,daily_budget
        # GET /act_{ad_account_id}/insights?fields=impressions,clicks,spend,actions
        logger.info("Meta Ads: Stub — no implementation yet")
        return []


class RedditAdsIntegration(IntegrationBase):
    name = "reddit_ads"
    refresh_interval_hours = 6

    def is_configured(self) -> bool:
        return bool(REDDIT_ADS_TOKEN)

    async def connect(self) -> bool:
        # Reddit Ads API: GET /api/v2.0/me
        resp = await self._request(
            "GET", "https://ads-api.reddit.com/api/v2.0/me",
            headers={"Authorization": f"Bearer {REDDIT_ADS_TOKEN}"},
        )
        return resp.status_code == 200

    async def fetch_metrics(self) -> list[MetricReading]:
        # TODO: Implement when Reddit Ads token is available
        # Endpoints:
        # GET /api/v2.0/accounts/{account_id}/campaigns
        # GET /api/v2.0/accounts/{account_id}/reports
        logger.info("Reddit Ads: Stub — no implementation yet")
        return []


class GoogleAdsIntegration(IntegrationBase):
    name = "google_ads"
    refresh_interval_hours = 6

    def is_configured(self) -> bool:
        return bool(GOOGLE_ADS_CREDENTIALS)

    async def connect(self) -> bool:
        # Google Ads API requires OAuth2 + developer token
        # TODO: Implement auth flow when credentials available
        logger.info("Google Ads: Stub — credentials not yet configured")
        return False

    async def fetch_metrics(self) -> list[MetricReading]:
        # TODO: Implement when Google Ads credentials are available
        # Use google-ads Python client library
        # Query: SELECT campaign.name, metrics.impressions, metrics.clicks,
        #         metrics.cost_micros, metrics.conversions
        #   FROM campaign WHERE segments.date DURING LAST_7_DAYS
        logger.info("Google Ads: Stub — no implementation yet")
        return []
