"""Fresh-r API client — read-only, current data only.

Simplified version using pure HTTP requests (no browser needed).
We just send requests with browser-like headers and handle session cookies.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any
import random

import aiohttp

_LOGGER = logging.getLogger(__name__)

# Browser-like headers to pretend we're a real browser
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
    "Accept-Encoding": "gzip, deflate",  # Removed 'br' (brotli) to avoid dependency
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://dashboard.bw-log.com/",
}

LOGIN_URL = "https://fresh-r.me/login"
DASHBOARD_URL = "https://dashboard.bw-log.com/?page=devices"
API_URL = "https://dashboard.bw-log.com/api.php"


class FreshRAuthError(Exception):
    """Login failed — bad credentials or service unreachable."""


class FreshRConnectionError(Exception):
    """Network or API error."""


class FreshRApiClient:
    """Simple HTTP client for Fresh-R - no browser needed!"""

    def __init__(self, email: str, password: str, ha_session: aiohttp.ClientSession = None) -> None:
        self._email = email
        self._password = password
        self._ha_session = ha_session
        self._session_token: str | None = None
        self._token_timestamp: datetime | None = None
        self._refresh_offset: timedelta | None = None
        self._cookie_jar = aiohttp.CookieJar(unsafe=True)
        
    def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with cookie jar."""
        return aiohttp.ClientSession(
            cookie_jar=self._cookie_jar,
            headers=BROWSER_HEADERS,
        )

    async def async_close(self) -> None:
        """Close HTTP session."""
        # Nothing persistent to close
        pass

    async def async_login(self) -> str | None:
        """Login via HTTP POST and extract session token from cookies."""
        _LOGGER.info("Logging in to Fresh-R via HTTP...")
        
        session = self._get_session()
        
        try:
            # Step 1: GET login page (to get any cookies)
            async with session.get(LOGIN_URL) as response:
                if response.status != 200:
                    _LOGGER.error(f"Login page failed: HTTP {response.status}")
                    return None
                    
                html = await response.text()
                _LOGGER.debug("Got login page")
                
                # Extract hidden form fields
                hidden_fields = self._extract_hidden_inputs(html)
            
            # Step 2: POST login credentials
            form_data = {
                **hidden_fields,
                "email": self._email,
                "password": self._password,
                "remember": "1",
            }
            
            post_headers = {
                **BROWSER_HEADERS,
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://fresh-r.me",
                "Referer": LOGIN_URL,
            }
            
            _LOGGER.debug(f"POSTing login form to {LOGIN_URL}")
            
            async with session.post(
                LOGIN_URL,
                data=form_data,
                headers=post_headers,
                allow_redirects=True
            ) as response:
                final_url = str(response.url)
                _LOGGER.debug(f"POST response: {response.status}, final URL: {final_url}")
                
                # Check cookies for session token
                cookies = [(c.key, c.value) for c in session.cookie_jar]
                _LOGGER.debug(f"Cookies after login: {cookies}")
                
                # Look for sess_token cookie
                sess_token = None
                for key, value in cookies:
                    if key == "sess_token":
                        sess_token = value
                        break
                
                # If we landed on dashboard, try to get token from there
                if not sess_token and "dashboard.bw-log.com" in final_url:
                    _LOGGER.debug("On dashboard, checking for token in dashboard cookies...")
                    async with session.get(DASHBOARD_URL) as dash_response:
                        if dash_response.status == 200:
                            dash_cookies = [(c.key, c.value) for c in session.cookie_jar]
                            for key, value in dash_cookies:
                                if key == "sess_token":
                                    sess_token = value
                                    break
                
                if sess_token:
                    self._session_token = sess_token
                    self._token_timestamp = datetime.now()
                    _LOGGER.info(f"✅ Login successful! Token: {sess_token[:20]}...")
                    return sess_token
                else:
                    _LOGGER.error("❌ Login failed - no session token found")
                    _LOGGER.debug(f"Final URL: {final_url}")
                    _LOGGER.debug(f"All cookies: {cookies}")
                    return None
                    
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Login network error: {e}")
            return None
        except Exception as e:
            _LOGGER.error(f"Login error: {e}")
            return None

    def _extract_hidden_inputs(self, html: str) -> dict:
        """Extract hidden form fields from HTML."""
        hidden = {}
        pattern = r'<input[^>]*type=["\']hidden["\'][^>]*>'
        matches = re.findall(pattern, html, re.I)
        
        for match in matches:
            name_match = re.search(r'name=["\']([^"\']+)["\']', match, re.I)
            value_match = re.search(r'value=["\']([^"\']*)["\']', match, re.I)
            if name_match:
                name = name_match.group(1)
                value = value_match.group(1) if value_match else ""
                hidden[name] = value
                
        return hidden

    async def _test_token(self, token: str) -> bool:
        """Test if session token is still valid."""
        try:
            cookies = {"sess_token": token}
            
            async with aiohttp.ClientSession(cookies=cookies, headers=BROWSER_HEADERS) as session:
                async with session.get(DASHBOARD_URL, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        text = await response.text()
                        return "dashboard" in text.lower() or "devices" in text.lower()
                    return False
        except Exception:
            return False

    async def async_ensure_token_valid(self):
        """Check if token needs refresh (called every hour)."""
        if not self._session_token or not self._token_timestamp:
            _LOGGER.info("No valid token, logging in...")
            await self.async_login()
            return
        
        # Check token age
        age = datetime.now() - self._token_timestamp
        
        # Generate random offset once (0-10 minutes) to distribute load
        if not self._refresh_offset:
            self._refresh_offset = timedelta(seconds=random.randint(0, 600))
            _LOGGER.debug(f"Token refresh offset: {self._refresh_offset.total_seconds():.0f}s")
        
        # Refresh if older than 50 min + offset
        threshold = timedelta(minutes=50) + self._refresh_offset
        
        if age > threshold:
            _LOGGER.info(f"Token is {age.total_seconds()/60:.0f} min old, refreshing...")
            await self.async_login()
        else:
            _LOGGER.debug(f"Token still valid ({age.total_seconds()/60:.0f} min old)")

    async def async_discover_devices(self) -> list[dict]:
        """Discover devices via HTTP requests."""
        if not self._session_token:
            _LOGGER.error("No session token for device discovery")
            return []
        
        try:
            cookies = {"sess_token": self._session_token}
            
            async with aiohttp.ClientSession(cookies=cookies, headers=BROWSER_HEADERS) as session:
                # Get devices page
                async with session.get(DASHBOARD_URL) as response:
                    if response.status != 200:
                        _LOGGER.error(f"Device discovery failed: HTTP {response.status}")
                        return []
                    
                    html = await response.text()
                    _LOGGER.debug("Got devices page")
                    
                    # Try API endpoint first
                    api_url = f"{API_URL}?q=devices"
                    async with session.get(api_url, headers=API_HEADERS) as api_response:
                        if api_response.status == 200:
                            try:
                                data = await api_response.json()
                                if isinstance(data, list):
                                    devices = []
                                    for device in data:
                                        device_id = device.get("id") or device.get("serial", "unknown")
                                        devices.append({
                                            "id": device_id,
                                            "type": "Fresh-r",
                                            "name": f"Fresh-r {device_id}",
                                        })
                                    if devices:
                                        _LOGGER.info(f"✅ Found {len(devices)} devices via API")
                                        return devices
                            except:
                                pass  # API didn't return JSON
                    
                    # Fallback: scrape HTML for device links
                    serials = re.findall(r'serial=([^&"\'>\s]+)', html)
                    
                    devices = []
                    for serial in set(serials):  # Remove duplicates
                        devices.append({
                            "id": serial,
                            "serial": serial,
                            "type": "Fresh-r",
                            "name": f"Fresh-r {serial}",
                        })
                    
                    if devices:
                        _LOGGER.info(f"✅ Found {len(devices)} devices via HTML scraping")
                        return devices
                    
                    # Last resort: create dummy device
                    _LOGGER.warning("No devices found, creating fallback")
                    return [{"id": "fresh-r-device", "type": "Fresh-r", "name": "Fresh-r Device"}]
                    
        except Exception as e:
            _LOGGER.error(f"Device discovery error: {e}")
            return []

    async def async_get_current(self, serial: str) -> dict[str, Any]:
        """Fetch current sensor data via API."""
        if not self._session_token:
            _LOGGER.error("No session token for data fetch")
            return {}
        
        try:
            cookies = {"sess_token": self._session_token}
            
            async with aiohttp.ClientSession(cookies=cookies, headers=API_HEADERS) as session:
                # Try API endpoint
                api_url = f"{API_URL}?q=" + json.dumps({"requests": {"devices": {"fields": ["*"]}}})
                
                async with session.get(api_url) as response:
                    if response.status == 200:
                        try:
                            data = await response.json()
                            
                            # Parse device data
                            if isinstance(data, dict):
                                # Look for device by serial
                                if serial in data:
                                    return self._parse_device_data(data[serial])
                                # Or check 'data' key
                                if "data" in data and isinstance(data["data"], list):
                                    for device in data["data"]:
                                        device_id = device.get("id") or device.get("serial", "")
                                        if device_id == serial:
                                            return self._parse_device_data(device)
                            elif isinstance(data, list):
                                for device in data:
                                    device_id = device.get("id") or device.get("serial", "")
                                    if device_id == serial:
                                        return self._parse_device_data(device)
                            
                        except json.JSONDecodeError:
                            _LOGGER.warning("API response is not valid JSON")
                    else:
                        _LOGGER.warning(f"API returned HTTP {response.status}")
                
                # Fallback: scrape dashboard HTML for data
                return await self._scrape_dashboard_data(session, serial)
                
        except Exception as e:
            _LOGGER.error(f"Error fetching data: {e}")
            return {}

    def _parse_device_data(self, device: dict) -> dict:
        """Parse device data from API response."""
        parsed = {}
        
        # Map common fields
        field_mapping = {
            "t1": "t1", "t2": "t2", "t3": "t3", "t4": "t4",
            "co2": "co2", "hum": "hum", "dp": "dp", "flow": "flow",
            "d5_25": "d5_25", "d4_25": "d4_25", "d1_25": "d1_25",
            "d5_1": "d5_1", "d4_1": "d4_1", "d1_1": "d1_1",
            "d5_03": "d5_03", "d4_03": "d4_03", "d1_03": "d1_03",
            "heat_recovered": "heat_recovered",
            "vent_loss": "vent_loss",
            "energy_loss": "energy_loss",
        }
        
        for api_key, our_key in field_mapping.items():
            if api_key in device:
                try:
                    parsed[our_key] = float(device[api_key])
                except (ValueError, TypeError):
                    parsed[our_key] = device[api_key]
        
        return parsed

    async def _scrape_dashboard_data(self, session: aiohttp.ClientSession, serial: str) -> dict:
        """Scrape data from dashboard HTML as fallback."""
        try:
            async with session.get(DASHBOARD_URL) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # Look for embedded JSON data
                    patterns = [
                        r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
                        r'window\.devices\s*=\s*(\[.+?\]);',
                        r'var\s+deviceData\s*=\s*({.+?});',
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, html, re.DOTALL)
                        for match in matches:
                            try:
                                data = json.loads(match)
                                if isinstance(data, dict) and serial in data:
                                    return self._parse_device_data(data[serial])
                                elif isinstance(data, list):
                                    for device in data:
                                        device_id = device.get("id") or device.get("serial", "")
                                        if device_id == serial:
                                            return self._parse_device_data(device)
                            except:
                                continue
                    
                    _LOGGER.debug("No JSON data found in dashboard HTML")
                    return {}
                else:
                    _LOGGER.error(f"Dashboard access failed: HTTP {response.status}")
                    return {}
        except Exception as e:
            _LOGGER.error(f"Dashboard scraping error: {e}")
            return {}
