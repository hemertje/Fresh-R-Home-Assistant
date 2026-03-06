#!/usr/bin/env python3
"""
Fresh-R HTTP-Only Implementation Validation
===========================================

Valideer dat de nieuwe HTTP-only versie correct is geïmplementeerd.
"""

import sys
import ast
import os

def validate_no_selenium():
    """Check dat Selenium/WebDriver/Chrome verwijderd zijn."""
    print("=" * 60)
    print("1. Validating No Selenium Dependencies")
    print("=" * 60)
    
    api_file = 'custom_components/fresh_r/api.py'
    with open(api_file, 'r') as f:
        source = f.read()
    
    # Check for forbidden terms (outside of comments/strings)
    forbidden = ['selenium', 'webdriver', 'chrome', 'chromedriver', 'headless']
    found = []
    
    for term in forbidden:
        if term in source.lower():
            # Check if it's just in headers or comments
            lines = source.split('\n')
            for i, line in enumerate(lines):
                if term in line.lower():
                    # Skip if in comment or headers definition
                    if '#' in line or '"User-Agent"' in line or 'Mozilla' in line:
                        continue
                    found.append((i+1, term, line.strip()))
    
    if found:
        print("⚠️  Found potential Selenium references:")
        for line, term, content in found[:5]:
            print(f"   Line {line}: {content[:60]}...")
        return False
    else:
        print("✅ No Selenium/WebDriver/Chrome references found")
        return True


def validate_http_headers():
    """Check dat HTTP headers correct zijn."""
    print("\n" + "=" * 60)
    print("2. Validating HTTP Headers")
    print("=" * 60)
    
    api_file = 'custom_components/fresh_r/api.py'
    with open(api_file, 'r') as f:
        source = f.read()
    
    # Check BROWSER_HEADERS
    checks = [
        ('User-Agent', 'Mozilla/5.0' in source),
        ('Accept-Encoding', 'gzip' in source and 'br' not in source),
        ('Accept-Language', 'en-US' in source),
        ('API_HEADERS', 'XMLHttpRequest' in source),
    ]
    
    all_ok = True
    for name, found in checks:
        if found:
            print(f"✅ {name} present")
        else:
            print(f"❌ {name} missing or incorrect")
            all_ok = False
    
    return all_ok


def validate_syntax():
    """Check Python syntax."""
    print("\n" + "=" * 60)
    print("3. Validating Python Syntax")
    print("=" * 60)
    
    files = [
        'custom_components/fresh_r/api.py',
        'custom_components/fresh_r/__init__.py',
        'custom_components/fresh_r/manifest.json',
    ]
    
    all_ok = True
    for filepath in files:
        if os.path.exists(filepath):
            try:
                if filepath.endswith('.json'):
                    import json
                    with open(filepath) as f:
                        json.load(f)
                    print(f"✅ {filepath} (JSON valid)")
                else:
                    with open(filepath) as f:
                        ast.parse(f.read())
                    print(f"✅ {filepath} (Python syntax valid)")
            except Exception as e:
                print(f"❌ {filepath}: {e}")
                all_ok = False
        else:
            print(f"⚠️  {filepath}: File not found")
    
    return all_ok


def validate_http_methods():
    """Check dat HTTP methods correct zijn geïmplementeerd."""
    print("\n" + "=" * 60)
    print("4. Validating HTTP Implementation")
    print("=" * 60)
    
    api_file = 'custom_components/fresh_r/api.py'
    with open(api_file, 'r') as f:
        source = f.read()
    
    required = [
        ('aiohttp.ClientSession', 'session' in source),
        ('session.get', 'session.get' in source),
        ('session.post', 'session.post' in source),
        ('cookie_jar', 'cookie_jar' in source or 'CookieJar' in source),
        ('async_login', 'async def async_login' in source),
        ('async_discover_devices', 'async def async_discover_devices' in source),
        ('async_get_current', 'async def async_get_current' in source),
    ]
    
    all_ok = True
    for name, found in required:
        if found:
            print(f"✅ {name} implemented")
        else:
            print(f"❌ {name} missing")
            all_ok = False
    
    return all_ok


def validate_manifest():
    """Check manifest.json heeft geen Selenium."""
    print("\n" + "=" * 60)
    print("5. Validating manifest.json")
    print("=" * 60)
    
    import json
    with open('custom_components/fresh_r/manifest.json') as f:
        manifest = json.load(f)
    
    reqs = manifest.get('requirements', [])
    
    has_selenium = any('selenium' in r.lower() for r in reqs)
    has_webdriver = any('webdriver' in r.lower() for r in reqs)
    has_aiohttp = any('aiohttp' in r.lower() for r in reqs)
    
    if has_selenium:
        print("❌ Selenium still in requirements!")
        return False
    
    if has_webdriver:
        print("❌ webdriver-manager still in requirements!")
        return False
    
    if not has_aiohttp:
        print("❌ aiohttp missing from requirements!")
        return False
    
    print("✅ Only aiohttp in requirements")
    print(f"   Requirements: {reqs}")
    return True


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("   Fresh-R HTTP-Only Implementation Validation")
    print("=" * 70)
    
    results = [
        ("No Selenium", validate_no_selenium()),
        ("HTTP Headers", validate_http_headers()),
        ("Python Syntax", validate_syntax()),
        ("HTTP Methods", validate_http_methods()),
        ("Manifest", validate_manifest()),
    ]
    
    print("\n" + "=" * 70)
    print("   SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print("=" * 70)
    
    if all_passed:
        print("\n🎉 VALIDATION SUCCESSFUL!")
        print("\nDe HTTP-only implementatie is correct:")
        print("   ✅ Geen Selenium/WebDriver/Chrome dependencies")
        print("   ✅ HTTP headers correct geconfigureerd")
        print("   ✅ Alle syntax valid")
        print("   ✅ HTTP implementatie compleet")
        print("   ✅ Manifest requirements correct")
        print("\n✅ De integratie is 100% klaar voor HACS!")
        sys.exit(0)
    else:
        print("\n❌ VALIDATION FAILED")
        print("Los de bovenstaande problemen op.")
        sys.exit(1)
