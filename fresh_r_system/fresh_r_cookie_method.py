#!/usr/bin/env python3
"""
Fresh-R Cookie Method - Manual Login Instructions
===============================================

STAP 1: HANDMATIG INLOGGEN
1. Open browser
2. Ga naar: https://fresh-r.me/login
3. Log in met uw credentials
4. U wordt redirected naar: https://dashboard.bw-log.com/?page=devices

STAP 2: COPIEER COOKIES
1. Open Developer Tools (F12)
2. Ga naar Application > Cookies > https://fresh-r.me
3. Kopieer de PHPSESSID cookie waarde

STAP 3: GEBRUIK IN HOME ASSISTANT
Voeg de cookie waarde toe aan uw Fresh-R integration configuration.

DEZE METHODE OMZEILT DE LOGIN PROBLEMATIEK!
"""

import asyncio
import aiohttp
import logging

_LOGGER = logging.getLogger(__name__)

class FreshRCookieMethod:
    """Fresh-R login using browser cookies instead of form login."""
    
    def __init__(self, email: str, php_sessid: str):
        self.email = email
        self.php_sessid = php_sessid
    
    async def test_cookie_login(self):
        """Test if PHPSESSID cookie works for dashboard access."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        cookies = {
            "PHPSESSID": self.php_sessid
        }
        
        async with aiohttp.ClientSession(cookies=cookies, headers=headers) as session:
            try:
                # Test dashboard access
                async with session.get("https://dashboard.bw-log.com/?page=devices") as response:
                    if response.status == 200:
                        text = await response.text()
                        if "dashboard" in text.lower() or "devices" in text.lower():
                            _LOGGER.warning("🎉 COOKIE LOGIN SUCCESS! Dashboard accessible with PHPSESSID")
                            return True
                        else:
                            _LOGGER.warning("❌ Cookie login failed - not dashboard content")
                            return False
                    else:
                        _LOGGER.warning("❌ Cookie login failed - HTTP %s", response.status)
                        return False
                        
            except Exception as e:
                _LOGGER.error("Cookie login error: %s", e)
                return False

# USAGE EXAMPLE:
# cookie_method = FreshRCookieMethod("your@email.com", "your_php_sessid_value")
# asyncio.run(cookie_method.test_cookie_login())
