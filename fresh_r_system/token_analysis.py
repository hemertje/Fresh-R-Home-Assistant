#!/usr/bin/env python3
"""
Fresh-R Working Token Analysis
==============================

Analyze the working session token to find a scalable solution.
"""

import asyncio
import aiohttp
import json
import re
import hashlib
from urllib.parse import urljoin

class FreshRTokenAnalysis:
    """Analyze the working session token."""
    
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.working_token = "686a6f04ebd68b86b3f91ee4cfd603b88ae8b7fa17f38aa04958e6e9d6bc50b2"
    
    async def analyze_token(self):
        """Analyze the working token and find APIs."""
        print("=== Fresh-R Working Token Analysis ===")
        
        # Step 1: Analyze token format
        await self.analyze_token_format()
        
        # Step 2: Test token with dashboard
        session = await self.test_token_with_dashboard()
        if not session:
            return False
        
        # Step 3: Find API endpoints
        api_endpoints = await self.find_api_endpoints(session)
        
        # Step 4: Test APIs
        working_apis = await self.test_api_endpoints(session, api_endpoints)
        
        # Step 5: Document solution
        await self.document_solution(working_apis)
        
        return True
    
    async def analyze_token_format(self):
        """Analyze the token format and possible sources."""
        print("\n1. Analyzing token format...")
        
        token = self.working_token
        print(f"Token: {token}")
        print(f"Length: {len(token)}")
        print(f"Format: {'hex' if all(c in '0123456789abcdef' for c in token.lower()) else 'unknown'}")
        
        # Test if it's a hash of common strings
        test_strings = [
            f"{self.email}:{self.password}",
            f"{self.email}:{self.password}:fresh-r",
            f"{self.email}:{self.password}:dashboard",
            f"buurkracht.binnenhof@gmail.com:Hemert@7733",
            f"buurkracht.binnenhof@gmail.com:Hemert@7733:2026",
            self.email,
            self.password,
        ]
        
        print("\nTesting if token is a hash...")
        for test_str in test_strings:
            sha256_hash = hashlib.sha256(test_str.encode()).hexdigest()
            if sha256_hash == token.lower():
                print(f"🎉 FOUND! Token is SHA256 of: '{test_str}'")
                return test_str
        
        print("❌ Token is not a simple hash of credentials")
        return None
    
    async def test_token_with_dashboard(self):
        """Test if the working token gives dashboard access."""
        print("\n2. Testing token with dashboard...")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        cookies = {
            "sess_token": self.working_token
        }
        
        try:
            session = aiohttp.ClientSession(cookies=cookies, headers=headers)
            
            async with session.get("https://dashboard.bw-log.com/?page=devices") as response:
                if response.status == 200:
                    text = await response.text()
                    if "dashboard" in text.lower():
                        print("✅ Working token gives dashboard access!")
                        return session
                    else:
                        print("❌ Token doesn't give dashboard access")
                        await session.close()
                        return None
                else:
                    print(f"❌ Dashboard access failed: {response.status}")
                    await session.close()
                    return None
                    
        except Exception as e:
            print(f"❌ Error testing token: {e}")
            return None
    
    async def find_api_endpoints(self, session):
        """Find API endpoints in dashboard pages."""
        print("\n3. Finding API endpoints...")
        
        pages = [
            "https://dashboard.bw-log.com/?page=devices",
            "https://dashboard.bw-log.com/?page=dashboard",
            "https://dashboard.bw-log.com/?page=overview",
        ]
        
        endpoints = set()
        
        for page in pages:
            print(f"   Analyzing: {page}")
            
            try:
                async with session.get(page) as response:
                    if response.status == 200:
                        text = await response.text()
                        
                        # Look for API calls
                        patterns = [
                            r'fetch\(["\']([^"\']+)["\']',
                            r'\.get\(["\']([^"\']+)["\']',
                            r'\.post\(["\']([^"\']+)["\']',
                            r'api["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                            r'url["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                            r'([^"\']*\.php[^"\']*)',
                            r'([^"\']*api[^"\']*)',
                        ]
                        
                        for pattern in patterns:
                            matches = re.findall(pattern, text, re.I)
                            for match in matches:
                                if 'api' in match.lower() or match.startswith('/'):
                                    full_url = urljoin("https://dashboard.bw-log.com", match)
                                    endpoints.add(full_url)
                                    print(f"      Found: {full_url}")
                    
            except Exception as e:
                print(f"   Error: {e}")
        
        return list(endpoints)
    
    async def test_api_endpoints(self, session, endpoints):
        """Test API endpoints."""
        print("\n4. Testing API endpoints...")
        
        working_apis = []
        
        for endpoint in endpoints:
            print(f"   Testing: {endpoint}")
            
            try:
                # Test different formats
                attempts = [
                    {"method": "GET", "params": {}},
                    {"method": "GET", "params": {"q": "devices"}},
                    {"method": "POST", "data": {}},
                    {"method": "POST", "data": {"q": "devices"}},
                    {"method": "POST", "data": {"requests": {"devices": {"fields": ["*"]}}}},
                ]
                
                for i, attempt in enumerate(attempts):
                    headers = {
                        "Accept": "application/json, text/plain, */*",
                        "X-Requested-With": "XMLHttpRequest",
                        "Referer": "https://dashboard.bw-log.com/",
                    }
                    
                    if attempt["method"] == "GET":
                        async with session.get(endpoint, params=attempt["params"], headers=headers) as response:
                            success = await self.analyze_response(response, endpoint, attempt)
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
                            success = await self.analyze_response(response, endpoint, attempt)
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
                print(f"   Error: {e}")
        
        return working_apis
    
    async def analyze_response(self, response, endpoint, attempt):
        """Analyze API response."""
        try:
            if response.status == 200:
                text = await response.text()
                
                try:
                    data = json.loads(text)
                    
                    if isinstance(data, dict):
                        if data.get("success") or data.get("data") or data.get("devices"):
                            print(f"      ✅ Success: {endpoint}")
                            return data
                        elif data.get("error") or data.get("reason"):
                            print(f"      ❌ API Error: {data.get('error', data.get('reason'))}")
                            return False
                    elif isinstance(data, list) and data:
                        print(f"      ✅ Success: {endpoint}")
                        return data
                    
                except json.JSONDecodeError:
                    if "device" in text.lower():
                        print(f"      📄 Contains device info")
                        return {"html": text[:500]}
                    else:
                        print(f"      ❌ Not useful")
                        return False
            else:
                print(f"      ❌ HTTP {response.status}")
                return False
                
        except Exception as e:
            print(f"      ❌ Error: {e}")
            return False
    
    async def document_solution(self, working_apis):
        """Document the working solution."""
        print("\n5. Documenting solution...")
        
        if not working_apis:
            print("❌ No working APIs found")
            return
        
        print("\n🎉 WORKING SOLUTION FOUND!")
        print("\n📋 IMPLEMENTATION GUIDE:")
        print("====================")
        print(f"Session Token: {self.working_token}")
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
            "session_token": self.working_token,
            "cookie_name": "sess_token",
            "working_apis": working_apis,
            "implementation": "Use form login to get session token, then use token for API calls"
        }
        
        with open("fresh_r_scalable_solution.json", "w") as f:
            json.dump(solution, f, indent=2)
        
        print("\n💾 Solution saved to: fresh_r_scalable_solution.json")

async def main():
    analysis = FreshRTokenAnalysis("buurkracht.binnenhof@gmail.com", "Hemert@7733")
    success = await analysis.analyze_token()
    
    if success:
        print("\n🎉 SCALABLE SOLUTION FOUND!")
        print("Check fresh_r_scalable_solution.json for implementation details.")
    else:
        print("\n❌ No scalable solution found.")
        print("The hardcoded token approach might be the only working method.")

if __name__ == "__main__":
    asyncio.run(main())
