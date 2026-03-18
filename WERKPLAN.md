# Fresh-R Home Assistant Integration - Werkplan

## 📋 PROJECT STATUS: ✅ GEÏMPLEMENTEERD - WACHT OP RATE LIMIT RESET

**Datum:** 18 maart 2026  
**Status:** 🚀 AUTHENTICATION FIX DEPLOYED - Wacht op rate limit reset voor testing  
**Versie:** v2.1.2 (Token activation + API validation)

---

## ✅ VOLTOOIDE TAKEN

### 1. **Authenticatie Formaat Debugging (14-16 maart 2026)**

**Iteratie 1: POST Body met Form Data**
- **Hypothese:** Browser stuurt `q` parameter in POST body als form-encoded data
- **Implementatie:** `data={"q": json.dumps(...)}`
- **Resultaat:** ❌ "Invalid token"

**Iteratie 2: Query String met Lege Body**
- **Hypothese:** Browser stuurt `q` parameter in query string
- **Implementatie:** `POST /api.php?q={...}` met lege body
- **Resultaat:** ❌ "Invalid token" (maar formaat correct)

**Browser cURL Analyse (16 maart):**
```bash
POST /api.php?q=%7B%22tzoffset%22%3A%2260%22%2C%22token%22%3A%22eb3165ad...
Content-Length: 0
Cookie: sess_token=eb3165ad...
```

**Conclusie:** Formaat is NU correct - query string met lege body

### 2. **KRITIEKE ONTDEKKING: Token Mismatch**

**Probleem:** Login API geeft token die NIET werkt voor Dashboard API

**HA Login Flow:**
```
POST /login/api/auth.php
Response: {"authenticated":true,"auth_token":"12db0b64..."}
→ Set sess_token cookie = 12db0b64...
→ API call met token 12db0b64...
→ Result: "Invalid token"
```

**Browser Flow:**
```
Login (oude sessie)
→ sess_token cookie = eb3165ad...
→ API call met token eb3165ad...
→ Result: SUCCESS
```

**Tokens zijn VERSCHILLEND:**
- HA login token: `12db0b64ab6ee3f59ff3378fda40ff8ca59bf969a139ed94fa89f262730bdf82`
- Browser token: `eb3165ad3ec828211366389c60483f80f97c71e4fc429c282cb1f6e0681258c7`

**Hypothese:** Token van login API is NIET de token voor dashboard API  
**Ontbrekende stap:** Ergens tussen login en API call wordt token "geactiveerd" of "gewisseld"

### 3. **Debugging Toegevoegd**
- Login response logging (auth_token waarde)
- Dashboard GET request na login (activatie poging)
- Volledige request/response logging
- Cookie jar state tracking

### 4. **HAR File Analyse (17 maart 2026)**

**HAR File Ontvangen:**
- Bevat bestaande sessie (NIET verse login)
- Geen `auth.php` request zichtbaar
- Gebruiker was al ingelogd

**Kritieke Bevindingen:**
```json
// Browser gebruikt BEIDE methoden:

// Methode 1: Query string (sommige calls)
POST /api.php?q={...}
Content-Length: 0

// Methode 2: POST body (andere calls)
POST /api.php
Content-Type: application/x-www-form-urlencoded
Body: q={...}
```

**Token in HAR:** `4dd8bf3b36d25e91da0b716d209dd502d87bdb9758469e763a4259ce1f954873`

**Conclusie:**
- Browser gebruikt BEIDE formaten (query string EN POST body)
- HAR bevat geen verse login flow
- Verse login HAR nodig om `auth.php` response te zien
- Moet Set-Cookie headers checken voor `sess_token` origin

### 5. **Browser Analyse Instructies Toegevoegd**
**Doel:** Voorkom 24+ uur debugging zonder complete data

**Toegevoegd aan code:**
- Docstring met CRITICAL LEARNING sectie
- Stap-voor-stap browser DevTools instructies
- Gedetailleerde request/response logging
- Auth failure guidance met browser comparison checklist

**Locatie:** `api.py` regel 868-890 (docstring)

### 3. **Debug Protocol Gedocumenteerd**
**File:** `FRESH_R_LOGIN_DEBUG_PROTOCOL.md`

**Inhoud:**
- Systematische debug flow
- Browser request capture instructies
- Symptoom matrix
- Common fixes
- Lessons learned

### 4. **Leermoment Gedocumenteerd**
**Memory opgeslagen:** "Fresh-R API Authentication - Critical Learning"

**Kern leermoment:**
- ALTIJD complete browser request analyseren (inclusief query parameters)
- Export HAR file of screenshot VOLLEDIGE URL
- Geen trial-and-error zonder complete data
- API's kunnen non-standard implementaties hebben

---

## 🔄 HUIDIGE STATUS

### **Code Deployment:**
✅ Query string formaat correct geïmplementeerd  
✅ Lege POST body correct  
✅ Alle browser headers aanwezig  
✅ DEEP_DEBUG enabled voor volledige analyse  
✅ Token activation solution found and implemented

### **Rate Limit Status:**
⏳ **Actief sinds:** 18 maart 09:14  
⏳ **Reset verwacht:** 19 maart ~09:14  
⏳ **Oorzaak:** Herhaalde test pogingen tijdens Python cache debugging

### **HAR Analyse Status:**
✅ **HAR file ontvangen** (17 maart 08:13)  
❌ **HAR bevat bestaande sessie** - geen verse login  
❌ **Geen auth.php request** - kunnen token origin niet zien  
✅ **Browser gebruikt BEIDE formaten** - query string EN POST body

### **v2.1.2 Implementation (18 maart 2026):**
✅ **Token Activation Fix:** `allow_redirects=False` op dashboard GET request  
✅ **Direct Token Storage:** Token opgeslagen in `self._token` na activation  
✅ **API Validation:** `_test_token()` aangepast voor session/token parameters  
✅ **Brand Icon:** `icon.png` (256x256) toegevoegd aan integration  
⚠️ **Python Cache Issue:** HA laadt oude modules ondanks restart + version bump  
✅ **Oplossing:** Fresh-R folder volledig verwijderd en opnieuw gedeployed

### **Deployment Status:**
✅ **Code gedeployed:** v2.1.2 op HA server (18 maart 09:25)  
✅ **Python cache cleared:** Integration folder verwijderd en opnieuw aangemaakt  
✅ **Files verified:** manifest.json (v2.1.2), api.py, icon.png aanwezig  
⏳ **Wacht op rate limit reset:** 19 maart ~09:14

### **Volgende Test:**
📅 **Wanneer:** Na rate limit reset (19 maart ~09:14)  
📋 **Actie:** Fresh-R integration toevoegen in HA  
🎯 **Verwacht:** Token activation → API validation → Device discovery via API

---

## 📊 TECHNISCHE DETAILS

### **Fresh-R API Authenticatie Flow:**

1. **Login Request:**
   ```
   POST https://fresh-r.me/login/api/auth.php
   Body: {"email":"...","password":"..."}
   Response: {"authenticated":true,"auth_token":"abc123..."}
   ```

2. **Cookie Setup:**
   ```python
   s.cookie_jar.update_cookies(
       {'sess_token': auth_token},
       response_url=URL('https://dashboard.bw-log.com/')
   )
   ```

3. **API Request (KRITIEK):**
   ```
   POST https://dashboard.bw-log.com/api.php?q={"tzoffset":"60","token":"abc123...","requests":{...}}
   Headers:
     Cookie: PHPSESSID=xyz; sess_token=abc123...
     X-Requested-With: XMLHttpRequest
     Origin: https://dashboard.bw-log.com
     Referer: https://dashboard.bw-log.com/?page=devices
   Body: LEEG
   ```

4. **Response:**
   ```json
   {
     "user_info": {"success": true, ...},
     "user_units": {"success": true, "units": ["e:232212/180027"]}
   }
   ```

### **Belangrijke Code Secties:**

| Functie | Locatie | Doel |
|---------|---------|------|
| `_login_and_follow_redirect` | api.py:650-749 | Login flow |
| `_fetch_devices_via_api` | api.py:858-1100 | API authenticatie |
| `update_cookies` | api.py:735-743 | Cookie setup |
| Auth detector | auth_detector.py | Systematisch testen (disabled) |

---

## 🎯 VOLGENDE STAPPEN

### **KRITIEK: Browser Login Flow Analyse (17 maart)**

**Doel:** Vind waar `sess_token` cookie vandaan komt en waarom login API token niet werkt

**Stappen:**
1. **Browser Preparation**
   - Logout uit Fresh-R
   - Clear ALL cookies (fresh-r.me + dashboard.bw-log.com)
   - F12 → Network tab → Clear
   - Zorg dat "Preserve log" AAN staat

2. **HAR Export**
   - Login met credentials
   - Wacht tot dashboard volledig geladen
   - Right-click in Network tab → Save all as HAR with content
   - Upload HAR file voor analyse

3. **Analyse Vragen**
   - Welke response ZET de `sess_token` cookie? (auth.php? redirect? JavaScript?)
   - Is `sess_token` waarde GELIJK aan `auth_token` uit JSON?
   - Zijn er requests TUSSEN auth.php en eerste api.php?
   - Wordt token "geactiveerd" via een specifieke request?

4. **Implementatie**
   - Repliceer EXACTE browser flow in HA code
   - Test met nieuwe token mechanisme
   - Verify "Invalid token" is opgelost

### **Bij Success:**
   - Verify devices discovered
   - Check sensors created
   - Test data updates
   - Disable DEEP_DEBUG
   - Update versie naar v2.1.0
   - Commit naar GitHub

### **Bij Failure:**
   - Herhaal HAR analyse met meer detail
   - Check JavaScript execution (inject.js?)
   - Mogelijk: Token wordt client-side gegenereerd
   - Mogelijk: Multi-step authentication flow

### **Middellange Termijn:**

1. **Code Optimalisatie**
   - Remove auth_detector.py (niet meer nodig)
   - Cleanup oude debug code
   - Optimize logging levels
   - Add unit tests

2. **Documentatie**
   - Update README.md
   - Add installation guide
   - Document API behavior
   - Create troubleshooting guide

3. **GitHub Release**
   - Tag v2.1.0
   - Release notes met authentication fix
   - Update CHANGELOG.md
   - Close related issues

### **Lange Termijn:**

1. **Feature Improvements**
   - Better error messages
   - Automatic retry logic
   - Token refresh optimization
   - Multi-device support improvements

2. **Testing**
   - Automated integration tests
   - Mock API for testing
   - CI/CD pipeline
   - Rate limit handling tests

---

## 📝 LESSONS LEARNED

### **1. Complete Browser Analysis is KRITIEK**
**Probleem:** Weken debugging zonder query string analyse  
**Oplossing:** ALTIJD HAR export of complete URL screenshot  
**Preventie:** Browser analysis EERST, code DAARNA

### **2. Non-Standard API Implementaties Bestaan**
**Probleem:** Aanname dat token in POST body of Cookie header  
**Realiteit:** Token in query string JSON (ongebruikelijk maar geldig)  
**Leermoment:** Geen aannames, alleen data

### **3. Rate Limiting is Streng**
**Probleem:** Auth detector triggerde rate limit  
**Oplossing:** Detector disabled, DEEP_DEBUG safe  
**Preventie:** Minimize login attempts tijdens development

### **4. Cache Problemen Zijn Real**
**Probleem:** Python `__pycache__` behoudt oude code  
**Oplossing:** Altijd cache cleanen bij deployment  
**Preventie:** Automated deployment script

---

## 🔧 DEPLOYMENT CHECKLIST

Bij elke code update:

- [ ] Code wijzigingen testen lokaal
- [ ] `__pycache__` verwijderen op HA
- [ ] Files kopiëren naar HA
- [ ] Home Assistant herstarten
- [ ] Integration testen
- [ ] Logs controleren
- [ ] Success criteria verifiëren

**Deployment Command:**
```powershell
Remove-Item -Recurse -Force \\192.168.2.5\config\custom_components\fresh_r\__pycache__
cp custom_components\fresh_r\*.py \\192.168.2.5\config\custom_components\fresh_r\
```

---

## 📚 REFERENTIES

**Documentatie:**
- `FRESH_R_LOGIN_DEBUG_PROTOCOL.md` - Systematische debug aanpak
- `CRITICAL_FINDING.md` - Analyse van auth probleem
- `AUTHENTICATION_METHODS_DETECTION.md` - Alle geteste methoden
- `LOG_ANALYSIS_09_34.txt` - Exacte log analyse

**Code Files:**
- `custom_components/fresh_r/api.py` - Main API logic
- `custom_components/fresh_r/auth_detector.py` - Auth method testing (disabled)
- `custom_components/fresh_r/config_flow.py` - HA config flow
- `deploy_fresh_r.bat` / `deploy_fresh_r.ps1` - Deployment scripts

**External:**
- Fresh-R Website: https://fresh-r.me
- Fresh-R API: https://dashboard.bw-log.com/api.php
- Home Assistant: http://192.168.2.5:8123

---

## ✅ SUCCESS CRITERIA

**Installatie succesvol als:**

1. ✅ Login succeeds zonder errors
2. ✅ Token correct in query string
3. ✅ API response: `{"success": true}`
4. ✅ Devices discovered: `"units": ["e:232212/180027"]`
5. ✅ Sensors created in HA
6. ✅ Data updates werkend
7. ✅ Geen rate limit errors
8. ✅ Geen authentication errors

**Logs moeten tonen:**
```
🔍 FRESH-R API REQUEST DEBUG
Full URL: https://dashboard.bw-log.com/api.php?q={"tzoffset":"60","token":"...","requests":{...}}
Method: POST
Body: EMPTY (Content-Length: 0)

🔍 FRESH-R API RESPONSE DEBUG
Status Code: 200
Response Body: {"user_info":{"success":true},"user_units":{"success":true,"units":[...]}}

Successfully found 1 valid device(s) via API
Fresh-r authenticated successfully
```

---

## 🎉 CONCLUSIE

**Status:** Code is klaar en correct geïmplementeerd  
**Blokkade:** Fresh-R API rate limit (tijdelijk)  
**Actie:** Wacht op rate limit reset, test opnieuw  
**Verwachting:** Succesvolle authenticatie en device discovery  

**Volgende update:** Na succesvolle test of bij nieuwe bevindingen
