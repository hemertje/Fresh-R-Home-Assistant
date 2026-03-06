#!/usr/bin/env python3
"""
Fresh-R Browser Automation Login
================================

Use Selenium to automate browser login and extract session token.
"""

import asyncio
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

class FreshRBrowserLogin:
    """Browser automation for Fresh-R login."""
    
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.login_url = "https://fresh-r.me/login"
        self.dashboard_url = "https://dashboard.bw-log.com/?page=devices"
    
    def setup_driver(self):
        """Setup Chrome driver with headless mode."""
        chrome_options = Options()
        
        # Headless mode for server use
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        # User agent
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Disable automation flags
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        
        # Execute script to disable webdriver flag
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    
    def login(self):
        """Perform browser login and extract session token."""
        print("=== Fresh-R Browser Login ===")
        
        driver = None
        try:
            print("1. Setting up Chrome driver...")
            driver = self.setup_driver()
            
            print(f"2. Navigating to login page: {self.login_url}")
            driver.get(self.login_url)
            
            # Wait for page to load
            wait = WebDriverWait(driver, 10)
            
            print("3. Looking for login form...")
            # Find email field
            email_field = wait.until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            print("   Found email field")
            
            # Find password field
            password_field = driver.find_element(By.ID, "password")
            print("   Found password field")
            
            # Find submit button
            submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
            print("   Found submit button")
            
            print("4. Filling in credentials...")
            email_field.clear()
            email_field.send_keys(self.email)
            
            password_field.clear()
            password_field.send_keys(self.password)
            
            print("5. Submitting login form...")
            submit_button.click()
            
            # Wait for redirect to dashboard
            print("6. Waiting for redirect...")
            wait.until(EC.url_contains("dashboard.bw-log.com"))
            
            current_url = driver.current_url
            print(f"   Redirected to: {current_url}")
            
            print("7. Extracting cookies...")
            cookies = driver.get_cookies()
            
            print(f"   Found {len(cookies)} cookies:")
            for cookie in cookies:
                print(f"      {cookie['name']}: {cookie['value'][:50]}...")
            
            # Find sess_token
            sess_token = None
            for cookie in cookies:
                if cookie['name'] == 'sess_token':
                    sess_token = cookie['value']
                    print(f"\n🎉 FOUND SESS_TOKEN: {sess_token}")
                    break
            
            if sess_token:
                # Save to file
                result = {
                    "success": True,
                    "sess_token": sess_token,
                    "dashboard_url": current_url,
                    "cookies": {c['name']: c['value'] for c in cookies}
                }
                
                with open("fresh_r_browser_login.json", "w") as f:
                    json.dump(result, f, indent=2)
                
                print("\n💾 Login result saved to: fresh_r_browser_login.json")
                
                return sess_token
            else:
                print("\n❌ sess_token not found in cookies")
                return None
                
        except Exception as e:
            print(f"\n❌ Browser login error: {e}")
            
            # Save screenshot for debugging
            if driver:
                try:
                    driver.save_screenshot("login_error.png")
                    print("📸 Error screenshot saved to: login_error.png")
                except:
                    pass
            
            return None
            
        finally:
            if driver:
                print("\n8. Closing browser...")
                driver.quit()
    
    def test_dashboard_access(self, sess_token):
        """Test dashboard access with extracted token."""
        print("\n=== Testing Dashboard Access ===")
        
        driver = None
        try:
            print("1. Setting up Chrome driver...")
            driver = self.setup_driver()
            
            print(f"2. Navigating to dashboard...")
            
            # Set cookie before navigating
            driver.get("https://dashboard.bw-log.com")
            
            print("3. Setting sess_token cookie...")
            driver.add_cookie({
                'name': 'sess_token',
                'value': sess_token,
                'domain': 'dashboard.bw-log.com',
                'path': '/'
            })
            
            print("4. Refreshing with cookie...")
            driver.refresh()
            
            # Wait for page to load
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            current_url = driver.current_url
            page_title = driver.title
            
            print(f"   Current URL: {current_url}")
            print(f"   Page title: {page_title}")
            
            # Check if we're on dashboard
            if "dashboard" in current_url.lower() or "dashboard" in page_title.lower():
                print("\n🎉 DASHBOARD ACCESS SUCCESS!")
                
                # Get page content
                page_source = driver.page_source
                
                # Look for device data
                if "device" in page_source.lower() or "fresh-r" in page_source.lower():
                    print("   Found Fresh-r device content!")
                    return True
                else:
                    print("   No device content found")
                    return False
            else:
                print("\n❌ Not on dashboard page")
                return False
                
        except Exception as e:
            print(f"\n❌ Dashboard test error: {e}")
            return False
            
        finally:
            if driver:
                driver.quit()

def main():
    print("Starting Fresh-R Browser Automation...")
    
    # Check if selenium is installed
    try:
        from selenium import webdriver
    except ImportError:
        print("❌ Selenium not installed. Installing...")
        import subprocess
        subprocess.run(["pip", "install", "selenium", "webdriver-manager"])
        print("✅ Selenium installed. Please run again.")
        return
    
    # Perform browser login
    browser_login = FreshRBrowserLogin(
        email="buurkracht.binnenhof@gmail.com",
        password="Hemert@7733"
    )
    
    sess_token = browser_login.login()
    
    if sess_token:
        print("\n🎉 BROWSER LOGIN SUCCESS!")
        print(f"Session Token: {sess_token}")
        
        # Test dashboard access
        success = browser_login.test_dashboard_access(sess_token)
        
        if success:
            print("\n✅ FULL WORKFLOW SUCCESS!")
            print("Browser automation works for login and dashboard access.")
        else:
            print("\n⚠️ Login worked but dashboard access failed")
    else:
        print("\n❌ BROWSER LOGIN FAILED")
        print("Check login_error.png for details")

if __name__ == "__main__":
    main()
