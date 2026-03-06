#!/usr/bin/env python3
"""
Fresh-R Device Discovery Fix
============================

Gebruik de werkende dashboard toegang om devices te vinden.
"""

import asyncio
import aiohttp
import re
import json

class FreshRDeviceDiscovery:
    """Find devices using the working dashboard access."""
    
    def __init__(self, session_token: str):
        self.session_token = session_token
        self.base_url = "https://dashboard.bw-log.com"
    
    async def discover_devices(self):
        """Discover devices via dashboard scraping."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://dashboard.bw-log.com/",
        }
        
        cookies = {
            "sess_token": self.session_token
        }
        
        try:
            async with aiohttp.ClientSession(cookies=cookies, headers=headers) as session:
                # Get devices page
                async with session.get(f"{self.base_url}/?page=devices") as response:
                    if response.status == 200:
                        text = await response.text()
                        
                        # Look for device data in the HTML
                        devices = []
                        
                        # Method 1: Look for JSON data in script tags
                        json_patterns = [
                            r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
                            r'window\.devices\s*=\s*(\[.+?\]);',
                            r'var\s+devices\s*=\s*(\[.+?\]);',
                            r'data-devices\s*=\s*({.+?})',
                        ]
                        
                        for pattern in json_patterns:
                            matches = re.findall(pattern, text, re.DOTALL)
                            for match in matches:
                                try:
                                    data = json.loads(match)
                                    if isinstance(data, list) and data:
                                        devices.extend(data)
                                    elif isinstance(data, dict) and 'devices' in data:
                                        devices.extend(data['devices'])
                                except:
                                    continue
                        
                        # Method 2: Look for device links/serials
                        serial_pattern = r'serial=([^&"\'>\s]+)'
                        serials = re.findall(serial_pattern, text)
                        
                        for serial in serials:
                            devices.append({
                                "id": serial,
                                "serial": serial,
                                "type": "Fresh-r",
                                "name": f"Fresh-r {serial}",
                                "status": "online"
                            })
                        
                        # Method 3: Look for device cards/elements
                        device_patterns = [
                            r'<div[^>]*class="[^"]*device[^"]*"[^>]*>(.+?)</div>',
                            r'<tr[^>]*class="[^"]*device[^"]*"[^>]*>(.+?)</tr>',
                        ]
                        
                        for pattern in device_patterns:
                            matches = re.findall(pattern, text, re.DOTALL)
                            for match in matches:
                                if 'fresh-r' in match.lower() or 'device' in match.lower():
                                    # Extract device info from HTML
                                    device_id = f"device-{len(devices)}"
                                    devices.append({
                                        "id": device_id,
                                        "type": "Fresh-r",
                                        "name": f"Fresh-r Device {len(devices)}",
                                        "status": "online",
                                        "raw_html": match[:200]  # For debugging
                                    })
                        
                        # Remove duplicates
                        seen_ids = set()
                        unique_devices = []
                        for device in devices:
                            device_id = device.get('id') or device.get('serial')
                            if device_id and device_id not in seen_ids:
                                seen_ids.add(device_id)
                                unique_devices.append(device)
                        
                        return unique_devices
                    
                    else:
                        print(f"Failed to get devices page: {response.status}")
                        return []
                        
        except Exception as e:
            print(f"Error discovering devices: {e}")
            return []

    async def test_api_endpoints(self):
        """Test possible API endpoints."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://dashboard.bw-log.com/",
        }
        
        cookies = {
            "sess_token": self.session_token
        }
        
        endpoints = [
            "/api/devices",
            "/api/data/devices",
            "/api/v1/devices", 
            "/devices/api",
            "/dashboard/api/devices",
            "/api.php?q=devices",
            "/api.php?q=" + json.dumps({"requests": {"devices": {"fields": ["*"]}}}),
        ]
        
        results = []
        
        async with aiohttp.ClientSession(cookies=cookies, headers=headers) as session:
            for endpoint in endpoints:
                try:
                    async with session.get(f"{self.base_url}{endpoint}") as response:
                        if response.status == 200:
                            try:
                                data = await response.json()
                                results.append({
                                    "endpoint": endpoint,
                                    "status": response.status,
                                    "data": data
                                })
                                print(f"✅ API SUCCESS: {endpoint}")
                            except:
                                text = await response.text()
                                results.append({
                                    "endpoint": endpoint,
                                    "status": response.status,
                                    "data": text[:500]
                                })
                        else:
                            print(f"❌ API FAILED: {endpoint} - {response.status}")
                            
                except Exception as e:
                    print(f"❌ API ERROR: {endpoint} - {e}")
        
        return results

# USAGE:
discovery = FreshRDeviceDiscovery("686a6f04ebd68b86b3f91ee4cfd603b88ae8b7fa17f38aa04958e6e9d6bc50b2")

async def test_freshr_me_login():
    """Test fresh-r.me login with correct credentials."""
    login_url = "https://fresh-r.me/login"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            # Step 1: GET login page and analyze form
            async with session.get(login_url) as response:
                if response.status != 200:
                    print(f"❌ Login page failed: HTTP {response.status}")
                    return False
                
                html = await response.text()
                print(f"✅ Got login page from fresh-r.me")
                
                # Analyze form fields
                import re
                form_inputs = re.findall(r'<input[^>]+>', html, re.I)
                print(f"\n🔍 Form Analysis - Found {len(form_inputs)} input fields:")
                
                hidden_fields = {}
                for i, input_tag in enumerate(form_inputs):
                    print(f"  {i+1}. {input_tag}")
                    
                    # Extract field info
                    name_match = re.search(r'name=["\']([^"\']+)["\']', input_tag, re.I)
                    type_match = re.search(r'type=["\']([^"\']+)["\']', input_tag, re.I)
                    value_match = re.search(r'value=["\']([^"\']*)["\']', input_tag, re.I)
                    
                    if name_match:
                        name = name_match.group(1)
                        type_ = type_match.group(1) if type_match else "text"
                        value = value_match.group(1) if value_match else ""
                        print(f"     Field: {name} (type: {type_}, value: '{value}')")
                        
                        # Collect hidden fields
                        if type_.lower() == "hidden":
                            hidden_fields[name] = value
                
                # Look for CSRF tokens in other places
                csrf_patterns = [
                    r'<meta[^>]*name=["\']csrf-token["\'][^>]*content=["\']([^"\']+)["\']',
                    r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']csrf-token["\']',
                    r'window\.csrfToken\s*=\s*["\']([^"\']+)["\']',
                    r'csrf["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                ]
                
                csrf_tokens = {}
                for pattern in csrf_patterns:
                    matches = re.findall(pattern, html, re.I)
                    for match in matches:
                        csrf_tokens[f"csrf_{len(csrf_tokens)}"] = match
                
                print(f"\n🔍 Hidden Fields: {hidden_fields}")
                print(f"🔍 CSRF Tokens: {csrf_tokens}")
                
                # Look for form action URL
                form_action_match = re.search(r'<form[^>]*action=["\']([^"\']+)["\']', html, re.I)
                form_action = form_action_match.group(1) if form_action_match else login_url
                print(f"🔍 Form Action: {form_action}")
                
                # Look for form method
                form_method_match = re.search(r'<form[^>]*method=["\']([^"\']+)["\']', html, re.I)
                form_method = form_method_match.group(1) if form_method_match else "POST"
                print(f"🔍 Form Method: {form_method}")
            
            # Step 2: Try different form data combinations
            form_attempts = [
                # Attempt 1: Standard fields
                {
                    "email": "buurkracht.binnenhof@gmail.com",
                    "password": "Hemert@7733",
                    "keep_logged_in": "1"
                },
                # Attempt 2: With username field
                {
                    "email": "buurkracht.binnenhof@gmail.com",
                    "username": "buurkracht.binnenhof@gmail.com",
                    "password": "Hemert@7733",
                    "keep_logged_in": "1"
                },
                # Attempt 3: Without keep_logged_in
                {
                    "email": "buurkracht.binnenhof@gmail.com",
                    "password": "Hemert@7733"
                },
                # Attempt 4: Different field names
                {
                    "user": "buurkracht.binnenhof@gmail.com",
                    "pass": "Hemert@7733",
                    "remember": "1"
                }
            ]
            
            for i, form_data in enumerate(form_attempts):
                print(f"\n🔍 Attempt {i+1}: {form_data}")
                
                post_headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://fresh-r.me",
                    "Referer": login_url,
                }
                
                async with session.post(login_url, data=form_data, headers=post_headers, allow_redirects=True) as response:
                    final_url = str(response.url)
                    response_text = await response.text()
                    
                    # Check for success
                    if "dashboard.bw-log.com" in final_url or "dashboard" in final_url.lower():
                        print(f"🎉 FRESH-R.ME LOGIN SUCCESS! Redirected to: {final_url}")
                        
                        # Test device discovery
                        print("\n2. Testing device discovery...")
                        api_url = "https://dashboard.bw-log.com/api.php?q=devices"
                        headers = {
                            "Accept": "application/json, text/plain, */*",
                            "X-Requested-With": "XMLHttpRequest",
                            "Referer": "https://dashboard.bw-log.com/",
                        }
                        
                        async with session.get(api_url, headers=headers) as response:
                            if response.status == 200:
                                try:
                                    data = await response.json()
                                    print(f"🎉 DEVICE DISCOVERY SUCCESS! Found {len(data) if isinstance(data, list) else 1} devices")
                                    print(f"Devices: {data}")
                                    return True
                                except:
                                    text = await response.text()
                                    print(f"❌ API response not JSON: {text[:200]}")
                                    return False
                            else:
                                print(f"❌ Device discovery failed: HTTP {response.status}")
                                return False
                    else:
                        print(f"❌ Attempt {i+1} failed - final URL: {final_url}")
                        
                        # Check if we have a PHPSESSID cookie and test API access
                        cookies = [(c.key, c.value) for c in session.cookie_jar]
                        phpsessid_cookie = next((c for c in cookies if c[0] == "PHPSESSID"), None)
                        
                        if phpsessid_cookie:
                            print(f"🔍 Found PHPSESSID cookie: {phpsessid_cookie[1]}")
                            print(f"🔍 Testing if cookie works for API access...")
                            
                            # Test different API request formats
                            api_attempts = [
                                # Attempt 1: Simple query
                                "https://dashboard.bw-log.com/api.php?q=devices",
                                
                                # Attempt 2: JSON query format
                                "https://dashboard.bw-log.com/api.php?q=" + json.dumps({"requests": {"devices": {"fields": ["*"]}}}),
                                
                                # Attempt 3: Different endpoint
                                "https://dashboard.bw-log.com/api.php",
                                
                                # Attempt 4: With token parameter
                                f"https://dashboard.bw-log.com/api.php?q=devices&token={phpsessid_cookie[1]}",
                                
                                # Attempt 5: POST request
                                "https://dashboard.bw-log.com/api.php",
                            ]
                            
                            for j, api_url in enumerate(api_attempts):
                                print(f"   🔍 API Attempt {j+1}: {api_url}")
                                
                                headers = {
                                    "Accept": "application/json, text/plain, */*",
                                    "X-Requested-With": "XMLHttpRequest",
                                    "Referer": "https://dashboard.bw-log.com/",
                                }
                                
                                if j == 4:  # POST request
                                    post_data = {"q": "devices", "token": phpsessid_cookie[1]}
                                    async with session.post(api_url, data=post_data, headers=headers) as api_response:
                                        if api_response.status == 200:
                                            try:
                                                data = await api_response.json()
                                                print(f"   🎉 API POST SUCCESS! Response: {data}")
                                                if data.get("success") or isinstance(data, list):
                                                    print(f"   🎉 DEVICE DISCOVERY SUCCESS!")
                                                    return True
                                            except:
                                                text = await api_response.text()
                                                print(f"   ❌ API POST not JSON: {text[:200]}")
                                        else:
                                            print(f"   ❌ API POST failed: HTTP {api_response.status}")
                                else:  # GET requests
                                    async with session.get(api_url, headers=headers) as api_response:
                                        if api_response.status == 200:
                                            try:
                                                data = await api_response.json()
                                                print(f"   🎉 API GET SUCCESS! Response: {data}")
                                                if data.get("success") or isinstance(data, list):
                                                    print(f"   🎉 DEVICE DISCOVERY SUCCESS!")
                                                    return True
                                            except:
                                                text = await api_response.text()
                                                print(f"   ❌ API GET not JSON: {text[:200]}")
                                        else:
                                            print(f"   ❌ API GET failed: HTTP {api_response.status}")
                            
                            print(f"   ❌ All API attempts failed")
                        
                        # Analyze response for clues
                        print(f"   Response status: {response.status}")
                        print(f"   Response headers: {dict(response.headers)}")
                        
                        # Look for specific error messages
                        if "invalid" in response_text.lower():
                            print(f"   ❌ Invalid credentials detected")
                        elif "error" in response_text.lower():
                            print(f"   ❌ Error message found")
                            # Extract error message
                            error_match = re.search(r'<[^>]*class="[^"]*error[^"]*"[^>]*>([^<]+)</', response_text, re.I)
                            if error_match:
                                print(f"   Error: {error_match.group(1).strip()}")
                        elif "login" in response_text.lower():
                            print(f"   🔄 Still on login page")
                            
                            # Check if there's a specific message
                            message_patterns = [
                                r'<div[^>]*class="[^"]*message[^"]*"[^>]*>([^<]+)</',
                                r'<p[^>]*class="[^"]*alert[^"]*"[^>]*>([^<]+)</',
                                r'<span[^>]*class="[^"]*warning[^"]*"[^>]*>([^<]+)</',
                            ]
                            
                            for pattern in message_patterns:
                                matches = re.findall(pattern, response_text, re.I)
                                for match in matches:
                                    if match.strip():
                                        print(f"   Message: {match.strip()}")
                        else:
                            print(f"   ❓ Unknown response pattern")
                            print(f"   Response preview: {response_text[:500]}")
                        
                        # Check for cookies
                        if cookies:
                            print(f"   Cookies set: {cookies}")
                        else:
                            print(f"   No cookies set")
                    
    except Exception as e:
        print(f"❌ Fresh-r.me login error: {e}")
        return False

async def test_working_token():
    """Test the working session token directly."""
    working_token = "686a6f04ebd68b86b3f91ee4cfd603b88ae8b7fa17f38aa04958e6e9d6bc50b2"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://dashboard.bw-log.com/",
    }
    
    cookies = {
        "sess_token": working_token
    }
    
    print("=== Testing Working Session Token ===")
    print(f"Token: {working_token}")
    
    try:
        async with aiohttp.ClientSession(cookies=cookies, headers=headers) as session:
            # Test 1: Dashboard access
            print("\n1. Testing dashboard access...")
            async with session.get("https://dashboard.bw-log.com/?page=devices") as response:
                if response.status == 200:
                    text = await response.text()
                    if "dashboard" in text.lower() or "devices" in text.lower():
                        print("✅ Dashboard access works!")
                    else:
                        print("❌ Dashboard access failed")
                else:
                    print(f"❌ Dashboard access failed: HTTP {response.status}")
            
            # Test 2: API access with different formats
            print("\n2. Testing API access...")
            
            api_attempts = [
                # Attempt 1: Simple query
                {"url": "https://dashboard.bw-log.com/api.php?q=devices", "method": "GET"},
                
                # Attempt 2: JSON query format
                {"url": "https://dashboard.bw-log.com/api.php?q=" + json.dumps({"requests": {"devices": {"fields": ["*"]}}}), "method": "GET"},
                
                # Attempt 3: POST with JSON
                {"url": "https://dashboard.bw-log.com/api.php", "method": "POST", "data": {"q": json.dumps({"requests": {"devices": {"fields": ["*"]}}})}},
                
                # Attempt 4: POST with simple data
                {"url": "https://dashboard.bw-log.com/api.php", "method": "POST", "data": {"q": "devices"}},
                
                # Attempt 5: GET with token
                {"url": f"https://dashboard.bw-log.com/api.php?q=devices&token={working_token}", "method": "GET"},
            ]
            
            for i, attempt in enumerate(api_attempts):
                print(f"\n   API Attempt {i+1}: {attempt['method']} {attempt['url']}")
                
                if attempt["method"] == "POST":
                    async with session.post(attempt["url"], data=attempt["data"]) as response:
                        await handle_api_response(response, i+1)
                else:
                    async with session.get(attempt["url"]) as response:
                        await handle_api_response(response, i+1)
            
            return False
            
    except Exception as e:
        print(f"❌ Error testing working token: {e}")
        return False

async def handle_api_response(response, attempt_num):
    """Handle API response and show results."""
    if response.status == 200:
        try:
            data = await response.json()
            print(f"   🎉 API Attempt {attempt_num} SUCCESS! Response: {data}")
            
            if data.get("success") and isinstance(data.get("data"), list):
                devices = data["data"]
                print(f"   🎉 FOUND {len(devices)} DEVICES: {devices}")
                return True
            elif isinstance(data, list):
                print(f"   🎉 FOUND {len(data)} DEVICES: {data}")
                return True
            elif data.get("success"):
                print(f"   ✅ API Success but no devices")
                return True
            else:
                print(f"   ❌ API Response: {data}")
                return False
        except:
            text = await response.text()
            print(f"   ❌ API Attempt {attempt_num} not JSON: {text[:200]}")
            return False
    else:
        print(f"   ❌ API Attempt {attempt_num} failed: HTTP {response.status}")
        return False

async def main():
    print("=== Fresh-R Working Token Test ===")
    
    success = await test_working_token()
    
    if success:
        print("\n🎉 SUCCESS! De working token werkt!")
        print("We kunnen de integration maken met deze token.")
    else:
        print("\n❌ Working token failed voor API access.")
        print("We moeten verder debuggen.")
    
    print("\n=== COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(main())
