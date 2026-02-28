"""Fresh-r integration constants."""
DOMAIN           = "fresh_r"
MANUFACTURER     = "Fresh-r"
MODEL            = "OTW + Filter"
DEFAULT_POLL     = 60      # seconds
MIN_POLL         = 30

# API
API_URL     = "https://dashboard.bw-log.com/api.php"
API_BASE    = "https://dashboard.bw-log.com"

# Login: tried in sequence until success
LOGIN_URLS = [
    "https://www.fresh-r.me/login/index.php",
    "https://www.fresh-r.me/",
    "https://dashboard.bw-log.com/?page=login",
]

# API field list (current data only — historical data is not available via Fresh-R.me)
FIELDS_NOW = [
    "date", "t1", "t2", "t3", "t4", "flow", "co2", "hum", "dp",
    "d5_25", "d4_25", "d4_03", "d5_03", "d5_1", "d4_1", "d1_25", "d1_03", "d1_1",
]

# Flow calibration (dashboard.js: ESP mode correction)
# Raw flow > 300 → calibrated = (raw - 700) / 30 + 20
FLOW_THRESHOLD = 300
FLOW_OFFSET    = 700
FLOW_DIVISOR   = 30
FLOW_BASE      = 20

# Physics constants (dashboard_data.js)
AIR_HEAT_CAP   = 1212   # J/(m³·K)
REF_FLOW       = 75     # m³/h mechanical ventilation reference

# MQTT
MQTT_STATE_TOPIC = "fresh_r/{device_id}/state"
MQTT_AVAIL_TOPIC = "fresh_r/{device_id}/availability"
MQTT_DISC_PREFIX = "homeassistant"

# InfluxDB
INFLUX_MEASUREMENT = "fresh_r"

# Sensor definitions — (api_field_or_None, friendly_name, unit, device_class, state_class, icon)
# device_class / state_class as strings to avoid import at module level
# api_field=None means value is taken by sensor key from parsed data (derived or calibrated)
SENSORS = {
    # Raw sensors — mapped to API response field names
    "t1":     ("t1",    "Indoor Temperature",     "°C",      "temperature",    "measurement", "mdi:home-thermometer"),
    "t2":     ("t2",    "Outdoor Temperature",    "°C",      "temperature",    "measurement", "mdi:thermometer"),
    "t3":     ("t3",    "Supply Temperature",     "°C",      "temperature",    "measurement", "mdi:thermometer-chevron-up"),
    "t4":     ("t4",    "Exhaust Temperature",    "°C",      "temperature",    "measurement", "mdi:thermometer-chevron-down"),
    "flow":   (None,    "Flow Rate",              "m³/h",    None,             "measurement", "mdi:air-filter"),
    "co2":    ("co2",   "CO2",                    "ppm",     "carbon_dioxide", "measurement", "mdi:molecule-co2"),
    "hum":    ("hum",   "Humidity",               "%",       "humidity",       "measurement", "mdi:water-percent"),
    "dp":     ("dp",    "Dew Point",              "°C",      "temperature",    "measurement", "mdi:water-thermometer"),
    # PM sensors
    "d5_25":  ("d5_25", "Supply PM2.5",           "µg/m³",   "pm25",           "measurement", "mdi:blur"),
    "d4_25":  ("d4_25", "Outdoor PM2.5",          "µg/m³",   "pm25",           "measurement", "mdi:blur"),
    "d1_25":  ("d1_25", "Indoor PM2.5",           "µg/m³",   "pm25",           "measurement", "mdi:blur"),
    "d5_03":  ("d5_03", "Supply PM0.3",           "#/0.1l",  None,             "measurement", "mdi:blur-radial"),
    "d4_03":  ("d4_03", "Outdoor PM0.3",          "#/0.1l",  None,             "measurement", "mdi:blur-radial"),
    "d1_03":  ("d1_03", "Indoor PM0.3",           "#/0.1l",  None,             "measurement", "mdi:blur-radial"),
    "d5_1":   ("d5_1",  "Supply PM1.0",           "µg/m³",   None,             "measurement", "mdi:blur-linear"),
    "d4_1":   ("d4_1",  "Outdoor PM1.0",          "µg/m³",   None,             "measurement", "mdi:blur-linear"),
    "d1_1":   ("d1_1",  "Indoor PM1.0",           "µg/m³",   None,             "measurement", "mdi:blur-linear"),
    # Derived (calculated from physics formulas)
    "heat_recovered": (None, "Heat Recovered",    "W",       "power",          "measurement", "mdi:heat-wave"),
    "vent_loss":      (None, "Ventilation Loss",  "W",       "power",          "measurement", "mdi:transmission-tower"),
    "energy_loss":    (None, "Energy Loss",       "W",       "power",          "measurement", "mdi:lightning-bolt"),
}
