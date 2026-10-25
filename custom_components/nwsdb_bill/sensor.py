"""Sensor platform for NWSDB Water Bill integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_ACCOUNT_NUMBER
from .coordinator import NWSDBBillCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the NWSDB sensors from config entry."""
    coordinator: NWSDBBillCoordinator = hass.data[DOMAIN][entry.entry_id]
    account_no = entry.data[CONF_ACCOUNT_NUMBER]

    async_add_entities(
        [
            NWSDBBillSensor(coordinator, account_no, entry.entry_id),
            NWSDBConnectionStatusSensor(coordinator, account_no, entry.entry_id),
        ]
    )


class NWSDBBillSensor(CoordinatorEntity[NWSDBBillCoordinator], SensorEntity):
    """Representation of NWSDB Water Bill Balance Sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "water_balance"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "LKR"
    _attr_icon = "mdi:water-pump"

    def __init__(
        self,
        coordinator: NWSDBBillCoordinator,
        account_number: str,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_number = account_number
        self._attr_unique_id = f"nwsdb_bill_{account_number.replace('/', '_')}"
        self._attr_name = "Water Bill Balance"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account_number)},
            name=f"NWSDB Account {account_number}",
            manufacturer="National Water Supply and Drainage Board",
            model="Water Account",
            entry_type=None,
        )

    @property
    def native_value(self) -> float | None:
        """Return the current balance (negative if credit balance, positive if amount due)."""
        if self.coordinator.data:
            return self.coordinator.data.get("balance")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity attributes."""
        if not self.coordinator.data:
            return {}
        return {
            "account_number": self._account_number,
            "customer_name": self.coordinator.data.get("customer_name"),
            "address": self.coordinator.data.get("address"),
            "meter_number": self.coordinator.data.get("meter_no"),
            "area": self.coordinator.data.get("area"),
            "category": self.coordinator.data.get("category"),
            "status": self.coordinator.data.get("status"),
            "account_status": self.coordinator.data.get("account_status"),
            "is_credit": self.coordinator.data.get("is_credit"),
            "raw_amount": self.coordinator.data.get("raw_amount"),
            "status_message": self.coordinator.data.get("status_message"),
            "last_synced": self.coordinator.data.get("last_synced"),
        }


class NWSDBConnectionStatusSensor(
    CoordinatorEntity[NWSDBBillCoordinator], SensorEntity
):
    """Representation of NWSDB Connection Status Sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "connection_status"

    def __init__(
        self,
        coordinator: NWSDBBillCoordinator,
        account_number: str,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_number = account_number
        self._attr_unique_id = f"nwsdb_status_{account_number.replace('/', '_')}"
        self._attr_name = "Connection Status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account_number)},
            name=f"NWSDB Account {account_number}",
            manufacturer="National Water Supply and Drainage Board",
            model="Water Account",
            entry_type=None,
        )

    @property
    def native_value(self) -> str:
        """Return the current connection or notice status."""
        if not self.coordinator.data:
            return "Unknown"
        acc_status = self.coordinator.data.get("account_status")
        # Surface specific notices/warnings (e.g. "Notice 2 Sent") prominently
        if acc_status and acc_status.strip().lower() not in ("normal", "active", ""):
            return acc_status.strip()
        return self.coordinator.data.get("status") or "Active"

    @property
    def icon(self) -> str:
        """Return dynamic icon based on status."""
        val = self.native_value.lower()
        if "notice" in val or "warn" in val or "pending" in val:
            return "mdi:water-alert"
        if "disconnect" in val or "inactive" in val:
            return "mdi:water-off"
        if "active" in val or "normal" in val:
            return "mdi:water-check"
        return "mdi:water"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity attributes."""
        if not self.coordinator.data:
            return {}
        return {
            "account_number": self._account_number,
            "connection_status": self.coordinator.data.get("status"),
            "account_status": self.coordinator.data.get("account_status"),
            "customer_name": self.coordinator.data.get("customer_name"),
            "meter_number": self.coordinator.data.get("meter_no"),
            "area": self.coordinator.data.get("area"),
            "category": self.coordinator.data.get("category"),
            "address": self.coordinator.data.get("address"),
            "last_synced": self.coordinator.data.get("last_synced"),
        }
