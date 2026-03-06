# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2024-03-05

### Added
- Complete browser automation with Selenium for automatic login
- Distributed token refresh with randomized timing (0-10 min offset) to prevent server overload
- Exponential backoff with jitter for retry logic
- 20+ sensors including PM2.5, PM1.0, PM0.3, temperature, CO2, humidity
- MQTT auto-discovery and state publishing
- InfluxDB export support
- Lovelace dashboard with calendar/date picker
- Grafana dashboards (overview and details)
- HACS compatibility
- Automatic dependency setup script (setup_selenium.sh)
- Comprehensive FAQ in English

### Changed
- Complete rewrite of authentication system
- Migrated from legacy API to dashboard scraping with session tokens
- Updated coordinator to check token validity before each API call

### Security
- Session tokens are never hardcoded
- Distributed refresh prevents thundering herd attacks on Fresh-R servers
- No credentials stored in code

## [1.0.0] - 2023-01-15

### Added
- Initial release
- Basic API integration
- Sensor platform with 10 sensors
- Config flow for UI configuration

[2.0.0]: https://github.com/custom-components/fresh-r/releases/tag/v2.0.0
[1.0.0]: https://github.com/custom-components/fresh-r/releases/tag/v1.0.0
