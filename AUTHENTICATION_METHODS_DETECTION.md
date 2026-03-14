# Fresh-R API Authentication Methods - Complete Detection Plan

## ALLE MOGELIJKE AUTHENTICATIE METHODEN

### 1. Cookie-based Authentication
- **Header:** `Cookie: name=value; name2=value2`
- **Varianten:**
  - Alleen sess_token
  - sess_token + PHPSESSID
  - Andere combinaties

### 2. Bearer Token
- **Header:** `Authorization: Bearer <token>`
- **Token:** sess_token of auth_token

### 3. Basic Auth
- **Header:** `Authorization: Basic <base64(username:password)>`

### 4. Custom Token Header
- **Header:** `X-Auth-Token: <token>`
- **Header:** `X-Session-Token: <token>`
- **Header:** `X-API-Key: <token>`

### 5. POST Body Token
- **Body:** `{"token": "...", "requests": {...}}`
- **Body:** `{"auth_token": "...", "requests": {...}}`
- **Body:** `{"sess_token": "...", "requests": {...}}`

### 6. Query Parameter
- **URL:** `api.php?token=...`
- **URL:** `api.php?sess_token=...`

### 7. Session-based (PHP Session)
- **Relies on:** PHPSESSID cookie only
- **No explicit token needed**

## DETECTION STRATEGY

### STAP 1: Log ALLE mogelijke auth headers/params
```python
# In _fetch_devices_via_api, VOOR de request:

_LOGGER.error("=" * 80)
_LOGGER.error("AUTHENTICATION METHOD DETECTION")
_LOGGER.error("=" * 80)

# Test 1: Cookie header (current)
cookie_header = "; ".join([f"{c.key}={c.value}" for c in s.cookie_jar])
_LOGGER.error(f"Cookie Header: {cookie_header}")

# Test 2: Authorization Bearer
auth_bearer = f"Bearer {sess_token}"
_LOGGER.error(f"Authorization Bearer: {auth_bearer}")

# Test 3: Custom headers
custom_headers = {
    "X-Auth-Token": sess_token,
    "X-Session-Token": sess_token,
    "X-API-Key": sess_token,
}
_LOGGER.error(f"Custom Headers: {json.dumps(custom_headers, indent=2)}")

# Test 4: POST body variants
body_variants = {
    "with_token": {"token": sess_token, **api_request},
    "with_auth_token": {"auth_token": sess_token, **api_request},
    "with_sess_token": {"sess_token": sess_token, **api_request},
}
_LOGGER.error(f"POST Body Variants: {json.dumps(body_variants, indent=2)}")

# Test 5: Query params
query_variants = [
    f"{api_url}?token={sess_token}",
    f"{api_url}?sess_token={sess_token}",
    f"{api_url}?auth_token={sess_token}",
]
_LOGGER.error(f"Query Param Variants: {json.dumps(query_variants, indent=2)}")
```

### STAP 2: Test ELKE methode systematisch
```python
async def _test_auth_method(self, s, method_name, url, headers, body):
    """Test een specifieke auth methode"""
    _LOGGER.error(f"\n{'='*60}")
    _LOGGER.error(f"TESTING: {method_name}")
    _LOGGER.error(f"{'='*60}")
    _LOGGER.error(f"URL: {url}")
    _LOGGER.error(f"Headers: {json.dumps(headers, indent=2)}")
    _LOGGER.error(f"Body: {json.dumps(body, indent=2)}")
    
    try:
        async with s.post(url, headers=headers, data={"q": json.dumps(body)}) as r:
            response = await r.text()
            _LOGGER.error(f"Status: {r.status}")
            _LOGGER.error(f"Response: {response}")
            
            # Check success
            try:
                data = json.loads(response)
                if data.get("success") == True or "user_units" in data:
                    _LOGGER.error(f"✅ SUCCESS WITH METHOD: {method_name}")
                    return True, data
                else:
                    _LOGGER.error(f"❌ FAILED: {data.get('reason', 'Unknown')}")
                    return False, data
            except:
                _LOGGER.error(f"❌ FAILED: Invalid JSON")
                return False, None
    except Exception as e:
        _LOGGER.error(f"❌ EXCEPTION: {e}")
        return False, None
```

### STAP 3: Test alle methoden in volgorde
```python
# Method 1: Cookie only (PHPSESSID + sess_token)
await _test_auth_method(
    s, 
    "Cookie: PHPSESSID + sess_token",
    api_url,
    {
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": f"PHPSESSID={phpsessid}; sess_token={sess_token}"
    },
    api_request
)

# Method 2: Cookie only (sess_token only)
await _test_auth_method(
    s,
    "Cookie: sess_token only",
    api_url,
    {
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": f"sess_token={sess_token}"
    },
    api_request
)

# Method 3: Authorization Bearer
await _test_auth_method(
    s,
    "Authorization: Bearer",
    api_url,
    {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Bearer {sess_token}"
    },
    api_request
)

# Method 4: X-Auth-Token
await _test_auth_method(
    s,
    "X-Auth-Token",
    api_url,
    {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Auth-Token": sess_token
    },
    api_request
)

# Method 5: POST body with token
await _test_auth_method(
    s,
    "POST body: token field",
    api_url,
    {"Content-Type": "application/x-www-form-urlencoded"},
    {"token": sess_token, **api_request}
)

# Method 6: Query parameter
await _test_auth_method(
    s,
    "Query param: ?token=",
    f"{api_url}?token={sess_token}",
    {"Content-Type": "application/x-www-form-urlencoded"},
    api_request
)

# Method 7: PHPSESSID only (no sess_token)
await _test_auth_method(
    s,
    "Cookie: PHPSESSID only",
    api_url,
    {
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": f"PHPSESSID={phpsessid}"
    },
    api_request
)
```

## IMPLEMENTATIE

Maak nieuwe functie in api.py:

```python
async def _detect_auth_method(self, s: aiohttp.ClientSession, sess_token: str) -> dict:
    """Detect which authentication method Fresh-R API accepts"""
    
    api_url = "https://dashboard.bw-log.com/api.php"
    
    # Get PHPSESSID from cookie jar
    phpsessid = None
    for cookie in s.cookie_jar:
        if cookie.key == "PHPSESSID":
            phpsessid = cookie.value
            break
    
    # Base API request
    api_request = {
        "tzoffset": "60",
        "requests": {
            "user_info": {
                "request": "userinfo",
                "fields": ["first_name"]
            }
        }
    }
    
    _LOGGER.error("\n" + "="*80)
    _LOGGER.error("FRESH-R AUTHENTICATION METHOD DETECTION")
    _LOGGER.error("="*80)
    _LOGGER.error(f"sess_token: {sess_token[:20]}...")
    _LOGGER.error(f"PHPSESSID: {phpsessid}")
    _LOGGER.error("="*80 + "\n")
    
    # Test all methods...
    # (code from STAP 3)
    
    _LOGGER.error("\n" + "="*80)
    _LOGGER.error("DETECTION COMPLETE")
    _LOGGER.error("="*80)
```

## GEBRUIK

In _fetch_devices_via_api:
```python
# Run detection ONCE
if DEEP_DEBUG:
    await self._detect_auth_method(s, sess_token)
```

Dit zal EXACT tonen welke methode werkt.
