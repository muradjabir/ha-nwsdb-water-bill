"""Constants for the National Water Supply and Drainage Board (NWSDB) Bill integration."""

DOMAIN = "nwsdb_bill"
CONF_ACCOUNT_NUMBER = "account_number"
CONF_SCAN_INTERVAL_HOURS = "scan_interval_hours"

DEFAULT_SCAN_INTERVAL_HOURS = 24
MIN_SCAN_INTERVAL_HOURS = 12
CACHE_TTL_SECONDS = 3600  # 1 hour minimum between portal network calls
METADATA_CACHE_TTL_SECONDS = 86400 * 7  # 7 days for static consumer metadata
