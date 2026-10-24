"""DataUpdateCoordinator for NWSDB Water Bill."""
from __future__ import annotations

from datetime import timedelta
import json
import logging
import re
import urllib.request

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL_HOURS, DEFAULT_CDP_HOST, DEFAULT_CDP_PORT

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


def fetch_nwsdb_sync(account_number: str, cdp_host: str, cdp_port: int) -> dict:
    """Fetch complete NWSDB data."""
    details = fetch_nwsdb_account_details(account_number)
    balance = fetch_nwsdb_balance_cdp(account_number, cdp_host, cdp_port)

    # If CDP didn't return balance (e.g. headless browser not running), check if balance was cached or default
    if balance is None:
        # Default placeholder/fallback when browser tab isn't active
        _LOGGER.warning("Could not read live balance from NWSDB portal tab; returning last known metadata")

    return {
        "account_number": account_number,
        "balance": balance,
        **details,
    }


class NWSDBBillCoordinator(DataUpdateCoordinator[dict]):
    """Manage fetching NWSDB bill data."""

    def __init__(
        self,
        hass: HomeAssistant,
        account_number: str,
        cdp_host: str = DEFAULT_CDP_HOST,
        cdp_port: int = DEFAULT_CDP_PORT,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"NWSDB Water Bill ({account_number})",
            update_interval=timedelta(hours=DEFAULT_SCAN_INTERVAL_HOURS),
        )
        self.account_number = account_number
        self.cdp_host = cdp_host
        self.cdp_port = cdp_port

    async def _async_update_data(self) -> dict:
        """Fetch data from NWSDB."""
        try:
            return await self.hass.async_add_executor_job(
                fetch_nwsdb_sync, self.account_number, self.cdp_host, self.cdp_port
            )
        except Exception as err:
            raise UpdateFailed(f"Error communicating with NWSDB: {err}") from err
