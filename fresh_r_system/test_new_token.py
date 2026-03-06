#!/usr/bin/env python3
"""
Fresh-R New Token Test
======================

Test the new session token from the user.
"""

import asyncio
import aiohttp

async def test_new_token():
    """Test the new session token."""
    print("=== Fresh-R New Token Test ===")
    
    # New token from user
    new_token = "b9063353d1e1a4c5017ed52aff54412d15bb3ab044e6c43202c12a6e21ab537a"
    
    print(f"Testing token: {new_token}")
    print(f"Token length: {len(new_token)}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://dashboard.bw-log.com/",
    }
    
    cookies = {
        "sess_token": new_token
    }
    
    try:
        async with aiohttp.ClientSession(cookies=cookies, headers=headers) as session:
            # Test 1: Dashboard access
            print("\n1. Testing dashboard access...")
            async with session.get("https://dashboard.bw-log.com/?page=devices") as response:
                print(f"   Status: {response.status}")
                
                if response.status == 200:
                    text = await response.text()
                    
                    if "dashboard" in text.lower():
                        print("   ✅ Dashboard access works!")
                        
                        # Look for device data
                        if "device" in text.lower() or "fresh-r" in text.lower():
                            print("   ✅ Found device content!")
                            
                            # Try to extract device info
                            import re
                            
                            # Look for serial numbers
                            serial_pattern = r'([a-z]{2}:\d+/\d+)'
                            serials = re.findall(serial_pattern, text, re.I)
                            
                            if serials:
                                print(f"   🎉 Found {len(serials)} device serials: {serials}")
                            else:
                                print("   ℹ️ No device serials found in HTML")
                            
                            return True
                        else:
                            print("   ⚠️ No device content found")
                            return False
                    else:
                        print("   ❌ Dashboard access failed")
                        return False
                else:
                    print(f"   ❌ Dashboard access failed: {response.status}")
                    return False
    
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_new_token())
    
    if success:
        print("\n🎉 NEW TOKEN WORKS!")
        print("This token gives dashboard access.")
    else:
        print("\n❌ NEW TOKEN FAILED")
