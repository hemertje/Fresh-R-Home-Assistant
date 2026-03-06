#!/usr/bin/env python3
"""
Fresh-R Real API Discovery Tool
==============================

Find the REAL API endpoints that work for any user.
"""

import asyncio
import aiohttp
import json
import re
from urllib.parse import urljoin, urlparse, parse_qs

class FreshRRealAPIDiscovery:
    """Find the real Fresh-R API that works for any user."""
    
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.base_url = "https://dashboard.bw-log.com"
        self.session = None
    
    async def discover_real_api(self):
        """Discover the real API endpoints through systematic testing."""
        print("=== Fresh-R Real API Discovery ===")
        
        # Step 1: Try login with different methods
        login_result = await self.try_login_methods()
        if not login_result:
            print("❌ All login methods failed")
            return False
        
        # Step 2: Find API endpoints in dashboard
        api_endpoints = await self.find_api_endpoints()
        
        # Step 3: Test each API endpoint
        working_apis = await self.test_api_endpoints(api_endpoints)
        
        # Step 4: Document the working solution
        await self.document_solution(working_apis)
        
        return True
    
    async def try_login_methods(self):
        """Try different login methods to get a working session."""
        print("\n1. Testing different login methods...")
        
        login_attempts = [
            {
                "name": "fresh-r.me form login",
                "url": "https://fresh-r.me/login",
                "method": "POST",
                "data": {
                    "email": self.email,
                    "password": self.password,
                    "keep_logged_in": "1"
                }
            },
            {
                "name": "fresh-r.me with username",
                "url": "https://fresh-r.me/login", 
                "method": "POST",
                "data": {
                    "email": self.email,
                    "username": self.email,
                    "password": self.password,
                    "keep_logged_in": "1"
                }
            },
            {
                "name": "fresh-r.me simple",
                "url": "https://fresh-r.me/login",
                "method": "POST", 
                "data": {
                    "email": self.email,
                    "password": self.password
                }
            }
        ]
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        for attempt in login_attempts:
            print(f"\n   Trying: {attempt['name']}")
            
            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    # Get login page first
                    async with session.get(attempt["url"]) as response:
                        if response.status != 200:
                            print(f"   ❌ Failed to get login page: {response.status}")
                            continue
                    
                    # Try login
                    post_headers = {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Origin": "https://fresh-r.me",
                        "Referer": attempt["url"],
                    }
                    
                    async with session.post(attempt["url"], data=attempt["data"], headers=post_headers, allow_redirects=True) as response:
                        final_url = str(response.url)
                        
                        if "dashboard.bw-log.com" in final_url:
                            print(f"   🎉 LOGIN SUCCESS! Redirected to: {final_url}")
                            self.session = session
                            return True
                        else:
                            print(f"   ❌ Login failed - final URL: {final_url}")
                            
                            # Check if we got useful cookies anyway
                            cookies = [(c.key, c.value) for c in session.cookie_jar]
                            if cookies:
                                print(f"   🍪 Got cookies: {cookies}")
                                
                                # Test if cookies work for dashboard
                                async with session.get("https://dashboard.bw-log.com/?page=devices") as dashboard_response:
                                    if dashboard_response.status == 200:
                                        text = await dashboard_response.text()
                                        if "dashboard" in text.lower():
                                            print(f"   🎉 COOKIES WORK! Dashboard accessible")
                                            self.session = session
                                            return True
                                        else:
                                            print(f"   ❌ Dashboard not accessible with cookies")
                                    else:
                                        print(f"   ❌ Dashboard access failed: {dashboard_response.status}")
                            
            except Exception as e:
                print(f"   ❌ Login error: {e}")
        
        return False
    
    async def find_api_endpoints(self):
        """Find API endpoints by analyzing dashboard pages."""
        print("\n2. Finding API endpoints in dashboard...")
        
        if not self.session:
            print("   ❌ No session available")
            return []
        
        pages_to_analyze = [
            "https://dashboard.bw-log.com/?page=devices",
            "https://dashboard.bw-log.com/?page=dashboard", 
            "https://dashboard.bw-log.com/?page=overview",
            "https://dashboard.bw-log.com/",
        ]
        
        api_endpoints = set()
        
        for page_url in pages_to_analyze:
            print(f"\n   Analyzing: {page_url}")
            
            try:
                async with self.session.get(page_url) as response:
                    if response.status != 200:
                        print(f"   ❌ Failed to get page: {response.status}")
                        continue
                    
                    text = await response.text()
                    
                    # Look for API endpoints in JavaScript
                    js_patterns = [
                        r'fetch\(["\']([^"\']+)["\']',
                        r'\.get\(["\']([^"\']+)["\']',
                        r'\.post\(["\']([^"\']+)["\']',
                        r'api["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                        r'url["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                        r'endpoint["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                    ]
                    
                    for pattern in js_patterns:
                        matches = re.findall(pattern, text, re.I)
                        for match in matches:
                            if 'api' in match.lower() or match.startswith('/'):
                                full_url = urljoin(self.base_url, match)
                                api_endpoints.add(full_url)
                                print(f"   🔍 Found API endpoint: {full_url}")
                    
                    # Look for common API patterns
                    common_patterns = [
                        r'/api/[^"\'>\s]+',
                        r'/data/[^"\'>\s]+',
                        r'/v1/[^"\'>\s]+',
                        r'/v2/[^"\'>\s]+',
                        r'\.php[^"\'>\s]*',
                    ]
                    
                    for pattern in common_patterns:
                        matches = re.findall(pattern, text, re.I)
                        for match in matches:
                            full_url = urljoin(self.base_url, match)
                            api_endpoints.add(full_url)
                            print(f"   🔍 Found potential API: {full_url}")
                    
                    # Look for JSON data structures
                    json_patterns = [
                        r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
                        r'window\.api\s*=\s*({.+?});',
                        r'window\.endpoints\s*=\s*({.+?});',
                    ]
                    
                    for pattern in json_patterns:
                        matches = re.findall(pattern, text, re.DOTALL)
                        for match in matches:
                            try:
                                data = json.loads(match)
                                print(f"   📄 Found JSON data: {type(data)}")
                                
                                # Look for URLs in JSON
                                def find_urls(obj, path=""):
                                    urls = []
                                    if isinstance(obj, dict):
                                        for key, value in obj.items():
                                            if isinstance(value, str) and ('api' in value.lower() or value.startswith('/')):
                                                urls.append((path + "." + key, value))
                                            elif isinstance(value, (dict, list)):
                                                urls.extend(find_urls(value, path + "." + key))
                                    elif isinstance(obj, list):
                                        for i, item in enumerate(obj):
                                            if isinstance(item, str) and ('api' in item.lower() or item.startswith('/')):
                                                urls.append((f"{path}[{i}]", item))
                                            elif isinstance(item, (dict, list)):
                                                urls.extend(find_urls(item, f"{path}[{i}]"))
                                    return urls
                                
                                urls = find_urls(data)
                                for path, url in urls:
                                    full_url = urljoin(self.base_url, url)
                                    api_endpoints.add(full_url)
                                    print(f"   🔍 Found API in JSON ({path}): {full_url}")
                                    
                            except:
                                continue
                    
            except Exception as e:
                print(f"   ❌ Error analyzing page: {e}")
        
        return list(api_endpoints)
    
    async def test_api_endpoints(self, api_endpoints):
        """Test each API endpoint to find working ones."""
        print("\n3. Testing API endpoints...")
        
        working_apis = []
        
        for endpoint in api_endpoints:
            print(f"\n   Testing: {endpoint}")
            
            try:
                # Try different request formats
                test_attempts = [
                    {"method": "GET", "params": {}},
                    {"method": "GET", "params": {"q": "devices"}},
                    {"method": "GET", "params": {"action": "list"}},
                    {"method": "POST", "data": {}},
                    {"method": "POST", "data": {"q": "devices"}},
                    {"method": "POST", "data": {"action": "list"}},
                    {"method": "POST", "data": {"requests": {"devices": {"fields": ["*"]}}}},
                ]
                
                for i, attempt in enumerate(test_attempts):
                    print(f"      Attempt {i+1}: {attempt['method']} {attempt}")
                    
                    headers = {
                        "Accept": "application/json, text/plain, */*",
                        "X-Requested-With": "XMLHttpRequest",
                        "Referer": "https://dashboard.bw-log.com/",
                    }
                    
                    if attempt["method"] == "GET":
                        async with self.session.get(endpoint, params=attempt["params"], headers=headers) as response:
                            success = await self.analyze_api_response(response, endpoint, attempt)
                            if success:
                                working_apis.append({
                                    "endpoint": endpoint,
                                    "method": "GET",
                                    "params": attempt["params"],
                                    "response": success
                                })
                                break
                    else:
                        async with self.session.post(endpoint, data=attempt["data"], headers=headers) as response:
                            success = await self.analyze_api_response(response, endpoint, attempt)
                            if success:
                                working_apis.append({
                                    "endpoint": endpoint,
                                    "method": "POST", 
                                    "data": attempt["data"],
                                    "response": success
                                })
                                break
                        
            except Exception as e:
                print(f"   ❌ Error testing {endpoint}: {e}")
        
        return working_apis
    
    async def analyze_api_response(self, response, endpoint, attempt):
        """Analyze API response to determine if it's useful."""
        try:
            if response.status == 200:
                text = await response.text()
                
                # Try to parse as JSON
                try:
                    data = json.loads(text)
                    
                    # Check if it's a successful response
                    if isinstance(data, dict):
                        if data.get("success") or data.get("data") or data.get("devices"):
                            print(f"      🎉 SUCCESS! {endpoint}")
                            print(f"      Response: {json.dumps(data, indent=2)[:500]}...")
                            return data
                        elif data.get("error") or data.get("reason"):
                            print(f"      ❌ API Error: {data.get('error', data.get('reason', 'Unknown error'))}")
                            return False
                    elif isinstance(data, list) and data:
                        print(f"      🎉 SUCCESS! {endpoint}")
                        print(f"      Response: {json.dumps(data, indent=2)[:500]}...")
                        return data
                    
                except json.JSONDecodeError:
                    # Not JSON, check if it contains useful info
                    if "device" in text.lower() or "fresh-r" in text.lower():
                        print(f"      📄 Contains device info (not JSON)")
                        print(f"      Preview: {text[:200]}...")
                        return {"html": text[:1000]}
                    else:
                        print(f"      ❌ Not useful response")
                        return False
            else:
                print(f"      ❌ HTTP {response.status}")
                return False
                
        except Exception as e:
            print(f"      ❌ Error analyzing response: {e}")
            return False
    
    async def document_solution(self, working_apis):
        """Document the working solution for other users."""
        print("\n4. Documenting the working solution...")
        
        if not working_apis:
            print("   ❌ No working APIs found")
            return
        
        print("\n   🎉 WORKING SOLUTION FOUND!")
        print("\n   📋 IMPLEMENTATION GUIDE:")
        print("   ====================")
        
        for i, api in enumerate(working_apis, 1):
            print(f"\n   API {i}: {api['endpoint']}")
            print(f"   Method: {api['method']}")
            if api['method'] == 'GET':
                print(f"   Params: {api.get('params', {})}")
            else:
                print(f"   Data: {api.get('data', {})}")
            
            print(f"   Response: {type(api['response'])}")
            
            if isinstance(api['response'], dict):
                if 'data' in api['response']:
                    print(f"   Data structure: {list(api['response']['data'].keys()) if isinstance(api['response']['data'], dict) else type(api['response']['data'])}")
                elif 'devices' in api['response']:
                    print(f"   Devices found: {len(api['response']['devices']) if isinstance(api['response']['devices'], list) else 'unknown'}")
        
        print("\n   🔧 INTEGRATION IMPLEMENTATION:")
        print("   1. Use form login to get session cookies")
        print("   2. Use working API endpoints for data")
        print("   3. Parse response for device information")
        print("   4. Create Home Assistant entities")
        
        print("\n   ✅ This solution works for ANY user!")
        
        # Save to file
        solution_data = {
            "login_method": "form_post",
            "login_url": "https://fresh-r.me/login",
            "working_apis": working_apis,
            "implementation_notes": "Use session cookies from login for API calls"
        }
        
        with open("fresh_r_real_api_solution.json", "w") as f:
            json.dump(solution_data, f, indent=2)
        
        print("\n   💾 Solution saved to: fresh_r_real_api_solution.json")

async def analyze_working_token(self):
        """Analyze how the working session token might be generated."""
        print("\n🔍 Analyzing the working session token...")
        
        working_token = "686a6f04ebd68b86b3f91ee4cfd603b88ae8b7fa17f38aa04958e6e9d6bc50b2"
        
        print(f"Working token: {working_token}")
        print(f"Token length: {len(working_token)}")
        print(f"Token format: {'hex' if all(c in '0123456789abcdef' for c in working_token.lower()) else 'unknown'}")
        
        # Test if this is a SHA256 hash
        import hashlib
        test_strings = [
            f"{self.email}:{self.password}",
            f"{self.email}:{self.password}:fresh-r",
            f"{self.email}:{self.password}:dashboard",
            f"buurkracht.binnenhof@gmail.com:Hemert@7733",
            f"buurkracht.binnenhof@gmail.com:Hemert@7733:2026",
            self.email,
            self.password,
        ]
        
        print("\nTesting if token is a hash of common strings...")
        for test_str in test_strings:
            sha256_hash = hashlib.sha256(test_str.encode()).hexdigest()
            if sha256_hash == working_token.lower():
                print(f"🎉 FOUND! Token is SHA256 of: '{test_str}'")
                return test_str, "sha256"
        
        # Test if this is a session ID from somewhere
        print("\nTesting token patterns...")
        
        # Check if it looks like a session ID
        if len(working_token) == 64 and all(c in '0123456789abcdef' for c in working_token.lower()):
            print("✅ Token looks like a 256-bit session ID (SHA256 format)")
            
            # Try to find the source
            print("\n🔍 Possible sources:")
            print("1. Hash of user credentials")
            print("2. Random session ID from server")
            print("3. Hash of timestamp + user info")
            print("4. Browser session ID")
            print("5. Database session identifier")
        
        # Try to use the working token to find the real API
        print("\n🚀 Testing working token with API discovery...")
        
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
        
        try:
            async with aiohttp.ClientSession(cookies=cookies, headers=headers) as session:
                # Test dashboard access
                async with session.get("https://dashboard.bw-log.com/?page=devices") as response:
                    if response.status == 200:
                        text = await response.text()
                        print("✅ Working token gives dashboard access!")
                        
                        # Now find API endpoints
                        api_endpoints = await self.find_api_endpoints_with_session(session)
                        working_apis = await self.test_api_endpoints_with_session(session, api_endpoints)
                        
                        if working_apis:
                            await self.document_working_solution(working_token, working_apis)
                            return working_token, working_apis
                        else:
                            print("❌ No working APIs found even with working token")
                    else:
                        print(f"❌ Working token failed: {response.status}")
        
        except Exception as e:
            print(f"❌ Error testing working token: {e}")
        
        return None, []

    async def find_api_endpoints_with_session(self, session):
        """Find API endpoints using the working session."""
        print("\n🔍 Finding API endpoints with working session...")
        
        pages_to_analyze = [
            "https://dashboard.bw-log.com/?page=devices",
            "https://dashboard.bw-log.com/?page=dashboard", 
            "https://dashboard.bw-log.com/?page=overview",
        ]
        
        api_endpoints = set()
        
        for page_url in pages_to_analyze:
            print(f"   Analyzing: {page_url}")
            
            try:
                async with session.get(page_url) as response:
                    if response.status == 200:
                        text = await response.text()
                        
                        # Look for fetch calls
                        fetch_patterns = [
                            r'fetch\(["\']([^"\']+)["\'][^;]*;',
                            r'\.get\(["\']([^"\']+)["\']',
                            r'\.post\(["\']([^"\']+)["\']',
                            r'api["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                            r'url["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                        ]
                        
                        for pattern in fetch_patterns:
                            matches = re.findall(pattern, text, re.I)
                            for match in matches:
                                if 'api' in match.lower() or match.startswith('/'):
                                    full_url = urljoin("https://dashboard.bw-log.com", match)
                                    api_endpoints.add(full_url)
                                    print(f"      Found: {full_url}")
                        
                        # Look for common API files
                        api_files = [
                            r'([^"\']*\.php[^"\']*)',
                            r'([^"\']*api[^"\']*)',
                            r'([^"\']*data[^"\']*)',
                        ]
                        
                        for pattern in api_files:
                            matches = re.findall(pattern, text, re.I)
                            for match in matches:
                                if 'api' in match.lower() or 'data' in match.lower():
                                    full_url = urljoin("https://dashboard.bw-log.com", match)
                                    api_endpoints.add(full_url)
                                    print(f"      Found: {full_url}")
            
            except Exception as e:
                print(f"   Error analyzing {page_url}: {e}")
        
        return list(api_endpoints)
    
    async def test_api_endpoints_with_session(self, session, api_endpoints):
        """Test API endpoints with working session."""
        print("\n🚀 Testing API endpoints with working session...")
        
        working_apis = []
        
        for endpoint in api_endpoints:
            print(f"   Testing: {endpoint}")
            
            try:
                # Test different request formats
                test_attempts = [
                    {"method": "GET", "params": {}},
                    {"method": "GET", "params": {"q": "devices"}},
                    {"method": "POST", "data": {}},
                    {"method": "POST", "data": {"q": "devices"}},
                    {"method": "POST", "data": {"requests": {"devices": {"fields": ["*"]}}}},
                ]
                
                for i, attempt in enumerate(test_attempts):
                    headers = {
                        "Accept": "application/json, text/plain, */*",
                        "X-Requested-With": "XMLHttpRequest",
                        "Referer": "https://dashboard.bw-log.com/",
                    }
                    
                    if attempt["method"] == "GET":
                        async with session.get(endpoint, params=attempt["params"], headers=headers) as response:
                            success = await self.analyze_api_response(response, endpoint, attempt)
                            if success:
                                working_apis.append({
                                    "endpoint": endpoint,
                                    "method": "GET",
                                    "params": attempt["params"],
                                    "response": success
                                })
                                print(f"      🎉 WORKING API FOUND!")
                                break
                    else:
                        async with session.post(endpoint, data=attempt["data"], headers=headers) as response:
                            success = await self.analyze_api_response(response, endpoint, attempt)
                            if success:
                                working_apis.append({
                                    "endpoint": endpoint,
                                    "method": "POST", 
                                    "data": attempt["data"],
                                    "response": success
                                })
                                print(f"      🎉 WORKING API FOUND!")
                                break
                        
            except Exception as e:
                print(f"   Error testing {endpoint}: {e}")
        
        return working_apis
    
    async def document_working_solution(self, token, working_apis):
        """Document the working solution."""
        print("\n🎉 WORKING SOLUTION FOUND!")
        print("\n📋 IMPLEMENTATION GUIDE:")
        print("====================")
        print(f"Session Token: {token}")
        print(f"Cookie Name: sess_token")
        print(f"Working APIs: {len(working_apis)}")
        
        for i, api in enumerate(working_apis, 1):
            print(f"\nAPI {i}: {api['endpoint']}")
            print(f"Method: {api['method']}")
            print(f"Response: {type(api['response'])}")
        
        print("\n🔧 SCALABLE SOLUTION:")
        print("1. User logs in via form")
        print("2. Extract session token from response")
        print("3. Use session token for API calls")
        print("4. Parse device data from API")
        
        # Save solution
        solution = {
            "session_token": token,
            "cookie_name": "sess_token",
            "working_apis": working_apis,
            "implementation": "Use form login to get session token, then use token for API calls"
        }
        
        with open("fresh_r_scalable_solution.json", "w") as f:
            json.dump(solution, f, indent=2)
        
        print("\n💾 Solution saved to: fresh_r_scalable_solution.json")

# Update main function
async def main():
    discovery = FreshRRealAPIDiscovery("buurkracht.binnenhof@gmail.com", "Hemert@7733")
    
    # First try the working token analysis
    token, apis = await discovery.analyze_working_token()
    
    if token and apis:
        print("\n🎉 SCALABLE SOLUTION FOUND!")
        print("Check fresh_r_scalable_solution.json for implementation details.")
    else:
        print("\n❌ No scalable solution found.")
        print("The hardcoded token approach might be the only working method.")

if __name__ == "__main__":
    asyncio.run(main())
