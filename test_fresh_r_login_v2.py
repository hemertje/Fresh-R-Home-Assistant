#!/usr/bin/env python3
"""
Fresh-R Login Flow Analyzer V2
Tests the auth_token redirect fix
"""
import aiohttp
import asyncio
import json
import re
from datetime import datetime


async def test_fresh_r_with_token_redirect(email: str, password: str):
    """Test Fresh-R login with auth_token redirect fix."""
    
    print("=" * 80)
    print("FRESH-R LOGIN FLOW ANALYZER V2 - WITH AUTH TOKEN REDIRECT")
    print("=" * 80)
    print(f"Timestamp: {datetime.now()}")
    print(f"Email: {email}")
    print("=" * 80)
    
    # Create session with unsafe cookie jar
    jar = aiohttp.CookieJar(unsafe=True, quote_cookie=False)
    connector = aiohttp.TCPConnector(ssl=False)
    
    async with aiohttp.ClientSession(cookie_jar=jar, connector=connector) as session:
        
        # ===================================================================
        # STEP 1: GET Login Page
        # ===================================================================
        print("\n[STEP 1] GET Login Page")
        print("-" * 80)
        
        login_page_url = "https://fresh-r.me/login/index.php?page=login"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "nl,en-US;q=0.9,en;q=0.8",
        }
        
        async with session.get(login_page_url, headers=headers) as r:
            print(f"Status: {r.status}")
            print(f"Cookies: {len(list(session.cookie_jar))} cookie(s)")
            for cookie in session.cookie_jar:
                print(f"  - {cookie.key} (domain={cookie['domain']})")
        
        # ===================================================================
        # STEP 2: POST Login Credentials
        # ===================================================================
        print("\n[STEP 2] POST Login Credentials")
        print("-" * 80)
        
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
        
        async with session.post(login_api_url, data=form, headers=headers) as r:
            body = await r.text()
            print(f"Status: {r.status}")
            
            try:
                data = json.loads(body)
                authenticated = data.get("authenticated", False)
                auth_token = data.get("auth_token", "")
                
                print(f"Authenticated: {authenticated}")
                if auth_token:
                    print(f"Auth Token: {auth_token[:32]}...")
                else:
                    print("Auth Token: None")
                
                if not authenticated:
                    print(f"[FAIL] Login failed: {data.get('message', 'Unknown error')}")
                    return
                
            except json.JSONDecodeError:
                print("[FAIL] Response is not JSON")
                return
        
        # ===================================================================
        # STEP 3: Navigate to Devices Page WITH Auth Token
        # ===================================================================
        print("\n[STEP 3] Navigate to Devices Page WITH Auth Token")
        print("-" * 80)
        
        if auth_token:
            devices_url_with_token = f"https://dashboard.bw-log.com/?page=devices&t={auth_token}"
            print(f"URL: {devices_url_with_token[:80]}...")
            
            async with session.get(devices_url_with_token, allow_redirects=True) as r:
                body = await r.text()
                print(f"Status: {r.status}")
                print(f"Final URL: {r.url}")
                
                # Check cookies after redirect
                print(f"\nCookies after token redirect: {len(list(session.cookie_jar))} cookie(s)")
                for cookie in session.cookie_jar:
                    print(f"  - {cookie.key} = {cookie.value[:16]}... (domain={cookie['domain']})")
                
                # Check page title
                if '<title>' in body:
                    title = body.split('<title>')[1].split('</title>')[0]
                    print(f"\nPage Title: {title}")
                    
                    if "Vaventis" in title:
                        print("[FAIL] Still redirected to Vaventis!")
                    elif "Dashboard" in title:
                        print("[SUCCESS] On Fresh-R devices page!")
                
                # Look for serial numbers
                serial_pattern = re.compile(r'serial=([^&"\'>\s]+)', re.I)
                serials = list(set(m.group(1) for m in serial_pattern.finditer(body)))
                
                if serials:
                    print(f"\n[SUCCESS] Found {len(serials)} serial number(s):")
                    for serial in serials:
                        print(f"  - {serial}")
                else:
                    print("\n[FAIL] No serial numbers found")
        
        # ===================================================================
        # STEP 4: GET Devices Page Again (Without Token)
        # ===================================================================
        print("\n[STEP 4] GET Devices Page Again (Without Token)")
        print("-" * 80)
        print("Testing if cookie persists for subsequent requests...")
        
        devices_url = "https://dashboard.bw-log.com/?page=devices"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "nl,en-US;q=0.9,en;q=0.8",
        }
        
        # Check which cookies will be sent
        print(f"\nCookies that will be sent to {devices_url}:")
        for cookie in session.cookie_jar:
            if "dashboard.bw-log.com" in cookie['domain'] or cookie['domain'].startswith('.'):
                print(f"  [OK] {cookie.key} (domain={cookie['domain']})")
            else:
                print(f"  [NO] {cookie.key} (domain={cookie['domain']})")
        
        async with session.get(devices_url, headers=headers, allow_redirects=True) as r:
            body = await r.text()
            print(f"\nStatus: {r.status}")
            print(f"Final URL: {r.url}")
            
            # Check page title
            if '<title>' in body:
                title = body.split('<title>')[1].split('</title>')[0]
                print(f"Page Title: {title}")
                
                if "Vaventis" in title:
                    print("[FAIL] Cookie didn't persist - back to Vaventis")
                elif "Dashboard" in title:
                    print("[SUCCESS] Cookie persists - still on devices page!")
            
            # Look for serial numbers
            serial_pattern = re.compile(r'serial=([^&"\'>\s]+)', re.I)
            serials = list(set(m.group(1) for m in serial_pattern.finditer(body)))
            
            if serials:
                print(f"\n[SUCCESS] Found {len(serials)} serial number(s):")
                for serial in serials:
                    print(f"  - {serial}")
        
        # ===================================================================
        # SUMMARY
        # ===================================================================
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        
        print(f"\nTotal cookies: {len(list(session.cookie_jar))}")
        for cookie in session.cookie_jar:
            print(f"  {cookie.key} (domain={cookie['domain']}, path={cookie.get('path', '/')})")
        
        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python test_fresh_r_login_v2.py <email> <password>")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    asyncio.run(test_fresh_r_with_token_redirect(email, password))
