"""
Fresh-R Authentication Method Detector
Tests ALL possible authentication methods systematically
"""
import json
import logging
import aiohttp

_LOGGER = logging.getLogger(__name__)


async def detect_auth_method(s: aiohttp.ClientSession, sess_token: str, api_request: dict) -> tuple:
    """
    Test ALL authentication methods to find which one Fresh-R API accepts.
    
    Returns:
        (success: bool, method_name: str, response_data: dict)
    """
    
    api_url = "https://dashboard.bw-log.com/api.php"
    
    # Get PHPSESSID from cookie jar
    phpsessid = None
    for cookie in s.cookie_jar:
        if cookie.key == "PHPSESSID":
            phpsessid = cookie.value
            break
    
    _LOGGER.error("\n" + "="*80)
    _LOGGER.error("🔍 FRESH-R AUTHENTICATION METHOD DETECTION")
    _LOGGER.error("="*80)
    _LOGGER.error(f"sess_token: {sess_token[:30]}...")
    _LOGGER.error(f"PHPSESSID: {phpsessid}")
    _LOGGER.error(f"API URL: {api_url}")
    _LOGGER.error("="*80 + "\n")
    
    # Test methods in order of likelihood
    methods = [
        # Method 1: Cookie with BOTH PHPSESSID and sess_token
        {
            "name": "Cookie: PHPSESSID + sess_token",
            "url": api_url,
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json, */*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Cookie": f"PHPSESSID={phpsessid}; sess_token={sess_token}"
            },
            "body": api_request
        },
        
        # Method 2: Cookie with sess_token only
        {
            "name": "Cookie: sess_token only",
            "url": api_url,
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json, */*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Cookie": f"sess_token={sess_token}"
            },
            "body": api_request
        },
        
        # Method 3: Cookie with PHPSESSID only (no sess_token)
        {
            "name": "Cookie: PHPSESSID only",
            "url": api_url,
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json, */*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Cookie": f"PHPSESSID={phpsessid}"
            },
            "body": api_request
        },
        
        # Method 4: Authorization Bearer
        {
            "name": "Authorization: Bearer",
            "url": api_url,
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json, */*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Authorization": f"Bearer {sess_token}"
            },
            "body": api_request
        },
        
        # Method 5: X-Auth-Token header
        {
            "name": "X-Auth-Token header",
            "url": api_url,
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json, */*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "X-Auth-Token": sess_token
            },
            "body": api_request
        },
        
        # Method 6: X-Session-Token header
        {
            "name": "X-Session-Token header",
            "url": api_url,
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json, */*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "X-Session-Token": sess_token
            },
            "body": api_request
        },
        
        # Method 7: POST body with "token" field
        {
            "name": "POST body: token field",
            "url": api_url,
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json, */*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            "body": {"token": sess_token, **api_request}
        },
        
        # Method 8: POST body with "auth_token" field
        {
            "name": "POST body: auth_token field",
            "url": api_url,
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json, */*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            "body": {"auth_token": sess_token, **api_request}
        },
        
        # Method 9: POST body with "sess_token" field
        {
            "name": "POST body: sess_token field",
            "url": api_url,
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json, */*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            "body": {"sess_token": sess_token, **api_request}
        },
        
        # Method 10: Query parameter ?token=
        {
            "name": "Query param: ?token=",
            "url": f"{api_url}?token={sess_token}",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json, */*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            "body": api_request
        },
        
        # Method 11: Query parameter ?sess_token=
        {
            "name": "Query param: ?sess_token=",
            "url": f"{api_url}?sess_token={sess_token}",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json, */*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            "body": api_request
        },
    ]
    
    # Test each method
    for i, method in enumerate(methods, 1):
        _LOGGER.error(f"\n{'='*60}")
        _LOGGER.error(f"TEST {i}/{len(methods)}: {method['name']}")
        _LOGGER.error(f"{'='*60}")
        _LOGGER.error(f"URL: {method['url']}")
        _LOGGER.error(f"Headers: {json.dumps(method['headers'], indent=2)}")
        _LOGGER.error(f"Body: {json.dumps(method['body'], indent=2)}")
        
        try:
            async with s.post(
                method['url'],
                headers=method['headers'],
                data={"q": json.dumps(method['body'])},
                timeout=30
            ) as r:
                response_text = await r.text()
                _LOGGER.error(f"Status: {r.status}")
                _LOGGER.error(f"Response: {response_text}")
                
                # Parse response
                try:
                    data = json.loads(response_text)
                    
                    # Check for success
                    if data.get("success") == True:
                        _LOGGER.error(f"\n{'🎉'*30}")
                        _LOGGER.error(f"✅ SUCCESS WITH METHOD: {method['name']}")
                        _LOGGER.error(f"{'🎉'*30}\n")
                        return True, method['name'], data
                    
                    # Check for nested success (user_info, user_units)
                    if "user_info" in data or "user_units" in data:
                        user_info_success = data.get("user_info", {}).get("success", False)
                        user_units_success = data.get("user_units", {}).get("success", False)
                        
                        if user_info_success or user_units_success:
                            _LOGGER.error(f"\n{'🎉'*30}")
                            _LOGGER.error(f"✅ SUCCESS WITH METHOD: {method['name']}")
                            _LOGGER.error(f"{'🎉'*30}\n")
                            return True, method['name'], data
                    
                    # Failed
                    reason = data.get("reason", "Unknown")
                    _LOGGER.error(f"❌ FAILED: {reason}")
                    
                except json.JSONDecodeError:
                    _LOGGER.error(f"❌ FAILED: Invalid JSON response")
                    
        except Exception as e:
            _LOGGER.error(f"❌ EXCEPTION: {type(e).__name__}: {e}")
    
    # All methods failed
    _LOGGER.error(f"\n{'='*80}")
    _LOGGER.error("❌ ALL AUTHENTICATION METHODS FAILED")
    _LOGGER.error("="*80 + "\n")
    
    return False, None, None
