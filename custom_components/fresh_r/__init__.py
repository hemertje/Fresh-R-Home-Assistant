"""Fresh-r Home Assistant integration — read-only cloud polling."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FreshRApiClient
from .coordinator import FreshRCoordinator
from .const import DOMAIN
from .config_flow import (
    CONF_EMAIL, CONF_PASSWORD, CONF_POLL,
    CONF_MQTT, CONF_INFLUX, CONF_INFLUX_HOST, CONF_INFLUX_PORT,
    CONF_INFLUX_DB, CONF_INFLUX_TOKEN, CONF_INFLUX_ORG,
    CONF_INFLUX_USER, CONF_INFLUX_PASS,
)

_LOGGER   = logging.getLogger(__name__)
PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    
    data    = entry.data
    session = async_get_clientsession(hass)

    client = FreshRApiClient(
        email      = data[CONF_EMAIL],
        password   = data[CONF_PASSWORD],
        ha_session = session,
        hass       = hass,  # Enable session persistence
    )

    try:
        await client.async_login()
        devices = data.get("devices") or await client.async_discover_devices()
    except Exception as err:
        _LOGGER.error("Fresh-r setup failed: %s", err)
        return False

    if not devices:
        _LOGGER.error("No Fresh-r devices found for %s", data[CONF_EMAIL])
        return False

    coordinators: list[FreshRCoordinator] = []

    for device in devices:
        coord = FreshRCoordinator(
            hass           = hass,
            client         = client,
            serial         = device["id"],
            device_info    = device,
            poll_interval  = data.get(CONF_POLL, 60),
            mqtt_enabled   = data.get(CONF_MQTT, True),
            influx_enabled = data.get(CONF_INFLUX, False),
            influx_host    = data.get(CONF_INFLUX_HOST, "localhost"),
            influx_port    = data.get(CONF_INFLUX_PORT, 8086),
            influx_db      = data.get(CONF_INFLUX_DB, "homeassistant"),
            influx_token    = data.get(CONF_INFLUX_TOKEN, ""),
            influx_org      = data.get(CONF_INFLUX_ORG, ""),
            influx_username = data.get(CONF_INFLUX_USER, ""),
            influx_password = data.get(CONF_INFLUX_PASS, ""),
        )
        await coord.async_config_entry_first_refresh()
        coordinators.append(coord)

        # MQTT: publish auto-discovery + current state
        if data.get(CONF_MQTT, True):
            try:
                from .mqtt import async_publish_discovery, async_publish_state

                await async_publish_discovery(hass, device["id"], device)

                async def _on_update(c=coord):
                    if c.data:
                        await async_publish_state(hass, c.serial, c.data)

                coord.async_add_listener(_on_update)
                if coord.data:
                    await async_publish_state(hass, device["id"], coord.data)

            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("MQTT init error (non-fatal): %s", err)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client":       client,
        "coordinators": coordinators,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, {})
        for coord in entry_data.get("coordinators", []):
            try:
                from .mqtt import async_mark_offline
                await async_mark_offline(hass, coord.serial)
            except Exception:  # noqa: BLE001
                pass
    return ok
