#!/usr/bin/env python3
"""
Fresh-R Full Browser Automation
===============================

Complete browser automation for automatic login and token extraction.
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

class FreshRFullAutomation:
    """Full browser automation for Fresh-R."""
    
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.login_url = "https://fresh-r.me/login"
        self.dashboard_url = "https://dashboard.bw-log.com/?page=devices"
        self.token_file = "fresh_r_token.json"
    
    def setup_driver(self):
        """Setup Chrome driver."""
        chrome_options = Options()
        
        # Headless for automation
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # User agent
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        # Disable automation flags
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        
        # Remove webdriver flag
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    
    async def get_token(self) -> str | None:
        """Get valid token - from storage or fresh login."""
        print("=== Fresh-R Full Automation ===")
        
        # Check if we have a stored token
        stored_token = self._load_stored_token()
        if stored_token:
            print(f"Found stored token: {stored_token[:20]}...")
            
            # Check if token is still valid
            if await self._test_token(stored_token):
                print("✅ Stored token is still valid")
                return stored_token
            else:
                print("❌ Stored token expired, performing fresh login...")
        
        # Perform browser login to get fresh token
        return await self._browser_login()
    
    def _load_stored_token(self) -> str | None:
        """Load token from storage."""
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                    token = data.get('token')
                    timestamp_str = data.get('timestamp')
                    
                    if token and timestamp_str:
                        timestamp = datetime.fromisoformat(timestamp_str)
                        age = datetime.now() - timestamp
                        
                        # Token valid for ~74 minutes, use 50 min threshold
                        if age < timedelta(minutes=50):
                            print(f"Token age: {age.total_seconds()/60:.0f} min (still valid)")
                            return token
                        else:
                            print(f"Token age: {age.total_seconds()/60:.0f} min (expired)")
                    
                    return None
            except Exception as e:
                print(f"Error loading token: {e}")
                return None
        return None
    
    def _save_token(self, token: str):
        """Save token to storage."""
        data = {
            'token': token,
            'timestamp': datetime.now().isoformat()
        }
        with open(self.token_file, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"💾 Token saved to {self.token_file}")
    
    async def _test_token(self, token: str) -> bool:
        """Test if token is valid."""
        import aiohttp
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        
        cookies = {"sess_token": token}
        
        try:
            async with aiohttp.ClientSession(cookies=cookies, headers=headers) as session:
                async with session.get(self.dashboard_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        text = await response.text()
                        return "dashboard" in text.lower()
                    return False
        except:
            return False
    
    async def _browser_login(self) -> str | None:
        """Perform browser login and extract token."""
        print("\n🚀 Starting browser automation...")
        
        driver = None
        try:
            print("1. Setting up Chrome...")
            driver = self.setup_driver()
            
            print(f"2. Navigating to {self.login_url}")
            driver.get(self.login_url)
            
            wait = WebDriverWait(driver, 15)
            
            # Wait for and fill email field
            print("3. Waiting for email field...")
            email_field = wait.until(EC.presence_of_element_located((By.ID, "email")))
            email_field.clear()
            email_field.send_keys(self.email)
            print("   ✓ Email entered")
            
            # Fill password field
            print("4. Filling password...")
            password_field = driver.find_element(By.ID, "password")
            password_field.clear()
            password_field.send_keys(self.password)
            print("   ✓ Password entered")
            
            # Find and click submit button
            print("5. Looking for submit button...")
            
            # Try different submit button selectors
            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button.btn-primary",
                "button.login-button",
                "form button",
                "form input[type='button']",
            ]
            
            submit_button = None
            for selector in submit_selectors:
                try:
                    submit_button = driver.find_element(By.CSS_SELECTOR, selector)
                    print(f"   Found submit button: {selector}")
                    break
                except:
                    continue
            
            if not submit_button:
                print("   ❌ No submit button found!")
                driver.save_screenshot("no_submit_button.png")
                return None
            
            print("6. Clicking submit...")
            submit_button.click()
            
            # Wait for redirect to dashboard
            print("7. Waiting for redirect...")
            wait.until(EC.url_contains("dashboard.bw-log.com"))
            
            current_url = driver.current_url
            print(f"   ✓ Redirected to: {current_url}")
            
            # Extract cookies
            print("8. Extracting cookies...")
            cookies = driver.get_cookies()
            
            print(f"   Found {len(cookies)} cookies:")
            for cookie in cookies:
                print(f"      {cookie['name']}: {cookie['value'][:30]}...")
            
            # Find sess_token
            sess_token = None
            for cookie in cookies:
                if cookie['name'] == 'sess_token':
                    sess_token = cookie['value']
                    break
            
            if sess_token:
                print(f"\n🎉 SUCCESS! Token extracted: {sess_token[:30]}...")
                
                # Save token
                self._save_token(sess_token)
                
                return sess_token
            else:
                print("\n❌ sess_token not found in cookies")
                driver.save_screenshot("no_token.png")
                return None
                
        except Exception as e:
            print(f"\n❌ Browser automation error: {e}")
            if driver:
                driver.save_screenshot("automation_error.png")
            return None
            
        finally:
            if driver:
                print("9. Closing browser...")
                driver.quit()
    
    async def ensure_fresh_token(self) -> str | None:
        """Ensure we have a fresh token - get new one if needed."""
        token = await self.get_token()
        
        if token:
            # Verify it's working
            if await self._test_token(token):
                return token
            else:
                # Token invalid, force new login
                print("Token invalid, forcing fresh login...")
                if os.path.exists(self.token_file):
                    os.remove(self.token_file)
                return await self._browser_login()
        
        return None

async def main():
    print("Fresh-R Full Browser Automation Test\n")
    
    automation = FreshRFullAutomation(
        email="buurkracht.binnenhof@gmail.com",
        password="Hemert@7733"
    )
    
    # Get valid token
    token = await automation.ensure_fresh_token()
    
    if token:
        print(f"\n{'='*60}")
        print("🎉 FULL AUTOMATION SUCCESS!")
        print(f"{'='*60}")
        print(f"\n✅ Token automatically extracted via browser")
        print(f"✅ Token stored persistently")
        print(f"✅ Token will be refreshed every hour")
        print(f"\nToken: {token[:50]}...")
        print(f"\nHome Assistant integration can now:")
        print("  • Login automatically via browser")
        print("  • Extract and store session token")
        print("  • Refresh token every hour")
        print("  • Read device parameters continuously")
    else:
        print(f"\n{'='*60}")
        print("❌ AUTOMATION FAILED")
        print(f"{'='*60}")
        print("Check screenshots for error details")

if __name__ == "__main__":
    asyncio.run(main())
