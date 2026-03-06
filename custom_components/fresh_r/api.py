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


def _all_inputs(html: str) -> list[tuple[str, str, str]]:
    """Return all <input> fields as (type, name, value) tuples — for diagnosis."""
    out = []
    for tag in re.finditer(r"<input[^>]+>", html, re.I | re.S):
        t   = tag.group(0)
        typ = (re.search(r'type=["\']?([^"\'>\s]+)["\']?', t, re.I) or type("", (), {"group": lambda s, n: "text"})).group(1)
        nm  = re.search(r'name=["\']([^"\']+)["\']', t, re.I)
        vl  = re.search(r'value=["\']([^"\']*)["\']', t, re.I)
        if nm:
            out.append((typ, nm.group(1), (vl.group(1) if vl else "")))
    return out


def _hidden_inputs(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for typ, name, value in _all_inputs(html):
        if typ.lower() == "hidden":
            out[name] = value
    return out


def _form_action(html: str, base: str) -> str:
    # Match both quoted and unquoted action attributes
    m = re.search(r'<form[^>]+action=["\']?([^"\'>\s]*)["\']?', html, re.I)
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
        """Authenticate and store session token. Raises FreshRAuthError on failure."""
        s = self._get_session()
        token = await self._login_all(s)

        if not token:
            raise FreshRAuthError(
                "Login failed — no session token received. "
                "Verify your credentials at fresh-r.me"
            )

        self._token = token
        _LOGGER.info("Fresh-r authenticated (token=%.8s…)", token)

    async def _login_bearer_token(self, s: aiohttp.ClientSession) -> str | None:
        """Authenticate using modern Fresh-r API and return Bearer token."""
        from .const import API_URL
        
        try:
            payload = {
                "email": self._email,
                "password": self._password
            }
            
            _LOGGER.debug("Attempting Bearer token authentication to %s", API_URL)
            
            async with s.post(
                API_URL,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Origin": "https://dashboard.bw-log.com",
                    "Referer": "https://dashboard.bw-log.com/",
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    token = data.get("token") or data.get("access_token")
                    if token:
                        _LOGGER.info("Bearer token received successfully")
                        return token
                
                _LOGGER.warning(
                    "Bearer token auth failed: HTTP %s | body=%s",
                    r.status, await r.text()
                )
                return None
                
        except aiohttp.ClientError as e:
            _LOGGER.error("Bearer token auth error: %s", e)
            return None

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
                all_inputs = _all_inputs(html)
                _LOGGER.warning(
                    "Fresh-r login-page diagnosis — GET %s → HTTP %s (final: %s) | "
                    "form_action=%s | all_inputs=%s | body[:1500]=\n%s",
                    login_url, r.status, str(r.url),
                    post_url, all_inputs, html[:1500],
                )
        except aiohttp.ClientError as e:
            _LOGGER.warning("GET %s failed: %s", login_url, e)

        # Step 2 — POST credentials, follow the full redirect chain automatically.
        # The fresh-r.me login form uses "email", "password", and "keep_logged_in" checkbox
        form = {**hidden, "email": self._email, "password": self._password, "keep_logged_in": ""}
        _LOGGER.warning(
            "Fresh-r POST payload — url=%s fields=%s",
            post_url,
            {k: ("***" if k == "password" else v) for k, v in form.items()},
        )
        try:
            async with s.post(
                post_url,
                data=form,  # Form-urlencoded (not JSON) for HTML form submission
                headers={
                    "Origin":       _origin(login_url),
                    "Referer":      login_url,
                    "X-Requested-With": "XMLHttpRequest",
                },
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as r:
                final_url = str(r.url)
                body      = await r.text()
                _LOGGER.warning(
                    "Fresh-r login-page diagnosis — POST %s → HTTP %s | "
                    "final_url=%s | cookies=%s | body[:1000]=\n%s",
                    post_url, r.status, final_url,
                    [c.key for c in s.cookie_jar], body[:1000],
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
                if "bw-log.com" in final_url:
                    _LOGGER.debug(
                        "Landed on dashboard (%s) — cookie-only auth. cookies=%s",
                        final_url, [c.key for c in s.cookie_jar],
                    )
                    return None

                # JavaScript / meta-refresh redirect in the POST response body?
                # Some PHP login pages respond with 200 + JS redirect instead of
                # an HTTP 3xx.  aiohttp follows 3xx automatically but not JS.
                js_url = _js_redirect(body)
                if js_url:
                    abs_js_url = urljoin(final_url, js_url)
                    _LOGGER.debug("POST response contains JS redirect → %s", abs_js_url)
                    try:
                        async with s.get(
                            abs_js_url, allow_redirects=True,
                            timeout=aiohttp.ClientTimeout(total=15),
                        ) as r2:
                            final_url2 = str(r2.url)
                            body2      = await r2.text()
                            tok2 = (
                                _token_in_headers(r2.headers) or
                                _token_in_jar(s.cookie_jar) or
                                _token_in_url(final_url2) or
                                _token_in_html(body2)
                            )
                            if tok2:
                                return tok2
                            if "bw-log.com" in final_url2:
                                _LOGGER.debug(
                                    "Landed on dashboard via JS redirect (%s) — cookie-only auth.",
                                    final_url2,
                                )
                                return None
                    except aiohttp.ClientError as e:
                        _LOGGER.debug("JS redirect GET failed: %s", e)

                # Explicit server-side error in body?
                if re.search(r'\b(invalid|incorrect|wrong|onjuist|fout)\b', body, re.I):
                    raise FreshRAuthError("Server rejected credentials")

                # Still on login page after POST — server rejected credentials.
                if "page=login" in final_url:
                    raise FreshRAuthError(
                        f"Login mislukt — server toont login-pagina na POST naar {post_url}. "
                        "Controleer je e-mailadres en wachtwoord op fresh-r.me. "
                        f"Verstuurde velden: {[k for k in form if k != 'password']}"
                    )

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
        """Return all devices using modern Fresh-r API."""
        from .const import API_DATA_URL
        
        try:
            s = self._get_session()
            headers = {"Authorization": f"Bearer {self._token}"}
            
            async with s.get(API_DATA_URL, headers=headers, 
                             timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    data = await r.json()
                    _LOGGER.info("Modern API device discovery successful")
                    
                    # Parse device data from modern API response
                    devices = []
                    if isinstance(data, dict):
                        for device_id, device_data in data.items():
                            devices.append({
                                "id": device_id,
                                "type": device_data.get("type", "Fresh-r"),
                                "room": device_data.get("room", ""),
                            })
                    elif isinstance(data, list):
                        for device in data:
                            devices.append({
                                "id": device.get("id", device.get("serial", "unknown")),
                                "type": device.get("type", "Fresh-r"),
                                "room": device.get("room", ""),
                            })
                    
                    _LOGGER.info("Discovered %d device(s) via modern API: %s", 
                                len(devices), [d["id"] for d in devices])
                    return devices
                else:
                    _LOGGER.error("Modern API device discovery failed: HTTP %s", r.status)
                    return []
                    
        except aiohttp.ClientError as e:
            _LOGGER.error("Modern API device discovery error: %s", e)
            return []

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
                        "No serial numbers found on devices page. Body[:3000]=\n%s", html[:3000]
                    )
                    return []

                _LOGGER.info("Discovered device serial(s) from HTML: %s", serials)
                return [{"id": s, "type": "Fresh-r", "room": ""} for s in serials]
        except aiohttp.ClientError as e:
            _LOGGER.error("Could not fetch devices page: %s", e)
            return []

    # ── Current data ───────────────────────────────────────────────────────────

    async def async_get_current(self, serial: str) -> dict[str, Any]:
        """Fetch current sensor values for one device using modern API with legacy token."""
        from .const import API_DATA_URL
        
        if not self._token:
            await self.async_login()
        
        try:
            s = self._get_session()
            # Use the legacy token as Bearer token for modern API
            headers = {"Authorization": f"Bearer {self._token}"}
            
            async with s.get(API_DATA_URL, headers=headers,
                             timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    data = await r.json()
                    _LOGGER.debug("Modern API data received: %s", data)
                    
                    # Parse sensor data from modern API response
                    if isinstance(data, dict) and serial in data:
                        return self._parse_modern_api_data(data[serial])
                    elif isinstance(data, list):
                        for device in data:
                            device_id = device.get("id", device.get("serial", ""))
                            if device_id == serial:
                                return self._parse_modern_api_data(device)
                    
                    _LOGGER.warning("Device %s not found in API response", serial)
                    return {}
                else:
                    _LOGGER.error("Modern API data fetch failed: HTTP %s", r.status)
                    return {}
                    
        except aiohttp.ClientError as e:
            _LOGGER.error("Modern API data fetch error: %s", e)
            return {}

    def _parse_modern_api_data(self, device_data: dict) -> dict[str, Any]:
        """Parse sensor data from modern API response format."""
        # Map modern API fields to our expected format
        parsed = {}
        
        # Temperature sensors
        for key in ["t1", "t2", "t3", "t4"]:
            if key in device_data:
                parsed[key] = device_data[key]
        
        # Other sensors
        for key in ["flow", "co2", "hum", "dp"]:
            if key in device_data:
                parsed[key] = device_data[key]
        
        # PM sensors
        for prefix in ["d1_", "d4_", "d5_"]:
            for size in ["03", "1", "25"]:
                key = f"{prefix}{size}"
                if key in device_data:
                    parsed[key] = device_data[key]
        
        # Calculated values
        for key in ["heat_recovered", "vent_loss", "energy_loss"]:
            if key in device_data:
                parsed[key] = device_data[key]
        
        return parsed

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
