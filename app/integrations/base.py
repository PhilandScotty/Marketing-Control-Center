"""Base class for all MCC integrations."""
import logging
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx

from app.models import HealthStatus

logger = logging.getLogger("mcc.integrations")

DEFAULT_TIMEOUT = 10.0
MAX_RETRIES = 3
BACKOFF_BASE = 2  # seconds


@dataclass
class MetricReading:
    channel_name: str
    metric_name: str
    value: float
    unit: str = "count"


@dataclass
class IntegrationResult:
    success: bool
    metrics: list = field(default_factory=list)
    error: Optional[str] = None


class IntegrationBase(ABC):
    """Abstract base class for all API integrations."""

    name: str = "base"
    refresh_interval_hours: int = 4
    _consecutive_failures: int = 0

    def __init__(self):
        self._consecutive_failures = 0

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if required API keys/config are present."""
        ...

    @abstractmethod
    async def connect(self) -> bool:
        """Verify connection to the external service."""
        ...

    @abstractmethod
    async def fetch_metrics(self) -> list[MetricReading]:
        """Fetch current metrics from the external service."""
        ...

    def get_health_status(self) -> HealthStatus:
        """Determine health based on consecutive failures."""
        if self._consecutive_failures >= 3:
            return HealthStatus.critical
        if self._consecutive_failures >= 1:
            return HealthStatus.warning
        return HealthStatus.healthy

    def record_success(self):
        self._consecutive_failures = 0

    def record_failure(self):
        self._consecutive_failures += 1

    async def _request(
        self,
        method: str,
        url: str,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> httpx.Response:
        """Make an HTTP request with exponential backoff retry."""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.request(
                        method, url,
                        headers=headers,
                        params=params,
                        json=json,
                    )
                    if resp.status_code == 429:
                        # Rate limited — back off
                        wait = BACKOFF_BASE ** (attempt + 1)
                        logger.warning(f"{self.name}: Rate limited, waiting {wait}s")
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    return resp
            except httpx.TimeoutException as e:
                last_error = f"Timeout on attempt {attempt + 1}: {e}"
                logger.warning(f"{self.name}: {last_error}")
            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}: {e}"
                logger.warning(f"{self.name}: {last_error}")
                if e.response.status_code in (401, 403):
                    raise  # Don't retry auth failures
            except httpx.HTTPError as e:
                last_error = f"HTTP error: {e}"
                logger.warning(f"{self.name}: {last_error}")

            if attempt < MAX_RETRIES - 1:
                wait = BACKOFF_BASE ** (attempt + 1)
                await asyncio.sleep(wait)

        raise httpx.HTTPError(f"{self.name}: All {MAX_RETRIES} attempts failed. Last: {last_error}")

    async def run(self) -> IntegrationResult:
        """Execute the integration: connect, fetch, return results."""
        if not self.is_configured():
            logger.info(f"{self.name}: Not configured, skipping")
            return IntegrationResult(success=False, error="Not configured")

        try:
            connected = await self.connect()
            if not connected:
                self.record_failure()
                return IntegrationResult(success=False, error="Connection failed")

            metrics = await self.fetch_metrics()
            self.record_success()
            return IntegrationResult(success=True, metrics=metrics)
        except Exception as e:
            self.record_failure()
            logger.error(f"{self.name}: Integration run failed: {e}")
            return IntegrationResult(success=False, error=str(e))
