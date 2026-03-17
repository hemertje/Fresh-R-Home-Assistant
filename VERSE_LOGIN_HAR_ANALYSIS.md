# VERSE LOGIN HAR ANALYSE - 17 maart 2026 22:28

## ✅ STATUS: COMPLETE LOGIN FLOW GEVONDEN!

**HAR bevat:**
- ✅ GET dashboard.bw-log.com (eerste request)
- ✅ Referer: https://www.fresh-r.me/ (komt van login page)
- ✅ API calls met werkende token
- ❌ GEEN auth.php POST request (maar wel werkende sessie)

## 🔍 KRITIEKE BEVINDING: TOKEN IN API CALLS

### Werkende Token
```
7788389042f84869ff3fee606bf5bd7894691240aed7dfe6ead14e075e591713
```

### API Call Formaten

**Format 1: Query String met Empty POST Body**
```
POST /api.php?q={"tzoffset":"60","token":"7788389042f84869ff3fee606bf5bd7894691240aed7dfe6ead14e075e591713","requests":{...}}
Content-Length: 0
```

**Format 2: POST Body Form-Encoded**
```
POST /api.php
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
Content-Length: 500

q=%7B%22tzoffset%22%3A%2260%22%2C%22token%22%3A%227788389042f84869ff3fee606bf5bd7894691240aed7dfe6ead14e075e591713%22%2C%22requests%22%3A%7B...%7D%7D
```

**Decoded POST body:**
```json
{
  "tzoffset": "60",
  "token": "7788389042f84869ff3fee606bf5bd7894691240aed7dfe6ead14e075e591713",
  "requests": {
    "e:232212/180027_current": {
      "request": "fresh-r-now",
      "serial": "e:232212/180027",
      "fields": ["t1", "t2", "t3", "t4", "flow", "co2", "hum", "dp", ...]
    }
  }
}
```

## 🎯 BELANGRIJKSTE BEVINDING

**GEEN COOKIES IN REQUESTS!**

```json
"cookies": []
```

**Alle API calls:**
- Entry 1 (GET dashboard): `"cookies": []`
- Entry 2+ (API calls): `"cookies": []`

**Dit betekent:**
1. ❌ Browser gebruikt GEEN `sess_token` cookie
2. ✅ Browser gebruikt ALLEEN token in JSON payload
3. ✅ Token zit in `q` parameter (query string OF POST body)
4. ✅ Beide formaten werken (query string EN POST body)

## 🔥 CONCLUSIE: ONZE CODE IS CORRECT!

**Onze huidige implementatie:**
```python
# We sturen token in POST body form-encoded
form_data = {
    "q": json.dumps(api_request, separators=(',', ':'))
}
```

**Dit is EXACT wat browser doet in laatste API call!**

## ❓ WAAROM WERKT HET DAN NIET?

**Mogelijke oorzaken:**

### 1. Token Expiry
- Token in HAR: `7788389042f84869ff3fee606bf5bd7894691240aed7dfe6ead14e075e591713`
- Onze token: Mogelijk verschillend of verlopen
- **Test:** Gebruik EXACT deze token uit HAR

### 2. Token Origin
- HAR toont GEEN login flow
- HAR start bij dashboard (na login)
- **Vraag:** Waar komt deze token vandaan?
- **Hypothese:** Token komt uit auth.php response JSON

### 3. Session Persistence
- Browser heeft mogelijk sessie van eerdere login
- Token is persistent over meerdere sessies
- **Test:** Check of oude token nog werkt

### 4. Rate Limit
- Onze pogingen triggeren rate limit
- Browser sessie is al authenticated
- **Oplossing:** Wacht tot rate limit reset

## 📊 API CALL DETAILS

**Succesvolle API call (laatste in HAR):**

**Request:**
```
POST /api.php
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
Content-Length: 500
Cookie: (EMPTY)
Origin: https://dashboard.bw-log.com
Referer: https://dashboard.bw-log.com/?page=devices
X-Requested-With: XMLHttpRequest

q=%7B%22tzoffset%22%3A%2260%22%2C%22token%22%3A%227788389042f84869ff3fee606bf5bd7894691240aed7dfe6ead14e075e591713%22%2C%22requests%22%3A%7B...%7D%7D
```

**Response:**
```
HTTP/2 200
Content-Type: text/html; charset=UTF-8
Content-Encoding: br
Access-Control-Allow-Origin: *

{...} (231 bytes)
```

## 🚀 VOLGENDE STAPPEN

1. **Test met HAR token**
   - Gebruik token `7788389042f84869ff3fee606bf5bd7894691240aed7dfe6ead14e075e591713`
   - Test of deze nog werkt
   - Als ja: token is persistent
   - Als nee: token is expired

2. **Wacht op rate limit reset**
   - Morgen 18 maart ~16:50
   - Verse login met HAR capture
   - Focus op auth.php response

3. **Analyseer auth.php response**
   - Zoek naar token in JSON
   - Check Set-Cookie headers
   - Identificeer token origin

## 💡 HYPOTHESE: TOKEN PERSISTENCE

**Browser gedrag:**
- Geen cookies in requests
- Token in JSON payload
- Token werkt over meerdere sessies

**Mogelijke verklaring:**
- Token wordt opgeslagen in localStorage/sessionStorage
- JavaScript haalt token uit storage
- Token heeft lange expiry (dagen/weken)

**Test:**
- Open browser DevTools → Application → Local Storage
- Check voor Fresh-R/dashboard.bw-log.com entries
- Zoek naar token value

## ✅ BEVESTIGING: ONZE CODE IS CORRECT

**Onze implementatie matcht browser EXACT:**
- ✅ POST to /api.php
- ✅ Content-Type: application/x-www-form-urlencoded
- ✅ Token in POST body as form-encoded `q` parameter
- ✅ JSON structure correct
- ✅ Headers correct

**Probleem is NIET in API call format.**
**Probleem is in token acquisition/persistence.**
