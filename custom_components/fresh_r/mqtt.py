"""Fresh-r MQTT: Home Assistant auto-discovery + state publishing."""
from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.core import HomeAssistant

from .const import DOMAIN, MANUFACTURER, SENSORS, MQTT_STATE_TOPIC, MQTT_AVAIL_TOPIC, MQTT_DISC_PREFIX

_LOGGER = logging.getLogger(__name__)


def _did(serial: str) -> str:
    """Sanitise serial for use in MQTT topics and entity IDs."""
    return serial.replace(":", "_").replace("/", "_")


async def async_publish_discovery(hass: HomeAssistant, serial: str, device_info: dict) -> None:
    """Publish MQTT auto-discovery config for all sensors."""
    try:
        from homeassistant.components import mqtt
        if not await mqtt.async_wait_for_mqtt_client(hass):
            _LOGGER.warning("MQTT client not ready — discovery skipped")
            return
    except ImportError:
        _LOGGER.debug("MQTT component not loaded")
        return

    did         = _did(serial)
    state_topic = MQTT_STATE_TOPIC.format(device_id=did)
    avail_topic = MQTT_AVAIL_TOPIC.format(device_id=did)

    ha_device = {
        "identifiers": [f"{DOMAIN}_{did}"],
        "name":        f"Fresh-r {device_info.get('room') or serial}",
        "manufacturer": MANUFACTURER,
        "model":       device_info.get("type", "Fresh-r"),
    }

    for key, defn in SENSORS.items():
        _, friendly, unit, dc_str, sc_str, icon = defn
        # JSON state payload always uses the sensor key directly
        value_tmpl = f"{{{{ value_json.{key} }}}}"

        payload: dict[str, Any] = {
            "name":               friendly,
            "unique_id":          f"{DOMAIN}_{did}_{key}",
            "state_topic":        state_topic,
            "availability_topic": avail_topic,
            "value_template":     value_tmpl,
            "icon":               icon,
            "device":             ha_device,
        }
        if unit:
            payload["unit_of_measurement"] = unit
        if dc_str:
            payload["device_class"] = dc_str
        if sc_str:
            payload["state_class"] = sc_str

        disc_topic = f"{MQTT_DISC_PREFIX}/sensor/{DOMAIN}_{did}_{key}/config"
        await mqtt.async_publish(hass, disc_topic, json.dumps(payload), retain=True)

    _LOGGER.info("MQTT discovery published: %d sensors for %s", len(SENSORS), serial)


async def async_publish_state(hass: HomeAssistant, serial: str, data: dict[str, Any]) -> None:
    """Publish current sensor values as a JSON object to the state topic.

    The payload uses sensor *keys* (e.g. "t1", "flow", "heat_recovered") as
    JSON field names so that value_templates in discovery messages resolve
    correctly with ``{{ value_json.<key> }}``.
    """
    try:
        from homeassistant.components import mqtt
    except ImportError:
        return

    did         = _did(serial)
    state_topic = MQTT_STATE_TOPIC.format(device_id=did)
    avail_topic = MQTT_AVAIL_TOPIC.format(device_id=did)

    # Build payload from every sensor key present in the parsed data
    payload: dict[str, Any] = {
        key: data[key]
        for key in SENSORS
        if key in data and data[key] is not None
    }

    await mqtt.async_publish(hass, avail_topic, "online",            retain=True)
    await mqtt.async_publish(hass, state_topic, json.dumps(payload), retain=False)
    _LOGGER.debug("MQTT state published: %d value(s) for %s", len(payload), serial)


async def async_mark_offline(hass: HomeAssistant, serial: str) -> None:
    """Mark the device as offline in MQTT."""
    try:
        from homeassistant.components import mqtt
        avail_topic = MQTT_AVAIL_TOPIC.format(device_id=_did(serial))
        await mqtt.async_publish(hass, avail_topic, "offline", retain=True)
    except ImportError:
        pass
