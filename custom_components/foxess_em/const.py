"""Constants for foxess_em."""

# Base component constants
from enum import Enum

NAME = "foxess_em"
DOMAIN = "foxess_em"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "1.8.0"

ISSUE_URL = "https://github.com/nathanmarlor/foxess_em/issues"

# Icons
ICON = "mdi:format-quote-close"

# Platforms
SENSOR = "sensor"
SWITCH = "switch"
CALENDAR = "calendar"
NUMBER = "number"
PLATFORMS = [SENSOR, SWITCH, CALENDAR, NUMBER]
ATTR_ENTRY_TYPE = "entry_type"

# Configuration and options
SOLCAST_API_KEY = "key"
SOLCAST_SCAN_INTERVAL = "scan_interval"
# SOLCAST_URL = "https://364c31d2-231a-4a41-a7ee-6b0f357fdb75.mock.pstmn.io"
SOLCAST_URL = "https://api.solcast.com.au"

FORECAST = "sensor.foxess_em_forecast"

# Fox Options
CONNECTION_TYPE = "connection_type"
FOX_MODBUS_TCP = "Modbus TCP"
FOX_MODBUS_SERIAL = "Modbus Serial"
FOX_MODBUS_HOST = "fox_modbus_host"
FOX_MODBUS_PORT = "fox_modbus_port"
FOX_MODBUS_SLAVE = "fox_modbus_slave"
FOX_CLOUD = "Fox Cloud"
FOX_API_KEY = "fox_api_key"

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
CHARGE_AMPS = "charge_amps"
BATTERY_VOLTS = "battery_volts"


# Connection types
class Connection(Enum):
    BOTH = "both"
    MODBUS = "modbus"
    CLOUD = "cloud"


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
