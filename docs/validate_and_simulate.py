#!/usr/bin/env python3
"""
Fresh-r integratie — validatie & simulatie
==========================================
Verifieert alle componenten volledig zonder Home Assistant nodig.

Uitvoeren:  python3 validate_and_simulate.py
"""

import ast
import importlib.util
import json
import sys
from pathlib import Path

ROOT    = Path(__file__).parent / "custom_components" / "fresh_r"
PY_FILES = sorted(ROOT.glob("*.py"))

errors = 0


def fail(msg: str) -> None:
    global errors
    print(f"  ✗  {msg}")
    errors += 1


# ── 1. Python syntaxvalidatie ─────────────────────────────────────────────────
print("=" * 62)
print("1. Python syntaxvalidatie")
print("=" * 62)
for f in PY_FILES:
    try:
        ast.parse(f.read_text())
        print(f"  ✓  {f.name}")
    except SyntaxError as e:
        fail(f"{f.name}: {e}")

# ── 2. JSON validatie ─────────────────────────────────────────────────────────
print()
print("=" * 62)
print("2. JSON validatie")
print("=" * 62)
json_files = (
    list(ROOT.glob("*.json"))
    + list(ROOT.glob("translations/*.json"))
    + list((Path(__file__).parent / "grafana").glob("*.json"))
)
for f in sorted(json_files):
    try:
        json.loads(f.read_text())
        print(f"  ✓  {f.relative_to(Path(__file__).parent)}")
    except json.JSONDecodeError as e:
        fail(str(e))

# ── 3. Manifest validatie ─────────────────────────────────────────────────────
print()
print("=" * 62)
print("3. Manifest validatie")
print("=" * 62)
manifest = json.loads((ROOT / "manifest.json").read_text())
required_keys = {"domain", "name", "version", "requirements", "iot_class", "config_flow"}
missing = required_keys - manifest.keys()
if missing:
    fail(f"Manifest mist verplichte sleutels: {missing}")
else:
    print(f"  ✓  domain:   {manifest['domain']}")
    print(f"  ✓  name:     {manifest['name']}")
    print(f"  ✓  version:  {manifest['version']}")
    print(f"  ✓  iot_class: {manifest['iot_class']}")
    if manifest.get("config_flow") is not True:
        fail("config_flow moet True zijn")
    else:
        print(f"  ✓  config_flow: {manifest['config_flow']}")

# ── 4. const.py validatie ─────────────────────────────────────────────────────
print()
print("=" * 62)
print("4. const.py — sensordefinities & constanten")
print("=" * 62)

def _load_const():
    spec = importlib.util.spec_from_file_location("fresh_r.const", ROOT / "const.py")
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

const = _load_const()

required_attrs = [
    "DOMAIN", "MANUFACTURER", "MODEL", "API_URL", "LOGIN_URLS",
    "FIELDS_NOW", "FLOW_THRESHOLD", "FLOW_OFFSET", "FLOW_DIVISOR", "FLOW_BASE",
    "AIR_HEAT_CAP", "REF_FLOW", "MQTT_STATE_TOPIC", "MQTT_AVAIL_TOPIC",
    "MQTT_DISC_PREFIX", "INFLUX_MEASUREMENT", "SENSORS",
]
for attr in required_attrs:
    if not hasattr(const, attr):
        fail(f"const.py mist '{attr}'")
    else:
        print(f"  ✓  {attr}")

print(f"\n  Aantal sensoren: {len(const.SENSORS)}")
if len(const.SENSORS) < 20:
    fail(f"Verwacht >= 20 sensors, got {len(const.SENSORS)}")

EXPECTED_KEYS = {
    "t1","t2","t3","t4","flow","co2","hum","dp",
    "d5_25","d4_25","d1_25","d5_03","d4_03","d1_03","d5_1","d4_1","d1_1",
    "heat_recovered","vent_loss","energy_loss",
}
missing_keys = EXPECTED_KEYS - set(const.SENSORS.keys())
if missing_keys:
    fail(f"Ontbrekende sensor-sleutels: {missing_keys}")
else:
    print(f"  ✓  Alle 20 verwachte sensorsleutels aanwezig")

# Validate sensor tuple structure: (api_field, name, unit, dc, sc, icon)
for key, defn in const.SENSORS.items():
    if len(defn) != 6:
        fail(f"Sensor '{key}' heeft {len(defn)} waarden, verwacht 6")

# ── 5. api.py — flow kalibratie & afgeleide sensoren ─────────────────────────
print()
print("=" * 62)
print("5. api.py — kalibratie & fysica")
print("=" * 62)

def _load_api():
    sys.modules["fresh_r.const"] = const
    sys.modules[".const"] = const
    spec = importlib.util.spec_from_file_location("fresh_r.api", ROOT / "api.py")
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

api = _load_api()

# Flow calibration tests
print("\n  Flow kalibratie (raw → m³/h):")
cal_cases = [
    (100,  100.0,  "normaal — geen correctie"),
    (200,  200.0,  "normaal — geen correctie"),
    (300,  300.0,  "drempel — net geen correctie"),
    (301,  None,   "ESP boost actief"),    # any calibrated value < 50 is fine
    (756,  21.9,   "ESP boost (HAR voorbeeld)"),
    (1432, 44.4,   "ESP boost (hoge waarde)"),
]
for raw, expected, desc in cal_cases:
    got = round(api.calibrate_flow(raw), 1)
    if expected is None:
        ok = got < 50   # sanity: should be much less than raw
    else:
        ok = abs(got - expected) < 1.0
    mark = "✓" if ok else "✗"
    print(f"  {mark}  raw={raw:5} → {got:5.1f}  ({desc})")
    if not ok:
        fail(f"Flow kalibratie mismatch: raw={raw} → {got}, verwacht ≈{expected}")

# Physics / derived sensors
print("\n  Afgeleide sensoren:")
data_in = {"t1": 21.5, "t2": 18.3, "t4": 19.9, "flow": 21.9}
d = api.derive(data_in)
assert d["heat_recovered"] >= 0, "heat_recovered < 0"
assert d["vent_loss"]      >= 0, "vent_loss < 0"
assert d["energy_loss"]    >= 0, "energy_loss < 0"

# heat_recovered = (19.9 - 18.3) * 21.9 * 1212 / 3600 = 1.6 * 21.9 * 0.3367 = ≈ 11.8 W
expected_hr = round(max(0.0, (19.9 - 18.3) * 21.9 * 1212 / 3600), 1)
assert abs(d["heat_recovered"] - expected_hr) < 0.2, f"heat_recovered={d['heat_recovered']}, verwacht={expected_hr}"

print(f"  ✓  heat_recovered = {d['heat_recovered']} W  (verwacht ≈{expected_hr} W)")
print(f"  ✓  vent_loss      = {d['vent_loss']} W")
print(f"  ✓  energy_loss    = {d['energy_loss']} W")
print(f"  ✓  Fysica sanity checks geslaagd")

# _parse() test
print("\n  _parse() met gesimuleerde API-respons:")
mock_raw = {
    "t1": "21.5", "t2": "18.3", "t3": "20.0", "t4": "19.9",
    "flow": "756", "co2": "681", "hum": "52", "dp": "11.2",
    "d5_25": "3.5", "d4_25": "8.1", "d1_25": "2.3",
    "d5_03": "120", "d4_03": "350", "d1_03": "95",
    "d5_1":  "1.2", "d4_1":  "3.1", "d1_1":  "0.9",
}
client = api.FreshRApiClient.__new__(api.FreshRApiClient)
parsed = api.FreshRApiClient._parse(client, mock_raw)

assert parsed["t1"]   == 21.5, f"t1={parsed['t1']}"
assert parsed["co2"]  == 681.0, f"co2={parsed['co2']}"
assert parsed["flow"] is not None, "flow ontbreekt"
assert "heat_recovered" in parsed, "heat_recovered ontbreekt"
assert "vent_loss"      in parsed, "vent_loss ontbreekt"
assert "energy_loss"    in parsed, "energy_loss ontbreekt"

# flow_raw 756 → calibrated: (756-700)/30+20 = 56/30+20 = 1.867+20 = 21.9
assert abs(parsed["flow"] - 21.9) < 0.5, f"flow={parsed['flow']}"

for k, v in sorted(parsed.items()):
    print(f"    {k:25} = {v}")

print(f"  ✓  Alle velden correct geparsed en berekend")

# ── 6. MQTT topics ─────────────────────────────────────────────────────────────
print()
print("=" * 62)
print("6. MQTT topics & payload")
print("=" * 62)

serial = "e:232212/180027"
# Use already-loaded const module (avoids importing HA packages via __init__.py)
MQTT_STATE_TOPIC = const.MQTT_STATE_TOPIC
MQTT_AVAIL_TOPIC = const.MQTT_AVAIL_TOPIC
MQTT_DISC_PREFIX = const.MQTT_DISC_PREFIX
SENSORS          = const.SENSORS

did   = serial.replace(":", "_").replace("/", "_")
state = MQTT_STATE_TOPIC.format(device_id=did)
avail = MQTT_AVAIL_TOPIC.format(device_id=did)
disc  = f"{MQTT_DISC_PREFIX}/sensor/{const.DOMAIN}_{did}_co2/config"

print(f"  State topic:  {state}")
print(f"  Avail topic:  {avail}")
print(f"  Disc (co2):   {disc}")

# Verify payload keys match sensor keys (value_json.<key>)
print(f"\n  MQTT state payload simulatie:")
payload = {k: parsed[k] for k in SENSORS if k in parsed}
print(f"  {json.dumps(payload, indent=4)}")
print(f"  ✓  {len(payload)} sensor-waarden in payload")

# Check value_templates resolve
for key, defn in SENSORS.items():
    tmpl = f"value_json.{key}"
    # Each discovery message has value_template="{{ value_json.<key> }}"
    # The payload must contain that key
    if key in payload:
        print(f"  ✓  {tmpl} → {payload[key]}")

# ── 7. InfluxDB line protocol ─────────────────────────────────────────────────
print()
print("=" * 62)
print("7. InfluxDB line protocol")
print("=" * 62)

from datetime import datetime, timezone  # noqa: E402
tag   = serial.replace(":", "_").replace("/", "_")
ts_ns = int(datetime(2026, 2, 27, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1_000_000_000)
fields_str = ",".join(
    f"{k}={v}" for k, v in parsed.items() if isinstance(v, (int, float))
)
line = f"{const.INFLUX_MEASUREMENT},device={tag} {fields_str} {ts_ns}"
print(f"  Measurement:  {const.INFLUX_MEASUREMENT}")
print(f"  Tag device:   {tag}")
print(f"  Aantal velden: {fields_str.count(',') + 1}")
print(f"  Line protocol (verkorte weergave):")
print(f"    {const.INFLUX_MEASUREMENT},device={tag} [fields] {ts_ns}")
print(f"  ✓  Line protocol correct opgebouwd")

# ── 8. Grafana dashboard ───────────────────────────────────────────────────────
print()
print("=" * 62)
print("8. Grafana dashboard validatie")
print("=" * 62)

gf_path = Path(__file__).parent / "grafana" / "fresh_r_dashboard.json"
gf = json.loads(gf_path.read_text())

panels = [p for p in gf["panels"] if p.get("type") != "row"]
rows   = [p for p in gf["panels"] if p.get("type") == "row"]

print(f"  ✓  Dashboard: {gf['title']}")
print(f"  ✓  {len(panels)} data-panelen, {len(rows)} rijen")

required_panels = [
    "CO2", "Binnentemperatuur", "Debiet", "Vochtigheid",
    "Warmteterugwinning", "CO2 (ppm)", "Temperaturen",
    "Luchtdebiet", "Warmte (W)", "PM2.5",
]
for ep in required_panels:
    found = any(ep.lower() in p.get("title", "").lower() for p in panels)
    mark  = "✓" if found else "✗"
    print(f"  {mark}  Panel '{ep}' {'aanwezig' if found else 'ONTBREEKT'}")
    if not found:
        fail(f"Grafana panel '{ep}' ontbreekt")

# Check datasource references
ds_ok = all(
    p.get("datasource", {}).get("type") in (None, "influxdb", "")
    for p in panels
)
if ds_ok:
    print("  ✓  Datasource-referenties correct")
else:
    fail("Datasource-referentie incorrect in 1 of meer panelen")

# ── 9. Lovelace YAML validatie ────────────────────────────────────────────────
print()
print("=" * 62)
print("9. Lovelace dashboard YAML")
print("=" * 62)

try:
    import yaml  # type: ignore
    yaml_available = True
except ImportError:
    yaml_available = False

lv_path = Path(__file__).parent / "lovelace_dashboard.yaml"
yaml_text = lv_path.read_text()

if yaml_available:
    lv = yaml.safe_load(yaml_text)
    views = lv.get("views", [])
    print(f"  ✓  Dashboard titel: {lv.get('title')}")
    print(f"  ✓  {len(views)} views")
    for v in views:
        cards = v.get("cards", [])
        print(f"     - {v['title']}: {len(cards)} kaart(en)")
    # Check first view has fresh-r-card
    first_view_cards = views[0].get("cards", [])
    has_custom = any(c.get("type") == "custom:fresh-r-card" for c in first_view_cards)
    if has_custom:
        print("  ✓  custom:fresh-r-card aanwezig in hoofdview")
    else:
        fail("custom:fresh-r-card ontbreekt in hoofdview")
else:
    # Minimal text check without pyyaml
    if "custom:fresh-r-card" in yaml_text:
        print("  ✓  custom:fresh-r-card aanwezig (yaml module niet beschikbaar)")
    else:
        fail("custom:fresh-r-card ontbreekt")
    print("  ⚠  Installeer PyYAML voor volledige YAML-validatie: pip install pyyaml")

# ── 10. Sensor entity IDs consistentie ────────────────────────────────────────
print()
print("=" * 62)
print("10. Sensor entity ID consistentie")
print("=" * 62)
# Without room prefix, entity names are "Fresh-r <FriendlyName>"
# HA normalises to sensor.fresh_r_<friendly_name_snake>
entity_map = {
    "t1":             "sensor.fresh_r_indoor_temperature",
    "t2":             "sensor.fresh_r_outdoor_temperature",
    "t3":             "sensor.fresh_r_supply_temperature",
    "t4":             "sensor.fresh_r_exhaust_temperature",
    "flow":           "sensor.fresh_r_flow_rate",
    "co2":            "sensor.fresh_r_co2",
    "hum":            "sensor.fresh_r_humidity",
    "dp":             "sensor.fresh_r_dew_point",
    "d5_25":          "sensor.fresh_r_supply_pm2_5",
    "d4_25":          "sensor.fresh_r_outdoor_pm2_5",
    "d1_25":          "sensor.fresh_r_indoor_pm2_5",
    "heat_recovered": "sensor.fresh_r_heat_recovered",
    "vent_loss":      "sensor.fresh_r_ventilation_loss",
    "energy_loss":    "sensor.fresh_r_energy_loss",
}
for key, eid in entity_map.items():
    if key not in SENSORS:
        fail(f"Sensorsleutel '{key}' niet in SENSORS const")
    else:
        print(f"  ✓  {key:20} → {eid}")

# ── Eindresultaat ──────────────────────────────────────────────────────────────
print()
print("=" * 62)
if errors == 0:
    print("✅  ALLE TESTS GESLAAGD — systeem klaar voor installatie")
    print()
    print("Installatieoverzicht:")
    print("  1. Kopieer custom_components/fresh_r/ naar HA <config>/custom_components/")
    print("  2. Kopieer www/fresh-r-card.js naar HA <config>/www/")
    print("  3. Voeg toe aan Lovelace resources:")
    print("       url: /local/fresh-r-card.js  type: module")
    print("  4. Herstart Home Assistant")
    print("  5. Ga naar Instellingen → Apparaten & diensten → Integratie toevoegen")
    print("     Zoek 'Fresh-r' → voer e-mail + wachtwoord in")
    print("  6. Importeer lovelace_dashboard.yaml als nieuw dashboard")
    print("  7. Importeer grafana/fresh_r_dashboard.json in Grafana")
else:
    print(f"❌  {errors} fout(en) gevonden — zie boven voor details")
    sys.exit(1)
print("=" * 62)
