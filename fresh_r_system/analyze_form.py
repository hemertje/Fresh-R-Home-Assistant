#!/usr/bin/env python3
"""
Fresh-R Login Form Analyzer
===========================

Deep analysis of the login form to find missing fields.
"""

import aiohttp
import asyncio
import re

async def analyze_login_form():
    """Analyze the login form structure."""
    print("=== Fresh-R Login Form Deep Analysis ===")
    
    async with aiohttp.ClientSession() as session:
        async with session.get("https://fresh-r.me/login") as response:
            if response.status == 200:
                html = await response.text()
                
                print("1. Looking for form element...")
                form_match = re.search(r'<form[^>]*action=["\']([^"\']*)["\'][^>]*>(.*?)</form>', html, re.DOTALL | re.I)
                if form_match:
                    action = form_match.group(1)
                    form_content = form_match.group(2)
                    print(f"   Form action: {action}")
                    print(f"   Form content preview: {form_content[:500]}")
                    
                    # Find all inputs
                    print("\n2. All input fields in form:")
                    inputs = re.findall(r'<input[^>]*>', form_content, re.I)
                    for inp in inputs:
                        print(f"   {inp}")
                    
                    # Find hidden inputs
                    print("\n3. Hidden input fields:")
                    hidden_inputs = re.findall(r'<input[^>]*type=["\']hidden["\'][^>]*>', form_content, re.I)
                    for hidden in hidden_inputs:
                        print(f"   {hidden}")
                        # Extract name and value
                        name_match = re.search(r'name=["\']([^"\']+)["\']', hidden, re.I)
                        value_match = re.search(r'value=["\']([^"\']*)["\']', hidden, re.I)
                        if name_match:
                            name = name_match.group(1)
                            value = value_match.group(1) if value_match else ""
                            print(f"      -> {name} = {value}")
                    
                    # Look for CSRF token patterns
                    print("\n4. Looking for CSRF tokens:")
                    csrf_patterns = [
                        r'csrf[^"\']*["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                        r'token[^"\']*["\']?\s*[:=]\s*["\']([a-f0-9]{16,64})["\']',
                        r'nonce[^"\']*["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                        r'[_-]token["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                    ]
                    
                    for pattern in csrf_patterns:
                        matches = re.findall(pattern, html, re.I)
                        if matches:
                            print(f"   Found potential CSRF tokens: {matches[:3]}")
                    
                    # Look for JavaScript form handling
                    print("\n5. Looking for JavaScript form handling:")
                    js_patterns = [
                        r'onsubmit=["\']([^"\']+)["\']',
                        r'onclick=["\']([^"\']*submit[^"\']*)["\']',
                        r'addEventListener\(["\']submit["\']',
                        r'\.submit\s*\(\s*\)',
                        r'preventDefault\(\s*\)',
                    ]
                    
                    for pattern in js_patterns:
                        matches = re.findall(pattern, html, re.I)
                        if matches:
                            print(f"   Found JS pattern: {matches[0][:100]}")
                    
                    # Look for AJAX/Fetch
                    print("\n6. Looking for AJAX/Fetch calls:")
                    ajax_patterns = [
                        r'fetch\(["\'][^"\']*login[^"\']*["\']',
                        r'\.ajax\s*\(\s*{[^}]*url\s*:\s*["\'][^"\']*login[^"\']*["\']',
                        r'XMLHttpRequest\(\s*\)',
                        r'axios\.[post|get]\s*\(\s*["\'][^"\']*login[^"\']*["\']',
                    ]
                    
                    for pattern in ajax_patterns:
                        matches = re.findall(pattern, html, re.I)
                        if matches:
                            print(f"   Found AJAX pattern: {matches[0][:100]}")
                    
                    return True
                else:
                    print("   ❌ No form found!")
                    return False
            else:
                print(f"❌ Failed to get login page: {response.status}")
                return False

if __name__ == "__main__":
    asyncio.run(analyze_login_form())
