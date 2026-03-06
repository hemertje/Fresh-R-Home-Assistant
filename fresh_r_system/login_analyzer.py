#!/usr/bin/env python3
"""
Fresh-R Login Response Analyzer
==============================

Analyze the login response to find where sess_token comes from.
"""

import asyncio
import aiohttp
import json
from urllib.parse import urljoin

async def analyze_login_response():
    """Analyze the login response in detail."""
    print("=== Fresh-R Login Response Analyzer ===")
    
    email = "buurkracht.binnenhof@gmail.com"
    password = "Hemert@7733"
    
    # Different login attempts
    login_attempts = [
        {
            "name": "fresh-r.me with redirect",
            "url": "https://fresh-r.me/login",
            "data": {"email": email, "password": password, "keep_logged_in": "1"},
            "allow_redirects": True,
        },
        {
            "name": "fresh-r.me without redirect",
            "url": "https://fresh-r.me/login", 
            "data": {"email": email, "password": password, "keep_logged_in": "1"},
            "allow_redirects": False,
        },
        {
            "name": "fresh-r.me AJAX request",
            "url": "https://fresh-r.me/login",
            "data": {"email": email, "password": password, "ajax": "1"},
            "allow_redirects": False,
            "ajax": True,
        },
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
        print(f"\n{'='*60}")
        print(f"Attempt: {attempt['name']}")
        print(f"{'='*60}")
        
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                # Get login page first (for cookies)
                print("1. Getting login page...")
                async with session.get(attempt["url"]) as response:
                    print(f"   Login page status: {response.status}")
                    initial_cookies = [(c.key, c.value) for c in session.cookie_jar]
                    print(f"   Initial cookies: {initial_cookies}")
                
                # Try login
                print("2. Posting login data...")
                post_headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://fresh-r.me",
                    "Referer": attempt["url"],
                }
                
                if attempt.get("ajax"):
                    post_headers["X-Requested-With"] = "XMLHttpRequest"
                    post_headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
                
                async with session.post(
                    attempt["url"], 
                    data=attempt["data"], 
                    headers=post_headers, 
                    allow_redirects=attempt["allow_redirects"]
                ) as response:
                    print(f"   Login response status: {response.status}")
                    
                    # Check all headers
                    print("\n3. Response headers:")
                    for header_name, header_value in response.headers.items():
                        print(f"   {header_name}: {header_value[:100]}...")
                    
                    # Check cookies after login
                    final_cookies = [(c.key, c.value) for c in session.cookie_jar]
                    print(f"\n4. Cookies after login:")
                    for name, value in final_cookies:
                        print(f"   {name}: {value[:50]}...")
                    
                    # Check for sess_token specifically
                    sess_token = next((v for n, v in final_cookies if n == "sess_token"), None)
                    if sess_token:
                        print(f"\n🎉 FOUND SESS_TOKEN: {sess_token}")
                    
                    # Check response body
                    print("\n5. Response body:")
                    if response.status == 200:
                        text = await response.text()
                        print(f"   Length: {len(text)} characters")
                        print(f"   Preview: {text[:500]}")
                        
                        # Look for sess_token in body
                        if "sess_token" in text:
                            print("\n   🎉 SESS_TOKEN FOUND IN BODY!")
                            # Extract it
                            import re
                            match = re.search(r'sess_token["\']?\s*[:=]\s*["\']([^"\']+)["\']', text)
                            if match:
                                print(f"   Token: {match.group(1)}")
                    
                    # If redirect, follow it
                    if response.status in (301, 302, 303, 307, 308):
                        location = response.headers.get("Location")
                        print(f"\n6. Redirect to: {location}")
                        
                        # Follow redirect
                        async with session.get(location, allow_redirects=True) as redirect_response:
                            print(f"   Final status: {redirect_response.status}")
                            final_url = str(redirect_response.url)
                            print(f"   Final URL: {final_url}")
                            
                            # Check cookies after redirect
                            redirect_cookies = [(c.key, c.value) for c in session.cookie_jar]
                            print(f"   Cookies after redirect:")
                            for name, value in redirect_cookies:
                                print(f"      {name}: {value[:50]}...")
                            
                            # Check for sess_token
                            sess_token = next((v for n, v in redirect_cookies if n == "sess_token"), None)
                            if sess_token:
                                print(f"\n   🎉 FOUND SESS_TOKEN AFTER REDIRECT: {sess_token}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print("Analysis complete!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(analyze_login_response())
