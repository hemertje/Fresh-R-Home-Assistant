"""Fresh-r DataUpdateCoordinator with optional InfluxDB write."""
from __future__ import annotations

import logging
from datetime import timedelta, datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FreshRApiClient, FreshRAuthError, FreshRConnectionError
from .const import DOMAIN, INFLUX_MEASUREMENT

_LOGGER = logging.getLogger(__name__)


class FreshRCoordinator(DataUpdateCoordinator):
    """Polls one Fresh-r device and optionally writes to InfluxDB."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: FreshRApiClient,
        serial: str,
        device_info: dict,
        poll_interval: int,
        mqtt_enabled: bool = True,
        influx_enabled: bool = False,
        influx_host: str = "localhost",
        influx_port: int = 8086,
        influx_db: str = "homeassistant",
        influx_token: str = "",
        influx_org: str = "",
        influx_username: str = "",
        influx_password: str = "",
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{serial}",
            update_interval=timedelta(seconds=poll_interval),
        )
        self.client         = client
        self.serial         = serial
        self.device_info    = device_info
        self.mqtt_enabled   = mqtt_enabled
        self.influx_enabled   = influx_enabled
        self.influx_host      = influx_host
        self.influx_port      = influx_port
        self.influx_db        = influx_db
        self.influx_token     = influx_token
        self.influx_org       = influx_org
        self.influx_username  = influx_username
        self.influx_password  = influx_password

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data from Fresh-R API with automatic token refresh."""
        try:
            # Ensure token is valid before making API call
            # This will refresh the token if it's older than 50 minutes
            await self.client.async_ensure_token_valid()
            
            # Now fetch current data
            data = await self.client.async_get_current(self.serial)
        except FreshRAuthError as e:
            raise UpdateFailed(f"Auth: {e}") from e
        except FreshRConnectionError as e:
            raise UpdateFailed(f"Connection: {e}") from e

        if not data:
            raise UpdateFailed("Empty response from Fresh-r API")

        if self.influx_enabled:
            self.hass.async_create_task(self._write_influx(data))

        return data

    async def _write_influx(self, data: dict[str, Any]) -> None:
        """Write a data point to InfluxDB (v1 line protocol, v2 also supported)."""
        try:
            import aiohttp as _aio

            tag   = self.serial.replace(":", "_").replace("/", "_")
            ts_ns = int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)

            fields = ",".join(
                f"{k}={v}"
                for k, v in data.items()
                if isinstance(v, (int, float))
            )
            if not fields:
                return

            line = f"{INFLUX_MEASUREMENT},device={tag} {fields} {ts_ns}"

            if self.influx_token:
                # InfluxDB v2
                url     = f"http://{self.influx_host}:{self.influx_port}/api/v2/write"
                headers = {
                    "Authorization": f"Token {self.influx_token}",
                    "Content-Type":  "text/plain; charset=utf-8",
                }
                params  = {
                    "org":       self.influx_org,
                    "bucket":    self.influx_db,
                    "precision": "ns",
                }
            else:
                # InfluxDB v1
                url     = f"http://{self.influx_host}:{self.influx_port}/write"
                headers = {"Content-Type": "text/plain; charset=utf-8"}
                params  = {"db": self.influx_db, "precision": "ns"}
                if self.influx_username:
                    params["u"] = self.influx_username
                    params["p"] = self.influx_password

            async with _aio.ClientSession() as sess:
                async with sess.post(
                    url,
                    data=line.encode(),
                    headers=headers,
                    params=params,
                    timeout=_aio.ClientTimeout(total=5),
                ) as r:
                    if r.status not in (200, 204):
                        body = await r.text()
                        _LOGGER.warning(
                            "InfluxDB write failed HTTP %s: %s", r.status, body[:200]
                        )
                    else:
                        _LOGGER.debug(
                            "InfluxDB: wrote %d field(s) for %s",
                            fields.count(",") + 1,
                            self.serial,
                        )

        except Exception as e:  # noqa: BLE001
            _LOGGER.warning("InfluxDB write error: %s", e)
