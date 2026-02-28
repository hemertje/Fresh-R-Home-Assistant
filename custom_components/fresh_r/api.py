"""Fresh-r API client — read-only, current data only.

Authentication flow (reverse-engineered from HAR + JS source):
  - All data lives on dashboard.bw-log.com
  - Login: POST to login page with email/password → Set-Cookie: sess_token
  - API: POST /api.php?q=<JSON> with token in JSON body
  - Serial is auto-discovered from the account; user never enters it

NOTE: Historical data is NOT available via the Fresh-R.me API.
      Home Assistant's own recorder stores history from the moment
      the integration is active.

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
    API_URL, LOGIN_URLS,
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
    # First: check well-known names
    for c in jar:
        if c.key.lower().replace("-", "_") in ("sess_token", "token", "session_token", "l", "sid"):
            if _TOKEN_RE.match(c.value):
                return c.value
    # Fallback: any cookie whose value looks like a hex session token
    for c in jar:
        if _TOKEN_RE.match(c.value):
            _LOGGER.debug("Using token from cookie '%s'", c.key)
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
            if k.lower() in ("l", "sess_token", "token"):
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


# ── Client ─────────────────────────────────────────────────────────────────────

class FreshRApiClient:
    """Async HTTP client for the Fresh-r bw-log API (read-only, current data)."""

    def __init__(self, email: str, password: str, ha_session: aiohttp.ClientSession) -> None:
        self._email      = email
        self._password   = password
        self._ha_session = ha_session
        self._token: str | None = None

    # ── Login ──────────────────────────────────────────────────────────────────

    async def async_login(self) -> None:
        """Authenticate and store sess_token. Raises FreshRAuthError on failure."""
        jar = aiohttp.CookieJar(unsafe=True)
        async with aiohttp.ClientSession(
            cookie_jar=jar,
            headers={"User-Agent": _USER_AGENT, "Accept-Language": "nl,en;q=0.9"},
        ) as s:
            token = await self._login_all(s)

        if not token:
            raise FreshRAuthError(
                "Login failed — no session token received. "
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
                _LOGGER.debug("No token via %s — trying next", url)
            except FreshRAuthError:
                raise      # Wrong credentials — no point trying others
            except aiohttp.ClientError as e:
                last_err = str(e)
                _LOGGER.debug("Network error %s: %s", url, e)
        _LOGGER.warning("All login URLs exhausted. Last error: %s", last_err)
        return None

    async def _login_one(self, s: aiohttp.ClientSession, login_url: str) -> str | None:
        """GET form → POST credentials → return token or None."""

        # Step 1 — GET login page (collect hidden CSRF fields + any existing cookie)
        post_url = login_url
        hidden:   dict[str, str] = {}
        try:
            async with s.get(login_url, allow_redirects=True,
                             timeout=aiohttp.ClientTimeout(total=15)) as r:
                html     = await r.text()
                hidden   = _hidden_inputs(html)
                post_url = _form_action(html, login_url)
                tok = _token_in_jar(s.cookie_jar) or _token_in_headers(r.headers)
                if tok:
                    return tok
                if r.status not in (200, 301, 302):
                    _LOGGER.warning("GET %s returned HTTP %s — login page blocked?", login_url, r.status)
                _LOGGER.debug("GET %s → %s hidden=%s action=%s", login_url, r.status, list(hidden.keys()), post_url)
        except aiohttp.ClientError as e:
            _LOGGER.warning("GET %s failed: %s", login_url, e)
            pass   # Continue to POST with no hidden fields

        # Step 2 — POST credentials
        # Note: "page=login" is a URL query param, not a form body field
        form = {**hidden, "email": self._email, "password": self._password}
        async with s.post(
            post_url,
            data=form,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin":       _origin(login_url),
                "Referer":      login_url,
            },
            allow_redirects=False,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as r:
            loc = r.headers.get("Location", "")
            _LOGGER.debug(
                "POST %s → status=%s loc=%s cookies=%s",
                post_url, r.status, loc or "(none)", [c.key for c in s.cookie_jar],
            )

            tok = _token_in_headers(r.headers) or _token_in_jar(s.cookie_jar) or _token_in_url(loc)
            if tok:
                return tok

            # Redirected back to login — credentials rejected or no token yet
            if "page=login" in loc:
                body = await r.text()
                if "invalid" in body.lower() or "incorrect" in body.lower() or "wrong" in body.lower():
                    raise FreshRAuthError("Server rejected credentials")
                _LOGGER.debug("Redirect back to login — trying next URL")
                return None

            if r.status == 200:
                body = await r.text()
                tok = _token_in_html(body)
                if tok:
                    return tok
                # Website may JS-redirect to dashboard.bw-log.com with token in URL
                js_loc = _js_redirect(body)
                if js_loc:
                    _LOGGER.debug("JS/meta redirect detected: %s", js_loc)
                    tok = _token_in_url(js_loc)
                    if tok:
                        return tok
                    if not loc:  # Use as fallback for step 3
                        loc = js_loc if js_loc.startswith("http") else urljoin(post_url, js_loc)
                if "invalid" in body.lower() or "incorrect" in body.lower() or "wrong" in body.lower():
                    raise FreshRAuthError("Server rejected credentials")
                _LOGGER.warning(
                    "POST %s → 200 but no token found. JS-redirect: %s. Body snippet: %.300s",
                    post_url, js_loc or "(none)", body[:300],
                )

        # Step 3 — follow redirect to dashboard (dashboard.bw-log.com/?page=devices)
        # Token may be in the dashboard page HTML/JS or in a cookie set after redirect
        if loc:
            abs_loc = loc if loc.startswith("http") else urljoin(post_url, loc)
            try:
                async with s.get(abs_loc, allow_redirects=True,
                                 timeout=aiohttp.ClientTimeout(total=10)) as r2:
                    dashboard_html = await r2.text()
                    tok = (
                        _token_in_headers(r2.headers) or
                        _token_in_jar(s.cookie_jar) or
                        _token_in_url(str(r2.url)) or
                        _token_in_html(dashboard_html)
                    )
                    if tok:
                        return tok
                    _LOGGER.warning(
                        "Step 3 GET %s → %s (final URL: %s) — no token. Cookies: %s. Body snippet: %.300s",
                        abs_loc, r2.status, str(r2.url),
                        [c.key for c in s.cookie_jar], dashboard_html[:300],
                    )
            except aiohttp.ClientError as e:
                _LOGGER.debug("Follow redirect error: %s", e)

        _LOGGER.warning("No token found via %s. Cookie names in jar: %s",
                        login_url, [c.key for c in s.cookie_jar])
        return None

    # ── Device discovery ───────────────────────────────────────────────────────

    async def async_discover_devices(self) -> list[dict]:
        """Return all devices on this account: [{id, type, room}]."""
        raw = await self._call({
            "user_units": {"request": "syssearch", "role": "user", "fields": ["units"]},
        })
        units = raw.get("user_units", {}).get("units", [])
        if not units:
            return []

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
        _LOGGER.info("Discovered %d device(s): %s", len(devices), [d["id"] for d in devices])
        return devices

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
        q = json.dumps({
            "token":    self._token,
            "tzoffset": self._tzoffset(),
            "requests": requests,
        })
        try:
            async with self._ha_session.post(
                API_URL, params={"q": q},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                if r.status != 200:
                    raise FreshRConnectionError(f"HTTP {r.status}")
                text = await r.text()
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
