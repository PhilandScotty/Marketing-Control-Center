"""Buffer integration — social media queue status and post analytics via GraphQL API."""
import logging
from collections import Counter
from app.config import BUFFER_ACCESS_TOKEN
from app.integrations.base import IntegrationBase, MetricReading

logger = logging.getLogger("mcc.integrations.buffer")

GRAPHQL_URL = "https://api.buffer.com"

# Map Buffer service names to MCC channel names
SERVICE_TO_CHANNEL = {
    "twitter": "X/Twitter",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "linkedin": "LinkedIn",
}


class BufferIntegration(IntegrationBase):
    name = "buffer"
    refresh_interval_hours = 4

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {BUFFER_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

    def is_configured(self) -> bool:
        return bool(BUFFER_ACCESS_TOKEN)

    async def _graphql(self, query: str, variables: dict | None = None) -> dict:
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        resp = await self._request(
            "POST", GRAPHQL_URL, headers=self._headers(), json=payload
        )
        raw = resp.text
        try:
            data = resp.json()
        except Exception:
            logger.error(f"Buffer: non-JSON response (HTTP {resp.status_code}): {raw[:500]}")
            raise RuntimeError(f"Buffer API returned non-JSON (HTTP {resp.status_code})")
        if "errors" in data:
            logger.error(f"Buffer GraphQL errors: {data['errors']}")
            # If auth error, raise so it counts as failure
            for err in data["errors"]:
                msg = err.get("message", "").lower()
                if "unauthorized" in msg or "forbidden" in msg or "unauthenticated" in msg:
                    raise RuntimeError(f"Buffer auth error: {err['message']}")
        return data.get("data", {})

    async def connect(self) -> bool:
        try:
            data = await self._graphql("{ account { id } }")
            return bool(data.get("account"))
        except Exception as e:
            logger.warning(f"Buffer: connect failed: {e}")
            return False

    async def _get_org_id(self) -> str | None:
        data = await self._graphql("{ account { organizations { id } } }")
        orgs = data.get("account", {}).get("organizations", [])
        return orgs[0]["id"] if orgs else None

    async def fetch_metrics(self) -> list[MetricReading]:
        metrics = []

        org_id = await self._get_org_id()
        if not org_id:
            logger.warning("Buffer: no organization found")
            return metrics

        # Get channels
        ch_data = await self._graphql(
            '{ channels(input: { organizationId: "%s" }) { id name service } }' % org_id
        )
        channels = ch_data.get("channels", [])
        if not isinstance(channels, list):
            channels = []

        channel_service = {ch["id"]: ch.get("service", "unknown") for ch in channels}

        # Get pending + sent posts in one query
        posts_data = await self._graphql('''
            {
                pending: posts(input: { organizationId: "%s", filter: { status: [scheduled] } }) {
                    edges { node { channelId } }
                }
                sent: posts(input: { organizationId: "%s", filter: { status: [sent] } }) {
                    edges { node { channelId } }
                }
            }
        ''' % (org_id, org_id))

        pending_ids = [e["node"]["channelId"] for e in posts_data.get("pending", {}).get("edges", [])]
        sent_ids = [e["node"]["channelId"] for e in posts_data.get("sent", {}).get("edges", [])]
        pending_by_ch = Counter(pending_ids)
        sent_by_ch = Counter(sent_ids)

        total_pending = len(pending_ids)
        total_sent = len(sent_ids)

        for ch_id, service in channel_service.items():
            channel_name = SERVICE_TO_CHANNEL.get(service)
            if not channel_name:
                continue
            pending_count = pending_by_ch.get(ch_id, 0)
            sent_count = sent_by_ch.get(ch_id, 0)
            metrics.append(MetricReading(
                channel_name,
                "buffer_queue",
                float(pending_count),
                "posts",
            ))
            if sent_count > 0:
                metrics.append(MetricReading(
                    channel_name,
                    "posts_published",
                    float(sent_count),
                    "posts",
                ))

        # Aggregate totals — save under first available buffer channel
        first_channel = next(
            (SERVICE_TO_CHANNEL[s] for s in channel_service.values() if s in SERVICE_TO_CHANNEL),
            None,
        )
        if first_channel:
            metrics.extend([
                MetricReading(first_channel, "buffer_total_queued", float(total_pending), "posts"),
                MetricReading(first_channel, "buffer_total_sent", float(total_sent), "posts"),
            ])

        return metrics
