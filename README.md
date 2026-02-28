# Fresh-r Home Assistant Integration

A Home Assistant custom integration that **reads** data from the [Fresh-r.me](https://fresh-r.me) cloud dashboard and replicates it inside Home Assistant — including a custom Lovelace card, MQTT publishing, InfluxDB writing, and a Grafana dashboard.

> **Read-only** — Active ventilation control is not possible. This is a firmware limitation of the Fresh-r device; the Fresh-r.me dashboard does not expose control endpoints.
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
Fresh-R-Home-Assistant/
├── custom_components/fresh_r/     # Home Assistant custom component
│   ├── __init__.py                #   Entry setup, MQTT init, coordinator wiring
│   ├── api.py                     #   HTTP client: login, device discovery, _parse()
│   ├── config_flow.py             #   UI config flow (email + password only)
│   ├── const.py                   #   All constants and sensor definitions
│   ├── coordinator.py             #   DataUpdateCoordinator + InfluxDB write
│   ├── mqtt.py                    #   MQTT auto-discovery + state publishing
│   ├── sensor.py                  #   HA sensor entity platform
│   ├── manifest.json
│   ├── strings.json
│   └── translations/
│       ├── nl.json
│       └── en.json
├── www/
│   └── fresh-r-card.js            # Custom Lovelace card
├── grafana/
│   └── fresh_r_dashboard.json     # Grafana dashboard (import-ready)
├── fresh_r_lovelace_dashboard.yaml # Home Assistant dashboard YAML
└── validate_and_simulate.py       # Offline validation + simulation script
```

---

## Installation

### 0 — Download

Download `fresh_r_system.zip` from the repository and extract it. This creates a `fresh-r/` folder containing all files.

### 1 — Copy the custom component

```bash
cp -r fresh-r/custom_components/fresh_r  <HA-config>/custom_components/
```

### 2 — Install the Lovelace card

```bash
cp www/fresh-r-card.js  <HA-config>/www/
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
1. Settings → Dashboards → Add Dashboard → Raw configuration editor
2. Paste the contents of `fresh_r_lovelace_dashboard.yaml`

**Grafana**
1. Dashboards → Import → Upload JSON file
2. Select `grafana/fresh_r_dashboard.json`
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

## Validation & Simulation

Run offline without Home Assistant to verify all components:

```bash
python3 validate_and_simulate.py
```

**10 test steps:**
1. Python syntax validation (all `.py` files)
2. JSON validation (manifest, strings, translations, Grafana)
3. Manifest required-fields check
4. `const.py` — all 20 sensor definitions present
5. `api.py` — flow calibration accuracy + physics formulas
6. MQTT topic generation + full 20-field payload simulation
7. InfluxDB line-protocol construction
8. Grafana dashboard — all required panels present
9. Lovelace YAML — views and `custom:fresh-r-card` present
10. Sensor entity ID consistency map

---

## Data Flow

```
Fresh-r.me API
     │
     │  HTTPS poll (every 60 s)
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

## Requirements

- Home Assistant 2024.1 or newer
- Python package: `aiohttp>=3.8.0` (installed automatically by HA)
- Optional: MQTT broker (e.g. Mosquitto add-on)
- Optional: InfluxDB v1 or v2 instance + Grafana

---

## License

See [LICENSE](LICENSE).
