"""DataUpdateCoordinator for NWSDB Water Bill with smart caching."""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
import re
import time
import urllib.request

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DEFAULT_CDP_HOST,
    DEFAULT_CDP_PORT,
    CACHE_TTL_SECONDS,
    METADATA_CACHE_TTL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


def fetch_nwsdb_account_details(account_number: str) -> dict:
    """Fetch consumer metadata from NWSDB REST API."""
    url = f"https://ebis.waterboard.lk/api_nwsdb/bill/accountDetails?accountNumber={account_number}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get("message") == 200 and data.get("Details"):
                detail = data["Details"][0]
                name = f"{detail.get('Title', '')} {detail.get('Initial', '')} {detail.get('ConsumerName', '')}".strip()
                return {
                    "customer_name": name,
                    "meter_no": detail.get("MeterNo"),
                    "area": detail.get("AreaName"),
                    "category": detail.get("CategoryDescription"),
                    "status": detail.get("ConnectionStatus"),
                }
    except Exception as e:
        _LOGGER.debug("Could not fetch NWSDB account details API: %s", e)
    return {}


def fetch_nwsdb_balance_cdp(account_number: str, cdp_host: str = DEFAULT_CDP_HOST, cdp_port: int = DEFAULT_CDP_PORT) -> float | None:
    """Read balance from active smartzone tab or trigger refresh via CDP."""
    try:
        req = urllib.request.Request(f"http://{cdp_host}:{cdp_port}/json")
        with urllib.request.urlopen(req, timeout=5) as resp:
            targets = json.loads(resp.read().decode())

        for target in targets:
            url = target.get("url", "")
            ws_url = target.get("webSocketDebuggerUrl")
            if "waterboard.lk" in url and ws_url:
                import websocket
                ws = websocket.create_connection(ws_url, timeout=10)
                cmd = {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": (
                            "document.getElementById('lbltotdue') ? "
                            "document.getElementById('lbltotdue').innerText : ''"
                        ),
                        "returnByValue": True,
                    },
                }
                ws.send(json.dumps(cmd))
                res = json.loads(ws.recv())
                ws.close()
                val = res.get("result", {}).get("result", {}).get("value")
                if val:
                    clean = re.sub(r"[^\d.]", "", val)
                    return float(clean)
    except Exception as e:
        _LOGGER.debug("Could not read balance via CDP: %s", e)
    return None


class NWSDBBillCoordinator(DataUpdateCoordinator[dict]):
    """Manage fetching NWSDB bill data with smart caching and anti-hammer protection."""

    def __init__(
        self,
        hass: HomeAssistant,
        account_number: str,
        cdp_host: str = DEFAULT_CDP_HOST,
        cdp_port: int = DEFAULT_CDP_PORT,
        scan_interval_hours: int = DEFAULT_SCAN_INTERVAL_HOURS,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"NWSDB Water Bill ({account_number})",
            update_interval=timedelta(hours=scan_interval_hours),
        )
        self.account_number = account_number
        self.cdp_host = cdp_host
        self.cdp_port = cdp_port
        self._last_balance_fetch_time: float = 0
        self._last_metadata_fetch_time: float = 0
        self._cached_metadata: dict = {}
        self._cached_data: dict | None = None

    async def _async_update_data(self) -> dict:
        """Fetch data from NWSDB using tiered caching to minimize site load."""
        now = time.monotonic()

        # If data is cached within 1 hour TTL, reuse it immediately without hitting NWSDB
        if self._cached_data and (now - self._last_balance_fetch_time < CACHE_TTL_SECONDS):
            _LOGGER.debug(
                "NWSDB Bill (%s): Using cached data to prevent overloading portal (%d seconds remaining in TTL)",
                self.account_number,
                int(CACHE_TTL_SECONDS - (now - self._last_balance_fetch_time)),
            )
            return self._cached_data

        try:
            # Refresh static consumer metadata only once a week (or first run)
            if not self._cached_metadata or (now - self._last_metadata_fetch_time > METADATA_CACHE_TTL_SECONDS):
                meta = await self.hass.async_add_executor_job(
                    fetch_nwsdb_account_details, self.account_number
                )
                if meta:
                    self._cached_metadata = meta
                    self._last_metadata_fetch_time = time.monotonic()

            # Read live balance
            balance = await self.hass.async_add_executor_job(
                fetch_nwsdb_balance_cdp, self.account_number, self.cdp_host, self.cdp_port
            )

            # If balance query failed or returned None, fall back to last known balance
            if balance is None and self._cached_data:
                balance = self._cached_data.get("balance")

            data = {
                "account_number": self.account_number,
                "balance": balance,
                "last_synced": datetime.now().isoformat(),
                **self._cached_metadata,
            }
            self._cached_data = data
            self._last_balance_fetch_time = time.monotonic()
            return data
        except Exception as err:
            if self._cached_data:
                _LOGGER.warning("Error refreshing NWSDB data: %s. Using cached data.", err)
                return self._cached_data
            raise UpdateFailed(f"Error communicating with NWSDB: {err}") from err
