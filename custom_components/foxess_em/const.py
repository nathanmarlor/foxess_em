"""Constants for foxess_em."""
# Base component constants
NAME = "foxess_em"
DOMAIN = "foxess_em"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "1.4.6"

ISSUE_URL = "https://github.com/nathanmarlor/foxess_em/issues"

# Icons
ICON = "mdi:format-quote-close"

# Platforms
SENSOR = "sensor"
SWITCH = "switch"
PLATFORMS = [SENSOR, SWITCH]
ATTR_ENTRY_TYPE = "entry_type"

# Configuration and options
SOLCAST_API_KEY = "key"
SOLCAST_SCAN_INTERVAL = "scan_interval"
# SOLCAST_URL = "https://091dad86-9afd-43a4-b29a-530be493c37a.mock.pstmn.io"
SOLCAST_URL = "https://api.solcast.com.au"
FOX_USERNAME = "fox_username"
FOX_PASSWORD = "fox_password"

# Battery options
HOUSE_POWER = "house_power"
AUX_POWER = "aux_power"
ECO_START_TIME = "eco_start_time"
ECO_END_TIME = "eco_end_time"
DAWN_BUFFER = "dawn_buffer"
DAY_BUFFER = "day_buffer"
MIN_SOC = "min_soc"
BATTERY_CAPACITY = "capacity"
BATTERY_SOC = "battery_soc"

# Defaults
DEFAULT_NAME = DOMAIN

STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
