# Fresh-R Home Assistant Integration

<div align="center">

![Fresh-R Logo](https://fresh-r.me/images/logo.png)

# 🌬️ Fresh-R Home Assistant Integration

**Complete Home Assistant integration for Fresh-R ventilation systems**

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/custom-components/fresh-r)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2023.1+-blue.svg)](https://home-assistant.io)
[![HACS](https://img.shields.io/badge/HACS-Default-orange.svg)](https://hacs.xyz)

</div>

---

## 🎯 Overview

This integration connects your [Fresh-R](https://fresh-r.me) ventilation system to Home Assistant, providing real-time monitoring of air quality, temperature, humidity, and energy metrics.

**✅ 100% Automatic Installation** - No browser or system dependencies needed!

> **⚠️ Read-only**: Active ventilation control is not possible. This is a firmware limitation; the Fresh-R dashboard does not expose control endpoints.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔐 **Automatic Login** | HTTP-based login every 50-60 minutes |
| 📊 **20+ Sensors** | Temperature, CO2, humidity, PM2.5/1.0/0.3, flow, energy metrics |
| 📈 **Dashboards** | Lovelace dashboard + Grafana dashboards included |
| 📡 **MQTT Support** | Auto-discovery and state publishing to MQTT |
| 🗄️ **InfluxDB Export** | Optional data export for long-term storage |
| 🌐 **Distributed Refresh** | Randomized token refresh prevents server overload |
| 🚀 **Zero Dependencies** | No browser installation needed! |

---

## 📦 Installation

### Method 1: HACS (Recommended) - 100% Automatic!

1. Open HACS in Home Assistant
2. Click **Integrations** → **Explore & Download Repositories**
3. Search for **Fresh-R**
4. Click **Download**
5. **That's it!** No additional setup needed

### Method 2: Manual Installation

1. Download the [latest release](https://github.com/custom-components/fresh-r/releases/latest)
2. Extract `fresh_r.zip`
3. Copy `custom_components/fresh_r/` to your Home Assistant `custom_components/` directory
4. Restart Home Assistant

---

## ⚙️ Configuration

### UI Configuration (Recommended)

1. Go to **Settings** → **Devices & Services** → **Integrations**
2. Click **Add Integration**
3. Search for **Fresh-R**
4. Enter your credentials:
   - **Email**: Your Fresh-R account email
   - **Password**: Your Fresh-R account password
   - **Poll Interval**: How often to fetch data (default: 60 seconds)

5. Click **Submit**

The integration will:
- Log in to fresh-r.me via HTTP requests
- Extract the session token
- Start polling data every 60 seconds
- Refresh the token every 50-60 minutes

---

## 📊 Available Sensors

### Temperature Sensors
| Sensor | Unit | Description |
|--------|------|-------------|
| `t1` | °C | Indoor Temperature |
| `t2` | °C | Outdoor Temperature |
| `t3` | °C | Supply Temperature |
| `t4` | °C | Exhaust Temperature |
| `dp` | °C | Dew Point |

### Air Quality Sensors
| Sensor | Unit | Description |
|--------|------|-------------|
| `co2` | ppm | CO2 Level |
| `hum` | % | Relative Humidity |

### Particulate Matter (PM)
| Sensor | Unit | Description |
|--------|------|-------------|
| `d5_25` | µg/m³ | Supply PM2.5 |
| `d4_25` | µg/m³ | Outdoor PM2.5 |
| `d1_25` | µg/m³ | Indoor PM2.5 |
| `d5_1` | µg/m³ | Supply PM1.0 |
| `d4_1` | µg/m³ | Outdoor PM1.0 |
| `d1_1` | µg/m³ | Indoor PM1.0 |
| `d5_03` | #/0.1l | Supply PM0.3 |
| `d4_03` | #/0.1l | Outdoor PM0.3 |
| `d1_03` | #/0.1l | Indoor PM0.3 |

### Ventilation & Energy
| Sensor | Unit | Description |
|--------|------|-------------|
| `flow` | m³/h | Ventilation Flow Rate |
| `heat_recovered` | W | Heat Recovery |
| `vent_loss` | W | Ventilation Heat Loss |
| `energy_loss` | W | Total Energy Loss |

---

## 🎨 Dashboards

### Lovelace Dashboard

Import the included dashboard configuration:

1. Go to **Settings** → **Dashboards**
2. Click **Add Dashboard**
3. Choose **Raw configuration editor**
4. Copy the content from `homeassistant/lovelace/fresh_r_dashboard.yaml`
5. Click **Save**

### Grafana Dashboards

Two pre-configured dashboards are included in `grafana/dashboards/`:

- **overview.json**: Main dashboard with gauges
- **details.json**: Detailed sensor analysis

See [grafana/docs/GRAFANA_README.md](grafana/docs/GRAFANA_README.md) for installation.

---

## 🔐 How It Works

### Authentication Flow

```
Home Assistant Start
       ↓
HTTP POST to fresh-r.me/login
       ↓
Follow redirects automatically
       ↓
Extract sess_token from cookies
       ↓
Use token for API calls
       ↓
Refresh every 50-60 minutes
```

**No browser needed!** We just send HTTP requests with browser-like headers.

---

## 📡 MQTT Auto-Discovery

When MQTT is enabled, the integration automatically:

1. Publishes sensor configurations to `homeassistant/sensor/fresh_r_{id}_{sensor}/config`
2. Publishes current values to `fresh_r/{device_id}/state`
3. Updates availability status to `fresh_r/{device_id}/availability`

---

## 🐛 Troubleshooting

### "Login failed"
- Verify your Fresh-R credentials
- Check internet connectivity to fresh-r.me
- Check Home Assistant logs for details

### "No devices found"
- Check if devices are visible in the Fresh-R dashboard
- Verify your account has access to devices

### "Token expired"
- This is normal; the integration auto-refreshes
- If persistent, restart the integration

---

## 📚 Documentation

- [FAQ_EN.md](docs/FAQ_EN.md) - Frequently Asked Questions
- [FAQ_NL.md](docs/FAQ_NL.md) - Veelgestelde vragen (Nederlands)
- [CHANGELOG.md](docs/CHANGELOG.md) - Version history
- [GRAFANA_README.md](grafana/docs/GRAFANA_README.md) - Grafana setup

---

## 📝 License

This project is licensed under the MIT License.

---

<div align="center">

**⭐ Star this repo if you find it useful!**

</div>
