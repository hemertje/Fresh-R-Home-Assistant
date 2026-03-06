# Fresh-R Home Assistant Integration

Complete Home Assistant integration for Fresh-R ventilation systems with automatic HTTP-based authentication.

## Features

- 🔐 **Automatic Login** - HTTP-based login every 50-60 minutes
- 📊 **20+ Sensors** - Temperature, CO2, humidity, PM2.5/1.0/0.3, flow, energy metrics
- 📈 **Dashboards** - Lovelace dashboard + Grafana dashboards included
- 📡 **MQTT Support** - Auto-discovery and state publishing
- 🗄️ **InfluxDB Export** - Optional data export
- 🌐 **Distributed Refresh** - Randomized token refresh prevents server overload
- 🚀 **Zero Dependencies** - 100% automatic installation via HACS

## Installation

### HACS (Recommended) - 100% Automatic!

1. Open HACS in Home Assistant
2. Click **Integrations** → **Explore & Download Repositories**
3. Search for **Fresh-R**
4. Click **Download**
5. That's it! No additional setup needed.

### Manual

1. Download the [latest release](https://github.com/custom-components/fresh-r/releases/latest)
2. Extract `fresh_r.zip`
3. Copy `custom_components/fresh_r/` to your Home Assistant `custom_components/` directory
4. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **Integrations**
2. Click **Add Integration**
3. Search for **Fresh-R**
4. Enter your Fresh-R credentials
5. Click **Submit**

The integration will automatically log in and start polling data every 60 seconds.

## Documentation

- [Full README](README.md)
- [FAQ](docs/FAQ_EN.md)
- [Changelog](CHANGELOG.md)

[![Open your Home Assistant instance and show the add integration dialog](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=fresh_r)
