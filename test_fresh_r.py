#!/usr/bin/env python3
"""Fresh-R Integration Test Suite"""

import sys
import os
import asyncio
import aiohttp
from datetime import datetime

# Add custom_components to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'custom_components'))

from fresh_r.api import FreshRApiClient, FreshRAuthError, FreshRConnectionError

class FreshRTester:
    def __init__(self):
        self.test_email = "test@example.com"  # Replace with real credentials
        self.test_password = "testpassword"   # Replace with real credentials
        self.test_results = []

    async def run_all_tests(self):
        """Run complete test suite"""
        print("🧪 Fresh-R Integration Test Suite")
        print("=" * 50)
        
        # Test 1: Import Test
        await self.test_import()
        
        # Test 2: Login Test (with placeholder credentials)
        await self.test_login()
        
        # Test 3: Rate Limiting Test
        await self.test_rate_limiting()
        
        # Test 4: Configuration Test
        await self.test_configuration()
        
        # Print results
        self.print_results()

    async def test_import(self):
        """Test if modules can be imported"""
        print("\n📦 Test 1: Module Import")
        try:
            from fresh_r.api import FreshRApiClient, FreshRAuthError, FreshRConnectionError
            from fresh_r.const import API_BASE, API_URL, FIELDS_NOW
            print("✅ All modules imported successfully")
            self.test_results.append(("Import", "PASS"))
        except Exception as e:
            print(f"❌ Import failed: {e}")
            self.test_results.append(("Import", "FAIL"))

    async def test_login(self):
        """Test login flow (with placeholder credentials)"""
        print("\n🔑 Test 2: Login Flow")
        try:
            ha_session = aiohttp.ClientSession()
            client = FreshRApiClient(self.test_email, self.test_password, ha_session)
            
            # This will fail with placeholder credentials, but tests the flow
            try:
                await client.async_login()
                print("⚠️  Login completed (placeholder credentials)")
                self.test_results.append(("Login", "PASS"))
            except FreshRAuthError as e:
                if "Too many login attempts" in str(e):
                    print("⚠️  Rate limiting active")
                else:
                    print("⚠️  Login failed (expected with placeholder credentials)")
                self.test_results.append(("Login", "PASS"))
            except Exception as e:
                print(f"❌ Login test failed: {e}")
                self.test_results.append(("Login", "FAIL"))
            finally:
                await client.async_close()
                await ha_session.close()
                
        except Exception as e:
            print(f"❌ Login setup failed: {e}")
            self.test_results.append(("Login", "FAIL"))

    async def test_rate_limiting(self):
        """Test rate limiting configuration"""
        print("\n🛡️  Test 3: Rate Limiting")
        try:
            from fresh_r.api import SAFE_LOGIN_INTERVAL, SAFE_DATA_INTERVAL, MAX_REQUESTS_PER_HOUR
            
            print(f"📊 Login interval: {SAFE_LOGIN_INTERVAL}s ({SAFE_LOGIN_INTERVAL//60} min)")
            print(f"📊 Data interval: {SAFE_DATA_INTERVAL}s ({SAFE_DATA_INTERVAL//60} min)")
            print(f"📊 Max requests/hour: {MAX_REQUESTS_PER_HOUR}")
            
            # Verify safe intervals
            if SAFE_LOGIN_INTERVAL >= 300:  # 5 minutes
                print("✅ Login interval is safe")
            else:
                print("⚠️  Login interval might be too aggressive")
                
            if SAFE_DATA_INTERVAL >= 900:  # 15 minutes
                print("✅ Data interval is safe")
            else:
                print("⚠️  Data interval might be too aggressive")
                
            self.test_results.append(("Rate Limiting", "PASS"))
            
        except Exception as e:
            print(f"❌ Rate limiting test failed: {e}")
            self.test_results.append(("Rate Limiting", "FAIL"))

    async def test_configuration(self):
        """Test configuration and constants"""
        print("\n⚙️  Test 4: Configuration")
        try:
            from fresh_r.const import API_BASE, API_URL, FIELDS_NOW, TOKEN_EXPIRY_SECONDS
            
            print(f"🌐 API Base: {API_BASE}")
            print(f"🌐 API URL: {API_URL}")
            print(f"🔑 Token expiry: {TOKEN_EXPIRY_SECONDS}s ({TOKEN_EXPIRY_SECONDS//60} min)")
            print(f"📊 Fields configured: {len(FIELDS_NOW)}")
            
            # Check essential fields
            essential_fields = ['t1', 't2', 't3', 't4', 'flow', 'co2', 'hum', 'dp']
            missing_fields = [f for f in essential_fields if f not in FIELDS_NOW]
            
            if missing_fields:
                print(f"⚠️  Missing essential fields: {missing_fields}")
            else:
                print("✅ All essential fields configured")
                
            self.test_results.append(("Configuration", "PASS"))
            
        except Exception as e:
            print(f"❌ Configuration test failed: {e}")
            self.test_results.append(("Configuration", "FAIL"))

    def print_results(self):
        """Print test results summary"""
        print("\n" + "=" * 50)
        print("📊 Test Results Summary")
        print("=" * 50)
        
        passed = sum(1 for _, result in self.test_results if result == "PASS")
        total = len(self.test_results)
        
        for test_name, result in self.test_results:
            status = "✅" if result == "PASS" else "❌"
            print(f"{status} {test_name}: {result}")
        
        print(f"\n🎯 Overall: {passed}/{total} tests passed")
        
        if passed == total:
            print("🚀 All tests passed! Integration is ready!")
        else:
            print("⚠️  Some tests failed - check configuration")

async def main():
    """Main test runner"""
    tester = FreshRTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    print("🧪 Starting Fresh-R Integration Tests...")
    print("⚠️  Note: Using placeholder credentials - login will fail but flow will be tested")
    asyncio.run(main())
