# Fresh-r Home Assistant Integration

A Home Assistant custom integration that **reads** data from the [Fresh-r.me](https://fresh-r.me) cloud dashboard and replicates it inside Home Assistant — including a custom Lovelace card, MQTT publishing, InfluxDB writing, and a Grafana dashboard.

> **Read-only** — Active ventilation control is not possible. This is a firmware limitation of the Fresh-r device; the Fresh-r.me dashboard does not expose control endpoints.
>
> **No historical data** — The Fresh-r.me database cannot be queried. Home Assistant's own recorder builds history going forward from the moment the integration is active.

---

## Features

| Feature | Details |
|---|---|
| **Login** | E-mail + password (serial number discovered automatically) |
| **Polling** | Configurable interval (default 60 s, minimum 30 s) |
| **Sensors** | 20 sensors: temperatures, flow, CO2, humidity, dew point, PM0.3/1.0/2.5, heat recovery, energy loss |
| **MQTT** | Auto-discovery + JSON state topic (compatible with any MQTT broker) |
| **InfluxDB** | Line-protocol write (v1 and v2 supported) |
| **Lovelace card** | Radial 24-hour clock + 3 tab views + live stats bar |
| **Grafana** | Ready-to-import dashboard JSON |

---

## Sensors

| Key | Friendly name | Unit | Source |
|---|---|---|---|
| `t1` | Indoor Temperature | °C | API |
| `t2` | Outdoor Temperature | °C | API |
| `t3` | Supply Temperature | °C | API |
| `t4` | Exhaust Temperature | °C | API |
| `flow` | Flow Rate | m³/h | API + calibration |
| `co2` | CO2 | ppm | API |
| `hum` | Humidity | % | API |
| `dp` | Dew Point | °C | API |
| `d5_25` | Supply PM2.5 | µg/m³ | API |
| `d4_25` | Outdoor PM2.5 | µg/m³ | API |
| `d1_25` | Indoor PM2.5 | µg/m³ | API |
| `d5_03` | Supply PM0.3 | #/0.1l | API |
| `d4_03` | Outdoor PM0.3 | #/0.1l | API |
| `d1_03` | Indoor PM0.3 | #/0.1l | API |
| `d5_1` | Supply PM1.0 | µg/m³ | API |
| `d4_1` | Outdoor PM1.0 | µg/m³ | API |
| `d1_1` | Indoor PM1.0 | µg/m³ | API |
| `heat_recovered` | Heat Recovered | W | Derived |
| `vent_loss` | Ventilation Loss (ref) | W | Derived |
| `energy_loss` | Energy Loss | W | Derived |

**Flow calibration** (ESP boost-mode correction from `dashboard.js`):
```
raw > 300  →  calibrated = (raw − 700) / 30 + 20
```

**Derived sensor physics** (from `dashboard_data.js`):
```
heat_recovered = max(0, (t4 − t2) × flow  × 1212 / 3600)  W
vent_loss      = max(0, (t1 − t2) × 75    × 1212 / 3600)  W  (ref 75 m³/h)
energy_loss    = max(0, (t1 − t4) × flow  × 1212 / 3600)  W
```

---

## Repository Structure

```
fresh_r.zip/
├── fresh-r/                    # Home Assistant integration
│   ├── custom_components/fresh_r/  # Integration code
│   │   ├── __init__.py
│   │   ├── api.py                 # HTTP client: login, device discovery
│   │   ├── config_flow.py         # UI config flow
│   │   ├── const.py               # Constants and sensor definitions
│   │   ├── coordinator.py         # DataUpdateCoordinator
│   │   ├── manifest.json
│   │   ├── mqtt.py                # MQTT publishing
│   │   ├── sensor.py              # HA sensor entities
│   │   ├── strings.json
│   │   └── translations/
│   │       ├── en.json
│   │       └── nl.json
│   └── www/                       # Lovelace card
│       ├── fresh-r-card.js
│       └── fresh-r-dashboard.yaml
├── grafana/
│   └── fresh_r_dashboard.json     # Grafana dashboard (import-ready)
├── docs/                          # Documentation
│   ├── FAQ_EN.md
│   └── FAQ_NL.md
├── README.md
└── LICENSE
```

---

## Installation

### 0 — Download

Download `fresh_r.zip` from the [latest release](https://github.com/hemertje/Fresh-R-Home-Assistant/releases/latest) and extract it. This creates a `fresh-r/` folder containing Home Assistant files, and a `grafana/` folder with the dashboard.

### 1 — Copy the custom component

```bash
cp -r fresh-r/custom_components/fresh_r  <HA-config>/custom_components/
```

### 2 — Install the Lovelace card

```bash
cp -r fresh-r/www/fresh-r-card.js  <HA-config>/www/
```

Add the resource via **Settings → Dashboards → Resources → Add resource**:

| Field | Value |
|---|---|
| URL | `/local/fresh-r-card.js` |
| Resource type | `JavaScript module` |

Or add it manually in `configuration.yaml`:

```yaml
lovelace:
  resources:
    - url: /local/fresh-r-card.js
      type: module
```

### 3 — Restart Home Assistant

### 4 — Add the integration

**Settings → Devices & Services → Add Integration → Fresh-r**

| Field | Value |
|---|---|
| E-mail | Your fresh-r.me e-mail address |
| Password | Your fresh-r.me password |
| Poll interval | Seconds between updates (default: 60, min: 30) |
| Publish to MQTT | Enable MQTT auto-discovery and state updates |
| Write to InfluxDB | Enable InfluxDB line-protocol writes |
| InfluxDB host | Hostname/IP of your InfluxDB instance |
| InfluxDB port | Default: 8086 |
| Database / bucket | Database name (v1) or bucket name (v2) |
| InfluxDB token | Leave empty for v1; required for v2 |
| InfluxDB org | Required for v2 only |
| InfluxDB username | Optional — only for v1 with authentication |
| InfluxDB password | Optional — only for v1 with authentication |

The device serial number is **discovered automatically** — you never need to enter it.

### 5 — Import the dashboards

**Home Assistant Lovelace**
1. Create a new dashboard: Settings → Dashboards → Add Dashboard
2. Click the three dots menu → Edit dashboard
3. Click three dots again → Raw configuration editor
4. Paste the contents from the `fresh-r/www/fresh-r-dashboard.yaml` file

**Grafana**
1. Dashboards → Import → Upload JSON file
2. Select `grafana/fresh_r_dashboard.json` (from the extracted ZIP root)
3. Choose your InfluxDB datasource

---

## MQTT Topics

```
fresh_r/<device_id>/availability   →  "online" / "offline"
fresh_r/<device_id>/state          →  JSON with all 20 sensor values
homeassistant/sensor/fresh_r_<device_id>_<key>/config  →  HA auto-discovery
```

**Example state payload:**
```json
{
  "t1": 21.5, "t2": 8.3, "t3": 20.1, "t4": 18.9,
  "flow": 21.9, "co2": 681.0, "hum": 52.0, "dp": 11.2,
  "d5_25": 3.5, "d4_25": 8.1, "d1_25": 2.3,
  "d5_03": 120.0, "d4_03": 350.0, "d1_03": 95.0,
  "d5_1": 1.2, "d4_1": 3.1, "d1_1": 0.9,
  "heat_recovered": 11.8, "vent_loss": 80.8, "energy_loss": 11.8
}
```

---

## Lovelace Card — `custom:fresh-r-card`

```yaml
type: custom:fresh-r-card
entities:
  t1:             sensor.fresh_r_indoor_temperature
  t2:             sensor.fresh_r_outdoor_temperature
  t3:             sensor.fresh_r_supply_temperature
  t4:             sensor.fresh_r_exhaust_temperature
  flow:           sensor.fresh_r_flow_rate
  co2:            sensor.fresh_r_co2
  hum:            sensor.fresh_r_humidity
  dp:             sensor.fresh_r_dew_point
  d5_25:          sensor.fresh_r_supply_pm2_5
  d4_25:          sensor.fresh_r_outdoor_pm2_5
  d1_25:          sensor.fresh_r_indoor_pm2_5
  heat_recovered: sensor.fresh_r_heat_recovered
  vent_loss:      sensor.fresh_r_ventilation_loss
  energy_loss:    sensor.fresh_r_energy_loss
```

The card has three tab views matching the Fresh-r.me dashboard:

| Tab | Content |
|---|---|
| **Zuurstof** | Radial 24h clock (CO2 / flow / temperature) · Temperature chart · Flow chart · Heat chart |
| **Vochtigheid** | Radial clock · Humidity & dew point chart · Flow chart · CO2 chart |
| **Fijnstof** | Radial clock · PM2.5 chart · Flow chart · CO2 chart |

Line charts use Home Assistant's own recorder history (today's data, builds from the moment the integration is active).


---

## Authentication

Login flow (confirmed via browser DevTools):

```
1. GET  fresh-r.me/login/index.php?page=login
        → collect hidden CSRF fields from the login form

2. POST credentials (email + password + hidden fields)
        → server validates and returns HTTP 302

3. Redirect → dashboard.bw-log.com/?page=devices&t=<64-char-hex-token>
        → the token in the URL (?t=) is the session token

4. Token stored; all API calls use:
        POST dashboard.bw-log.com/api.php?q={"token":"<hex>","requests":{...}}

5. Serial number discovered automatically via the API (syssearch request)
```

The integration uses a **persistent `aiohttp.ClientSession`** for the lifetime of the config entry and follows all redirects automatically, so the token is captured from the final URL after login.

---

## Data Flow

```
fresh-r.me/login
     │
     │  POST email + password
     │  302 → dashboard.bw-log.com/?page=devices&t=<hex-token>
     ▼
dashboard.bw-log.com/api.php
     │
     │  HTTPS poll every 60 s
     │  {"token": "<hex>", "requests": {"current-data": {"request": "fresh-r-now", ...}}}
     ▼
  api._parse()          — calibrate flow, derive heat/energy sensors
     │
     ├──► HA sensor entities  (20 sensors, visible in HA UI)
     │
     ├──► MQTT broker          fresh_r/<device>/state  (JSON)
     │                         fresh_r/<device>/availability
     │                         homeassistant/sensor/.../config  (discovery)
     │
     └──► InfluxDB             fresh_r measurement, device tag
```

---

## Troubleshooting

**Login fails**

Enable debug logging in `configuration.yaml`:
```yaml
logger:
  default: warning
  logs:
    custom_components.fresh_r: debug
```
After restarting HA the log shows:
- `GET … hidden_fields=[...] action=…` — what fields the login form has
- `POST … final_url=…` — where the server redirected after login
- `cookies=[...]` — which cookies are present

A successful login shows `final_url` ending in `dashboard.bw-log.com/...&t=<hex>` and logs `Fresh-r authenticated (token=xxxxxxxx…)`.

If `final_url` still ends in `page=login`, the credentials are rejected by the server.

**No devices found after login**

The integration first tries the JSON API (`syssearch`), then falls back to scraping `dashboard.bw-log.com/?page=devices` for serial links. If both fail, enable debug logging and look for the `Devices page GET` line and the body snippet.

---

## Requirements

- Home Assistant 2024.1 or newer
- Python package: `aiohttp>=3.8.0` (installed automatically by HA)
- Optional: MQTT broker (e.g. Mosquitto add-on)
- Optional: InfluxDB v1 or v2 instance + Grafana

---

## License

See [LICENSE](LICENSE).
