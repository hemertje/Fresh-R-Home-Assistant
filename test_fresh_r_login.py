#!/usr/bin/env python3
"""
Fresh-R Login Flow Analyzer
Simulates browser login and logs all cookies, redirects, and responses
"""
import aiohttp
import asyncio
import json
from datetime import datetime


async def analyze_fresh_r_login(email: str, password: str):
    """Analyze Fresh-R login flow with detailed logging."""
    
    print("=" * 80)
    print("FRESH-R LOGIN FLOW ANALYZER")
    print("=" * 80)
    print(f"Timestamp: {datetime.now()}")
    print(f"Email: {email}")
    print("=" * 80)
    
    # Create session with unsafe cookie jar (allows cross-domain)
    jar = aiohttp.CookieJar(unsafe=True, quote_cookie=False)
    connector = aiohttp.TCPConnector(ssl=False)
    
    async with aiohttp.ClientSession(cookie_jar=jar, connector=connector) as session:
        
        # ===================================================================
        # STEP 1: GET Login Page
        # ===================================================================
        print("\n" + "=" * 80)
        print("STEP 1: GET Login Page")
        print("=" * 80)
        
        login_page_url = "https://fresh-r.me/login/index.php?page=login"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "nl,en-US;q=0.9,en;q=0.8",
        }
        
        print(f"\nRequest: GET {login_page_url}")
        print(f"Headers: {json.dumps(headers, indent=2)}")
        
        async with session.get(login_page_url, headers=headers, allow_redirects=True) as r:
            body = await r.text()
            print(f"\nResponse Status: {r.status}")
            print(f"Response URL: {r.url}")
            print(f"Response Headers: {dict(r.headers)}")
            
            print(f"\nCookies after GET login page:")
            for cookie in session.cookie_jar:
                print(f"  {cookie.key} = {cookie.value[:20]}...")
                print(f"    Domain: {cookie['domain']}")
                print(f"    Path: {cookie.get('path', '/')}")
                print(f"    Secure: {cookie.get('secure', False)}")
                print(f"    HttpOnly: {cookie.get('httponly', False)}")
        
        # ===================================================================
        # STEP 2: POST Login Credentials
        # ===================================================================
        print("\n" + "=" * 80)
        print("STEP 2: POST Login Credentials")
        print("=" * 80)
        
        login_api_url = "https://fresh-r.me/login/api/auth.php"
        form = {"email": email, "password": password}
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json, */*",
            "Origin": "https://fresh-r.me",
            "Referer": login_page_url,
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        
        print(f"\nRequest: POST {login_api_url}")
        print(f"Headers: {json.dumps(headers, indent=2)}")
        print(f"Form Data: email={email}, password=***")
        
        async with session.post(
            login_api_url,
            data=form,
            headers=headers,
            allow_redirects=True,
        ) as r:
            body = await r.text()
            print(f"\nResponse Status: {r.status}")
            print(f"Response URL: {r.url}")
            print(f"Response Headers: {dict(r.headers)}")
            print(f"\nResponse Body (first 500 chars):")
            print(body[:500])
            
            # Try to parse JSON
            try:
                data = json.loads(body)
                print(f"\nJSON Response:")
                print(json.dumps(data, indent=2))
            except json.JSONDecodeError:
                print("\nResponse is not JSON")
            
            print(f"\nCookies after POST login:")
            for cookie in session.cookie_jar:
                print(f"  {cookie.key} = {cookie.value[:20]}...")
                print(f"    Domain: {cookie['domain']}")
                print(f"    Path: {cookie.get('path', '/')}")
                print(f"    Secure: {cookie.get('secure', False)}")
                print(f"    HttpOnly: {cookie.get('httponly', False)}")
        
        # ===================================================================
        # STEP 3: GET Devices Page
        # ===================================================================
        print("\n" + "=" * 80)
        print("STEP 3: GET Devices Page")
        print("=" * 80)
        
        devices_url = "https://dashboard.bw-log.com/?page=devices"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "nl,en-US;q=0.9,en;q=0.8",
            "Referer": "https://fresh-r.me/login/index.php?page=login",
        }
        
        print(f"\nRequest: GET {devices_url}")
        print(f"Headers: {json.dumps(headers, indent=2)}")
        
        # Log which cookies will be sent
        print(f"\nCookies that will be sent to {devices_url}:")
        sent_cookies = []
        for cookie in session.cookie_jar:
            # Check if cookie domain matches
            if "dashboard.bw-log.com" in cookie['domain'] or cookie['domain'].startswith('.'):
                sent_cookies.append(cookie.key)
                print(f"  [OK] {cookie.key} (domain={cookie['domain']})")
            else:
                print(f"  [NO] {cookie.key} (domain={cookie['domain']}) - WILL NOT BE SENT")
        
        async with session.get(devices_url, headers=headers, allow_redirects=True) as r:
            body = await r.text()
            print(f"\nResponse Status: {r.status}")
            print(f"Response URL: {r.url}")
            print(f"Response Headers: {dict(r.headers)}")
            
            # Check page title
            if '<title>' in body:
                title = body.split('<title>')[1].split('</title>')[0]
                print(f"\nPage Title: {title}")
                
                if "Vaventis" in title:
                    print("[FAIL] REDIRECTED TO VAVENTIS - LOGIN FAILED!")
                elif "Dashboard" in title:
                    print("[SUCCESS] ON FRESH-R DEVICES PAGE!")
            
            # Look for serial numbers
            import re
            serial_pattern = re.compile(r'serial=([^&"\'>\s]+)', re.I)
            serials = list(set(m.group(1) for m in serial_pattern.finditer(body)))
            
            if serials:
                print(f"\n[OK] Found {len(serials)} serial number(s):")
                for serial in serials:
                    print(f"  - {serial}")
            else:
                print("\n[FAIL] No serial numbers found")
            
            print(f"\nCookies after GET devices page:")
            for cookie in session.cookie_jar:
                print(f"  {cookie.key} = {cookie.value[:20]}...")
                print(f"    Domain: {cookie['domain']}")
                print(f"    Path: {cookie.get('path', '/')}")
        
        # ===================================================================
        # SUMMARY
        # ===================================================================
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        
        print(f"\nTotal cookies in jar: {len(list(session.cookie_jar))}")
        print("\nAll cookies:")
        for cookie in session.cookie_jar:
            print(f"  {cookie.key} (domain={cookie['domain']}, path={cookie.get('path', '/')})")
        
        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python test_fresh_r_login.py <email> <password>")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    asyncio.run(analyze_fresh_r_login(email, password))
