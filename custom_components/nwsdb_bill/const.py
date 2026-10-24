"""Constants for the National Water Supply and Drainage Board (NWSDB) Bill integration."""

DOMAIN = "nwsdb_bill"
CONF_ACCOUNT_NUMBER = "account_number"
CONF_CDP_HOST = "cdp_host"
CONF_CDP_PORT = "cdp_port"
CONF_SCAN_INTERVAL_HOURS = "scan_interval_hours"

DEFAULT_SCAN_INTERVAL_HOURS = 24
MIN_SCAN_INTERVAL_HOURS = 12
DEFAULT_CDP_HOST = "127.0.0.1"
DEFAULT_CDP_PORT = 9222
CACHE_TTL_SECONDS = 3600  # 1 hour minimum between network calls
METADATA_CACHE_TTL_SECONDS = 86400 * 7  # 7 days for static consumer metadata (name, meter no, area)
