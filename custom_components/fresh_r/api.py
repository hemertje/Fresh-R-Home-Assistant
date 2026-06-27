"""Fresh-r API client — read-only, current data only.

Authentication flow (observed via browser / HAR):
  - Login: POST credentials to www.fresh-r.me (HAR) → HTML of JSON → navigate-GET dashboard.bw-log.com
    (sometimes with ``?t=<activation nonce>`` in the URL).
  - The ``t=`` query value is **not** the same as the 64-hex ``token`` in ``api.php`` JSON;
    after a GET with ``t=``, the server sets ``sess_token`` / ``auth_token`` cookies.
  - ``api.php`` uses that cookie-derived hex token in JSON ``token``; reuse the cookie jar
    for all dashboard requests.
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

import asyncio
import json
import logging
import math
import re
from datetime import datetime, timezone, timedelta
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlparse

import aiohttp
from aiohttp import ClientConnectorError, ClientSSLError, ServerTimeoutError
from yarl import URL

from .const import (
    API_BASE,
    API_URL,
    FIELDS_NOW,
    FLOW_BASE,
    FLOW_DIVISOR,
    FLOW_OFFSET,
    FLOW_THRESHOLD,
    LOGIN_URLS,
    REF_FLOW,
    AIR_HEAT_CAP,
)

# Token expires after 75 minutes (4500 seconds)
TOKEN_EXPIRY_SECONDS = 4500
# Proactively refresh 5 minutes before expiry
TOKEN_REFRESH_SECONDS = 300

# Safe testing intervals (realistisch)
SAFE_LOGIN_INTERVAL = 300      # 5 minuten tussen login attempts
SAFE_DATA_INTERVAL = 900       # 15 minuten tussen data polls
SAFE_MONITORING_INTERVAL = 3600 # 1 uur tussen monitoring checks

# Rate limit protection
MAX_REQUESTS_PER_HOUR = 12  # 1 per 5 minuten
RATE_LIMIT_BACKOFF = 3600   # 1 hour backoff when rate limited

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
RETRY_BACKOFF_MULTIPLIER = 2

# Timeout configuration
DEFAULT_TIMEOUT = 30  # seconds
LOGIN_TIMEOUT = 45    # seconds (login can take longer)

# Live monitoring configuration
LIVE_MONITORING = False  # Set to False for production
DEEP_DEBUG = False  # Enable via code only when needed; use logger: custom_components.fresh_r: debug

# Resource limits
MAX_MONITOR_CACHE = 100  # Max cached requests/responses
MAX_COOKIE_JAR_SIZE = 50  # Max cookies to keep

# Data validation ranges
TEMP_MIN, TEMP_MAX = -40.0, 85.0  # °C
FLOW_MIN, FLOW_MAX = 0.0, 500.0   # m³/h
CO2_MIN, CO2_MAX = 0.0, 5000.0     # ppm
HUMIDITY_MIN, HUMIDITY_MAX = 0.0, 100.0  # %

_LOGGER     = logging.getLogger(__name__)
_TOKEN_RE   = re.compile(r'^[0-9a-f]{32,}$', re.I)
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
# HAR api.php XHR op dashboard (Chrome/macOS)
_DASHBOARD_CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
)

# Serial pattern: e.g. serial=e:XXXXXX/XXXXXX or URL-encoded serial=e%3A...
_SERIAL_RE = re.compile(r'serial=([^&"\'>\s]+)', re.I)
# Fallback: any e:digits/digits in page (dashboard links, JSON, data-attrs)
_E_PAIR_RE = re.compile(r'\be:(\d+)/(\d+)\b')
# Device serial validation patterns
_SERIAL_PATTERN_1 = re.compile(r'^e:\d+/\d+$')  # e:XXXXXX/XXXXXX
_SERIAL_PATTERN_2 = re.compile(r'^\d+$')  # All digits


class FreshRAuthError(Exception):
    """Login failed — bad credentials or service unreachable."""


class FreshRConnectionError(Exception):
    """Network or API error."""


class FreshRRateLimitError(Exception):
    """Rate limit exceeded — too many requests."""


class FreshRTokenExpiredError(Exception):
    """Session token expired — re-authentication required."""


class FreshRDataValidationError(Exception):
    """Invalid or out-of-range sensor data received."""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe_str_for_in(value: object) -> str:
    """Coerce to str before substring checks like ``\"x\" in value``.

    aiohttp/yarl may return ``yarl.URL`` for response URLs and cookie domains.
    Using ``\"sub\" in url_obj`` raises *TypeError: URL is not a container or iterable*.
    """
    return "" if value is None else str(value)


def _is_login_rate_limited_body(body: str) -> bool:
    """True als het auth.php-antwoord een login rate limit meldt (XHR/JSON/HTML)."""
    b = (body or "").strip()
    if not b:
        return False
    low = b.lower()
    if "too many" in low and ("login" in low or "attempt" in low or "later" in low):
        return True
    if b.startswith("<") and "too many" in low and "login" in low:
        return True
    if b.startswith("{"):
        try:
            d = json.loads(b)
            msg = _safe_str_for_in(d.get("message", ""))
            mlow = msg.lower()
            if d.get("authenticated") is False and (
                "too many" in mlow
                or "try again later" in mlow
                or "rate limit" in mlow
                or "rate-limit" in mlow
            ):
                return True
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return False


def _raise_if_login_rate_limited(body: str) -> None:
    """Stop login chain immediately if the server reports rate limiting.

    Calling ``auth.php`` multiple times per login (nav + XHR + JSON) worsens this.
    """
    if not _is_login_rate_limited_body(body):
        return
    b = (body or "").strip()
    _LOGGER.warning(
        "auth.php: server meldt rate limit — fragment: %.220s",
        b.replace("\n", " ").replace("\r", " "),
    )
    if b.startswith("{"):
        try:
            d = json.loads(b)
            msg = _safe_str_for_in(d.get("message", ""))
            raise FreshRRateLimitError(msg or "Too many login attempts")
        except FreshRRateLimitError:
            raise
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    raise FreshRRateLimitError(
        "Too many login attempts — wait before retrying (server rate limit)."
    )


def calibrate_flow(raw: float) -> float:
    """Apply ESP mode flow correction (from dashboard.js)."""
    if raw > FLOW_THRESHOLD:
        return (raw - FLOW_OFFSET) / FLOW_DIVISOR + FLOW_BASE
    return raw


def _validate_device_serial(serial: str) -> bool:
    """Validate device serial number format.
    
    Args:
        serial: Device serial number to validate
        
    Returns:
        True if serial format is valid, False otherwise
    """
    if not serial or not isinstance(serial, str):
        return False
    
    # Accept known formats
    if _SERIAL_PATTERN_1.match(serial):  # e:XXXXXX/XXXXXX
        return True
    if _SERIAL_PATTERN_2.match(serial):  # All digits
        return True
    
    _LOGGER.warning("Unknown device serial format: %s", serial)
    return False


def _validate_sensor_data(data: dict) -> dict[str, float]:
    """Validate and sanitize sensor data.
    
    Args:
        data: Raw sensor data from API
        
    Returns:
        Validated sensor data with only valid values
        
    Raises:
        FreshRDataValidationError: If no valid sensor data found
    """
    validated = {}
    
    # Temperature validation
    for temp_key in ['t1', 't2', 't3', 't4']:
        if temp_key in data:
            try:
                temp = float(data[temp_key])
                if TEMP_MIN <= temp <= TEMP_MAX:
                    validated[temp_key] = temp
                else:
                    _LOGGER.warning(
                        "Temperature %s out of range: %.1f°C (valid: %.0f to %.0f°C)",
                        temp_key, temp, TEMP_MIN, TEMP_MAX
                    )
            except (ValueError, TypeError) as err:
                _LOGGER.warning("Invalid temperature %s value: %s (%s)", temp_key, data[temp_key], err)
    
    # Flow validation
    if 'flow' in data:
        try:
            flow = float(data['flow'])
            if FLOW_MIN <= flow <= FLOW_MAX:
                validated['flow'] = flow
            else:
                _LOGGER.warning(
                    "Flow out of range: %.1f m³/h (valid: %.0f to %.0f m³/h)",
                    flow, FLOW_MIN, FLOW_MAX
                )
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Invalid flow value: %s (%s)", data['flow'], err)
    
    # CO2 validation
    if 'co2' in data:
        try:
            co2 = float(data['co2'])
            if CO2_MIN <= co2 <= CO2_MAX:
                validated['co2'] = co2
            else:
                _LOGGER.warning(
                    "CO2 out of range: %.0f ppm (valid: %.0f to %.0f ppm)",
                    co2, CO2_MIN, CO2_MAX
                )
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Invalid CO2 value: %s (%s)", data['co2'], err)
    
    # Humidity validation (API field is ``hum``; accept ``humidity`` too)
    _hum_raw = data.get("humidity", data.get("hum"))
    if _hum_raw is not None:
        try:
            hum = float(_hum_raw)
            if HUMIDITY_MIN <= hum <= HUMIDITY_MAX:
                validated["hum"] = hum
            else:
                _LOGGER.warning(
                    "Humidity out of range: %.1f%% (valid: %.0f to %.0f%%)",
                    hum, HUMIDITY_MIN, HUMIDITY_MAX
                )
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Invalid humidity value: %s (%s)", _hum_raw, err)
    
    # Copy other fields without validation
    for key in data:
        if key not in validated and key not in [
            "t1", "t2", "t3", "t4", "flow", "co2", "humidity", "hum",
        ]:
            try:
                validated[key] = float(data[key])
            except (ValueError, TypeError):
                _LOGGER.debug("Skipping non-numeric field: %s = %s", key, data[key])
    
    if not validated:
        _LOGGER.error("No valid sensor data found in response")
        raise FreshRDataValidationError("No valid sensor data received from API")
    
    return validated


def _safe_json_parse(body: str, context: str = "API") -> dict:
    """Safely parse JSON with detailed error reporting.
    
    Args:
        body: JSON string to parse
        context: Context description for error messages
        
    Returns:
        Parsed JSON as dictionary
        
    Raises:
        FreshRConnectionError: If JSON is invalid or not a dict
    """
    try:
        data = json.loads(body)
        if not isinstance(data, dict):
            _LOGGER.error("%s returned non-dict JSON: %s", context, type(data).__name__)
            raise FreshRConnectionError(f"{context} returned unexpected JSON type: {type(data).__name__}")
        return data
    except json.JSONDecodeError as err:
        _LOGGER.error("%s JSON parse error at position %d: %s", context, err.pos, err.msg)
        _LOGGER.debug("Invalid JSON body (first 500 chars): %s", body[:500])
        raise FreshRConnectionError(f"{context} returned invalid JSON") from err


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


def water_vapor_g_m3(t_celsius: float, rh_percent: float) -> float:
    """Absolute humidity (g/m³) from indoor °C and RH% — matches Fresh-r humidity tab."""
    # Magnus over water; coefficient 2.166 → g/m³ (typical HVAC / psychrometric form)
    es = 6.112 * math.exp((17.67 * t_celsius) / (t_celsius + 243.5))
    e = es * rh_percent / 100.0
    return round(2.166 * e / (273.15 + t_celsius), 2)


def _fresh_r_now_request_key(serial: str) -> str:
    """HAR/browser use ``<serial>_current`` as the ``requests`` key for fresh-r-now."""
    return f"{serial}_current"


def _sync_dashboard_auth_cookie(
    jar: aiohttp.CookieJar,
    token: str | None,
    *,
    include_sess: bool = True,
) -> None:
    """Zet ``auth_token`` op dashboard-host; optioneel ook ``sess_token`` (zelfde hex).

    Gebruik ``include_sess=False`` vóór de eerste dashboard-document-GET: de server
    zet ``sess_token`` vaak via Set-Cookie; een vroege client-side ``sess_token`` kan
    een tweede GET met ``?t=`` laten doorverwijzen naar fresh-r login terwijl de shell
    zonder ``t=`` wél op het dashboard blijft.
    """
    if not token or not _TOKEN_RE.match(token):
        return
    cookies: dict[str, str] = {"auth_token": token}
    if include_sess:
        cookies["sess_token"] = token
    jar.update_cookies(cookies, URL("https://dashboard.bw-log.com"))


def _token_in_jar(jar: aiohttp.CookieJar) -> str | None:
    """Return a hex token from the jar for ``api.php`` JSON ``token``.

    **Order matters:** ``sess_token`` (set after redirect naar ``/?page=devices``) is what
    the dashboard XHR uses; ``auth_token`` from the login JSON is often *not* accepted by
    ``api.php`` (``Invalid token``). Prefer ``sess_token`` first, then other known names.
    """
    preferred = (
        "sess_token",
        "auth_token",
        "token",
        "session_token",
        "l",
        "sid",
    )
    for name in preferred:
        for c in jar:
            if c.key.lower().replace("-", "_") != name:
                continue
            if _TOKEN_RE.match(c.value):
                return c.value
    # Fallback: any hex-looking cookie on the jar (last resort)
    for c in jar:
        if _TOKEN_RE.match(c.value):
            _LOGGER.debug("Using token from cookie '%s'", c.key)
            return c.value
    return None


def _sess_token_value(jar: aiohttp.CookieJar) -> str | None:
    """Alleen de ``sess_token`` cookie (die ``api.php`` verwacht), niet ``auth_token``."""
    for c in jar:
        if c.key.lower().replace("-", "_") == "sess_token" and _TOKEN_RE.match(c.value):
            return c.value
    return None


def _activation_nonce_from_login_json(data: dict[str, Any], auth_token: str) -> str:
    """``t=`` voor dashboard-activatie: voorkeur JSON-velden, anders ``auth_token``."""
    for key in ("t", "activation", "activation_token", "nonce"):
        v = data.get(key)
        if isinstance(v, str) and v and _TOKEN_RE.match(v):
            return v
    for key in ("redirect", "redirect_url", "url", "dashboard_url"):
        v = data.get(key)
        if isinstance(v, str) and "http" in v.lower():
            try:
                tq = parse_qs(urlparse(v).query).get("t") or []
            except Exception:
                continue
            if tq and tq[0] and _TOKEN_RE.match(tq[0]):
                return tq[0]
    return auth_token


def _dashboard_redirect_url_from_login_json(data: dict[str, Any]) -> str | None:
    """Volledige dashboard-URL uit auth-JSON (bevat vaak ``?page=devices&t=…`` voor activatie)."""
    for key in (
        "redirect",
        "redirect_url",
        "url",
        "dashboard_url",
        "location",
        "next",
        "goto",
        "target",
    ):
        v = data.get(key)
        if not isinstance(v, str):
            continue
        v = v.strip()
        if "dashboard.bw-log.com" not in v.lower():
            continue
        try:
            p = urlparse(v)
            if p.scheme in ("http", "https") and p.netloc:
                return v
        except Exception:
            continue
    return None


def _phpsessid_from_jar(jar: aiohttp.CookieJar) -> str | None:
    """Return the PHPSESSID value from the cookie jar."""
    for c in jar:
        if c.key.upper() == "PHPSESSID":
            return c.value
    return None


def _phpsessid_dashboard(jar: aiohttp.CookieJar) -> str | None:
    """``PHPSESSID`` voor ``dashboard.bw-log.com`` (soms ``token`` in ``q`` i.p.v. hex)."""
    for c in jar:
        if c.key.upper() != "PHPSESSID":
            continue
        if "bw-log.com" in _safe_str_for_in(c["domain"]):
            return c.value
    return None


def _phpsessid_www_fresh_r(jar: aiohttp.CookieJar) -> str | None:
    for c in jar:
        if c.key.upper() != "PHPSESSID":
            continue
        d = _safe_str_for_in(c["domain"]).lower()
        if "www.fresh-r.me" in d:
            return c.value
    return None


def _phpsessid_apex_fresh_r(jar: aiohttp.CookieJar) -> str | None:
    """PHPSESSID op ``fresh-r.me`` zonder ``www`` (login-flow zet soms beide)."""
    for c in jar:
        if c.key.upper() != "PHPSESSID":
            continue
        d = _safe_str_for_in(c["domain"]).lower()
        if "fresh-r.me" not in d:
            continue
        if "www" in d:
            continue
        return c.value
    return None


def _strip_bw_log_cookies_from_jar(jar: aiohttp.CookieJar) -> None:
    """Verwijder alle cookies voor ``*.bw-log.com`` (stale ``sess_token``/``auth_token`` na mislukte login).

    Zonder dit blijft een oude hex in de jar staan terwijl ``auth.php`` een nieuwe ``auth_token``
    teruggeeft — ``_sess_token_value`` leest dan de verkeerde sessie (api.php: Invalid token).
    """
    clear_domain = getattr(jar, "clear_domain", None)
    if not callable(clear_domain):
        return
    try:
        clear_domain("bw-log.com")
        _LOGGER.debug("Cookie jar: bw-log.com cookies gewist vóór login")
    except Exception:
        _LOGGER.debug("bw-log cookies wissen mislukt", exc_info=True)


def _jar_strip_token_failure_cookie(jar: aiohttp.CookieJar) -> None:
    """Verwijder ``token_failure`` uit de jar (server zet die na mislukte api.php; breekt vervolg-calls)."""
    try:
        raw = getattr(jar, "_cookies", None)
        if not isinstance(raw, dict):
            return
        cache = getattr(jar, "_morsel_cache", None)
        for key, bucket in list(raw.items()):
            if not bucket or "token_failure" not in bucket:
                continue
            del bucket["token_failure"]
            if isinstance(cache, dict) and key in cache and "token_failure" in cache[key]:
                del cache[key]["token_failure"]
    except Exception:
        _LOGGER.debug("token_failure uit jar strippen mislukt", exc_info=True)


def _dashboard_cookie_header_no_failure(jar: aiohttp.CookieJar) -> str | None:
    """``Cookie:`` voor dashboard-host: alle ``*.bw-log.com`` cookies behalve ``token_failure``."""
    parts: list[str] = []
    for c in jar:
        if c.key == "token_failure":
            continue
        dom = _safe_str_for_in(c["domain"])
        if "bw-log.com" not in dom:
            continue
        parts.append(f"{c.key}={c.value}")
    return "; ".join(parts) if parts else None


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


# HAR (Chrome): auth.php op www; eerste dashboard-GET heeft Referer https://www.fresh-r.me/
_LOGIN_WWW = "https://www.fresh-r.me"

_DASHBOARD_ABS_URL_RE = re.compile(
    r"https://dashboard\.bw-log\.com[/0-9a-zA-Z.?&=_%-]*",
    re.I,
)


def _dashboard_url_from_auth_html(html: str) -> str | None:
    """Pak eerste absolute dashboard-URL uit auth.php HTML-response (HAR: text/html, ~102 B)."""
    m = _DASHBOARD_ABS_URL_RE.search(html or "")
    if not m:
        return None
    u = m.group(0).rstrip(".,;)'\"]")
    return u


def _extract_dashboard_activation_url_from_auth_body(body: str) -> str | None:
    """Als auth.php HTML teruggeeft i.p.v. JSON: URL voor navigate-GET (vaak ``?page=devices&t=``)."""
    b = (body or "").strip()
    if not b.startswith("<"):
        return None
    u = _dashboard_url_from_auth_html(b)
    if u:
        return u
    jr = _js_redirect(b)
    if not jr:
        return None
    jrl = jr.lower()
    if "dashboard.bw-log.com" not in jrl:
        return None
    if jr.startswith("//"):
        return "https:" + jr
    if jr.startswith("/"):
        return urljoin("https://dashboard.bw-log.com/", jr)
    return jr


def _navigate_dashboard_document_headers(referer: str) -> dict[str, str]:
    """Headers zoals Chrome **document**-navigatie naar dashboard (HAR: sec-fetch cross-site)."""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
        ),
        "Accept-Language": "nl,en-US;q=0.9,en;q=0.8",
        "Referer": referer,
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }


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
    seen: dict[str, None] = {}
    for m in _SERIAL_RE.finditer(html):
        raw = m.group(1).strip().strip('"').strip("'")
        try:
            raw = unquote(raw)
        except Exception:
            pass
        if _validate_device_serial(raw):
            seen[raw] = None
    # Some pages encode serial in query as e%3A… or only embed e:NNN/NNN in href/JSON
    for m in _E_PAIR_RE.finditer(html):
        s = f"e:{m.group(1)}/{m.group(2)}"
        if _validate_device_serial(s):
            seen[s] = None
    return list(seen.keys())


# ── Client ─────────────────────────────────────────────────────────────────────

class FreshRApiClient:
    """Async HTTP client for the Fresh-r bw-log API (read-only, current data).

    IMPORTANT: A single persistent aiohttp.ClientSession is created on first
    login and reused for all API calls.  This is necessary because auth is
    cookie-based (PHPSESSID on dashboard.bw-log.com) — the cookie jar must
    survive between the login redirect and subsequent API POSTs.
    """

    def __init__(self, email: str, password: str, ha_session: aiohttp.ClientSession, hass=None) -> None:
        self._email      = email
        self._password   = password
        self._hass       = hass  # Home Assistant instance for storage
        # ha_session kept only for backward-compatibility; not used for API calls
        self._ha_session = ha_session
        self._token: str | None = None
        self._token_time: datetime | None = None  # Track when token was obtained
        # Welke ``token``-string in api.php ``q`` werkt (HAR: soms leeg als sessie alleen via cookies)
        self._api_q_token_override: str | None = None
        self._rate_limit_until: datetime | None = None  # Track rate limit backoff
        self._serials: list[str] = []  # Cached device serials
        # Persistent session — preserves cookies (PHPSESSID) across requests
        self._session: aiohttp.ClientSession | None = None
        # Session persistence storage
        self._store = None  # Will be initialized if hass is provided
        # Live monitoring
        self._monitor_requests = []
        self._monitor_responses = []
        # Thread safety locks
        self._login_lock = asyncio.Lock()
        self._data_lock = asyncio.Lock()

    def _log_request(self, method: str, url: str, headers: dict, data: str = None):
        """Log HTTP request for live monitoring and deep debugging"""
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
        
        if DEEP_DEBUG:
            _LOGGER.error("="*80)
            _LOGGER.error(f"🔍 DEEP DEBUG REQUEST [{timestamp}]")
            _LOGGER.error(f"Method: {method}")
            _LOGGER.error(f"URL: {url}")
            _LOGGER.error(f"Headers: {json.dumps(headers, indent=2)}")
            if data:
                _LOGGER.error(f"Data: {data}")
            _LOGGER.error("="*80)
        elif LIVE_MONITORING:
            _LOGGER.info(f"📤 REQUEST {timestamp}: {method} {url}")
            _LOGGER.info(f"📤 Headers: {headers}")
            if data:
                _LOGGER.info(f"📤 Data: {data}")
        
        if LIVE_MONITORING or DEEP_DEBUG:
            self._monitor_requests.append({
                'timestamp': timestamp,
                'method': method,
                'url': url,
                'headers': headers,
                'data': data
            })
            
            # Limit cache size to prevent memory issues
            if len(self._monitor_requests) > MAX_MONITOR_CACHE:
                self._monitor_requests = self._monitor_requests[-MAX_MONITOR_CACHE:]

    def _log_response(self, status: int, url: str, headers: dict, body: str, cookies):
        """Log HTTP response for live monitoring and deep debugging"""
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
        
        if DEEP_DEBUG:
            _LOGGER.error("="*80)
            _LOGGER.error(f"🔍 DEEP DEBUG RESPONSE [{timestamp}]")
            _LOGGER.error(f"Status: {status}")
            _LOGGER.error(f"URL: {url}")
            _LOGGER.error(f"Headers: {json.dumps(dict(headers), indent=2)}")
            _LOGGER.error(f"Body (first 2000 chars): {body[:2000]}")
            _LOGGER.error(f"Body length: {len(body)} bytes")
            _LOGGER.error("\n🍪 COOKIES IN JAR:")
            for cookie in cookies:
                _LOGGER.error(f"  - {cookie.key} = {cookie.value[:50]}... (domain: {cookie['domain']}, path: {cookie['path']})")
            _LOGGER.error("="*80)
        elif LIVE_MONITORING:
            _LOGGER.info(f"📥 RESPONSE {timestamp}: {status} {url}")
            _LOGGER.info(f"📥 Headers: {headers}")
            _LOGGER.info(f"📥 Body: {body[:200]}...")
            _LOGGER.info(f"📥 Cookies: {list(cookies)}")
        
        if LIVE_MONITORING or DEEP_DEBUG:
            self._monitor_responses.append({
                'timestamp': timestamp,
                'status': status,
                'url': url,
                'headers': headers,
                'body': body[:500] if not DEEP_DEBUG else body[:2000],
                'cookies': {c.key: c.value for c in cookies}
            })
            
            # Limit cache size to prevent memory issues
            if len(self._monitor_responses) > MAX_MONITOR_CACHE:
                self._monitor_responses = self._monitor_responses[-MAX_MONITOR_CACHE:]

    def _get_session(self) -> aiohttp.ClientSession:
        """Return the persistent session, creating it if needed or if closed."""
        if self._session is None or self._session.closed:
            # unsafe=True allows cookies to be shared across domains
            # quote_cookie=False prevents cookie value encoding issues
            jar = aiohttp.CookieJar(unsafe=True, quote_cookie=False)
            # Default connector: verified TLS for https:// (unsafe cookie jar still allows
            # cross-subdomain cookies for fresh-r.me / dashboard.bw-log.com).
            self._session = aiohttp.ClientSession(
                cookie_jar=jar,
                headers={"User-Agent": _USER_AGENT, "Accept-Language": "nl,en;q=0.9"},
                connector=aiohttp.TCPConnector(),
            )
        return self._session

    async def async_close(self) -> None:
        """Close the persistent HTTP session and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            # Allow time for cleanup
            await asyncio.sleep(0.25)
        self._session = None
        
        # Clear caches to free memory
        self._monitor_requests.clear()
        self._monitor_responses.clear()
        self._serials.clear()
        
        _LOGGER.debug("Fresh-R API client closed and resources cleaned up")

    # ── Login ──────────────────────────────────────────────────────────────────

    def _is_rate_limited(self) -> bool:
        """Check if we're currently in rate limit backoff period."""
        if self._rate_limit_until is None:
            return False
        return datetime.now(timezone.utc) < self._rate_limit_until
    
    def _set_rate_limit_backoff(self) -> None:
        """Set rate limit backoff period."""
        now_utc = datetime.now(timezone.utc)
        until = now_utc + timedelta(seconds=RATE_LIMIT_BACKOFF)
        self._rate_limit_until = until
        _LOGGER.warning(
            "Rate limit — client wacht %s s (~%s min); nu (UTC) %s; integratie probeert niet opnieuw vóór %s (UTC)",
            RATE_LIMIT_BACKOFF,
            max(1, RATE_LIMIT_BACKOFF // 60),
            now_utc.isoformat(),
            until.isoformat(),
        )
    
    def _is_token_expired(self) -> bool:
        """Check if current token is expired or needs refresh."""
        if self._token is None or self._token_time is None:
            return True
        age = (datetime.now(timezone.utc) - self._token_time).total_seconds()
        return age >= (TOKEN_EXPIRY_SECONDS - TOKEN_REFRESH_SECONDS)

    def _init_storage(self):
        """Initialize session storage if hass is available."""
        if self._hass and not self._store:
            from homeassistant.helpers.storage import Store
            self._store = Store(self._hass, 1, f"fresh_r_session_{self._email}")
            _LOGGER.info("📦 Session persistence enabled for %s", self._email)

    async def _save_session(self):
        """Save current session to persistent storage."""
        if not self._store or not self._token:
            return
        
        try:
            import time
            session_data = {
                "sess_token": self._token,
                "timestamp": time.time(),
                "email": self._email,
            }
            
            # Save cookies from session
            if self._session:
                cookies = {}
                for cookie in self._session.cookie_jar:
                    cookies[cookie.key] = {
                        "value": cookie.value,
                        "domain": cookie["domain"],
                        "path": cookie["path"],
                    }
                session_data["cookies"] = cookies
            
            await self._store.async_save(session_data)
            _LOGGER.info("💾 Session saved to storage (token=%.8s…)", self._token)
        except Exception as err:
            _LOGGER.warning("Failed to save session: %s", err)

    async def _restore_session(self) -> bool:
        """Try to restore session from persistent storage.
        
        Returns:
            True if session was restored and is valid, False otherwise
        """
        if not self._store:
            return False
        
        try:
            import time
            saved = await self._store.async_load()
            if not saved:
                _LOGGER.debug("No saved session found")
                return False
            
            # Check session age
            age = time.time() - saved.get("timestamp", 0)
            max_age = 86400  # 24 hours
            
            if age > max_age:
                _LOGGER.info("📅 Saved session expired (%.1f hours old)", age / 3600)
                return False
            
            _LOGGER.info("🔄 Attempting to restore session (%.1f hours old)", age / 3600)
            
            # Restore token
            self._token = saved.get("sess_token")
            self._token_time = datetime.now(timezone.utc) - timedelta(seconds=age)
            
            # Restore cookies if available
            if "cookies" in saved and self._session:
                for name, cookie_data in saved["cookies"].items():
                    self._session.cookie_jar.update_cookies(
                        {name: cookie_data["value"]},
                        response_url=URL(f"https://{cookie_data['domain']}{cookie_data['path']}")
                    )
                _LOGGER.debug("🍪 Restored %d cookies from storage", len(saved["cookies"]))
            
            # Test if restored session is still valid
            if await self._test_token():
                _LOGGER.info("✅ Session restored successfully (token=%.8s…)", self._token)
                return True
            else:
                _LOGGER.info("❌ Restored session is no longer valid")
                self._token = None
                self._token_time = None
                return False
                
        except Exception as err:
            _LOGGER.warning("Failed to restore session: %s", err)
            return False

    def _token_for_api_q(self) -> str:
        """Waarde voor ``token`` in ``api.php?q=…`` (override na succesvolle probe)."""
        if self._api_q_token_override is not None:
            return self._api_q_token_override
        return self._token or ""

    async def _test_token(self, session: aiohttp.ClientSession | None = None, token: str | None = None) -> bool:
        """Quick API call to test if current token is still valid.
        
        Probeert meerdere ``token``-vormen in ``q`` (HAR: 64-hex; soms leeg + alleen cookies;
        zelden ``PHPSESSID``). Zet ``_api_q_token_override`` bij succes met niet-standaard vorm.
        """
        test_token = token or self._token
        if not test_token:
            return False
        
        try:
            s = session or self._get_session()
            tz = self._tzoffset()
            self._api_q_token_override = None
            _jar_strip_token_failure_cookie(s.cookie_jar)

            variants: list[tuple[str, str]] = [
                (test_token, "hex_in_q"),
                ("", "token_leeg"),
            ]
            seen_tok = {test_token, ""}
            for val, lab in (
                (_phpsessid_dashboard(s.cookie_jar), "PHPSESSID_dashboard"),
                (_phpsessid_www_fresh_r(s.cookie_jar), "PHPSESSID_www"),
                (_phpsessid_apex_fresh_r(s.cookie_jar), "PHPSESSID_apex"),
            ):
                if val and val not in seen_tok:
                    seen_tok.add(val)
                    variants.append((val, lab))

            # HAR: POST met lege body, ``q`` in URL, sec-fetch cors, Chrome/macOS UA
            base_headers = {
                "Accept": "*/*",
                "Accept-Language": "nl,en-US;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Origin": "https://dashboard.bw-log.com",
                "Referer": "https://dashboard.bw-log.com/?page=devices",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "User-Agent": _DASHBOARD_CHROME_UA,
                "X-Requested-With": "XMLHttpRequest",
            }
            # Geen handmatige ``Cookie:``-header: aiohttp stuurt de jar automatisch mee op
            # ``dashboard.bw-log.com``. Dubbele of conflicterende Cookie-headers geven vaak
            # ``Invalid token`` op api.php (HAR gebruikt ook alleen de sessie-cookies).

            for tok_in_q, label in variants:
                headers = dict(base_headers)
                api_request = {
                    "tzoffset": tz,
                    "token": tok_in_q,
                    "requests": {
                        "user_info": {
                            "request": "userinfo",
                            "fields": ["first_name"],
                        }
                    },
                }
                q = json.dumps(api_request, separators=(",", ":"))
                post_url = f"{API_URL}?{urlencode({'q': q})}"
                if DEEP_DEBUG:
                    _LOGGER.error(
                        "🔍 API TEST variant=%s token_in_q=%.12s…",
                        label,
                        (tok_in_q[:12] if tok_in_q else "(leeg)"),
                    )
                async with s.post(
                    post_url,
                    headers=headers,
                    data=b"",
                    timeout=aiohttp.ClientTimeout(total=12),
                    allow_redirects=False,
                ) as r:
                    if r.status != 200:
                        _LOGGER.debug("API test variant %s: HTTP %s", label, r.status)
                        continue
                    body = await r.text()
                if DEEP_DEBUG:
                    _LOGGER.error("🔍 API TEST RESPONSE [%s]: %.500s", label, body[:500])
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    _LOGGER.debug("API test variant %s: geen JSON — %.120s", label, body[:120])
                    continue
                if not isinstance(data, dict):
                    continue
                user_info = data.get("user_info")
                if not isinstance(user_info, dict):
                    _LOGGER.warning(
                        "Token test [%s]: onverwachte vorm — keys=%s body=%.300s",
                        label,
                        list(data.keys()),
                        body[:300],
                    )
                    continue
                if user_info.get("success") is True:
                    if tok_in_q != test_token:
                        self._api_q_token_override = tok_in_q
                        _LOGGER.info(
                            "api.php: werkt met token-variant “%s” — opslaan voor volgende calls",
                            label,
                        )
                    else:
                        self._api_q_token_override = None
                    _LOGGER.debug("✓ Token test OK (variant %s)", label)
                    return True
                if user_info.get("success") is False:
                    reason = user_info.get("reason") or user_info.get("error") or "unknown"
                    _LOGGER.debug(
                        "Token test [%s]: API weigerde — %s",
                        label,
                        reason,
                    )
                    continue
                if any(k in user_info for k in ("first_name", "last_name", "locale", "type")):
                    if tok_in_q != test_token:
                        self._api_q_token_override = tok_in_q
                        _LOGGER.info(
                            "api.php: profiel OK met variant “%s” — opslaan voor volgende calls",
                            label,
                        )
                    else:
                        self._api_q_token_override = None
                    return True

            _LOGGER.warning(
                "Token test: alle varianten geweigerd (laatste reden zie DEBUG). "
                "Controleer sessie/cookies op dashboard.bw-log.com."
            )
            return False

        except Exception as err:
            _LOGGER.debug("Token test failed: %s", err)
            return False

    async def async_login(self, force: bool = False) -> None:
        """Authenticate and store session. Raises FreshRAuthError on failure.
        
        Thread-safe with lock to prevent concurrent logins.
        Implements session persistence to mimic browser behavior.
        
        Args:
            force: Force re-authentication even if token is still valid
        """
        async with self._login_lock:
            # Initialize storage on first use
            self._init_storage()
            
            # Try to restore saved session first (unless forced)
            if not force and await self._restore_session():
                _LOGGER.info("🎯 Using restored session - no login needed")
                return
            
            # Check rate limit
            if self._is_rate_limited():
                raise FreshRRateLimitError(
                    f"Rate limited until {self._rate_limit_until.strftime('%H:%M:%S')}. "
                    "Please wait before retrying."
                )
            
            # Skip login if token is still valid (double-check after acquiring lock)
            if not force and not self._is_token_expired():
                _LOGGER.debug("Token still valid, skipping login")
                return
            
            _LOGGER.info("🔐 Starting Fresh-R authentication...")
            s = self._get_session()
        
        # Retry logic with exponential backoff
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                if attempt > 0:
                    delay = RETRY_DELAY * (RETRY_BACKOFF_MULTIPLIER ** (attempt - 1))
                    _LOGGER.info("Retry attempt %d/%d after %.1fs delay", attempt + 1, MAX_RETRIES, delay)
                    await asyncio.sleep(delay)
                
                self._api_q_token_override = None
                # Step 1: Login and activate token (sets self._token internally)
                await self._login_and_follow_redirect(s)
                
                # Token is now set and activated - test it with an API call
                if self._token:
                    _LOGGER.info("Testing activated token with API call...")
                    if not await self._test_token(s, self._token):
                        _LOGGER.error(
                            "Fresh-r: login cookies/token zijn gezet, maar dashboard api.php "
                            "weigert de sessie. Controleer wachtwoord, of probeer later opnieuw "
                            "(Mogelijk andere response-vorm dan verwacht — zie DEBUG-log voor body)."
                        )
                        raise FreshRAuthError(
                            "Login gelukt niet volledig: API validatie mislukt na inloggen. "
                            "Controleer je gegevens of herstart en probeer opnieuw."
                        )
                    _LOGGER.info("Token validated successfully via API")
                    await self._save_session()
                    return
                else:
                    raise FreshRAuthError("Login failed - no token received from auth API")
                
            except FreshRRateLimitError:
                # Don't retry on rate limit - set backoff and re-raise
                self._set_rate_limit_backoff()
                raise
                
            except ClientConnectorError as err:
                last_error = err
                error_msg = str(err)
                
                # Specific error messages for common issues
                if "Name or service not known" in error_msg or "getaddrinfo failed" in error_msg:
                    _LOGGER.error("DNS resolution failed - cannot resolve Fresh-R domain")
                    if attempt == MAX_RETRIES - 1:
                        raise FreshRConnectionError(
                            "Cannot resolve Fresh-R domain - check internet connection and DNS settings"
                        ) from err
                elif "Connection refused" in error_msg:
                    _LOGGER.error("Connection refused - Fresh-R service may be down")
                    if attempt == MAX_RETRIES - 1:
                        raise FreshRConnectionError(
                            "Fresh-R service unavailable - server may be down or under maintenance"
                        ) from err
                else:
                    _LOGGER.warning(
                        "Network connection error on attempt %d/%d: %s",
                        attempt + 1, MAX_RETRIES, err
                    )
                    if attempt == MAX_RETRIES - 1:
                        raise FreshRConnectionError(f"Network error after {MAX_RETRIES} attempts: {err}") from err
                        
            except ClientSSLError as err:
                last_error = err
                _LOGGER.error("SSL/TLS certificate error: %s", err)
                if attempt == MAX_RETRIES - 1:
                    raise FreshRConnectionError(
                        "SSL certificate error - Fresh-R may have certificate issues. "
                        "Try again later or contact support."
                    ) from err
                    
            except ServerTimeoutError as err:
                last_error = err
                _LOGGER.warning(
                    "Server timeout on attempt %d/%d - slow network or server overload",
                    attempt + 1, MAX_RETRIES
                )
                if attempt == MAX_RETRIES - 1:
                    raise FreshRConnectionError(
                        f"Server timeout after {MAX_RETRIES} attempts - Fresh-R may be overloaded"
                    ) from err
                    
            except asyncio.TimeoutError as err:
                last_error = err
                _LOGGER.warning(
                    "Request timeout on attempt %d/%d - slow network connection",
                    attempt + 1, MAX_RETRIES
                )
                if attempt == MAX_RETRIES - 1:
                    raise FreshRConnectionError(
                        f"Request timeout after {MAX_RETRIES} attempts - check network speed"
                    ) from err
                    
            except aiohttp.ClientError as err:
                last_error = err
                _LOGGER.warning(
                    "Connection error on attempt %d/%d: %s",
                    attempt + 1, MAX_RETRIES, err
                )
                if attempt == MAX_RETRIES - 1:
                    raise FreshRConnectionError(f"Failed after {MAX_RETRIES} attempts: {err}") from err
                    
            except Exception as err:
                last_error = err
                _LOGGER.error(
                    "Unexpected error on attempt %d/%d: %s",
                    attempt + 1, MAX_RETRIES, err
                )
                if attempt == MAX_RETRIES - 1:
                    raise FreshRAuthError(f"Login failed after {MAX_RETRIES} attempts: {err}") from err
        
        # Should never reach here, but just in case
        raise FreshRAuthError(f"Login failed: {last_error}")

    async def _discover_hex_token_from_dashboard(
        self,
        s: aiohttp.ClientSession,
        *,
        referer: str = "https://www.fresh-r.me/",
    ) -> str | None:
        """GET ``/?page=devices`` so cookies / inline JS expose the hex API token (sess_token).

        Browsers often receive ``PHPSESSID`` on the first dashboard hit; the ``token`` field
        in ``api.php?q=...`` must match the hex session id the backend expects — that may only
        appear after loading the devices shell (same as HAR flow).
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "Referer": referer,
        }
        devices_url = f"{API_BASE}/?page=devices"
        try:
            async with s.get(
                devices_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=True,
            ) as dr:
                html = await dr.text()
                tok = _token_in_url(_safe_str_for_in(dr.url))
                if tok and _TOKEN_RE.match(tok):
                    return tok
                tok = _token_in_html(html)
                if tok and _TOKEN_RE.match(tok):
                    return tok
                tok = _token_in_jar(s.cookie_jar)
                if tok and _TOKEN_RE.match(tok):
                    return tok
        except aiohttp.ClientError as err:
            _LOGGER.debug("Dashboard GET for hex token failed: %s", err)
        return None

    async def _recover_if_auth_rate_limited_but_dashboard_ok(
        self, s: aiohttp.ClientSession
    ) -> bool:
        """auth.php meldt rate limit, maar bestaande dashboard-cookies laten api.php nog toe (zoals terug naar dashboard in de browser)."""
        _jar_strip_token_failure_cookie(s.cookie_jar)
        tok = _sess_token_value(s.cookie_jar) or _token_in_jar(s.cookie_jar)
        if not tok or not _TOKEN_RE.match(tok):
            return False
        prev = self._token
        self._token = tok
        self._token_time = datetime.now(timezone.utc)
        try:
            ok = await self._test_token(s, token=tok)
        except Exception:
            ok = False
        if not ok:
            self._token = prev
            return False
        _LOGGER.info(
            "auth.php: rate limit op nieuwe login — bestaande dashboard-sessie werkt nog voor api.php."
        )
        return True

    async def _login_and_follow_redirect(self, s: aiohttp.ClientSession) -> None:
        """Login and follow redirect to devices page.
        
        Raises:
            FreshRRateLimitError: If rate limited by API
            FreshRAuthError: If authentication fails
            aiohttp.ClientError: On network errors
        """
        # HAR: login + auth op **www**; dashboard navigate-GET gebruikt Referer https://www.fresh-r.me/
        login_page_url = f"{_LOGIN_WWW}/login/index.php?page=login"
        login_api_url = f"{_LOGIN_WWW}/login/api/auth.php"
        site_origin = _LOGIN_WWW
        dashboard_referer = f"{_LOGIN_WWW}/"

        # bw-log cookies niet hier wissen: bij rate limit kan een bestaande sessie nog geldig zijn.
        self._api_q_token_override = None

        # GET login page first
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "nl,en-US;q=0.9,en;q=0.8",
            }
            async with s.get(login_page_url, headers=headers, timeout=15) as r:
                _LOGGER.debug("GET login page: %s", r.status)
                # Log cookies after GET
                for cookie in s.cookie_jar:
                    _LOGGER.debug("Cookie after GET login page: %s=%s (domain=%s)", 
                                cookie.key, cookie.value[:8] if cookie.value else 'None', cookie['domain'])
        except aiohttp.ClientError as e:
            _LOGGER.warning("GET login page failed: %s", e)
        
        form = {"email": self._email, "password": self._password}
        # XHR/fetch (zoals login.js): server antwoordt vrijwel altijd met JSON.
        form_headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            # HAR: accept */* — anders geeft de server JSON i.p.v. HTML met dashboard-URL
            "Accept": "*/*",
            "Origin": site_origin,
            "Referer": login_page_url,
            "X-Requested-With": "XMLHttpRequest",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
            ),
        }
        json_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Origin": site_origin,
            "Referer": login_page_url,
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        def _form_login_response_complete(final_url: str, resp_body: str, status: int) -> bool:
            """True if we should NOT try JSON (dashboard redirect or JSON auth outcome)."""
            if "dashboard.bw-log.com" in _safe_str_for_in(final_url):
                return True
            b = (resp_body or "").strip()
            # HAR: auth.php kan text/html met dashboard-URL zijn (geen tweede POST nodig).
            if b.startswith("<") and "dashboard.bw-log.com" in b.lower():
                return True
            if b.startswith("{") and '"authenticated"' in b:
                try:
                    d = json.loads(b)
                    if d.get("authenticated") is True:
                        return True
                    if d.get("authenticated") is False:
                        return True  # definite failure — do not retry with JSON
                except json.JSONDecodeError:
                    return False
            return False
        
        try:
            if s.closed:
                s = self._get_session()
                
            body = ""
            login_status = None
            login_final_url = None
            # Max. 2 POSTs naar auth.php: XHR form-urlencoded (HAR) → JSON fallback.
            # Geen extra navigatie-POST: telt bij Fresh-r als aparte loginpoging en verergert rate limits.
            async with s.post(
                login_api_url,
                data=form,
                headers=form_headers,
                allow_redirects=True,
                timeout=20,
            ) as r0:
                body = await r0.text()
                login_status = r0.status
                login_final_url = r0.url
            if login_status == 429:
                _LOGGER.warning(
                    "auth.php HTTP 429 — fragment: %.220s",
                    (body or "").replace("\n", " "),
                )
                if await self._recover_if_auth_rate_limited_but_dashboard_ok(s):
                    return
                raise FreshRRateLimitError("Too many requests — auth.php returned HTTP 429")
            if _is_login_rate_limited_body(body):
                if await self._recover_if_auth_rate_limited_but_dashboard_ok(s):
                    return
                _raise_if_login_rate_limited(body)
            if not _form_login_response_complete(login_final_url, body, login_status):
                _LOGGER.info(
                    "auth.php: form POST geen dashboard/duidelijke JSON-auth — probeer JSON (fallback)"
                )
                async with s.post(
                    login_api_url,
                    data=json.dumps({"email": self._email, "password": self._password}),
                    headers=json_headers,
                    allow_redirects=True,
                    timeout=20,
                ) as r0:
                    body = await r0.text()
                    login_status = r0.status
                    login_final_url = r0.url
                if login_status == 429:
                    _LOGGER.warning(
                        "auth.php (JSON) HTTP 429 — fragment: %.220s",
                        (body or "").replace("\n", " "),
                    )
                    if await self._recover_if_auth_rate_limited_but_dashboard_ok(s):
                        return
                    raise FreshRRateLimitError("Too many requests — auth.php returned HTTP 429")
                if _is_login_rate_limited_body(body):
                    if await self._recover_if_auth_rate_limited_but_dashboard_ok(s):
                        return
                    _raise_if_login_rate_limited(body)
            _LOGGER.debug("Login API response status: %s", login_status)
            _LOGGER.debug("Login final URL: %s", login_final_url)

            # Log cookies after login
            if DEEP_DEBUG:
                _LOGGER.error("🍪 COOKIES AFTER LOGIN:")
                for cookie in s.cookie_jar:
                    _LOGGER.error("  - %s = %s (domain: %s, path: %s)", 
                                cookie.key, cookie.value[:20] + "..." if len(cookie.value) > 20 else cookie.value, 
                                str(cookie['domain']), str(cookie['path']))

            # HAR: auth.php kan **text/html** zijn met dashboard-URL; eerste GET is navigate + Referer www
            html_act = _extract_dashboard_activation_url_from_auth_body(body)
            if login_status == 200 and html_act:
                _LOGGER.info("auth.php HTML: dashboard-URL gevonden — navigate-GET (HAR-pad)")
                try:
                    nd = _navigate_dashboard_document_headers(dashboard_referer)
                    async with s.get(
                        html_act,
                        headers=nd,
                        timeout=aiohttp.ClientTimeout(total=25),
                        allow_redirects=True,
                    ) as r_html:
                        await r_html.text()
                        _LOGGER.info(
                            "HTML→dashboard GET: HTTP %s final=%s",
                            r_html.status,
                            r_html.url,
                        )
                except aiohttp.ClientError as err:
                    _LOGGER.warning("HTML→dashboard GET mislukt: %s", err)
                else:
                    st = _sess_token_value(s.cookie_jar) or _token_in_jar(s.cookie_jar)
                    if st and _TOKEN_RE.match(st):
                        self._token = st
                        self._token_time = datetime.now(timezone.utc)
                        _sync_dashboard_auth_cookie(s.cookie_jar, st)
                        _LOGGER.info("🔑 Sessie na HTML-auth-pad: %.8s…", st)
                        return
                    discovered = await self._discover_hex_token_from_dashboard(
                        s, referer=dashboard_referer
                    )
                    if discovered:
                        self._token = discovered
                        self._token_time = datetime.now(timezone.utc)
                        _sync_dashboard_auth_cookie(s.cookie_jar, discovered)
                        _LOGGER.info(
                            "🔑 Token via devices-HTML na HTML-auth: %.8s…", discovered
                        )
                        return

            # Check if we ended up on dashboard (success)
            if login_status == 200 and "dashboard.bw-log.com" in _safe_str_for_in(login_final_url):
                _LOGGER.info("✅ Login successful - redirected to dashboard")
                _LOGGER.info("Final URL: %s", login_final_url)

                # HAR (2026): ?t= in the redirect URL is an *activation* nonce — it is NOT
                # the same value as ``token`` inside api.php JSON. Browser: GET
                # /?page=devices&t=… → 302 → /?page=devices; server sets sess_token cookie;
                # XHR uses sess_token (64 hex chars), not t=.
                parsed_final = urlparse(_safe_str_for_in(login_final_url))
                url_token = (parse_qs(parsed_final.query).get("t") or [None])[0]
                if url_token:
                    act_url = f"{API_BASE}/?page=devices&t={quote(url_token, safe='')}"
                    act_headers = _navigate_dashboard_document_headers(dashboard_referer)
                    try:
                        async with s.get(
                            act_url,
                            headers=act_headers,
                            timeout=aiohttp.ClientTimeout(total=15),
                            allow_redirects=True,
                        ) as ar:
                            await ar.text()
                            _LOGGER.debug(
                                "Dashboard t= activation GET → HTTP %s final=%s",
                                ar.status,
                                ar.url,
                            )
                    except aiohttp.ClientError as err:
                        _LOGGER.warning("Dashboard activation GET failed: %s", err)

                    api_tok = _token_in_jar(s.cookie_jar)
                    if api_tok:
                        self._token = api_tok
                        self._token_time = datetime.now(timezone.utc)
                        _sync_dashboard_auth_cookie(s.cookie_jar, api_tok)
                        _LOGGER.info(
                            "🔑 API token from cookies after t= activation: %.8s… "
                            "(t= ≠ api token — matches browser/HAR)",
                            api_tok,
                        )
                        return
                    _LOGGER.warning(
                        "t= in URL but no hex sess_token in jar after activation — falling back"
                    )

                # sess_token cookie (Hex) if present
                sess_from_jar = None
                for cookie in s.cookie_jar:
                    if cookie.key == "sess_token" and "bw-log.com" in _safe_str_for_in(
                        cookie["domain"]
                    ):
                        sess_from_jar = cookie.value
                        break
                if sess_from_jar and _TOKEN_RE.match(sess_from_jar):
                    self._token = sess_from_jar
                    self._token_time = datetime.now(timezone.utc)
                    _sync_dashboard_auth_cookie(s.cookie_jar, sess_from_jar)
                    _LOGGER.info(
                        "🔑 Using sess_token cookie for API: %.8s…", sess_from_jar
                    )
                    return

                # Load devices shell (browser does this); often sets / reveals hex sess_token
                discovered = await self._discover_hex_token_from_dashboard(
                    s, referer=dashboard_referer
                )
                if discovered:
                    self._token = discovered
                    self._token_time = datetime.now(timezone.utc)
                    _sync_dashboard_auth_cookie(s.cookie_jar, discovered)
                    _LOGGER.info(
                        "🔑 Token from dashboard devices GET: %.8s…", discovered
                    )
                    return

                # Any hex token in jar after redirect (auth_token, l, …)
                jar_any = _token_in_jar(s.cookie_jar)
                if jar_any:
                    self._token = jar_any
                    self._token_time = datetime.now(timezone.utc)
                    _sync_dashboard_auth_cookie(s.cookie_jar, jar_any)
                    _LOGGER.info(
                        "🔑 Using hex token from cookie jar: %.8s…", jar_any
                    )
                    return

                # Last resort: PHPSESSID — api.php often rejects this as JSON ``token``
                php_sessid = None
                for cookie in s.cookie_jar:
                    if cookie.key.upper() == "PHPSESSID" and "dashboard.bw-log.com" in _safe_str_for_in(
                        cookie["domain"]
                    ):
                        php_sessid = cookie.value
                        break
                if php_sessid:
                    _LOGGER.warning(
                        "Alleen PHPSESSID gevonden (geen hex sess_token). "
                        "api.php kan 'Invalid token' geven — probeer opnieuw of controleer Fresh-r."
                    )
                    self._token = php_sessid
                    self._token_time = datetime.now(timezone.utc)
                    _sync_dashboard_auth_cookie(s.cookie_jar, php_sessid)
                    return
                _LOGGER.error("❌ No dashboard token (t=), sess_token, or PHPSESSID")
                raise FreshRAuthError("Login failed - no session/token after redirect")

            # Fallback: Check for JSON response (old behavior)
            if login_status == 200 and body.startswith('{'):
                try:
                    data = json.loads(body)

                    if DEEP_DEBUG:
                        _LOGGER.error("\n" + "="*80)
                        _LOGGER.error("🔐 LOGIN RESPONSE DEBUG")
                        _LOGGER.error("="*80)
                        _LOGGER.error(f"Status: {login_status}")
                        _LOGGER.error(f"Response: {body}")
                        _LOGGER.error(f"Parsed JSON: {json.dumps(data, indent=2)}")
                        _LOGGER.error("="*80 + "\n")

                    if data.get("authenticated") is True:
                        auth_token = data.get("auth_token", "")
                        _LOGGER.info("Login successful - JSON authentication confirmed")
                        _LOGGER.info(
                            "Auth token received: %s (length: %d)",
                            auth_token[:16] if auth_token else "None",
                            len(auth_token) if auth_token else 0,
                        )

                        # Verwijder oude dashboard-cookies vóór nieuwe auth_token (retry na mislukte poging).
                        _strip_bw_log_cookies_from_jar(s.cookie_jar)

                        # Alleen auth_token in de jar vóór de eerste dashboard-GET; sess_token
                        # volgt uit Set-Cookie of wordt hierna gesynchroniseerd (zie protocol-doc).
                        if auth_token and _TOKEN_RE.match(auth_token):
                            _sync_dashboard_auth_cookie(
                                s.cookie_jar, auth_token, include_sess=False
                            )

                        # CRITICAL: Browser sends token in URL parameter to activate it
                        if auth_token:
                            act_t = _activation_nonce_from_login_json(data, auth_token)
                            _LOGGER.info(
                                "🔑 Activating session via dashboard GET (HAR: volg redirects → sess_token cookie)..."
                            )
                            # HAR: cross-site navigate naar dashboard met Referer https://www.fresh-r.me/
                            # (site-root). Met loginpagina-Referer redirect de shell soms naar fresh-r login.
                            dashboard_headers = _navigate_dashboard_document_headers(
                                dashboard_referer
                            )
                            try:
                                redirect_url = _dashboard_redirect_url_from_login_json(data)
                                if redirect_url:
                                    _LOGGER.info(
                                        "Activatie: auth-JSON bevat redirect — eerste GET (meestal juiste t=)"
                                    )
                                    try:
                                        async with s.get(
                                            redirect_url,
                                            headers=dashboard_headers,
                                            timeout=aiohttp.ClientTimeout(total=20),
                                            allow_redirects=True,
                                        ) as r_redir:
                                            await r_redir.text()
                                            _LOGGER.info(
                                                "Redirect-activatie GET: HTTP %s final=%s",
                                                r_redir.status,
                                                r_redir.url,
                                            )
                                    except aiohttp.ClientError as err:
                                        _LOGGER.warning("Redirect-activatie GET mislukt: %s", err)

                                # Eerst GET met ``?t=`` — shell zonder ``t`` redirect bij Fresh-r vaak naar
                                # login en verpest de dashboard-sessie voor api.php.
                                dashboard_url = f"{API_BASE}/?page=devices&t={quote(act_t, safe='')}"
                                _LOGGER.info(
                                    "Dashboard activatie-GET (met t=): %s",
                                    dashboard_url,
                                )
                                async with s.get(
                                    dashboard_url,
                                    headers=dashboard_headers,
                                    timeout=aiohttp.ClientTimeout(total=20),
                                    allow_redirects=True,
                                ) as dash_r:
                                    await dash_r.text()
                                    _LOGGER.info(
                                        "✅ Dashboard activation GET afgerond: HTTP %s final=%s",
                                        dash_r.status,
                                        dash_r.url,
                                    )
                                    if DEEP_DEBUG:
                                        _LOGGER.error(
                                            "🔍 DASHBOARD ACTIVATION final URL: %s",
                                            dash_r.url,
                                        )

                                dash_final = _safe_str_for_in(dash_r.url)
                                if (
                                    "login" in dash_final.lower()
                                    and "fresh-r.me" in dash_final
                                ):
                                    alt_h = dict(dashboard_headers)
                                    alt_h["Referer"] = "https://www.fresh-r.me/"
                                    _LOGGER.info(
                                        "Dashboard `t=` GET eindigde op login — "
                                        "herprobeer met Referer https://www.fresh-r.me/"
                                    )
                                    async with s.get(
                                        dashboard_url,
                                        headers=alt_h,
                                        timeout=aiohttp.ClientTimeout(total=20),
                                        allow_redirects=True,
                                    ) as dash_r2:
                                        await dash_r2.text()
                                        _LOGGER.info(
                                            "Dashboard activation (www Referer): HTTP %s final=%s",
                                            dash_r2.status,
                                            dash_r2.url,
                                        )

                                if not _sess_token_value(s.cookie_jar):
                                    _sync_dashboard_auth_cookie(s.cookie_jar, auth_token)
                                    _LOGGER.info(
                                        "Nog geen sess_token — extra GET %s/?page=devices (devices-shell, zoals browser)",
                                        API_BASE,
                                    )
                                    async with s.get(
                                        f"{API_BASE}/?page=devices",
                                        headers=dashboard_headers,
                                        timeout=aiohttp.ClientTimeout(total=20),
                                        allow_redirects=True,
                                    ) as shell_r:
                                        await shell_r.text()
                                        _LOGGER.debug(
                                            "Devices shell GET: HTTP %s final=%s",
                                            shell_r.status,
                                            shell_r.url,
                                        )

                                api_tok = _sess_token_value(s.cookie_jar)
                                if api_tok:
                                    self._token = api_tok
                                    self._token_time = datetime.now(timezone.utc)
                                    _sync_dashboard_auth_cookie(s.cookie_jar, api_tok)
                                    _LOGGER.info(
                                        "Fresh-r authenticated (sess_token voor api.php): %.8s…",
                                        api_tok,
                                    )
                                else:
                                    discovered = await self._discover_hex_token_from_dashboard(
                                        s, referer=dashboard_referer
                                    )
                                    if discovered:
                                        self._token = discovered
                                        self._token_time = datetime.now(timezone.utc)
                                        _sync_dashboard_auth_cookie(s.cookie_jar, discovered)
                                        _LOGGER.info(
                                            "Fresh-r authenticated (token uit dashboard-HTML): %.8s…",
                                            discovered,
                                        )
                                    else:
                                        jar_hex = _token_in_jar(s.cookie_jar)
                                        if jar_hex:
                                            self._token = jar_hex
                                            self._token_time = datetime.now(timezone.utc)
                                            _sync_dashboard_auth_cookie(s.cookie_jar, jar_hex)
                                            _LOGGER.warning(
                                                "Geen sess_token — gebruik hex-token uit jar (%s): %.8s… "
                                                "(api.php kan alsnog 'Invalid token' geven)",
                                                "auth_token?"
                                                if jar_hex == auth_token
                                                else "andere cookie",
                                                jar_hex,
                                            )
                                        else:
                                            _LOGGER.warning(
                                                "Geen sess_token — fallback naar JSON auth_token "
                                                "(api.php kan 'Invalid token' geven)"
                                            )
                                            self._token = auth_token
                                            self._token_time = datetime.now(timezone.utc)
                                            _sync_dashboard_auth_cookie(s.cookie_jar, auth_token)

                            except Exception as e:
                                _LOGGER.error(
                                    "❌ Dashboard GET failed - token may not be activated: %s", e
                                )
                                raise FreshRAuthError(f"Token activation failed: {e}") from e

                        return
                    if data.get("authenticated") is False:
                        msg = data.get("message", "Unknown error")
                        _LOGGER.warning("Login failed: %s", msg)
                        if "Too many login attempts" in msg or "too many" in msg.lower():
                            raise FreshRRateLimitError(f"Rate limited: {msg}")
                        raise FreshRAuthError(f"Login failed: {msg}")
                except json.JSONDecodeError:
                    _LOGGER.warning("Login response is not JSON: %s", body[:200])
                    raise FreshRAuthError("Login failed - unexpected response format")
            elif login_status == 429:
                _LOGGER.warning("Rate limited by API (HTTP 429)")
                raise FreshRRateLimitError("Too many requests - rate limited by API")
            elif login_status == 401 or login_status == 403:
                _LOGGER.warning("Authentication failed with status: %s", login_status)
                body_lower = body.lower()
                if "suspended" in body_lower or "banned" in body_lower:
                    raise FreshRAuthError("Account suspended or banned - contact Fresh-R support")
                elif "verify" in body_lower and "email" in body_lower:
                    raise FreshRAuthError("Email verification required - check your inbox")
                elif "blocked" in body_lower or "blacklist" in body_lower:
                    raise FreshRAuthError("IP address blocked - contact Fresh-R support")
                else:
                    raise FreshRAuthError(f"Invalid credentials - HTTP {login_status}")
            else:
                _LOGGER.warning("Login failed with status: %s", login_status)
                raise FreshRAuthError(f"Login failed - HTTP {login_status}")
                    
        except FreshRRateLimitError:
            # Re-raise rate limit errors without wrapping
            raise
        except ClientConnectorError as e:
            error_msg = str(e)
            if "Name or service not known" in error_msg or "getaddrinfo failed" in error_msg:
                _LOGGER.error("DNS resolution failed for Fresh-R login")
                raise FreshRConnectionError("Cannot resolve Fresh-R domain - check DNS/internet") from e
            elif "Connection refused" in error_msg:
                _LOGGER.error("Connection refused during login")
                raise FreshRConnectionError("Fresh-R service unavailable") from e
            else:
                _LOGGER.error("Network error during login: %s", e)
                raise FreshRConnectionError(f"Login connection failed: {e}") from e
        except ClientSSLError as e:
            _LOGGER.error("SSL error during login: %s", e)
            raise FreshRConnectionError("SSL certificate error - Fresh-R may have certificate issues") from e
        except aiohttp.ClientError as e:
            _LOGGER.error("Network error during login: %s", e)
            raise FreshRConnectionError(f"Login request failed: {e}") from e

    async def _extract_from_devices_page(self, s: aiohttp.ClientSession) -> str | None:
        """Extract session token and serial numbers via API endpoint.
        
        Raises:
            FreshRTokenExpiredError: If session token is invalid/expired
            FreshRConnectionError: On network errors
        """
        # Get sess_token from cookie jar
        sess_token = None
        for cookie in s.cookie_jar:
            if cookie.key == "sess_token":
                sess_token = cookie.value
                break
        
        if not sess_token:
            _LOGGER.error("No sess_token cookie found after login!")
            _LOGGER.debug("Available cookies: %s", [c.key for c in s.cookie_jar])
            raise FreshRAuthError("Session token not set - login may have failed")
        
        _LOGGER.info("Using sess_token for API request: %.8s…", sess_token)
        
        # Try to fetch devices via API with retry logic
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                if attempt > 0:
                    delay = RETRY_DELAY * (RETRY_BACKOFF_MULTIPLIER ** (attempt - 1))
                    _LOGGER.info("Retry devices API attempt %d/%d after %.1fs", attempt + 1, MAX_RETRIES, delay)
                    await asyncio.sleep(delay)
                
                return await self._fetch_devices_via_api(s, sess_token)
                
            except FreshRTokenExpiredError:
                # Token expired - don't retry, need to re-authenticate
                _LOGGER.warning("Session token expired, re-authentication required")
                raise
                
            except aiohttp.ClientError as err:
                last_error = err
                _LOGGER.warning(
                    "API connection error on attempt %d/%d: %s",
                    attempt + 1, MAX_RETRIES, err
                )
                if attempt == MAX_RETRIES - 1:
                    raise FreshRConnectionError(f"Failed to fetch devices after {MAX_RETRIES} attempts: {err}") from err
        
        # Should never reach here
        raise FreshRConnectionError(f"Failed to fetch devices: {last_error}")
    
    async def _fetch_devices_via_api(self, s: aiohttp.ClientSession, sess_token: str) -> str:
        """Fetch devices via API endpoint.
        
        Returns:
            Session token if successful
            
        Raises:
            FreshRTokenExpiredError: If token is invalid/expired
            aiohttp.ClientError: On network errors
        
        CRITICAL LEARNING (Maart 2026):
        ================================
        If authentication fails, DO NOT GUESS! Capture browser request FIRST:
        
        1. Open Chrome/Edge → F12 → Network tab → Preserve log
        2. Login to https://fresh-r.me
        3. Find api.php request in Network tab
        4. Right-click → Copy → Copy as HAR (or screenshot COMPLETE request)
        5. Analyze EVERYTHING:
           - Full URL (including query parameters!)
           - Request method
           - All headers
           - Request body
           - Response
        
        Fresh-R API uses NON-STANDARD authentication:
        - Token in QUERY STRING: /api.php?q={"token":"...","requests":{...}}
        - POST body is EMPTY (Content-Length: 0)
        - Cookie header also contains sess_token
        - Requires browser-like headers (X-Requested-With, Origin, Referer)
        
        This was missed for WEEKS because we didn't analyze query string parameters!
        """
        
        try:
            _jar_strip_token_failure_cookie(s.cookie_jar)
            # Use API endpoint to get user units (serial numbers)
            api_url = "https://dashboard.bw-log.com/api.php"
            
            # Build API request for user info and units
            # CRITICAL: Browser sends token IN the JSON query string, not POST body
            api_request = {
                "tzoffset": self._tzoffset(),
                "token": self._token_for_api_q(),
                "requests": {
                    "user_info": {
                        "request": "userinfo",
                        "fields": ["first_name", "last_name", "gender", "locale", "type"]
                    },
                    "user_units": {
                        "request": "syssearch",
                        "role": "user",
                        "fields": ["units"]
                    }
                }
            }
            
            # Browser: token in query ``q``, lege POST-body; cookies per host (geen handmatige Cookie:-soup).
            query_params = {
                "q": json.dumps(api_request, separators=(',', ':'))
            }
            api_url_with_query = f"{api_url}?{urlencode(query_params)}"
            
            headers = {
                "Accept": "*/*",
                "Accept-Language": "nl,en-US;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "User-Agent": _DASHBOARD_CHROME_UA,
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "https://dashboard.bw-log.com",
                "Referer": "https://dashboard.bw-log.com/?page=devices",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }
            ch2 = _dashboard_cookie_header_no_failure(s.cookie_jar)
            if ch2:
                headers["Cookie"] = ch2
            
            if DEEP_DEBUG:
                _LOGGER.error("\n" + "="*80)
                _LOGGER.error("🔍 FRESH-R API REQUEST DEBUG")
                _LOGGER.error("="*80)
                _LOGGER.error(f"URL: {api_url_with_query[:150]}...")
                _LOGGER.error(f"Method: POST")
                _LOGGER.error(f"Body: EMPTY (Content-Length: 0)")
                _LOGGER.error(f"\nHeaders:")
                for key, value in headers.items():
                    if key == "Cookie":
                        _LOGGER.error(f"  {key}: {value[:80]}...")
                    else:
                        _LOGGER.error(f"  {key}: {value}")
                _LOGGER.error(f"\nToken in query string: {self._token_for_api_q()[:20]}...")
                _LOGGER.error(f"Timezone Offset: {self._tzoffset()}")
                _LOGGER.error("="*80 + "\n")
            else:
                _LOGGER.debug("API request to: %s", api_url_with_query)
            
            async with s.post(
                api_url_with_query,
                headers=headers,
                data=b"",
                timeout=DEFAULT_TIMEOUT,
                allow_redirects=False
            ) as r:
                body = await r.text()
                
                if DEEP_DEBUG:
                    _LOGGER.error("\n" + "="*80)
                    _LOGGER.error("🔍 FRESH-R API RESPONSE DEBUG")
                    _LOGGER.error("="*80)
                    _LOGGER.error(f"Status Code: {r.status}")
                    _LOGGER.error(f"Response Body: {body}")
                    _LOGGER.error(f"Response Length: {len(body)} bytes")
                    _LOGGER.error("\n🍪 Cookie Jar State:")
                    for cookie in s.cookie_jar:
                        _LOGGER.error(f"  {cookie.key} = {cookie.value[:30]}... (domain: {cookie['domain']})")
                    
                    # Check for auth errors and provide guidance
                    if "not authenticated" in body.lower() or "invalid token" in body.lower():
                        _LOGGER.error("\n" + "⚠️"*40)
                        _LOGGER.error("❌ AUTHENTICATION FAILED!")
                        _LOGGER.error("⚠️"*40)
                        _LOGGER.error("\n🔍 NEXT STEPS - DO NOT GUESS:")
                        _LOGGER.error("1. Open browser → https://fresh-r.me → Login")
                        _LOGGER.error("2. F12 → Network tab → Find api.php request")
                        _LOGGER.error("3. Copy COMPLETE request (URL + Headers + Payload)")
                        _LOGGER.error("4. Compare with our request above")
                        _LOGGER.error("5. Find the difference")
                        _LOGGER.error("\n📋 What to check:")
                        _LOGGER.error("   - Is token in URL query string?")
                        _LOGGER.error("   - Are all cookies sent?")
                        _LOGGER.error("   - Are all headers present?")
                        _LOGGER.error("   - Is POST body empty?")
                        _LOGGER.error("\n💡 Export HAR file for complete analysis")
                        _LOGGER.error("="*80 + "\n")
                    _LOGGER.error("="*80 + "\n")
                else:
                    _LOGGER.info("Devices API response status: %s", r.status)
                    _LOGGER.debug("Devices API response body: %s", body[:500])
                
                # Check for redirects (indicates auth failure)
                if r.status in (301, 302, 303, 307, 308):
                    redirect_url = _safe_str_for_in(r.headers.get("Location"))
                    _LOGGER.error("Redirected to %s - session token likely expired", redirect_url)
                    if 'login' in redirect_url.lower() or 'vaventis' in redirect_url.lower():
                        raise FreshRTokenExpiredError("Session expired - redirected to login page")
                    raise FreshRAuthError(f"Unexpected redirect to {redirect_url}")
                
                # Check for auth errors
                if r.status == 401 or r.status == 403:
                    if DEEP_DEBUG:
                        _LOGGER.error("🔍 DEEP DEBUG: Auth failed - analyzing response")
                        _LOGGER.error(f"Response body: {body}")
                        _LOGGER.error(f"Response headers: {dict(r.headers)}")
                    _LOGGER.error("Authentication failed (HTTP %s) - token may be expired", r.status)
                    raise FreshRTokenExpiredError(f"Session token invalid - HTTP {r.status}")
                
                if r.status == 429:
                    _LOGGER.warning("Rate limited by devices API (HTTP 429)")
                    raise FreshRRateLimitError("Too many requests to devices API")
                
                if r.status == 200:
                    # Check if we got HTML (redirect page) before parsing JSON
                    if '<html' in body.lower() or '<!doctype' in body.lower():
                        if 'vaventis' in body.lower() or 'login' in body.lower():
                            raise FreshRTokenExpiredError("Received login page instead of API response - token expired")
                        raise FreshRAuthError("Received HTML page instead of API response")
                    
                    # Use safe JSON parsing with detailed error reporting
                    data = _safe_json_parse(body, "Devices API")
                    
                    # DEEP DEBUG: Log complete API response structure
                    if DEEP_DEBUG:
                        _LOGGER.error("🔍 DEEP DEBUG: Parsed JSON Response")
                        _LOGGER.error(f"Top-level keys: {list(data.keys())}")
                        _LOGGER.error(f"Full JSON (pretty-printed):\n{json.dumps(data, indent=2)}")
                        
                        # Analyze each top-level key
                        for key, value in data.items():
                            _LOGGER.error(f"\n🔍 Analyzing key '{key}':")
                            _LOGGER.error(f"  Type: {type(value).__name__}")
                            if isinstance(value, dict):
                                _LOGGER.error(f"  Dict keys: {list(value.keys())}")
                                _LOGGER.error(f"  Dict content: {json.dumps(value, indent=4)}")
                            elif isinstance(value, list):
                                _LOGGER.error(f"  List length: {len(value)}")
                                if value:
                                    _LOGGER.error(f"  First item type: {type(value[0]).__name__}")
                                    _LOGGER.error(f"  First item: {value[0]}")
                                _LOGGER.error(f"  Full list: {value}")
                            else:
                                _LOGGER.error(f"  Value: {value}")
                    else:
                        _LOGGER.error("DEBUG: Full API response keys: %s", list(data.keys()))
                        _LOGGER.error("DEBUG: Full API response: %s", json.dumps(data, indent=2)[:1000])
                    
                    # Check for error responses in JSON
                    if "error" in data:
                        error_msg = data.get("error", "Unknown error")
                        _LOGGER.error("API returned error: %s", error_msg)
                        if "token" in error_msg.lower() or "auth" in error_msg.lower():
                            raise FreshRTokenExpiredError(f"API error: {error_msg}")
                        raise FreshRConnectionError(f"API error: {error_msg}")
                    
                    # Extract serial numbers from user_units with flexible field names
                    serials = None
                    
                    # Try all possible field combinations
                    if DEEP_DEBUG:
                        _LOGGER.error("\n🔍 DEEP DEBUG: Searching for device serials...")
                    
                    if "user_units" in data:
                        if DEEP_DEBUG:
                            _LOGGER.error("✓ Found 'user_units' key")
                            _LOGGER.error(f"  Type: {type(data['user_units']).__name__}")
                            _LOGGER.error(f"  Content: {json.dumps(data['user_units'], indent=4)}")
                        
                        if isinstance(data["user_units"], dict) and "units" in data["user_units"]:
                            serials = data["user_units"]["units"]
                            if DEEP_DEBUG:
                                _LOGGER.error(f"✓ Found serials in user_units.units: {serials}")
                        elif isinstance(data["user_units"], list):
                            serials = data["user_units"]
                            if DEEP_DEBUG:
                                _LOGGER.error(f"✓ user_units is a list: {serials}")
                    
                    if not serials and "units" in data:  # Alternative format
                        serials = data["units"]
                        if DEEP_DEBUG:
                            _LOGGER.error(f"✓ Found serials in top-level 'units': {serials}")
                    
                    if not serials and "devices" in data:  # Another alternative
                        serials = data["devices"]
                        if DEEP_DEBUG:
                            _LOGGER.error(f"✓ Found serials in 'devices': {serials}")
                    
                    if serials:
                        if DEEP_DEBUG:
                            _LOGGER.error("\n🔍 DEEP DEBUG: Processing found serials")
                            _LOGGER.error(f"Serials type: {type(serials).__name__}")
                            _LOGGER.error(f"Serials value: {serials}")
                        else:
                            _LOGGER.error("DEBUG: Serials found, type: %s, value: %s", type(serials), serials)
                        
                        # Handle different serial formats
                        if isinstance(serials, list):
                            # List of serials or list of dicts with 'id' field
                            serial_strings = []
                            for item in serials:
                                if isinstance(item, str):
                                    serial_strings.append(item)
                                elif isinstance(item, dict) and "id" in item:
                                    serial_strings.append(item["id"])
                                else:
                                    _LOGGER.warning("Unknown serial format in list: %s", item)
                            serials = serial_strings
                        elif isinstance(serials, dict):
                            # Dict with serial as key or 'id' field
                            if "id" in serials:
                                serials = [serials["id"]]
                            else:
                                serials = list(serials.keys())
                        
                        if DEEP_DEBUG:
                            _LOGGER.error(f"\n🔍 DEEP DEBUG: Processed serials: {serials}")
                        else:
                            _LOGGER.error("DEBUG: Processed serials: %s", serials)
                        
                        # Validate device serials
                        valid_serials = [s for s in serials if _validate_device_serial(s)]
                        
                        if valid_serials:
                            _LOGGER.info("Successfully found %d valid device(s) via API: %s", len(valid_serials), valid_serials)
                            if len(valid_serials) < len(serials):
                                _LOGGER.warning(
                                    "Filtered out %d invalid serial(s): %s",
                                    len(serials) - len(valid_serials),
                                    [s for s in serials if not _validate_device_serial(s)]
                                )
                            self._serials = valid_serials
                            return sess_token
                        else:
                            _LOGGER.error("No valid device serials found. Raw serials: %s", serials)
                            raise FreshRAuthError(
                                f"No valid devices found - invalid serial formats: {serials}"
                            )
                    else:
                        if DEEP_DEBUG:
                            _LOGGER.error("\n❌ DEEP DEBUG: NO SERIALS FOUND!")
                            _LOGGER.error("Checked all possible field combinations")
                            _LOGGER.error(f"Available top-level keys: {list(data.keys())}")
                            _LOGGER.error("\nDetailed analysis of each key:")
                            for key in data.keys():
                                _LOGGER.error(f"\nKey: '{key}'")
                                _LOGGER.error(f"  Type: {type(data[key]).__name__}")
                                _LOGGER.error(f"  Value: {json.dumps(data[key], indent=4) if isinstance(data[key], (dict, list)) else str(data[key])}")
                        else:
                            _LOGGER.error("No devices found in API response - checked all field combinations")
                            _LOGGER.error("Available top-level keys: %s", list(data.keys()))
                            for key in data.keys():
                                _LOGGER.error("Key '%s' type: %s, value: %s", key, type(data[key]), str(data[key])[:200])
                        raise FreshRAuthError(
                            "No devices found in account - verify your account has Fresh-R devices"
                        )
                else:
                    _LOGGER.error("API request failed with HTTP %s", r.status)
                    raise FreshRConnectionError(f"API request failed - HTTP {r.status}")
                    
        except (FreshRTokenExpiredError, FreshRRateLimitError, FreshRAuthError):
            # Re-raise our custom exceptions
            raise
        except aiohttp.ClientError as e:
            _LOGGER.error("Network error fetching devices: %s", e)
            raise

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

    async def _login_one(self, s: aiohttp.ClientSession, login_page_url: str) -> str | None:
        """POST credentials to auth API endpoint and extract auth_token from JSON response.
        
        The correct login endpoint is /login/api/auth.php (not the form action).
        Returns the auth_token from JSON response {"authenticated": true, "auth_token": "..."}
        """
        
        # Same host as login page (www vs apex) — HAR gebruikt www.fresh-r.me
        login_api_url = f"{_origin(login_page_url)}/login/api/auth.php"
        
        # Step 1 — GET login page to establish PHPSESSID cookie
        try:
            # Ensure we have a fresh session
            s = self._get_session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "nl,en-US;q=0.9,en;q=0.8,de;q=0.7,ms;q=0.6,id;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            self._log_request('GET', login_page_url, headers)
            
            async with s.get(login_page_url, allow_redirects=True,
                             headers=headers,
                             timeout=aiohttp.ClientTimeout(total=15)) as r:
                body = await r.text()
                self._log_response(r.status, str(r.url), dict(r.headers), body, s.cookie_jar)
        except aiohttp.ClientError as e:
            _LOGGER.warning("GET %s failed: %s", login_page_url, e)
            # Don't re-raise, continue to POST attempt

        # Step 2 — POST credentials to the API endpoint
        form = {"email": self._email, "password": self._password}
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "*/*",
            "Accept-Language": "nl,en-US;q=0.9,en;q=0.8,de;q=0.7,ms;q=0.6,id;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Origin": _origin(login_page_url),
            "Referer": login_page_url,
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        }
        
        self._log_request('POST', login_api_url, headers, f"email={self._email}&password=***")
        
        try:
            # Ensure session is still open
            if s.closed:
                _LOGGER.warning("Session was closed, creating new session")
                s = self._get_session()
                
            async with s.post(
                login_api_url,
                data=form,
                headers=headers,
                allow_redirects=True,  # CRITICAL: Follow the 302 redirect!
                timeout=aiohttp.ClientTimeout(total=20),
            ) as r:
                body = await r.text()
                self._log_response(r.status, str(r.url), dict(r.headers), body, s.cookie_jar)
                
                # Check if we're redirected to dashboard (success!)
                if "dashboard.bw-log.com" in _safe_str_for_in(r.url) and "page=devices" in _safe_str_for_in(r.url):
                    _LOGGER.info("Login successful - redirected to dashboard: %s", r.url)
                    # Extract token from redirect URL parameter
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(_safe_str_for_in(r.url))
                    token = parse_qs(parsed.get('query', '')).get('t', [None])[0]
                    if token:
                        return token
                    # If no token in URL, use PHPSESSID
                    phpsessid = _phpsessid_from_jar(s.cookie_jar)
                    if phpsessid:
                        return phpsessid
                
                # Handle JSON response (fallback)
                if r.status == 200:
                    try:
                        data = json.loads(body)
                        if data.get("authenticated") == True and "auth_token" in data:
                            auth_token = data["auth_token"]
                            _LOGGER.info("Login successful - auth_token received")
                            return auth_token
                        elif data.get("authenticated") == False:
                            msg = data.get("message", "Unknown error")
                            _LOGGER.warning("Login failed: %s", msg)
                            if "Too many login attempts" in msg:
                                raise FreshRAuthError(f"Rate limited: {msg}")
                            return None
                    except json.JSONDecodeError:
                        _LOGGER.warning("Login response is not valid JSON: %s", body[:100])
                        
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
        """GET dashboard.bw-log.com/?page=devices and extract serial numbers.

        Chrome HAR: eerste document-GET is ``/?page=devices`` (zonder ``t=``), Referer
        ``https://www.fresh-r.me/``. Tweede poging: ``?page=devices&t=`` als de server
        zonder ``t=`` de Vaventis-shell geeft.
        """
        s = self._get_session()
        s.cookie_jar.update_cookies(
            {"auth_token": self._token or ""},
            URL("https://dashboard.bw-log.com"),
        )

        urls: list[str] = [f"{API_BASE}/?page=devices"]
        if self._token:
            urls.append(
                f"{API_BASE}/?page=devices&t={quote(self._token, safe='')}"
            )

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "Accept-Language": "nl,en-US;q=0.9,en;q=0.8,de;q=0.7,ms;q=0.6,id;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://www.fresh-r.me/",
        }

        last_html = ""
        for attempt, devices_url in enumerate(urls, start=1):
            self._log_request("GET", devices_url, headers)
            try:
                async with s.get(
                    devices_url,
                    allow_redirects=True,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as r:
                    html = await r.text()
                    last_html = html
                    self._log_response(
                        r.status, str(r.url), dict(r.headers), html, s.cookie_jar
                    )
                    _LOGGER.debug(
                        "Devices page GET [%s/%s] %s → %s (final: %s)",
                        attempt,
                        len(urls),
                        devices_url,
                        r.status,
                        str(r.url),
                    )
                    if r.status != 200:
                        _LOGGER.error("Devices page returned HTTP %s", r.status)
                        continue

                    serials = _serials_in_html(html)
                    if serials:
                        _LOGGER.info(
                            "Discovered device serial(s) from HTML: %s", serials
                        )
                        return [
                            {"id": s, "type": "Fresh-r", "room": ""} for s in serials
                        ]

                    low = html[:6000].lower()
                    if "vaventis" in low and attempt < len(urls):
                        _LOGGER.debug(
                            "Devices HTML looks like Vaventis shell — retry with ?t= "
                            "(attempt %s)",
                            attempt + 1,
                        )
                        continue

                    if "vaventis" in low:
                        _LOGGER.error(
                            "Fresh-r: devices-HTML is de Vaventis login/shell "
                            "(geen dashboard). Sessie ontbreekt of is verlopen — "
                            "Integratie → Fresh-r → opnieuw inloggen."
                        )
                    else:
                        _LOGGER.warning(
                            "No serial numbers found on devices page. Body snippet: %.500s",
                            html[:500],
                        )
                    return []
            except aiohttp.ClientError as e:
                _LOGGER.error("Could not fetch devices page (%s): %s", devices_url, e)
                continue

        if last_html:
            _LOGGER.warning(
                "No serial numbers after %s URL attempt(s). Snippet: %.500s",
                len(urls),
                last_html[:500],
            )
        return []

    # ── Current data ───────────────────────────────────────────────────────────

    async def async_get_current(self, serial: str) -> dict[str, float]:
        """Home Assistant coordinator entrypoint: fetch values for one device serial."""
        return await self.get_current_data(serial)

    async def get_current_data(self, serial: str) -> dict[str, float]:
        """Fetch current sensor values for the configured device.
        Returns a dict with calibrated values (flow, temps, etc.).
        
        Thread-safe with lock. Automatically handles token refresh and retries on failures.
        
        Raises:
            FreshRConnectionError: On network errors after retries
            FreshRAuthError: On authentication failures
            FreshRDataValidationError: If no valid sensor data received
        """
        async with self._data_lock:
            # Check if token needs refresh
            if self._is_token_expired():
                _LOGGER.info("Token expired or near expiry, refreshing...")
                try:
                    await self.async_login(force=True)
                except FreshRRateLimitError:
                    # If rate limited, try to use existing token anyway
                    _LOGGER.warning("Rate limited during token refresh, attempting with existing token")
                    if self._token is None:
                        raise
            
            # Retry logic for data fetching
            last_error = None
            for attempt in range(MAX_RETRIES):
                try:
                    if attempt > 0:
                        delay = RETRY_DELAY * (RETRY_BACKOFF_MULTIPLIER ** (attempt - 1))
                        _LOGGER.info("Retry data fetch attempt %d/%d after %.1fs", attempt + 1, MAX_RETRIES, delay)
                        await asyncio.sleep(delay)
                    
                    raw_data = await self._fetch_current_data(serial)
                    
                    # Validate sensor data before returning
                    validated_data = _validate_sensor_data(raw_data)
                    _LOGGER.debug("Validated %d sensor values", len(validated_data))
                    
                    return validated_data
                    
                except FreshRTokenExpiredError:
                    # Token expired during fetch - try to refresh once
                    _LOGGER.warning("Token expired during data fetch, attempting refresh")
                    try:
                        await self.async_login(force=True)
                        # Retry immediately after refresh
                        raw_data = await self._fetch_current_data(serial)
                        return _validate_sensor_data(raw_data)
                    except FreshRRateLimitError:
                        # Can't refresh due to rate limit
                        raise FreshRConnectionError("Token expired and cannot refresh due to rate limit")
                        
                except FreshRRateLimitError:
                    # Don't retry on rate limit
                    raise
                    
                except FreshRDataValidationError:
                    # Don't retry on validation errors - data is fundamentally bad
                    raise
                    
                except aiohttp.ClientError as err:
                    last_error = err
                    _LOGGER.warning(
                        "Connection error fetching data on attempt %d/%d: %s",
                        attempt + 1, MAX_RETRIES, err
                    )
                    if attempt == MAX_RETRIES - 1:
                        raise FreshRConnectionError(f"Failed to fetch data after {MAX_RETRIES} attempts: {err}") from err
            
            # Should never reach here
            raise FreshRConnectionError(f"Failed to fetch data: {last_error}")
    
    async def _fetch_current_data(self, serial: str) -> dict[str, float]:
        """Internal method to fetch current data without retry logic.
        
        Raises:
            FreshRTokenExpiredError: If token is expired
            FreshRRateLimitError: If rate limited
            aiohttp.ClientError: On network errors
        """
        # Check if token needs proactive refresh
        if self._token and self._token_time:
            token_age = (datetime.now(timezone.utc) - self._token_time).total_seconds()
            if token_age > (TOKEN_EXPIRY_SECONDS - TOKEN_REFRESH_SECONDS):
                _LOGGER.info("Token expires soon (%.0fs old) - proactive re-login", token_age)
                await self._refresh_token()
        
        if not self._token:
            await self.async_login()
            
        rk = _fresh_r_now_request_key(serial)
        req = {
            rk: {
                "request": "fresh-r-now",
                "serial": serial,
                "fields": FIELDS_NOW,
            }
        }
        try:
            raw = await self._call(req)
        except FreshRConnectionError:
            _LOGGER.info("API error — re-authenticating")
            await self._refresh_token()
            raw = await self._call(req)
        # HAR: response uses same key as request; legacy integrations used ``current-data``
        block = raw.get(rk) or raw.get("current-data") or {}
        if not block and raw:
            _LOGGER.debug(
                "fresh-r-now: no data under %r or current-data; response keys: %s",
                rk,
                list(raw.keys()),
            )
        return self._parse(block)

    # ── Internal ───────────────────────────────────────────────────────────────

    @staticmethod
    def _tzoffset() -> str:
        off = datetime.now(timezone.utc).astimezone().utcoffset()
        return str(abs(int(off.total_seconds() / 60))) if off else "0"

    async def _call(self, requests: dict[str, Any]) -> dict[str, Any]:
        """POST to api.php using the auth_token and proper headers."""
        s = self._get_session()
        q = json.dumps({
            "token":    self._token_for_api_q(),
            "tzoffset": self._tzoffset(),
            "requests": requests,
        })
        try:
            _jar_strip_token_failure_cookie(s.cookie_jar)
            hdrs = {
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "https://dashboard.bw-log.com",
                "Referer": "https://dashboard.bw-log.com/?page=devices",
            }
            ch = _dashboard_cookie_header_no_failure(s.cookie_jar)
            if ch:
                hdrs["Cookie"] = ch
            async with s.post(
                API_URL, 
                params={"q": q},
                headers=hdrs,
                data=b"",
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

        # Humidity tab: water vapor (g/m³) from indoor T + RH
        if "t1" in result and "hum" in result:
            result["water_vapor"] = water_vapor_g_m3(result["t1"], result["hum"])

        return result

    async def _refresh_token(self) -> None:
        """Refresh the authentication token."""
        _LOGGER.debug("Refreshing authentication token")
        self._token = None
        self._token_time = None
        await self.async_login()
