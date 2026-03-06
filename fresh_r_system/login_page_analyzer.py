#!/usr/bin/env python3
"""
Fresh-R Login Page Analyzer
===========================

Analyze the login page HTML to find the correct form structure.
"""

import aiohttp
import re

async def analyze_login_page():
    """Analyze the login page HTML structure."""
    print("=== Fresh-R Login Page Analyzer ===")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get("https://fresh-r.me/login") as response:
            if response.status == 200:
                text = await response.text()
                
                print("1. Looking for form elements...")
                
                # Find all input fields
                input_pattern = r'<input[^>]*>'
                inputs = re.findall(input_pattern, text, re.I)
                print(f"   Found {len(inputs)} input elements:")
                for inp in inputs:
                    print(f"      {inp}")
                
                # Find all buttons
                button_pattern = r'<button[^>]*>.*?</button>'
                buttons = re.findall(button_pattern, text, re.I | re.DOTALL)
                print(f"\n2. Found {len(buttons)} button elements:")
                for btn in buttons[:5]:  # Limit to first 5
                    print(f"      {btn}")
                
                # Find form element
                form_pattern = r'<form[^>]*>.*?</form>'
                forms = re.findall(form_pattern, text, re.I | re.DOTALL)
                print(f"\n3. Found {len(forms)} form elements")
                
                if forms:
                    print(f"   First form: {forms[0][:500]}")
                
                # Look for submit elements
                submit_pattern = r'<[^>]*type=["\']submit["\'][^>]*>'
                submits = re.findall(submit_pattern, text, re.I)
                print(f"\n4. Found {len(submits)} submit elements:")
                for sub in submits:
                    print(f"      {sub}")
                
                # Look for onclick handlers
                onclick_pattern = r'<[^>]*onclick=["\'][^"\']*submit[^"\']*["\'][^>]*>'
                onclicks = re.findall(onclick_pattern, text, re.I)
                print(f"\n5. Found {len(onclicks)} elements with submit onclick:")
                for onclick in onclicks[:3]:
                    print(f"      {onclick}")
                
                # Look for JavaScript form submission
                js_pattern = r'form\.submit\(\)|document\.forms\[\d+\]\.submit\(\)'
                js_matches = re.findall(js_pattern, text, re.I)
                print(f"\n6. Found {len(js_matches)} JavaScript form submissions")
                
                return True
            else:
                print(f"❌ Failed to get login page: {response.status}")
                return False

if __name__ == "__main__":
    import asyncio
    asyncio.run(analyze_login_page())
