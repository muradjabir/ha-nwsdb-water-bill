"""DataUpdateCoordinator for NWSDB Water Bill with smart caching and browserless fetching."""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
import re
import time
import urllib.request

from bs4 import BeautifulSoup
import requests

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL_HOURS,
    CACHE_TTL_SECONDS,
    METADATA_CACHE_TTL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

PORTAL_URL = "https://ebis.waterboard.lk/smartzone/English/OnlinePayments"
FORM_PREFIX = "ctl00$ASPxRoundPanel1$ContentPlaceHolder1$"
TARGET_ACCOUNT_INPUT = FORM_PREFIX + "ASPxRoundPanel2$atbRefNo"
PREFIX_DETAILS = "ASPxRoundPanel1_ContentPlaceHolder1_ASPxRoundPanel2_apDetails_"


def format_nwsdb_account(account: str) -> str:
    """Ensure account number has 99/99/999/999/99 format."""
    clean = re.sub(r"[^\d]", "", account)
    if len(clean) == 12:
        return f"{clean[0:2]}/{clean[2:4]}/{clean[4:7]}/{clean[7:10]}/{clean[10:12]}"
    return account.strip()


def extract_hidden_inputs(html: str) -> dict[str, str]:
    """Extract ASP.NET hidden inputs from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    return {
        tag["name"]: tag.get("value", "")
        for tag in soup.select("input[type=hidden]")
        if tag.get("name")
    }


def fetch_nwsdb_account_details(account_number: str) -> dict:
    """Fetch consumer metadata from NWSDB REST API."""
    acc = format_nwsdb_account(account_number)
    url = f"https://ebis.waterboard.lk/api_nwsdb/bill/accountDetails?accountNumber={acc}"
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
                    "account_status": detail.get("StatusDescription") or detail.get("AccStus"),
                }
    except Exception as e:
        _LOGGER.debug("Could not fetch NWSDB REST API details: %s", e)
    return {}


def fetch_nwsdb_portal_sync(account_number: str) -> dict:
    """Scrape live bill balance and account info directly from NWSDB portal without a browser."""
    acc = format_nwsdb_account(account_number)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": PORTAL_URL,
        }
    )

    # 1. Establish session and get initial form viewstate
    resp1 = session.get(PORTAL_URL, timeout=20)
    resp1.raise_for_status()

    # 2. Select 'Bill Payment' (1) and Proceed
    data1 = extract_hidden_inputs(resp1.text)
    data1[FORM_PREFIX + "rblPaymentType"] = "1"
    data1[FORM_PREFIX + "cmdProceed"] = "Proceed"

    resp2 = session.post(PORTAL_URL, data=data1, timeout=20)
    resp2.raise_for_status()

    # 3. Simulate DevExpress masked input postback for account number
    data2 = extract_hidden_inputs(resp2.text)
    data2[FORM_PREFIX + "rblPaymentType"] = "1"
    data2[FORM_PREFIX + "ASPxRoundPanel2$txtAmount"] = "0.00"
    data2["__EVENTTARGET"] = TARGET_ACCOUNT_INPUT
    data2["__EVENTARGUMENT"] = ""
    data2[TARGET_ACCOUNT_INPUT] = acc
    data2[TARGET_ACCOUNT_INPUT + "$State"] = json.dumps(
        {"rawValue": acc, "validationState": ""}
    )

    resp3 = session.post(PORTAL_URL, data=data2, timeout=25)
    resp3.raise_for_status()

    soup = BeautifulSoup(resp3.text, "html.parser")

    # Locate amount tag
    amt_elem = soup.find("span", {"id": PREFIX_DETAILS + "lblAmount"})
    if not amt_elem:
        msg_elem = soup.find(
            "span", {"id": "ASPxRoundPanel1_ContentPlaceHolder1_ASPxRoundPanel2_lblMsg"}
        )
        err_msg = (
            msg_elem.get_text(strip=True) if msg_elem else "No balance details returned"
        )
        raise ValueError(f"Could not retrieve bill for NWSDB account {acc}: {err_msg}")

    amt_str = amt_elem.get_text(strip=True)
    is_credit = "CR" in amt_str.upper()
    clean_num = re.sub(r"[^\d.]", "", amt_str)
    amt_val = float(clean_num) if clean_num else 0.0
    balance = -amt_val if is_credit else amt_val

    name_elem = soup.find("span", {"id": PREFIX_DETAILS + "lblName"})
    customer_name = name_elem.get_text(strip=True) if name_elem else None

    addr_elem = soup.find("span", {"id": PREFIX_DETAILS + "lblAddress"})
    address = addr_elem.get_text(strip=True) if addr_elem else None

    msg_elem = soup.find(
        "span", {"id": "ASPxRoundPanel1_ContentPlaceHolder1_ASPxRoundPanel2_lblMsg"}
    )
    status_msg = msg_elem.get_text(strip=True) if msg_elem else None

    return {
        "account_number": acc,
        "balance": balance,
        "raw_amount": amt_str,
        "is_credit": is_credit,
        "customer_name": customer_name,
        "address": address,
        "status_message": status_msg,
    }


class NWSDBBillCoordinator(DataUpdateCoordinator[dict]):
    """Manage fetching NWSDB bill data with smart caching and anti-hammer protection."""

    def __init__(
        self,
        hass: HomeAssistant,
        account_number: str,
        scan_interval_hours: int = DEFAULT_SCAN_INTERVAL_HOURS,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"NWSDB Water Bill ({account_number})",
            update_interval=timedelta(hours=scan_interval_hours),
        )
        self.account_number = format_nwsdb_account(account_number)
        self._last_balance_fetch_time: float = 0
        self._last_metadata_fetch_time: float = 0
        self._cached_metadata: dict = {}
        self._cached_data: dict | None = None

    async def _async_update_data(self) -> dict:
        """Fetch data from NWSDB using tiered caching to minimize site load."""
        now = time.monotonic()

        # If data is cached within 1 hour TTL, reuse it immediately without hitting NWSDB
        if self._cached_data and (
            now - self._last_balance_fetch_time < CACHE_TTL_SECONDS
        ):
            _LOGGER.debug(
                "NWSDB Bill (%s): Using cached data to prevent overloading portal (%d seconds remaining in TTL)",
                self.account_number,
                int(CACHE_TTL_SECONDS - (now - self._last_balance_fetch_time)),
            )
            return self._cached_data

        try:
            # Refresh static consumer metadata only once a week (or on first run)
            if not self._cached_metadata or (
                now - self._last_metadata_fetch_time > METADATA_CACHE_TTL_SECONDS
            ):
                meta = await self.hass.async_add_executor_job(
                    fetch_nwsdb_account_details, self.account_number
                )
                if meta:
                    self._cached_metadata = meta
                    self._last_metadata_fetch_time = time.monotonic()

            # Query live bill portal directly via requests (no browser needed)
            portal_data = await self.hass.async_add_executor_job(
                fetch_nwsdb_portal_sync, self.account_number
            )

            # Merge portal data with cached metadata
            merged_data = {
                **self._cached_metadata,
                **portal_data,
                "last_synced": datetime.now().isoformat(),
            }

            self._cached_data = merged_data
            self._last_balance_fetch_time = time.monotonic()
            return merged_data
        except Exception as err:
            if self._cached_data:
                _LOGGER.warning(
                    "Error refreshing NWSDB data: %s. Using cached data.", err
                )
                return self._cached_data
            raise UpdateFailed(f"Error communicating with NWSDB: {err}") from err
