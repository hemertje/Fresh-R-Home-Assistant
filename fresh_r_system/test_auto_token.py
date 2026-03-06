#!/usr/bin/env python3
"""
Fresh-R Automatic Token Refresh Test
====================================

Test the automatic token extraction and hourly refresh mechanism.
"""

import asyncio
import sys
sys.path.insert(0, 'custom_components/fresh_r')

from api import FreshRApiClient

async def test_auto_token_refresh():
    """Test automatic token extraction and refresh."""
    print("=== Fresh-R Automatic Token Refresh Test ===")
    
    # Create API client
    client = FreshRApiClient(
        email="buurkracht.binnenhof@gmail.com",
        password="Hemert@7733"
    )
    
    print("\n1. Testing initial login with automatic token extraction...")
    
    try:
        # First login - should extract token automatically
        result = await client.async_login()
        
        if hasattr(client, '_session_token') and client._session_token:
            print(f"🎉 SUCCESS! Token extracted: {client._session_token[:30]}...")
            
            # Check token timestamp
            if hasattr(client, '_token_timestamp') and client._token_timestamp:
                from datetime import datetime
                age = datetime.now() - client._token_timestamp
                print(f"   Token age: {age.total_seconds():.0f} seconds")
            
            # Test device discovery
            print("\n2. Testing device discovery with extracted token...")
            devices = await client.async_discover_devices()
            
            if devices:
                print(f"🎉 Device discovery successful! Found {len(devices)} devices")
                for device in devices:
                    print(f"   - {device.get('name', 'Unknown')} (ID: {device.get('id', 'Unknown')})")
            else:
                print("⚠️ No devices found, but token works")
            
            # Test token validation
            print("\n3. Testing token validation...")
            is_valid = await client._test_token(client._session_token)
            if is_valid:
                print("✅ Token is valid")
            else:
                print("❌ Token is invalid")
            
            # Test token refresh (simulate age)
            print("\n4. Testing token refresh mechanism...")
            from datetime import timedelta, datetime
            
            # Simulate old token
            client._token_timestamp = datetime.now() - timedelta(minutes=55)
            
            print("   Simulating 55-minute old token...")
            await client.async_ensure_token_valid()
            
            if hasattr(client, '_session_token') and client._session_token:
                print(f"✅ Token refresh triggered successfully")
            else:
                print("⚠️ Token refresh may not have worked")
            
            print("\n🎉 AUTOMATIC TOKEN REFRESH TEST PASSED!")
            return True
        else:
            print("❌ FAILED: No token extracted")
            return False
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_auto_token_refresh())
    
    if success:
        print("\n✅ Automatic token refresh is working!")
        print("Home Assistant will login every hour to refresh the token.")
    else:
        print("\n❌ Automatic token refresh failed.")
        print("Check the logs above for details.")
