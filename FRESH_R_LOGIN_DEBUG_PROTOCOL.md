# Fresh-R Login Debug Protocol
## Systematische aanpak voor authenticatie problemen

## 🎯 DOEL
Methodisch identificeren en oplossen van Fresh-R login/authenticatie issues zonder blind te staren.

## ⚠️ KRITIEK LEERMOMENT (Maart 2026)
**ALTIJD EERST: Complete browser request capture**

Weken verspild omdat we query string parameters niet analyseerden!

**CORRECTE METHODE:**
```
Browser DevTools → Network tab → api.php request
→ Kopieer VOLLEDIGE URL (inclusief ?q=...)
→ Of: Export as HAR
```

**Token zit in QUERY STRING, niet POST body:**
```
POST /api.php?q={"tzoffset":"60","token":"bf7975f224...","requests":{...}}
Content-Length: 0
Cookie: sess_token=bf7975f224...
```

---

## 📋 STAP 1: DATA VERZAMELEN

### A. Browser request capture (VERPLICHT EERST!)
```
1. Open Chrome/Edge → F12 → Network tab
2. Vink aan: Preserve log
3. Login op https://fresh-r.me
4. Zoek api.php request
5. Rechtermuisknop → Copy → Copy as HAR
   OF: Screenshot van COMPLETE request (URL + Headers + Payload)
```

**Analyseer ALLES:**
- [ ] **Volledige URL** (inclusief query parameters!) ← KRITIEK
- [ ] Request method (GET/POST)
- [ ] Request headers (ALL)
- [ ] Request body
- [ ] Response headers
- [ ] Response body
- [ ] Cookies

### B. Home Assistant logs ophalen
```
Settings → System → Logs → Search: "fresh_r"
```

**Verzamel:**
- [ ] Alle ERROR messages
- [ ] Alle WARNING messages  
- [ ] Alle 🔍 DEEP DEBUG output
- [ ] Timestamps van pogingen
- [ ] Rate limit messages

### C. Identificeer de login flow stappen
```
1. POST naar https://fresh-r.me/login/api/auth.php
2. JSON response met auth_token
3. Set sess_token cookie op dashboard.bw-log.com
4. POST naar https://dashboard.bw-log.com/api.php?q={...,"token":"..."}
5. JSON response met user_units
```

**Check voor ELKE stap:**
- [ ] HTTP status code
- [ ] **Request URL (inclusief query params)**
- [ ] Request headers
- [ ] Request body
- [ ] Response headers
- [ ] Response body
- [ ] Cookies in jar
- [ ] Cookies in request

---

## 📊 STAP 2: SYMPTOOM ANALYSE

### Symptoom Matrix

| API Response | Betekenis | Oorzaak | Fix |
|--------------|-----------|---------|-----|
| `"Invalid request. Invalid token."` | Token in POST body | API accepteert geen token in body | Verwijder token uit POST |
| `"Invalid request. Not authenticated."` | Cookie niet meegestuurd | Cookie jar stuurt niet automatisch | Voeg Cookie header toe |
| `"success": false` met nested objects | Oude API formaat | user_info/user_units structuur | Check nested success fields |
| `"success": false` top-level | Nieuwe API formaat | Direct top-level response | Check top-level success |
| HTTP 401/403 | Sessie verlopen | Token expired | Force re-login |
| HTTP 429 | Rate limited | Te veel requests | Wacht 1 uur |
| Redirect naar login | Sessie verlopen | Token invalid | Force re-login |

---

## 🔍 STAP 3: VERIFICATIE CHECKLIST

### Login Request (auth.php)
- [ ] URL: `https://fresh-r.me/login/api/auth.php`
- [ ] Method: POST
- [ ] Headers: `Content-Type: application/json`
- [ ] Body: `{"email": "...", "password": "..."}`
- [ ] Response: JSON met `auth_token` field
- [ ] Status: 200

### Cookie Setting
- [ ] Cookie name: `sess_token`
- [ ] Cookie value: auth_token uit response
- [ ] Cookie domain: `dashboard.bw-log.com`
- [ ] Cookie in jar: Verify met `s.cookie_jar`
- [ ] Cookie path: `/`

### API Request (api.php)
- [ ] URL: `https://dashboard.bw-log.com/api.php?q={"tzoffset":"60","token":"...","requests":{...}}` ✅ KRITIEK!
- [ ] Method: POST
- [ ] Headers: `Cookie: sess_token=...`
- [ ] Headers: `X-Requested-With: XMLHttpRequest`
- [ ] Headers: `Origin: https://dashboard.bw-log.com`
- [ ] Headers: `Referer: https://dashboard.bw-log.com/?page=devices`
- [ ] Body: LEEG (Content-Length: 0) ✅ KRITIEK!
- [ ] Token in QUERY STRING binnen JSON, niet in POST body ✅ KRITIEK!
- [ ] Response: JSON met user_units
- [ ] Status: 200

---

## 🔧 STAP 4: COMMON FIXES

### Fix 1: Token moet in query string JSON
```python
# ❌ FOUT - Token in POST body
api_request = {"tzoffset": "60", "requests": {...}}
async with s.post(api_url, data={"q": json.dumps(api_request)}):
    # Token ontbreekt!

# ✅ GOED - Token in query string JSON
api_request = {
    "tzoffset": "60",
    "token": sess_token,  # Token IN de JSON
    "requests": {...}
}
api_url_with_params = f"{api_url}?q={json.dumps(api_request)}"
async with s.post(api_url_with_params):  # Lege body
    # Token zit in URL query string
```

### Fix 2: Browser-like headers
```python
# ❌ FOUT - minimale headers
headers = {
    "Content-Type": "application/x-www-form-urlencoded"
}

# ✅ GOED - alle browser headers
cookie_parts = []
for cookie in s.cookie_jar:
    cookie_parts.append(f"{cookie.key}={cookie.value}")
cookie_header = "; ".join(cookie_parts)

headers = {
    "Accept": "*/*",
    "Cookie": cookie_header,  # Alle cookies
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://dashboard.bw-log.com",
    "Referer": "https://dashboard.bw-log.com/?page=devices",
}
```

### Fix 3: Cache problemen
```powershell
# Altijd bij code updates:
Remove-Item -Recurse -Force \\192.168.2.5\config\custom_components\fresh_r\__pycache__
cp api.py \\192.168.2.5\config\custom_components\fresh_r\
# Dan restart HA
```

### Fix 4: Rate limit
```
Wacht 1 uur na laatste error
Test op website: https://fresh-r.me
Als website werkt maar HA niet = code probleem, niet rate limit
```

---

## 🎯 STAP 5: SYSTEMATISCHE DEBUG FLOW

```
START
  ↓
Verzamel logs (Stap 1)
  ↓
Identificeer symptoom (Stap 2)
  ↓
Check symptoom matrix → Vind oorzaak
  ↓
Run verificatie checklist (Stap 3)
  ↓
Identificeer welke check faalt
  ↓
Apply relevante fix (Stap 4)
  ↓
Deploy met cache cleanup
  ↓
Restart HA
  ↓
Test opnieuw
  ↓
Logs checken → Nieuwe symptoom?
  ↓
Repeat tot SUCCESS
```

---

## ✅ SUCCESS CRITERIA

**Logs moeten tonen:**

```
🔍 DEEP DEBUG: API Request Details
Full API Request: {
  "tzoffset": "60",
  "requests": {...}
}
# GEEN "token" field!

🔍 DEEP DEBUG: Devices API Response
Status Code: 200
Response Body: {
  "user_info": {"success": true, ...},
  "user_units": {"success": true, "units": ["e:232212/180027"]}
}
# success: true!

Successfully found 1 valid device(s) via API
Fresh-r authenticated successfully
```

---

## 🚫 ANTI-PATTERNS (NIET DOEN!)

1. ❌ **Blind fixes toepassen** zonder logs te analyseren
2. ❌ **Meerdere fixes tegelijk** - kan niet zien wat werkt
3. ❌ **Cache niet cleanen** - oude code blijft draaien
4. ❌ **Rate limit negeren** - veroorzaakt meer problemen
5. ❌ **Gissen naar oplossing** - gebruik symptoom matrix
6. ❌ **Logs niet volledig lezen** - mis kritieke details
7. ❌ **Niet verifiëren na fix** - aanname dat het werkt

---

## 📝 DEBUG LOG TEMPLATE

Bij elke poging, documenteer:

```markdown
## Poging [N] - [Timestamp]

### Symptoom
- API Response: [...]
- HTTP Status: [...]
- Error message: [...]

### Analyse (Symptoom Matrix)
- Oorzaak: [...]
- Fix: [...]

### Verificatie Checklist
- [ ] Login request OK
- [ ] Cookie gezet OK
- [ ] Cookie in jar OK
- [ ] Cookie in API request OK
- [ ] POST body correct OK

### Applied Fix
[Code changes]

### Result
- Success: [Yes/No]
- Next symptoom: [...]
```

---

## 🎓 LESSONS LEARNED

1. **ALTIJD complete browser request analyseren**
   - Inclusief query string parameters!
   - Export HAR file of screenshot VOLLEDIGE URL
   - Weken verspild door incomplete analyse

2. **Fresh-R API: Token in query string JSON**
   - URL: `/api.php?q={"token":"...","requests":{...}}`
   - POST body is LEEG
   - Token ook in Cookie header
   
3. **Browser headers repliceren**
   - X-Requested-With, Origin, Referer
   - Alle cookies uit jar
   
4. **Python cache kan oude code behouden**
   - Altijd __pycache__ verwijderen bij updates
   
5. **Rate limiting is strict**
   - 1 uur backoff na te veel pogingen
   
6. **Logs zijn de waarheid**
   - Niet gissen, logs analyseren
   - Maar logs tonen niet alles - browser DevTools wel!

---

## 🔄 MAINTENANCE

**Bij elke code update:**
```powershell
# 1. Clean cache
Remove-Item -Recurse -Force \\192.168.2.5\config\custom_components\fresh_r\__pycache__

# 2. Deploy
cp api.py \\192.168.2.5\config\custom_components\fresh_r\

# 3. Restart HA
# Settings → System → Restart

# 4. Test
# Settings → Devices & Services → Add Integration → Fresh-R

# 5. Verify logs
# Settings → System → Logs → Search: "fresh_r"
```

**Bij rate limit:**
```
1. Check website: https://fresh-r.me
2. Als website werkt = code probleem
3. Als website niet werkt = wacht 1 uur
4. Test opnieuw
```
