#!/usr/bin/env python3
"""Backfill EV laadkosten offsets na reboot of handmatige reset.

Herstelt offset/opgebouwd helpers uit live integrators + kWh-verhouding
(vandaag vs live sinds dashboard). Overschrijft geen integrator-cumulatieven.

Token: HA_TOKEN / HOMEASSISTANT_TOKEN, of ~/.cursor/mcp.json (home-assistant).

  python3 scripts/ev_backfill_laadkosten.py --dry-run
  python3 scripts/ev_backfill_laadkosten.py
  python3 scripts/ev_backfill_laadkosten.py --force
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Amsterdam")
MCP_JSON = Path.home() / ".cursor" / "mcp.json"
RECORDER_DAYS = 7

ENTITY_LOAD = "sensor.thuislader_jeroen_laadvermogen"
ENTITY_PV = "sensor.solaredge_huidig_vermogen"
ENTITY_PRICE = "sensor.hemertje_elektriciteitsprijs"
ENTITY_PRICE_FALLBACK = "sensor.nordpool_kwh_nl_eur_5_09_0"
SENSOR_METER_KWH = "sensor.thuislader_jeroen_meterwaarde"
INPUT_LIVE_START = "input_datetime.ev_kosten_live_start"
INPUT_METER_LIVE = "input_number.ev_meter_kwh_bij_live_start"
INPUT_LIVE_OPG = "input_number.ev_kosten_live_opgebouwd_eur"
INPUT_OFFSET = "input_number.ev_kosten_integrator_offset_eur"
INPUT_TL_OPG = "input_number.ev_gemiste_teruglever_opgebouwd_eur"
INPUT_TL_OFFSET = "input_number.ev_gemiste_teruglever_offset_eur"
INPUT_START = "input_datetime.ev_thuisladen_start"
INTEGRATOR = "sensor.ev_kosten_net_cum_eur"
INTEGRATOR_TL = "sensor.ev_gemiste_teruglever_cum_eur"
SENSOR_VANDAAG_KWH = "sensor.ev_geladen_vandaag"
SENSOR_LIVE_KWH = "sensor.ev_kwh_live_sinds_dashboard"

LOAD_MIN_W = 100.0
STEP = timedelta(minutes=5)
DEFAULT_PRICE = 0.28
ZONDAG_HOUR_START = 11
ZONDAG_HOUR_END = 19
NIGHT_HOUR_START = 0
NIGHT_HOUR_END = 7
ZONDAG_WEIGHT = 0.75
INPUT_ZONDAG_SEED = "input_number.ev_laadprijs_zondag_seed"
INPUT_NACHT_SEED = "input_number.ev_laadprijs_nacht_seed"


@dataclass
class Point:
    t: datetime
    v: float


@dataclass
class PeriodResult:
    kwh_net: float
    kwh_zon: float
    cost_eur: float


def load_ha_credentials(url_override: str | None = None) -> tuple[str, str]:
    url = (url_override or os.environ.get("HA_URL") or "").rstrip("/")
    token = os.environ.get("HA_TOKEN") or os.environ.get("HOMEASSISTANT_TOKEN") or ""
    if MCP_JSON.is_file():
        data = json.loads(MCP_JSON.read_text())
        env = data.get("mcpServers", {}).get("home-assistant", {}).get("env", {})
        if not url:
            url = env.get("HOMEASSISTANT_URL", "http://192.168.2.5:8123").rstrip("/")
        if not token:
            token = env.get("HOMEASSISTANT_TOKEN", "")
    if not url:
        url = "http://192.168.2.5:8123"
    return url, token


def ha_request(
    base: str, token: str, method: str, path: str, body: dict | None = None
) -> object:
    url = f"{base.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def parse_ts(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def history(base: str, token: str, entity: str, start: datetime, end: datetime) -> list[Point]:
    q = urllib.parse.urlencode(
        {
            "filter_entity_id": entity,
            "minimal_response": "true",
            "no_attributes": "true",
        }
    )
    start_utc = start.astimezone(ZoneInfo("UTC")).isoformat()
    path = f"/api/history/period/{urllib.parse.quote(start_utc)}?{q}"
    rows = ha_request(base, token, "GET", path)
    if not rows or not rows[0]:
        return []
    out: list[Point] = []
    for row in rows[0]:
        try:
            v = float(row.get("state", 0))
        except (TypeError, ValueError):
            continue
        out.append(Point(parse_ts(row["last_changed"]), v))
    out.sort(key=lambda p: p.t)
    return out


def value_at(points: list[Point], t: datetime, default: float = 0.0) -> float:
    if not points:
        return default
    v = default
    for p in points:
        if p.t > t:
            break
        v = p.v
    return v


def midnight_local(d: date) -> datetime:
    return datetime.combine(d, time(0, 0), tzinfo=TZ)


def state_float(by_id: dict, entity_id: str, default: float = 0.0) -> float:
    raw = by_id.get(entity_id, {}).get("state", default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def avg_price(price_h: list[Point]) -> float:
    vals = [p.v for p in price_h if p.v > 0]
    return sum(vals) / len(vals) if vals else DEFAULT_PRICE


def in_laadvenster(t: datetime) -> str | None:
    if t.weekday() == 6 and ZONDAG_HOUR_START <= t.hour < ZONDAG_HOUR_END:
        return "zondag"
    if NIGHT_HOUR_START <= t.hour < NIGHT_HOUR_END:
        return "nacht"
    return None


def laadprofiel_avg(price_h: list[Point]) -> tuple[float, float, float]:
    z_vals: list[float] = []
    n_vals: list[float] = []
    for p in price_h:
        if p.v <= 0:
            continue
        slot = in_laadvenster(p.t)
        if slot == "zondag":
            z_vals.append(p.v)
        elif slot == "nacht":
            n_vals.append(p.v)
    az = sum(z_vals) / len(z_vals) if z_vals else 0.0
    an = sum(n_vals) / len(n_vals) if n_vals else 0.0
    if z_vals and n_vals:
        combined = ZONDAG_WEIGHT * az + (1 - ZONDAG_WEIGHT) * an
    else:
        combined = az or an or DEFAULT_PRICE
    return az, an, combined


def compute_meter_delta_cost(
    meter_h: list[Point],
    price_h: list[Point],
    start: datetime,
    end: datetime,
    fallback_price: float,
) -> tuple[float, float]:
    """kWh en EUR uit meterstappen × Tibber op moment van laden."""
    kwh = 0.0
    cost = 0.0
    for i in range(1, len(meter_h)):
        t0, m0 = meter_h[i - 1]
        t1, m1 = meter_h[i]
        if t1 <= start or t0 >= end:
            continue
        dk = max(0.0, m1 - m0)
        if dk <= 0:
            continue
        price = value_at(price_h, t1, default=0.0)
        if price <= 0:
            price = fallback_price
        kwh += dk
        cost += dk * price
    return kwh, cost


def compute_period(
    load_h: list[Point],
    pv_h: list[Point],
    price_h: list[Point],
    start: datetime,
    end: datetime,
    fallback_price: float,
) -> PeriodResult:
    kwh_net = 0.0
    kwh_zon = 0.0
    cost_eur = 0.0
    t = start
    while t < end:
        t_next = min(t + STEP, end)
        dt_h = (t_next - t).total_seconds() / 3600.0
        load_w = value_at(load_h, t)
        if load_w > LOAD_MIN_W:
            load_kw = load_w / 1000.0
            pv_kw = value_at(pv_h, t) / 1000.0
            price = value_at(price_h, t, default=0.0)
            if price <= 0:
                price = value_at(price_h, t_next, default=fallback_price)
            grid_kw = max(load_kw - pv_kw, 0.0)
            solar_kw = min(load_kw, pv_kw)
            kwh_net += grid_kw * dt_h
            kwh_zon += solar_kw * dt_h
            cost_eur += grid_kw * price * dt_h
        t = t_next
    return PeriodResult(kwh_net, kwh_zon, cost_eur)


def proportional_opgebouwd(cum: float, live_kwh: float, vandaag_kwh: float) -> float:
    if live_kwh <= 0.01:
        return 0.0
    kwh_voor = max(live_kwh - vandaag_kwh, 0.0)
    return round(cum * kwh_voor / live_kwh, 2)


def needs_offset_fix(
    cum: float, offset: float, opg: float, live_kwh: float, vandaag_kwh: float
) -> bool:
    return (
        cum > 0.01
        and offset < 0.001
        and opg < 0.001
        and live_kwh > vandaag_kwh + 0.5
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Herstel EV kosten offsets uit integrators (na reboot)"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Altijd herberekenen")
    parser.add_argument("--url", default=None)
    args = parser.parse_args()
    base, token = load_ha_credentials(args.url)
    if not token:
        print(
            "Geen token: HA_TOKEN, HOMEASSISTANT_TOKEN, of ~/.cursor/mcp.json (home-assistant).",
            file=sys.stderr,
        )
        return 1

    states = ha_request(base, token, "GET", "/api/states")
    by_id = {s["entity_id"]: s for s in states}

    cum = state_float(by_id, INTEGRATOR)
    cum_tl = state_float(by_id, INTEGRATOR_TL)
    off = state_float(by_id, INPUT_OFFSET)
    opg = state_float(by_id, INPUT_LIVE_OPG)
    off_tl = state_float(by_id, INPUT_TL_OFFSET)
    opg_tl = state_float(by_id, INPUT_TL_OPG)
    live_kwh = state_float(by_id, SENSOR_LIVE_KWH)
    vandaag_kwh = state_float(by_id, SENSOR_VANDAAG_KWH)
    meter = state_float(by_id, SENSOR_METER_KWH)

    opgebouwd = proportional_opgebouwd(cum, live_kwh, vandaag_kwh)
    opgebouwd_tl = proportional_opgebouwd(cum_tl, live_kwh, vandaag_kwh)
    vandaag_kosten = round(cum - opgebouwd, 2)
    vandaag_tl = round(cum_tl - opgebouwd_tl, 2)

    fix_kosten = args.force or needs_offset_fix(cum, off, opg, live_kwh, vandaag_kwh)
    fix_tl = args.force or needs_offset_fix(cum_tl, off_tl, opg_tl, live_kwh, vandaag_kwh)

    print("=== EV offset herstel (integrator-first) ===")
    print(f"  Live kWh:           {live_kwh:.2f}")
    print(f"  Vandaag kWh:        {vandaag_kwh:.2f}")
    print(f"  Integrator kosten:  €{cum:.4f}  (offset €{off:.4f}, opg €{opg:.2f})")
    print(f"  → opgebouwd:        €{opgebouwd:.2f}  vandaag: €{vandaag_kosten:.2f}")
    print(f"  Integrator teruglev: €{cum_tl:.4f}  (offset €{off_tl:.4f}, opg €{opg_tl:.2f})")
    print(f"  → opgebouwd:        €{opgebouwd_tl:.2f}  vandaag: €{vandaag_tl:.2f}")
    print(f"  Zaptec meter:       {meter:.3f} kWh")

    if not fix_kosten and not fix_tl:
        print("\nGeen actie nodig — offsets lijken correct.")
        return 0

    if args.dry_run:
        print("\n[dry-run] Zou instellen:")
        if fix_kosten:
            print(f"  {INPUT_LIVE_OPG} = {opgebouwd}")
            print(f"  {INPUT_OFFSET} = {opgebouwd}")
        if fix_tl:
            print(f"  {INPUT_TL_OPG} = {opgebouwd_tl}")
            print(f"  {INPUT_TL_OFFSET} = {opgebouwd_tl}")
        return 0

    updates: list[tuple[str, float]] = []
    if fix_kosten:
        updates.extend(
            [(INPUT_LIVE_OPG, opgebouwd), (INPUT_OFFSET, opgebouwd)]
        )
    if fix_tl:
        updates.extend(
            [(INPUT_TL_OPG, opgebouwd_tl), (INPUT_TL_OFFSET, opgebouwd_tl)]
        )

    for eid, val in updates:
        ha_request(
            base,
            token,
            "POST",
            "/api/services/input_number/set_value",
            {"entity_id": eid, "value": val},
        )
        print(f"  ingesteld: {eid} = {val}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
