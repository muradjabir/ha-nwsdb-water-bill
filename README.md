# NWSDB Water Bill (Sri Lanka) - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/default)
[![GitHub release](https://img.shields.io/github/v/release/muradjabir/ha-nwsdb-water-bill?style=for-the-badge)](https://github.com/muradjabir/ha-nwsdb-water-bill/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

Track your **National Water Supply & Drainage Board (NWSDB)** water bill balance and connection status directly in Home Assistant.

---

## Features

- **Automated Tracking:** Fetches current outstanding balance and account status daily.
- **Config Flow Setup:** Easy UI configuration directly in Home Assistant (Settings -> Devices & Services -> Add Integration).
- **Rich Account Information:**
  - `account_number`: Your 14-character NWSDB account format (`00/00/000/000/00`)
  - `customer_name`: Consumer name registered with NWSDB
  - `meter_number`: Water meter serial number
  - `area`: Supply region & service area
  - `category`: Connection category (e.g. Domestic, Commercial)
  - `status`: Connection status (Active, Notice, etc.)
  - `unit_of_measurement`: `LKR`
  - `device_class`: `monetary`

---

## Installation

### Method 1: Via HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed in your Home Assistant.
2. In Home Assistant, open **HACS** > **Integrations**.
3. Click the **three dots** in the top right corner and select **Custom repositories**.
4. Paste the repository URL:
   ```text
   https://github.com/muradjabir/ha-nwsdb-water-bill
   ```
5. Select Category: **Integration** and click **Add**.
6. Search for **NWSDB Water Bill (Sri Lanka)** and click **Download**.
7. Restart Home Assistant.

### Method 2: Manual Installation

1. Download the latest release `.zip` or clone this repository.
2. Copy the `custom_components/nwsdb_bill` directory into your Home Assistant `<config_dir>/custom_components/` folder.
3. Restart Home Assistant.

---

## Configuration

1. In Home Assistant, navigate to **Settings** > **Devices & Services**.
2. Click **Add Integration** in the bottom right corner.
3. Search for **NWSDB Water Bill (Sri Lanka)**.
4. Enter your NWSDB Account Number (e.g. `22/28/206/006/17`) and submit.
5. A new sensor `sensor.water_bill_balance` will be created under your NWSDB water account device.

---

## Example Automation: Bill Change Notification

Get an alert on your phone when your water bill changes:

```yaml
alias: "NWSDB Water Bill Notification"
description: "Notify when water bill balance changes"
trigger:
  - platform: state
    entity_id: sensor.nwsdb_account_22_28_206_006_17_water_bill_balance
condition:
  - condition: template
    value_template: >-
      {{ trigger.from_state is not none and
         trigger.to_state is not none and
         trigger.from_state.state not in ['unavailable', 'unknown'] and
         trigger.to_state.state not in ['unavailable', 'unknown'] and
         trigger.from_state.state != trigger.to_state.state }}
action:
  - service: notify.notify
    data:
      title: "Water Bill Updated"
      message: >-
        Your NWSDB water bill changed from {{ trigger.from_state.state }} LKR to {{ trigger.to_state.state }} LKR.
mode: single
```

---

## Disclaimer

This integration is an independent open-source project and is not officially affiliated with, endorsed by, or sponsored by the National Water Supply and Drainage Board (NWSDB).

---

## License

[MIT License](LICENSE)
