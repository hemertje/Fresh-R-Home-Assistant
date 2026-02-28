"""Fresh-r config flow — email/password only, serial auto-discovered."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, DEFAULT_POLL, MIN_POLL

_LOGGER = logging.getLogger(__name__)

CONF_EMAIL          = "email"
CONF_PASSWORD       = "password"
CONF_POLL           = "poll_interval"
CONF_MQTT           = "mqtt_enabled"
CONF_INFLUX         = "influx_enabled"
CONF_INFLUX_HOST    = "influx_host"
CONF_INFLUX_PORT    = "influx_port"
CONF_INFLUX_DB      = "influx_db"
CONF_INFLUX_TOKEN   = "influx_token"
CONF_INFLUX_ORG     = "influx_org"

SCHEMA = vol.Schema({
    vol.Required(CONF_EMAIL):                              str,
    vol.Required(CONF_PASSWORD):                           str,
    vol.Optional(CONF_POLL,         default=DEFAULT_POLL): vol.All(int, vol.Range(min=MIN_POLL)),
    vol.Optional(CONF_MQTT,         default=True):         bool,
    vol.Optional(CONF_INFLUX,       default=False):        bool,
    vol.Optional(CONF_INFLUX_HOST,  default="localhost"):  str,
    vol.Optional(CONF_INFLUX_PORT,  default=8086):         int,
    vol.Optional(CONF_INFLUX_DB,    default="homeassistant"): str,
    vol.Optional(CONF_INFLUX_TOKEN, default=""):           str,
    vol.Optional(CONF_INFLUX_ORG,   default=""):           str,
})


class FreshRConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                from .api import FreshRApiClient, FreshRAuthError
                session = async_get_clientsession(self.hass)
                client  = FreshRApiClient(
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                    session,
                )
                await client.async_login()
                devices = await client.async_discover_devices()

                if not devices:
                    errors["base"] = "no_devices"
                else:
                    await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Fresh-r ({user_input[CONF_EMAIL]})",
                        data={**user_input, "devices": devices},
                    )

            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Config flow error: %s", err)
                msg = str(err).lower()
                if "auth" in msg or "credentials" in msg or "login failed" in msg:
                    errors["base"] = "invalid_auth"
                elif "connection" in msg or "timeout" in msg:
                    errors["base"] = "cannot_connect"
                else:
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=SCHEMA,
            errors=errors,
        )
