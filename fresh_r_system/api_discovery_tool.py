#!/usr/bin/env python3
"""
Fresh-R API Discovery Tool
==========================

STAP 1: Browser Analysis
1. Open browser
2. Ga naar: https://dashboard.bw-log.com/?page=devices
3. F12 → Network tab
4. Refresh pagina (F5)
5. Zoek naar XHR/Fetch requests
6. Kopieer de request URL en headers

STAP 2: API Endpoint Analysis
- Zoek naar requests naar /api/ of /data/
- Check Authorization headers
- Check response data structure

STAP 3: Implementatie
- Gebruik de gevonden API endpoint
- Gebruik de juiste headers
- Gebruik de cookie authenticatie
"""

import asyncio
import aiohttp
import json
from urllib.parse import urljoin

class FreshRAPIDiscovery:
    """Discover the actual Fresh-R API endpoints."""
    
    def __init__(self, session_token: str):
        self.session_token = session_token
        self.base_url = "https://dashboard.bw-log.com"
        self.session = None
    
    async def setup_session(self):
        """Setup aiohttp session with cookies."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://dashboard.bw-log.com/",
            "X-Requested-With": "XMLHttpRequest",
        }
        
        cookies = {
            "sess_token": self.session_token
        }
        
        self.session = aiohttp.ClientSession(cookies=cookies, headers=headers)
    
    async def test_api_endpoints(self):
        """Test common API endpoints."""
        endpoints = [
            "/api/devices",
            "/api/data/devices", 
            "/api/v1/devices",
            "/api/fresh-r/devices",
            "/data/devices",
            "/devices/api",
            "/dashboard/api/devices",
            "/api/user/devices",
            "/api/system/devices",
        ]
        
        results = []
        
        for endpoint in endpoints:
            url = urljoin(self.base_url, endpoint)
            try:
                async with self.session.get(url) as response:
                    if response.status == 200:
                        try:
                            data = await response.json()
                            results.append({
                                "endpoint": endpoint,
                                "status": response.status,
                                "data": data,
                                "content_type": response.headers.get("content-type", "")
                            })
                            print(f"✅ SUCCESS: {endpoint} - {len(data)} items")
                        except:
                            text = await response.text()
                            results.append({
                                "endpoint": endpoint,
                                "status": response.status,
                                "data": text[:500],
                                "content_type": response.headers.get("content-type", "")
                            })
                            print(f"✅ SUCCESS: {endpoint} - {response.status}")
                    else:
                        print(f"❌ FAILED: {endpoint} - {response.status}")
                        
            except Exception as e:
                print(f"❌ ERROR: {endpoint} - {e}")
        
        return results
    
    async def test_dashboard_pages(self):
        """Test dashboard pages for embedded data."""
        pages = [
            "/?page=devices",
            "/?page=dashboard",
            "/?page=overview",
            "/?page=settings",
        ]
        
        results = []
        
        for page in pages:
            url = urljoin(self.base_url, page)
            try:
                async with self.session.get(url) as response:
                    if response.status == 200:
                        text = await response.text()
                        
                        # Look for embedded JSON data
                        import re
                        json_patterns = [
                            r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
                            r'window\.data\s*=\s*({.+?});',
                            r'data-device\s*=\s*({.+?})',
                            r'var\s+devices\s*=\s*(\[.+?\]);',
                        ]
                        
                        found_data = []
                        for pattern in json_patterns:
                            matches = re.findall(pattern, text, re.DOTALL)
                            if matches:
                                found_data.extend(matches)
                        
                        results.append({
                            "page": page,
                            "status": response.status,
                            "embedded_data": found_data,
                            "has_devices": "device" in text.lower(),
                            "has_api": "api" in text.lower()
                        })
                        
                        print(f"✅ PAGE: {page} - Found {len(found_data)} data patterns")
                    else:
                        print(f"❌ PAGE: {page} - {response.status}")
                        
            except Exception as e:
                print(f"❌ PAGE ERROR: {page} - {e}")
        
        return results
    
    async def close(self):
        """Close the session."""
        if self.session:
            await self.session.close()

# USAGE:
# discovery = FreshRAPIDiscovery("your_session_token")
# await discovery.setup_session()
# 
# print("=== Testing API Endpoints ===")
# api_results = await discovery.test_api_endpoints()
# 
# print("\n=== Testing Dashboard Pages ===")
# page_results = await discovery.test_dashboard_pages()
# 
# await discovery.close()
# 
# print("\n=== RESULTS ===")
# print("API Results:", json.dumps(api_results, indent=2))
# print("Page Results:", json.dumps(page_results, indent=2))
