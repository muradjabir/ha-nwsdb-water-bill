"""Config flow for NWSDB Water Bill integration."""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    CONF_ACCOUNT_NUMBER,
    CONF_SCAN_INTERVAL_HOURS,
    DEFAULT_SCAN_INTERVAL_HOURS,
    MIN_SCAN_INTERVAL_HOURS,
)
from .coordinator import (
    fetch_nwsdb_account_details,
    fetch_nwsdb_portal_sync,
    format_nwsdb_account,
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate user input by verifying account number format and reaching NWSDB."""
    raw_account = data[CONF_ACCOUNT_NUMBER].strip()
    account_no = format_nwsdb_account(raw_account)

    if not re.match(r"^\d{2}/\d{2}/\d{3}/\d{3}/\d{2}$", account_no):
        raise InvalidAccountNumber

    # Attempt to query account via portal or REST API
    details: dict[str, Any] = {}
    try:
        details = await hass.async_add_executor_job(
            fetch_nwsdb_account_details, account_no
        )
    except Exception:
        pass

    # If REST API didn't return metadata, verify directly with portal
    if not details:
        try:
            portal_info = await hass.async_add_executor_job(
                fetch_nwsdb_portal_sync, account_no
            )
            if portal_info:
                details = portal_info
        except Exception as err:
            raise CannotConnect from err

    title = f"NWSDB {account_no}"
    if details.get("customer_name"):
        title = f"Water ({details['customer_name']})"

    return {"title": title, "account_number": account_no}


class NWSDBConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NWSDB Water Bill."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get options flow for this handler."""
        return NWSDBOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_account = user_input[CONF_ACCOUNT_NUMBER].strip()
            formatted_acc = format_nwsdb_account(raw_account)
            await self.async_set_unique_id(formatted_acc)
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
                # Store normalized account number
                user_input[CONF_ACCOUNT_NUMBER] = formatted_acc
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAccountNumber:
                errors[CONF_ACCOUNT_NUMBER] = "invalid_account_number"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"

        schema = vol.Schema(
            {
                vol.Required(CONF_ACCOUNT_NUMBER): str,
                vol.Optional(
                    CONF_SCAN_INTERVAL_HOURS, default=DEFAULT_SCAN_INTERVAL_HOURS
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_HOURS)),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )


class NWSDBOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for NWSDB integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL_HOURS,
            self.config_entry.data.get(
                CONF_SCAN_INTERVAL_HOURS, DEFAULT_SCAN_INTERVAL_HOURS
            ),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL_HOURS,
                        default=current_interval,
                    ): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_HOURS)
                    ),
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAccountNumber(HomeAssistantError):
    """Error to indicate account number is invalid."""
