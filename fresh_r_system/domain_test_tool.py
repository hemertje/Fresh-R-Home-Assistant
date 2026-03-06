#!/usr/bin/env python3
"""
Fresh-R Domain Test Tool
========================

Test beide domeinen met juiste credentials:
- fresh-r.me (huidige wachtwoord)
- fresh-r.eu (ander wachtwoord)
"""

import asyncio
import aiohttp

class FreshRDomainTest:
    """Test beide Fresh-R domeinen."""
    
    def __init__(self, email: str, password_me: str, password_eu: str):
        self.email = email
        self.password_me = password_me
        self.password_eu = password_eu
    
    async def test_domain(self, domain: str, password: str):
        """Test login op specifiek domein."""
        login_url = f"https://{domain}/login"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                # Step 1: GET login page
                async with session.get(login_url) as response:
                    if response.status != 200:
                        return {"domain": domain, "success": False, "error": f"GET failed: {response.status}"}
                    
                    html = await response.text()
                    
                    # Step 2: POST login
                    form_data = {
                        "email": self.email,
                        "password": password,
                        "keep_logged_in": "1"
                    }
                    
                    post_headers = {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Origin": f"https://{domain}",
                        "Referer": login_url,
                    }
                    
                    async with session.post(login_url, data=form_data, headers=post_headers, allow_redirects=True) as response:
                        final_url = str(response.url)
                        
                        # Check for success
                        success_indicators = [
                            "dashboard" in final_url.lower(),
                            "devices" in final_url.lower(),
                            "welcome" in (await response.text()).lower(),
                            response.status in [302, 303],
                        ]
                        
                        if any(success_indicators):
                            return {
                                "domain": domain,
                                "success": True,
                                "final_url": final_url,
                                "status": response.status,
                                "cookies": [c.key for c in session.cookie_jar]
                            }
                        else:
                            return {
                                "domain": domain,
                                "success": False,
                                "final_url": final_url,
                                "status": response.status,
                                "error": "No success indicators found"
                            }
                        
        except Exception as e:
            return {"domain": domain, "success": False, "error": str(e)}
    
    async def test_both_domains(self):
        """Test beide domeinen."""
        print("=== Testing Fresh-R Domains ===")
        print(f"Email: {self.email}")
        print()
        
        # Test fresh-r.me met huidige wachtwoord
        print("Testing fresh-r.me...")
        result_me = await self.test_domain("fresh-r.me", self.password_me)
        print(f"Result: {result_me}")
        print()
        
        # Test fresh-r.eu met ander wachtwoord
        print("Testing fresh-r.eu...")
        result_eu = await self.test_domain("fresh-r.eu", self.password_eu)
        print(f"Result: {result_eu}")
        print()
        
        # Analyseer resultaten
        if result_me["success"] and result_eu["success"]:
            print("🎉 BEIDE WERKEN! Gebruik de beste.")
        elif result_me["success"]:
            print("✅ fresh-r.me werkt - gebruik deze.")
        elif result_eu["success"]:
            print("✅ fresh-r.eu werkt - gebruik deze.")
        else:
            print("❌ Geen van beide werkt - check credentials.")
        
        return result_me, result_eu

# USAGE:
# test = FreshRDomainTest("your@email.com", "password_me", "password_eu")
# await test.test_both_domains()
