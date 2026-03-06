#!/usr/bin/env python3
"""
Fresh-R Token Source Finder
=========================

Find where the session token comes from in the website.
"""

import asyncio
import aiohttp
import json
import re
from urllib.parse import urljoin

class FreshRTokenSourceFinder:
    """Find the source of the session token."""
    
    def __init__(self):
        self.target_token = "686a6f04ebd68b86b3f91ee4cfd603b88ae8b7fa17f38aa04958e6e9d6bc50b2"
    
    async def find_token_source(self):
        """Find where the session token comes from."""
        print("=== Fresh-R Token Source Finder ===")
        print(f"Target token: {self.target_token}")
        
        # Method 1: Check if token is in any public page
        await self.check_public_pages()
        
        # Method 2: Check if token is in JavaScript files
        await self.check_javascript_files()
        
        # Method 3: Check if token is generated client-side
        await self.check_client_side_generation()
        
        # Method 4: Check if token comes from login response
        await self.check_login_response()
        
        print("\n🔍 Token source analysis complete!")
    
    async def check_public_pages(self):
        """Check if token is in public pages."""
        print("\n1. Checking public pages...")
        
        pages = [
            "https://fresh-r.me/",
            "https://fresh-r.me/login",
            "https://dashboard.bw-log.com/",
            "https://dashboard.bw-log.com/login",
        ]
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            for page in pages:
                print(f"   Checking: {page}")
                
                try:
                    async with session.get(page) as response:
                        if response.status == 200:
                            text = await response.text()
                            
                            if self.target_token in text:
                                print(f"   🎉 FOUND TOKEN IN: {page}")
                                
                                # Find context around token
                                index = text.find(self.target_token)
                                start = max(0, index - 200)
                                end = min(len(text), index + 200)
                                context = text[start:end]
                                print(f"   Context: {context}")
                                
                                # Look for patterns
                                patterns = [
                                    r'var\s+\w+\s*=\s*["\']' + self.target_token + '["\']',
                                    r'["\']' + self.target_token + '["\']\s*[:=]',
                                    r'token["\']?\s*[:=]\s*["\']' + self.target_token + '["\']',
                                    r'session["\']?\s*[:=]\s*["\']' + self.target_token + '["\']',
                                ]
                                
                                for pattern in patterns:
                                    matches = re.findall(pattern, text, re.I)
                                    if matches:
                                        print(f"   Pattern found: {matches[0]}")
                                
                                return True
                            else:
                                print(f"   ❌ Token not found in {page}")
                        else:
                            print(f"   ❌ Failed to get {page}: {response.status}")
                
                except Exception as e:
                    print(f"   ❌ Error checking {page}: {e}")
        
        return False
    
    async def check_javascript_files(self):
        """Check if token is in JavaScript files."""
        print("\n2. Checking JavaScript files...")
        
        # Common JS file paths
        js_paths = [
            "/js/main.js",
            "/js/app.js", 
            "/js/dashboard.js",
            "/js/api.js",
            "/assets/js/main.js",
            "/static/js/main.js",
        ]
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            for base_url in ["https://fresh-r.me", "https://dashboard.bw-log.com"]:
                for js_path in js_paths:
                    url = base_url + js_path
                    print(f"   Checking: {url}")
                    
                    try:
                        async with session.get(url) as response:
                            if response.status == 200:
                                text = await response.text()
                                
                                if self.target_token in text:
                                    print(f"   🎉 FOUND TOKEN IN: {url}")
                                    
                                    # Find context
                                    index = text.find(self.target_token)
                                    start = max(0, index - 100)
                                    end = min(len(text), index + 100)
                                    context = text[start:end]
                                    print(f"   Context: {context}")
                                    return True
                                else:
                                    print(f"   ❌ Token not found in {url}")
                            else:
                                print(f"   ❌ Failed to get {url}: {response.status}")
                    
                    except Exception as e:
                        print(f"   ❌ Error checking {url}: {e}")
        
        return False
    
    async def check_client_side_generation(self):
        """Check if token is generated client-side."""
        print("\n3. Checking client-side generation...")
        
        # Look for token generation functions
        generation_patterns = [
            r'function\s+generateToken\s*\([^)]*\)\s*{[^}]*}',
            r'function\s+createSession\s*\([^)]*\)\s*{[^}]*}',
            r'function\s+getSessionId\s*\([^)]*\)\s*{[^}]*}',
            r'token\s*=\s*[^;]*;',
            r'session.*=.*[^;]*;',
        ]
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        
        pages = [
            "https://fresh-r.me/login",
            "https://dashboard.bw-log.com/",
        ]
        
        async with aiohttp.ClientSession(headers=headers) as session:
            for page in pages:
                print(f"   Checking: {page}")
                
                try:
                    async with session.get(page) as response:
                        if response.status == 200:
                            text = await response.text()
                            
                            for pattern in generation_patterns:
                                matches = re.findall(pattern, text, re.I | re.DOTALL)
                                if matches:
                                    print(f"   🔍 Found generation function: {matches[0][:100]}...")
                                    
                                    # Check if this could generate our token
                                    if "sha256" in matches[0].lower() or "hash" in matches[0].lower():
                                        print(f"   🎉 This might generate our token!")
                                        return True
                
                except Exception as e:
                    print(f"   ❌ Error checking {page}: {e}")
        
        return False
    
    async def check_login_response(self):
        """Check if token comes from login response."""
        print("\n4. Checking login response...")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        
        login_data = {
            "email": "buurkracht.binnenhof@gmail.com",
            "password": "Hemert@7733",
            "keep_logged_in": "1"
        }
        
        post_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://fresh-r.me",
            "Referer": "https://fresh-r.me/login",
        }
        
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                # Get login page first
                async with session.get("https://fresh-r.me/login") as response:
                    if response.status != 200:
                        print("   ❌ Failed to get login page")
                        return False
                
                # Try login
                async with session.post("https://fresh-r.me/login", data=login_data, headers=post_headers, allow_redirects=False) as response:
                    print(f"   Login response status: {response.status}")
                    
                    # Check response headers
                    headers_dict = dict(response.headers)
                    print(f"   Response headers: {list(headers_dict.keys())}")
                    
                    # Check for token in headers
                    for header_name, header_value in headers_dict.items():
                        if self.target_token in header_value:
                            print(f"   🎉 FOUND TOKEN IN HEADER: {header_name}")
                            print(f"   Value: {header_value}")
                            return True
                    
                    # Check for token in response body
                    if response.status == 200:
                        text = await response.text()
                        
                        if self.target_token in text:
                            print(f"   🎉 FOUND TOKEN IN RESPONSE BODY!")
                            
                            # Find context
                            index = text.find(self.target_token)
                            start = max(0, index - 200)
                            end = min(len(text), index + 200)
                            context = text[start:end]
                            print(f"   Context: {context}")
                            return True
                        
                        # Look for JSON response
                        try:
                            data = json.loads(text)
                            
                            def find_token_in_obj(obj, path=""):
                                if isinstance(obj, dict):
                                    for key, value in obj.items():
                                        if value == self.target_token:
                                            return f"{path}.{key}"
                                        elif isinstance(value, (dict, list)):
                                            result = find_token_in_obj(value, f"{path}.{key}")
                                            if result:
                                                return result
                                elif isinstance(obj, list):
                                    for i, item in enumerate(obj):
                                        if item == self.target_token:
                                            return f"{path}[{i}]"
                                        elif isinstance(item, (dict, list)):
                                            result = find_token_in_obj(item, f"{path}[{i}]")
                                            if result:
                                                return result
                                return None
                            
                            token_path = find_token_in_obj(data)
                            if token_path:
                                print(f"   🎉 FOUND TOKEN IN JSON at: {token_path}")
                                print(f"   JSON data: {json.dumps(data, indent=2)[:500]}...")
                                return True
                        
                        except json.JSONDecodeError:
                            pass
                    
                    # Check for cookies
                    cookies = [(c.key, c.value) for c in session.cookie_jar]
                    print(f"   Cookies set: {cookies}")
                    
                    for cookie_name, cookie_value in cookies:
                        if cookie_value == self.target_token:
                            print(f"   🎉 FOUND TOKEN IN COOKIE: {cookie_name}")
                            return True
                    
                    print("   ❌ Token not found in login response")
        
        except Exception as e:
            print(f"   ❌ Error checking login response: {e}")
        
        return False

async def main():
    finder = FreshRTokenSourceFinder()
    await finder.find_token_source()

if __name__ == "__main__":
    asyncio.run(main())
