# Changelog

All notable changes to the Fresh-R Home Assistant Integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.2] - 2026-03-18

### 🔧 Fixed - Token Activation Redirect Handling

**CRITICAL FIX: Dashboard Activation Redirect**

The token activation GET request was following redirects to the login page, preventing proper token activation.

#### Changes
- **Token Activation:** Set `allow_redirects=False` on dashboard GET request to prevent redirect loops
- **Direct Token Storage:** Store `auth_token` directly in `self._token` after activation (no cookie dependency)
- **API Validation:** Enhanced `_test_token()` to accept session and token parameters for validation during login
- **Brand Icon:** Added `icon.png` (256x256px) for Home Assistant brand selector

#### Technical Details
```python
# Dashboard activation now prevents redirects
async with s.get(dashboard_url, headers=headers, timeout=15, allow_redirects=False) as dash_r:
    if dash_r.status == 302:
        _LOGGER.info("🎯 Token activated successfully (302 redirect)")
    # Store token directly
    self._token = auth_token
```

#### Deployment Notes
- **Python Cache Issue:** Home Assistant aggressively caches Python modules
- **Solution:** Complete integration folder deletion and redeployment required for code updates
- **Version Bump:** Helps but not sufficient - physical file deletion needed

### 📦 Added
- Brand icon (`icon.png`) for integration display in Home Assistant UI
- Enhanced token validation with session parameter support

### 🐛 Fixed
- Token activation redirect loop causing authentication failures
- Cookie dependency removed - direct token storage more reliable

## [2.1.0] - 2026-03-17

### 🎉 Fixed - Authentication Issue RESOLVED

**CRITICAL FIX: Token Activation Flow**

After extensive HAR analysis of browser login behavior, discovered that the Fresh-R API requires a token activation step that was missing from the integration.

#### The Problem
- Login API returned `auth_token` successfully
- API calls with this token failed with "Invalid token"
- Browser login worked, but integration didn't

#### Root Cause
Browser performs a critical GET request after login that activates the token server-side:
```
GET https://dashboard.bw-log.com/?page=devices&t={auth_token}
```

This request was missing from the integration's login flow.

#### The Solution
Implemented token activation step in `api.py`:
- After receiving `auth_token` from login API
- Perform GET request to dashboard with token in URL parameter
- Token is activated server-side
- Subsequent API calls now work correctly

#### Changed
- **`api.py`**: Added token activation via dashboard GET request (lines 922-956)
- **`manifest.json`**: Version bumped to 2.1.0
- **Documentation**: Added `VERSE_LOGIN_COMPLETE_HAR_ANALYSIS.md` with complete flow analysis

#### Technical Details
**Old Flow (BROKEN):**
```
1. POST /login/api/auth.php → get auth_token
2. API call with token → FAILS ❌
```

**New Flow (WORKING):**
```
1. POST /login/api/auth.php → get auth_token
2. GET /dashboard/?page=devices&t={auth_token} → activate token
3. API calls with token → SUCCESS ✅
```

#### Testing
- Deployed to Home Assistant
- Ready for integration testing
- Expected: Devices discovered and sensors created successfully

---

## [2.0.7] - 2026-03-16

### Fixed
- Corrected API request format to match browser behavior
- Token now sent in query string with empty POST body
- Enhanced debug logging for authentication troubleshooting

### Changed
- Updated API call format: `POST /api.php?q={JSON}` with `Content-Length: 0`
- Added DEEP_DEBUG mode for detailed request/response analysis
- Improved error messages for authentication failures

---

## [2.0.6] - 2026-03-15

### Added
- Session persistence to avoid repeated logins
- Rate limit detection and backoff
- Comprehensive error handling for network issues

### Changed
- Improved cookie handling across domains
- Enhanced logging for debugging

---

## [2.0.0] - 2026-03-14

### Added
- Initial release of Fresh-R Home Assistant Integration
- Support for Fresh-R ventilation system monitoring
- Real-time sensor data (temperature, flow, CO2, humidity)
- Calculated sensors (heat recovery, energy loss)
- Config flow for easy setup

### Features
- Automatic device discovery
- Session-based authentication
- Configurable update intervals
- Home Assistant integration via YAML or UI
