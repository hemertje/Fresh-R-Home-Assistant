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

import asyncio
import json
import logging
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import parse_qs, urljoin, urlparse

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

# Serial pattern: e.g. "e:XXXXXX/XXXXXX" or just digits
_SERIAL_RE = re.compile(r'serial=([^&"\'>\s]+)', re.I)
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
    
    # Humidity validation
    if 'humidity' in data:
        try:
            hum = float(data['humidity'])
            if HUMIDITY_MIN <= hum <= HUMIDITY_MAX:
                validated['humidity'] = hum
            else:
                _LOGGER.warning(
                    "Humidity out of range: %.1f%% (valid: %.0f to %.0f%%)",
                    hum, HUMIDITY_MIN, HUMIDITY_MAX
                )
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Invalid humidity value: %s (%s)", data['humidity'], err)
    
    # Copy other fields without validation
    for key in data:
        if key not in validated and key not in ['t1', 't2', 't3', 't4', 'flow', 'co2', 'humidity']:
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
    # Pattern confirmed from HTML analysis: serial="e:XXXXXX/XXXXXX" (PRIVACY PROTECTED)
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

    def __init__(self, email: str, password: str, ha_session: aiohttp.ClientSession, hass=None) -> None:
        self._email      = email
        self._password   = password
        self._hass       = hass  # Home Assistant instance for storage
        # ha_session kept only for backward-compatibility; not used for API calls
        self._ha_session = ha_session
        self._token: str | None = None
        self._token_time: datetime | None = None  # Track when token was obtained
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
            self._session = aiohttp.ClientSession(
                cookie_jar=jar,
                headers={"User-Agent": _USER_AGENT, "Accept-Language": "nl,en;q=0.9"},
                # Treat both domains as secure origins for cookie sharing
                connector=aiohttp.TCPConnector(
                    ssl=False,  # Allow HTTP for local testing
                ),
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
        self._rate_limit_until = datetime.now(timezone.utc) + timedelta(seconds=RATE_LIMIT_BACKOFF)
        _LOGGER.warning(
            "Rate limit detected - backing off until %s",
            self._rate_limit_until.strftime("%H:%M:%S")
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

    async def _test_token(self, session: aiohttp.ClientSession | None = None, token: str | None = None) -> bool:
        """Quick API call to test if current token is still valid.
        
        Args:
            session: Optional session to use (for testing during login)
            token: Optional token to test (defaults to self._token)
        
        Returns:
            True if token works, False otherwise
        """
        test_token = token or self._token
        if not test_token:
            return False
        
        try:
            s = session or self._get_session()
            
            # Quick API call with minimal data
            import time
            tz_offset = int(time.timezone / 60)

            # Same shape as _call(): token + tzoffset + requests inside JSON param `q`.
            # Session cookie jar is applied automatically by aiohttp.
            api_request = {
                "tzoffset": str(abs(tz_offset)),
                "token": test_token,
                "requests": {
                    "user_info": {
                        "request": "userinfo",
                        "fields": ["first_name"],
                    }
                },
            }
            q = json.dumps(api_request, separators=(",", ":"))
            headers = {
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "https://dashboard.bw-log.com",
                "Referer": "https://dashboard.bw-log.com/?page=devices",
                "Accept": "*/*",
            }
            if DEEP_DEBUG:
                _LOGGER.error("🔍 API TEST (userinfo) params q token prefix: %.12s…", test_token[:12])
            async with s.post(
                API_URL,
                params={"q": q},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
                allow_redirects=False,
            ) as r:
                if r.status != 200:
                    _LOGGER.debug("API test failed with status: %s", r.status)
                    return False
                
                body = await r.text()
                data = _safe_json_parse(body, "Token test")
                
                if DEEP_DEBUG:
                    _LOGGER.error("🔍 API TEST RESPONSE - Status: %s, Body: %.500s", r.status, body[:500])
                
                # Check if authenticated
                if "user_info" in data:
                    user_info = data["user_info"]
                    if isinstance(user_info, dict) and user_info.get("success") == True:
                        _LOGGER.debug("✓ Token test successful")
                        return True
                
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
                
                # Step 1: Login and activate token (sets self._token internally)
                await self._login_and_follow_redirect(s)
                
                # Token is now set and activated - test it with an API call
                if self._token:
                    _LOGGER.info("Testing activated token with API call...")
                    await self._test_token(s, self._token)
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

    async def _login_and_follow_redirect(self, s: aiohttp.ClientSession) -> None:
        """Login and follow redirect to devices page.
        
        Raises:
            FreshRRateLimitError: If rate limited by API
            FreshRAuthError: If authentication fails
            aiohttp.ClientError: On network errors
        """
        login_api_url = "https://fresh-r.me/login/api/auth.php"
        login_page_url = "https://fresh-r.me/login/index.php?page=login"
        
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
        
        # POST credentials - Expect 302 redirect like browser
        form = {"email": self._email, "password": self._password}
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json, text/html, application/xhtml+xml, application/xml;q=0.9, */*;q=0.8",
            "Origin": "https://fresh-r.me",
            "Referer": login_page_url,
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        
        try:
            if s.closed:
                s = self._get_session()
                
            # FOLLOW redirects like browser - expect 302 to dashboard
            async with s.post(
                login_api_url,
                data=form,
                headers=headers,
                allow_redirects=True,  # FOLLOW redirects - browser behavior!
                timeout=20,
            ) as r:
                body = await r.text()
                _LOGGER.debug("Login API response status: %s", r.status)
                _LOGGER.debug("Login final URL: %s", r.url)
                
                # Log cookies after login
                if DEEP_DEBUG:
                    _LOGGER.error("🍪 COOKIES AFTER LOGIN:")
                    for cookie in s.cookie_jar:
                        _LOGGER.error("  - %s = %s (domain: %s, path: %s)", 
                                    cookie.key, cookie.value[:20] + "..." if len(cookie.value) > 20 else cookie.value, 
                                    str(cookie['domain']), str(cookie['path']))
                
                # Check if we ended up on dashboard (success)
                if r.status == 200 and "dashboard.bw-log.com" in _safe_str_for_in(r.url):
                    _LOGGER.info("✅ Login successful - redirected to dashboard")
                    _LOGGER.info("Final URL: %s", r.url)

                    # HAR/browser: token in query ?t=... (same hex as auth_token path)
                    parsed_final = urlparse(_safe_str_for_in(r.url))
                    url_token = (parse_qs(parsed_final.query).get("t") or [None])[0]
                    if url_token:
                        self._token = url_token
                        self._token_time = datetime.now(timezone.utc)
                        _LOGGER.info(
                            "🔑 Token from dashboard URL (t=): %.8s…",
                            url_token,
                        )
                        return

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
                        _LOGGER.info(
                            "🔑 Using sess_token cookie for API: %.8s…", sess_from_jar
                        )
                        return

                    # Fallback: PHPSESSID session id for api.php `token` + cookie jar
                    php_sessid = None
                    for cookie in s.cookie_jar:
                        if cookie.key == "PHPSESSID" and "dashboard.bw-log.com" in _safe_str_for_in(
                            cookie["domain"]
                        ):
                            php_sessid = cookie.value
                            break
                    
                    if php_sessid:
                        _LOGGER.info("🔑 PHPSESSID cookie found: %s...", php_sessid[:8])
                        self._token = php_sessid
                        self._token_time = datetime.now(timezone.utc)
                        return
                    _LOGGER.error("❌ No dashboard token (t=), sess_token, or PHPSESSID")
                    raise FreshRAuthError("Login failed - no session/token after redirect")
                
                # Fallback: Check for JSON response (old behavior)
                if r.status == 200 and body.startswith('{'):
                    try:
                        data = json.loads(body)
                        
                        if DEEP_DEBUG:
                            _LOGGER.error("\n" + "="*80)
                            _LOGGER.error("🔐 LOGIN RESPONSE DEBUG")
                            _LOGGER.error("="*80)
                            _LOGGER.error(f"Status: {r.status}")
                            _LOGGER.error(f"Response: {body}")
                            _LOGGER.error(f"Parsed JSON: {json.dumps(data, indent=2)}")
                            _LOGGER.error("="*80 + "\n")
                        
                        if data.get("authenticated") == True:
                            auth_token = data.get("auth_token", "")
                            _LOGGER.info("Login successful - JSON authentication confirmed")
                            _LOGGER.info("Auth token received: %s (length: %d)", auth_token[:16] if auth_token else 'None', len(auth_token) if auth_token else 0)
                            
                            # CRITICAL: Browser sends token in URL parameter to activate it
                            # HAR analysis shows: GET /?page=devices&t={token}
                            # This activates the token server-side before API calls work
                            if auth_token:
                                _LOGGER.info("🔑 Activating token via dashboard GET (HAR-verified flow)...")
                                
                                # Step 1: GET dashboard with token in URL (exactly as browser does)
                                # Don't follow redirects - just make the request to activate token
                                dashboard_url = f"https://dashboard.bw-log.com/?page=devices&t={auth_token}"
                                dashboard_headers = {
                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                                    "Referer": "https://fresh-r.me/",  # Coming from login page
                                }
                                
                                try:
                                    async with s.get(dashboard_url, headers=dashboard_headers, timeout=15, allow_redirects=False) as dash_r:
                                        _LOGGER.info("✅ Dashboard GET status: %s (token activation)", dash_r.status)
                                        
                                        # Server should return 302 redirect after activating token
                                        if dash_r.status == 302:
                                            _LOGGER.info("🎯 Token activated successfully (302 redirect) - ready for API calls")
                                        elif dash_r.status == 200:
                                            _LOGGER.info("🎯 Token activated successfully (200 OK) - ready for API calls")
                                        else:
                                            raise FreshRAuthError(
                                                f"Token activation failed (unexpected dashboard HTTP {dash_r.status})"
                                            )
                                        
                                        if DEEP_DEBUG:
                                            _LOGGER.error("="*80)
                                            _LOGGER.error("🔍 DASHBOARD ACTIVATION RESPONSE")
                                            _LOGGER.error(f"Status: {dash_r.status}")
                                            _LOGGER.error(f"URL: {dash_r.url}")
                                            _LOGGER.error(f"Headers: {dict(dash_r.headers)}")
                                            _LOGGER.error("="*80)
                                            
                                        # Store token directly - don't rely on cookies
                                        self._token = auth_token
                                        self._token_time = datetime.now(timezone.utc)
                                        _LOGGER.info("Fresh-r authenticated successfully (token=%.8s…)", auth_token)
                                        
                                except Exception as e:
                                    _LOGGER.error("❌ Dashboard GET failed - token may not be activated: %s", e)
                                    raise FreshRAuthError(f"Token activation failed: {e}") from e
                            
                            # Success! Session cookies are now set on correct domain
                            return
                        elif data.get("authenticated") == False:
                            msg = data.get("message", "Unknown error")
                            _LOGGER.warning("Login failed: %s", msg)
                            # Detect rate limiting
                            if "Too many login attempts" in msg or "too many" in msg.lower():
                                raise FreshRRateLimitError(f"Rate limited: {msg}")
                            raise FreshRAuthError(f"Login failed: {msg}")
                    except json.JSONDecodeError:
                        _LOGGER.warning("Login response is not JSON: %s", body[:200])
                        raise FreshRAuthError("Login failed - unexpected response format")
                elif r.status == 429:
                    # HTTP 429 Too Many Requests
                    _LOGGER.warning("Rate limited by API (HTTP 429)")
                    raise FreshRRateLimitError("Too many requests - rate limited by API")
                elif r.status == 401 or r.status == 403:
                    # Unauthorized or Forbidden - check for specific account issues
                    _LOGGER.warning("Authentication failed with status: %s", r.status)
                    
                    # Check response body for specific error messages
                    body_lower = body.lower()
                    if "suspended" in body_lower or "banned" in body_lower:
                        raise FreshRAuthError("Account suspended or banned - contact Fresh-R support")
                    elif "verify" in body_lower and "email" in body_lower:
                        raise FreshRAuthError("Email verification required - check your inbox")
                    elif "blocked" in body_lower or "blacklist" in body_lower:
                        raise FreshRAuthError("IP address blocked - contact Fresh-R support")
                    else:
                        raise FreshRAuthError(f"Invalid credentials - HTTP {r.status}")
                else:
                    _LOGGER.warning("Login failed with status: %s", r.status)
                    raise FreshRAuthError(f"Login failed - HTTP {r.status}")
                    
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
            # Use API endpoint to get user units (serial numbers)
            api_url = "https://dashboard.bw-log.com/api.php"
            
            # Build API request for user info and units
            import time
            from datetime import datetime, timezone
            
            tz_offset = int(time.timezone / 60)  # Timezone offset in minutes
            
            # CRITICAL: Browser sends token IN the JSON query string, not POST body
            api_request = {
                "tzoffset": str(abs(tz_offset)),
                "token": sess_token,  # Token MUST be in the JSON
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
            
            # CRITICAL: Build Cookie header with ALL cookies from jar
            # API needs both sess_token AND PHPSESSID
            cookie_parts = []
            for cookie in s.cookie_jar:
                cookie_parts.append(f"{cookie.key}={cookie.value}")
            cookie_header = "; ".join(cookie_parts)
            
            # CRITICAL: Browser sends token in QUERY STRING with EMPTY POST body!
            # Build URL with query string parameter
            from urllib.parse import urlencode
            query_params = {
                "q": json.dumps(api_request, separators=(',', ':'))
            }
            api_url_with_query = f"{api_url}?{urlencode(query_params)}"
            
            headers = {
                "Accept": "*/*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Cookie": cookie_header,
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "https://dashboard.bw-log.com",
                "Referer": "https://dashboard.bw-log.com/?page=devices",
            }
            
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
                _LOGGER.error(f"\nToken in query string: {sess_token[:20]}...")
                _LOGGER.error(f"Timezone Offset: {tz_offset}")
                _LOGGER.error("="*80 + "\n")
            else:
                _LOGGER.debug("API request to: %s", api_url_with_query)
            
            async with s.post(
                api_url_with_query,
                headers=headers,
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
        
        # The CORRECT login API endpoint (discovered via browser DevTools)
        login_api_url = "https://fresh-r.me/login/api/auth.php"
        
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
            "Origin": "https://fresh-r.me",
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
        """GET dashboard.bw-log.com/?page=devices and extract serial numbers."""
        s = self._get_session()
        devices_url = f"{API_BASE}/?page=devices"
        
        # Add auth_token as cookie for dashboard access
        from yarl import URL
        s.cookie_jar.update_cookies(
            {"auth_token": self._token or ""},
            URL("https://dashboard.bw-log.com")
        )
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "nl,en-US;q=0.9,en;q=0.8,de;q=0.7,ms;q=0.6,id;q=0.5",
            "Accept-Encoding": "gzip, deflate",  # Remove brotli to avoid encoding issues
            "Connection": "keep-alive",
            "Referer": "https://fresh-r.me/login/index.php?page=login",
        }
        
        self._log_request('GET', devices_url, headers)
        
        try:
            async with s.get(devices_url, allow_redirects=True,
                             headers=headers,
                             timeout=aiohttp.ClientTimeout(total=15)) as r:
                html = await r.text()
                self._log_response(r.status, str(r.url), dict(r.headers), html, s.cookie_jar)
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
            
        try:
            raw = await self._call({
                "current-data": {
                    "request": "fresh-r-now",
                    "serial": serial,
                    "fields": FIELDS_NOW,
                }
            })
        except FreshRConnectionError:
            _LOGGER.info("API error — re-authenticating")
            await self._refresh_token()
            raw = await self._call({
                "current-data": {
                    "request": "fresh-r-now",
                    "serial": serial,
                    "fields": FIELDS_NOW,
                }
            })
        return self._parse(raw.get("current-data", {}))

    # ── Internal ───────────────────────────────────────────────────────────────

    @staticmethod
    def _tzoffset() -> str:
        off = datetime.now(timezone.utc).astimezone().utcoffset()
        return str(abs(int(off.total_seconds() / 60))) if off else "0"

    async def _call(self, requests: dict[str, Any]) -> dict[str, Any]:
        """POST to api.php using the auth_token and proper headers."""
        s = self._get_session()
        q = json.dumps({
            "token":    self._token or "",
            "tzoffset": self._tzoffset(),
            "requests": requests,
        })
        try:
            async with s.post(
                API_URL, 
                params={"q": q},
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": "https://dashboard.bw-log.com",
                    "Referer": "https://dashboard.bw-log.com/?page=devices",
                },
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

    async def _refresh_token(self) -> None:
        """Refresh the authentication token."""
        _LOGGER.debug("Refreshing authentication token")
        self._token = None
        self._token_time = None
        await self.async_login()
