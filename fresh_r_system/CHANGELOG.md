# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2024-03-05

### Major Changes - HTTP-Only Implementation
- **REMOVED**: Selenium browser automation (no longer needed!)
- **REMOVED**: Chrome/Chromium dependency (no longer needed!)
- **REMOVED**: setup_selenium.sh script (no longer needed!)
- **ADDED**: Pure HTTP-based authentication using aiohttp
- **ADDED**: Browser-like headers for website requests
- **ADDED**: Automatic cookie handling for session tokens

### Benefits of v2.0.0
- **100% Automatic Installation** via HACS - no manual setup required!
- **Zero System Dependencies** - only requires aiohttp (included in HA)
- **Simpler Architecture** - HTTP requests instead of browser automation
- **Faster Login** - direct HTTP POST instead of browser loading
- **Lower Resource Usage** - no Chrome process overhead

### Added
- 20+ sensors including PM2.5, PM1.0, PM0.3, temperature, CO2, humidity, flow, energy metrics
- MQTT auto-discovery and state publishing
- InfluxDB export support
- Lovelace dashboard with calendar/date picker
- Grafana dashboards (overview and details)
- HACS compatibility with automatic installation
- Distributed token refresh with random offset (prevents server overload)
- Comprehensive FAQ in English and Dutch

### Changed
- Complete rewrite of authentication system (HTTP instead of browser)
- Updated api.py to use pure HTTP requests
- Simplified manifest.json (only aiohttp dependency)
- Updated all documentation for HTTP-only approach

### Security
- Session tokens handled via HTTP cookies
- Distributed refresh prevents thundering herd attacks
- No credentials stored in code

## [1.0.0] - 2023-01-15

### Added
- Initial release
- Basic API integration
- Sensor platform with 10 sensors
- Config flow for UI configuration

[2.0.0]: https://github.com/custom-components/fresh-r/releases/tag/v2.0.0
[1.0.0]: https://github.com/custom-components/fresh-r/releases/tag/v1.0.0
