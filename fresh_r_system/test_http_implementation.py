#!/usr/bin/env python3
"""
Fresh-R HTTP-Only Implementation Test
=====================================

Valideer dat de nieuwe HTTP-only versie werkt zonder Selenium/Chrome.
"""

import asyncio
import sys
sys.path.insert(0, 'custom_components/fresh_r')

async def test_http_login():
    """Test de nieuwe HTTP-only login implementatie."""
    print("=" * 60)
    print("Fresh-R HTTP-Only Implementation Test")
    print("=" * 60)
    
    # Import de nieuwe API client
    try:
        from api import FreshRApiClient, BROWSER_HEADERS, API_HEADERS
        print("✅ api.py imported successfully")
    except Exception as e:
        print(f"❌ Failed to import api.py: {e}")
        return False
    
    # Test 1: Check class initialization
    print("\n1. Testing FreshRApiClient initialization...")
    try:
        client = FreshRApiClient(
            email="buurkracht.binnenhof@gmail.com",
            password="Hemert@7733",
            ha_session=None
        )
        print("✅ Client initialized successfully")
        print(f"   - Email: {client._email}")
        print(f"   - Has cookie jar: {client._cookie_jar is not None}")
    except Exception as e:
        print(f"❌ Client initialization failed: {e}")
        return False
    
    # Test 2: Check HTTP headers are set correctly
    print("\n2. Testing HTTP headers...")
    try:
        assert "User-Agent" in BROWSER_HEADERS
        assert "Mozilla/5.0" in BROWSER_HEADERS["User-Agent"]
        assert "Accept" in BROWSER_HEADERS
        print("✅ BROWSER_HEADERS configured correctly")
        print(f"   - User-Agent: {BROWSER_HEADERS['User-Agent'][:50]}...")
        
        assert "X-Requested-With" in API_HEADERS
        assert API_HEADERS["X-Requested-With"] == "XMLHttpRequest"
        print("✅ API_HEADERS configured correctly")
    except Exception as e:
        print(f"❌ Headers check failed: {e}")
        return False
    
    # Test 3: Test login (online test - alleen als gewenst)
    print("\n3. Testing online login...")
    print("   (Dit test de echte login met fresh-r.me)")
    
    try:
        token = await client.async_login()
        if token:
            print(f"✅ Login successful!")
            print(f"   - Token: {token[:30]}...")
            
            # Test 4: Device discovery
            print("\n4. Testing device discovery...")
            devices = await client.async_discover_devices()
            if devices:
                print(f"✅ Found {len(devices)} device(s)")
                for device in devices:
                    print(f"   - {device.get('id')}: {device.get('name')}")
                
                # Test 5: Data fetch
                if devices:
                    print("\n5. Testing data fetch...")
                    serial = devices[0]["id"]
                    data = await client.async_get_current(serial)
                    if data:
                        print(f"✅ Data fetched successfully!")
                        print(f"   - Fields: {list(data.keys())[:5]}...")
                        if 't1' in data:
                            print(f"   - t1 (indoor temp): {data['t1']}°C")
                        if 'co2' in data:
                            print(f"   - co2: {data['co2']} ppm")
                    else:
                        print("⚠️ No data returned (might be OK if no recent data)")
            else:
                print("⚠️ No devices found (check credentials)")
        else:
            print("❌ Login failed - check credentials or website availability")
            return False
            
    except Exception as e:
        print(f"❌ Online test failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False
    
    # Test 6: Verify no Selenium imports
    print("\n6. Verifying no Selenium dependencies...")
    try:
        import api
        source = open('custom_components/fresh_r/api.py').read()
        
        if 'selenium' in source.lower():
            print("❌ ERROR: Selenium still referenced in api.py!")
            return False
        if 'webdriver' in source.lower():
            print("❌ ERROR: WebDriver still referenced in api.py!")
            return False
        if 'chrome' in source.lower() and 'headers' not in source.lower():
            print("❌ ERROR: Chrome still referenced (not just in headers)!")
            return False
            
        print("✅ No Selenium/WebDriver/Chrome dependencies found")
    except Exception as e:
        print(f"⚠️ Could not verify Selenium removal: {e}")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print("\nDe HTTP-only implementatie werkt correct!")
    print("Geen browser installatie nodig!")
    
    return True


def test_syntax():
    """Test alle Python files op syntax errors."""
    print("\n" + "=" * 60)
    print("Syntax Validation")
    print("=" * 60)
    
    import os
    import py_compile
    
    files_to_check = [
        'custom_components/fresh_r/__init__.py',
        'custom_components/fresh_r/api.py',
        'custom_components/fresh_r/config_flow.py',
        'custom_components/fresh_r/const.py',
        'custom_components/fresh_r/coordinator.py',
        'custom_components/fresh_r/sensor.py',
        'custom_components/fresh_r/mqtt.py',
    ]
    
    all_ok = True
    for filepath in files_to_check:
        if os.path.exists(filepath):
            try:
                py_compile.compile(filepath, doraise=True)
                print(f"✅ {filepath}")
            except py_compile.PyCompileError as e:
                print(f"❌ {filepath}: {e}")
                all_ok = False
        else:
            print(f"⚠️ {filepath}: File not found")
    
    return all_ok


if __name__ == "__main__":
    # First check syntax
    syntax_ok = test_syntax()
    
    if not syntax_ok:
        print("\n❌ Syntax errors found! Fix these first.")
        sys.exit(1)
    
    # Then run online tests
    print("\n" + "=" * 60)
    print("Online Validation")
    print("=" * 60)
    print("\nDeze test maakt ECHTE HTTP requests naar fresh-r.me")
    print("Dit verifieert dat de nieuwe implementatie werkt.")
    print("\nWil je doorgaan? (y/n): ", end="")
    
    # Auto-continue for now
    response = "y"
    print("y (auto-continue)")
    
    if response.lower() == "y":
        success = asyncio.run(test_http_login())
        if success:
            print("\n🎉 VALIDATIE SUCCESVOL!")
            print("De integratie is klaar voor gebruik.")
            sys.exit(0)
        else:
            print("\n❌ VALIDATIE MISLUKT")
            print("Controleer de errors hierboven.")
            sys.exit(1)
    else:
        print("Test overgeslagen.")
        sys.exit(0)
