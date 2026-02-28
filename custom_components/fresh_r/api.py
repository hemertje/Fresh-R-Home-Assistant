"""Fresh-r API client — read-only, current data only.

Authentication flow (observed via browser):
  - Login: POST credentials to fresh-r.me → HTTP 302 → dashboard.bw-log.com/?page=devices
    PHPSESSID cookie is set on dashboard.bw-log.com during this redirect chain.
  - There is NO separate hex token — auth is purely cookie-based (PHPSESSID).
  - The persistent session (cookie jar) MUST be reused for all subsequent API calls
    so the PHPSESSID is sent automatically on the same domain.
  - Serial: extracted from the devices page href (e.g. ?serial=e:XXXXXX/XXXXXX)

API (dashboard_data.js):
  POST https://dashboard.bw-log.com/api.php?q=<JSON>
  JSON body includes token (PHPSESSID value or empty), tzoffset, requests dict.

Flow calibration (dashboard.js):
  raw > 300 → calibrated = (raw - 700) / 30 + 20  (ESP boost mode correction)

Derived sensors (dashboard_data.js physics):
  heat_recovered = max(0, (t4 - t2) × flow × 1212 / 3600)  W
  vent_loss      = max(0, (t1 - t2) × 75   × 1212 / 3600)  W  (ref 75 m³/h)
  energy_loss    = max(0, (t1 - t4) × flow × 1212 / 3600)  W
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, parse_qs, urlparse

import aiohttp

from .const import (
    API_URL, API_BASE, LOGIN_URLS,
    FIELDS_NOW,
    FLOW_THRESHOLD, FLOW_OFFSET, FLOW_DIVISOR, FLOW_BASE,
    AIR_HEAT_CAP, REF_FLOW,
)

_LOGGER     = logging.getLogger(__name__)
_TOKEN_RE   = re.compile(r'^[0-9a-f]{32,}$', re.I)
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Serial pattern: e.g. "e:XXXXXX/XXXXXX" or just digits
_SERIAL_RE = re.compile(r'serial=([^&"\'>\s]+)', re.I)


class FreshRAuthError(Exception):
    """Login failed — bad credentials or service unreachable."""


class FreshRConnectionError(Exception):
    """Network or API error."""


# ── Helpers ────────────────────────────────────────────────────────────────────

def calibrate_flow(raw: float) -> float:
    """Apply ESP mode flow correction (from dashboard.js)."""
    if raw > FLOW_THRESHOLD:
        return (raw - FLOW_OFFSET) / FLOW_DIVISOR + FLOW_BASE
    return raw


def derive(data: dict[str, float]) -> dict[str, float]:
    """Calculate physics-based derived sensors (dashboard_data.js)."""
    t1   = data.get("t1", 0.0)
    t2   = data.get("t2", 0.0)
    t4   = data.get("t4", 0.0)
    flow = data.get("flow", 0.0)
    return {
        "heat_recovered": round(max(0.0, (t4 - t2) * flow  * AIR_HEAT_CAP / 3600), 1),
        "vent_loss":      round(max(0.0, (t1 - t2) * REF_FLOW * AIR_HEAT_CAP / 3600), 1),
        "energy_loss":    round(max(0.0, (t1 - t4) * flow  * AIR_HEAT_CAP / 3600), 1),
    }


def _token_in_jar(jar: aiohttp.CookieJar) -> str | None:
    """Return the first cookie value that looks like a hex session token."""
    # First: check well-known names
    for c in jar:
        if c.key.lower().replace("-", "_") in ("sess_token", "token", "session_token", "l", "sid"):
            if _TOKEN_RE.match(c.value):
                return c.value
    # Fallback: any cookie whose value is pure lowercase hex 32+ chars
    for c in jar:
        if _TOKEN_RE.match(c.value):
            _LOGGER.debug("Using token from cookie '%s'", c.key)
            return c.value
    return None


def _phpsessid_from_jar(jar: aiohttp.CookieJar) -> str | None:
    """Return the PHPSESSID value from the cookie jar."""
    for c in jar:
        if c.key.upper() == "PHPSESSID":
            return c.value
    return None


def _token_in_html(html: str) -> str | None:
    """Scan page HTML/JS for session token assignments (e.g. var token = '...')."""
    for pat in (
        r"""['"]?(?:sess_token|token|session_token|l)['"]?\s*[:=]\s*['"]([0-9a-fA-F]{32,})['"]""",
        r"""token['"]\s*:\s*['"]([0-9a-fA-F]{32,})['"]""",
    ):
        m = re.search(pat, html, re.I)
        if m:
            return m.group(1)
    return None


def _js_redirect(html: str) -> str | None:
    """Find a JavaScript or meta-refresh redirect URL in page HTML."""
    for pat in (
        r"""(?:window\.location\.href|window\.location|location\.href)\s*=\s*['"]([^'"]+)['"]""",
        r"""<meta[^>]+http-equiv=['"]\s*refresh\s*['"][^>]+content=['"]\d+;\s*url=([^'"]+)['"]""",
        r"""<meta[^>]+content=['"]\d+;\s*url=([^'"]+)['"][^>]+http-equiv=['"]\s*refresh\s*['"]""",
    ):
        m = re.search(pat, html, re.I | re.S)
        if m:
            return m.group(1).strip()
    return None


def _token_in_headers(headers: Any) -> str | None:
    for hv in headers.getall("Set-Cookie", []):
        for part in hv.split(";"):
            k, _, v = part.strip().partition("=")
            if k.lower().replace("-", "_") in ("sess_token", "token", "session_token"):
                if _TOKEN_RE.match(v):
                    return v
    return None


def _token_in_url(url: str) -> str | None:
    try:
        for k, vals in parse_qs(urlparse(url).query).items():
            if k.lower() in ("l", "t", "sess_token", "token"):
                for v in vals:
                    if _TOKEN_RE.match(v):
                        return v
    except Exception:
        pass
    return None


def _hidden_inputs(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for tag in re.finditer(r"<input[^>]+>", html, re.I | re.S):
        t = tag.group(0)
        if not re.search(r'type=["\']hidden["\']', t, re.I):
            continue
        nm = re.search(r'name=["\']([^"\']+)["\']', t, re.I)
        vl = re.search(r'value=["\']([^"\']*)["\']', t, re.I)
        if nm:
            out[nm.group(1)] = vl.group(1) if vl else ""
    return out


def _form_action(html: str, base: str) -> str:
    m = re.search(r'<form[^>]+action=["\']([^"\']*)["\']', html, re.I)
    if not m:
        return base
    action = m.group(1)
    if action.startswith("http"):
        return action
    return urljoin(base, action)


def _origin(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _serials_in_html(html: str) -> list[str]:
    """Extract device serial numbers from dashboard.bw-log.com devices page."""
    return list(dict.fromkeys(
        m.group(1) for m in _SERIAL_RE.finditer(html)
    ))


# ── Client ─────────────────────────────────────────────────────────────────────

class FreshRApiClient:
    """Async HTTP client for the Fresh-r bw-log API (read-only, current data).

    IMPORTANT: A single persistent aiohttp.ClientSession is created on first
    login and reused for all API calls.  This is necessary because auth is
    cookie-based (PHPSESSID on dashboard.bw-log.com) — the cookie jar must
    survive between the login redirect and subsequent API POSTs.
    """

    def __init__(self, email: str, password: str, ha_session: aiohttp.ClientSession) -> None:
        self._email      = email
        self._password   = password
        # ha_session kept only for backward-compatibility; not used for API calls
        self._ha_session = ha_session
        self._token: str | None = None
        # Persistent session — preserves cookies (PHPSESSID) across requests
        self._session: aiohttp.ClientSession | None = None

    def _get_session(self) -> aiohttp.ClientSession:
        """Return the persistent session, creating it if needed or if closed."""
        if self._session is None or self._session.closed:
            jar = aiohttp.CookieJar(unsafe=True)
            self._session = aiohttp.ClientSession(
                cookie_jar=jar,
                headers={"User-Agent": _USER_AGENT, "Accept-Language": "nl,en;q=0.9"},
            )
        return self._session

    async def async_close(self) -> None:
        """Close the persistent HTTP session (call on integration unload)."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    # ── Login ──────────────────────────────────────────────────────────────────

    async def async_login(self) -> None:
        """Authenticate and store session. Raises FreshRAuthError on failure."""
        s = self._get_session()
        token = await self._login_all(s)

        if not token:
            # No hex token found — use PHPSESSID as the API token value.
            # dashboard.bw-log.com authenticates via cookie; the JSON "token"
            # field may be optional or accept the session ID.
            phpsessid = _phpsessid_from_jar(s.cookie_jar)
            if phpsessid:
                _LOGGER.info(
                    "No hex token found — using PHPSESSID as session token (%.8s…)", phpsessid
                )
                token = phpsessid
            else:
                raise FreshRAuthError(
                    "Login failed — no session token or PHPSESSID received. "
                    "Verify your credentials at fresh-r.me"
                )

        self._token = token
        _LOGGER.info("Fresh-r authenticated (token=%.8s…)", token)

    async def _login_all(self, s: aiohttp.ClientSession) -> str | None:
        """Try each login URL in sequence; return first token found."""
        last_err = ""
        for url in LOGIN_URLS:
            try:
                tok = await self._login_one(s, url)
                if tok:
                    _LOGGER.debug("Login succeeded via %s", url)
                    return tok
                _LOGGER.debug("No hex token via %s — trying next", url)
            except FreshRAuthError:
                raise      # Wrong credentials — no point trying others
            except aiohttp.ClientError as e:
                last_err = str(e)
                _LOGGER.debug("Network error %s: %s", url, e)
        _LOGGER.warning("All login URLs exhausted. Last error: %s", last_err)
        return None

    async def _login_one(self, s: aiohttp.ClientSession, login_url: str) -> str | None:
        """GET form → POST credentials (following all redirects) → return hex token or None.

        With allow_redirects=True the POST follows the 302 → dashboard.bw-log.com chain
        automatically, so PHPSESSID ends up in the cookie jar after a single call.
        """

        # Step 1 — GET login page (collect hidden CSRF fields + any existing cookie)
        post_url = login_url
        hidden:   dict[str, str] = {}
        try:
            async with s.get(login_url, allow_redirects=True,
                             timeout=aiohttp.ClientTimeout(total=15)) as r:
                html     = await r.text()
                hidden   = _hidden_inputs(html)
                post_url = _form_action(html, str(r.url))
                tok = _token_in_jar(s.cookie_jar) or _token_in_headers(r.headers)
                if tok:
                    return tok
                _LOGGER.debug(
                    "GET %s → %s (final: %s) hidden_fields=%s action=%s",
                    login_url, r.status, str(r.url), list(hidden.keys()), post_url,
                )
        except aiohttp.ClientError as e:
            _LOGGER.warning("GET %s failed: %s", login_url, e)

        # Step 2 — POST credentials, follow the full redirect chain automatically.
        # Send both "email" and "username" so we work regardless of which name the
        # server expects (fresh-r.me login forms have been observed using both).
        form = {**hidden, "email": self._email, "username": self._email, "password": self._password}
        try:
            async with s.post(
                post_url,
                data=form,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin":       _origin(login_url),
                    "Referer":      login_url,
                },
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as r:
                final_url = str(r.url)
                body      = await r.text()
                _LOGGER.debug(
                    "POST %s → status=%s final_url=%s cookies=%s",
                    post_url, r.status, final_url, [c.key for c in s.cookie_jar],
                )

                # Hex token anywhere?
                tok = (
                    _token_in_headers(r.headers) or
                    _token_in_jar(s.cookie_jar) or
                    _token_in_url(final_url) or
                    _token_in_html(body)
                )
                if tok:
                    return tok

                # Landed on dashboard.bw-log.com → login succeeded (cookie-only auth).
                # PHPSESSID will be returned by async_login() as the token value.
                if "bw-log.com" in final_url:
                    _LOGGER.debug(
                        "Landed on dashboard (%s) — cookie-only auth. cookies=%s",
                        final_url, [c.key for c in s.cookie_jar],
                    )
                    return None

                # Explicit server-side error in body?
                if re.search(r'\b(invalid|incorrect|wrong|onjuist|fout)\b', body, re.I):
                    raise FreshRAuthError("Server rejected credentials")

                # Still on login page after POST — login failed silently.
                if "page=login" in final_url:
                    _LOGGER.warning(
                        "Still on login page after POST (%s) — "
                        "credentials may be wrong, or form field names differ. "
                        "Found form fields: %s",
                        final_url, list(hidden.keys()),
                    )
                    return None

                _LOGGER.warning(
                    "POST %s → %s (final: %s) — unexpected. cookies=%s body=%.300s",
                    post_url, r.status, final_url,
                    [c.key for c in s.cookie_jar], body[:300],
                )
                return None

        except aiohttp.ClientError as e:
            raise FreshRConnectionError(str(e)) from e

    # ── Device discovery ───────────────────────────────────────────────────────

    async def async_discover_devices(self) -> list[dict]:
        """Return all devices on this account.

        Strategy:
          1. Try the JSON API (syssearch + sysinfo).
          2. If that yields nothing, fall back to scraping the devices page HTML
             for serial numbers embedded in dashboard links.
        """
        # Strategy 1: JSON API
        try:
            raw = await self._call({
                "user_units": {"request": "syssearch", "role": "user", "fields": ["units"]},
            })
            units = raw.get("user_units", {}).get("units", [])
            if units:
                sys_req = {
                    u["id"]: {"request": "sysinfo", "id": u["id"], "fields": ["type", "room"]}
                    for u in units
                }
                sys_raw = await self._call(sys_req)
                devices = []
                for u in units:
                    uid  = u["id"]
                    info = sys_raw.get(uid, {})
                    devices.append({
                        "id":   uid,
                        "type": info.get("type", "Fresh-r"),
                        "room": info.get("room", ""),
                    })
                _LOGGER.info("Discovered %d device(s) via API: %s", len(devices), [d["id"] for d in devices])
                return devices
        except (FreshRConnectionError, Exception) as e:  # noqa: BLE001
            _LOGGER.warning("API device discovery failed (%s) — falling back to HTML scraping", e)

        # Strategy 2: scrape the devices page for serial numbers in dashboard links
        return await self._discover_from_html()

    async def _discover_from_html(self) -> list[dict]:
        """GET dashboard.bw-log.com/?page=devices and extract serial numbers."""
        s = self._get_session()
        devices_url = f"{API_BASE}/?page=devices"
        try:
            async with s.get(devices_url, allow_redirects=True,
                             timeout=aiohttp.ClientTimeout(total=15)) as r:
                html = await r.text()
                _LOGGER.debug(
                    "Devices page GET %s → %s (final: %s)",
                    devices_url, r.status, str(r.url),
                )
                if r.status != 200:
                    _LOGGER.error("Devices page returned HTTP %s", r.status)
                    return []

                serials = _serials_in_html(html)
                if not serials:
                    _LOGGER.warning(
                        "No serial numbers found on devices page. Body snippet: %.500s", html[:500]
                    )
                    return []

                _LOGGER.info("Discovered device serial(s) from HTML: %s", serials)
                return [{"id": s, "type": "Fresh-r", "room": ""} for s in serials]
        except aiohttp.ClientError as e:
            _LOGGER.error("Could not fetch devices page: %s", e)
            return []

    # ── Current data ───────────────────────────────────────────────────────────

    async def async_get_current(self, serial: str) -> dict[str, Any]:
        """Fetch current sensor values for one device."""
        if not self._token:
            await self.async_login()
        try:
            raw = await self._call({
                "current-data": {
                    "request": "fresh-r-now",
                    "serial":  serial,
                    "fields":  FIELDS_NOW,
                }
            })
        except FreshRConnectionError:
            _LOGGER.info("API error — re-authenticating")
            self._token = None
            await self.async_login()
            raw = await self._call({
                "current-data": {
                    "request": "fresh-r-now",
                    "serial":  serial,
                    "fields":  FIELDS_NOW,
                }
            })
        return self._parse(raw.get("current-data", {}))

    # ── Internal ───────────────────────────────────────────────────────────────

    @staticmethod
    def _tzoffset() -> str:
        off = datetime.now(timezone.utc).astimezone().utcoffset()
        return str(abs(int(off.total_seconds() / 60))) if off else "0"

    async def _call(self, requests: dict[str, Any]) -> dict[str, Any]:
        """POST to api.php using the persistent session (PHPSESSID cookie included)."""
        s = self._get_session()
        q = json.dumps({
            "token":    self._token or "",
            "tzoffset": self._tzoffset(),
            "requests": requests,
        })
        try:
            async with s.post(
                API_URL, params={"q": q},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                if r.status != 200:
                    raise FreshRConnectionError(f"HTTP {r.status}")
                text = await r.text()
                _LOGGER.debug("api.php response: %.300s", text[:300])
                return json.loads(text) if text.strip() else {}
        except aiohttp.ClientError as e:
            raise FreshRConnectionError(str(e)) from e
        except json.JSONDecodeError as e:
            raise FreshRConnectionError(f"Bad JSON: {e}") from e

    def _parse(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Convert raw API strings to floats, apply flow calibration, derive physics."""
        result: dict[str, Any] = {}

        # Temperature and air quality fields
        for key in ("t1", "t2", "t3", "t4", "co2", "hum", "dp",
                    "d5_25", "d4_25", "d1_25",
                    "d5_03", "d4_03", "d1_03",
                    "d5_1",  "d4_1",  "d1_1"):
            v = raw.get(key)
            if v is not None:
                try:
                    result[key] = round(float(v), 1)
                except (ValueError, TypeError):
                    pass

        # Flow calibration
        v = raw.get("flow")
        if v is not None:
            try:
                flow_raw       = float(v)
                result["flow"] = round(calibrate_flow(flow_raw), 1)
            except (ValueError, TypeError):
                pass

        # Derived sensors (require t1, t2, t4, flow)
        if {"t1", "t2", "t4", "flow"} <= result.keys():
            result.update(derive(result))

        return result
