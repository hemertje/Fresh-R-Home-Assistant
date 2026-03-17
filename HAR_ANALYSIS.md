# Fresh-R HAR File Analyse - 17 maart 2026

## 📋 ONTVANGEN HAR FILE

**Datum:** 17 maart 2026 08:13  
**Type:** Bestaande sessie (NIET verse login)  
**Probleem:** Geen `auth.php` request aanwezig

---

## 🔍 KRITIEKE BEVINDINGEN

### Browser gebruikt TWEE API formaten

**Methode 1: Query String (GET-achtig)**
```http
POST /api.php?q=%7B%22tzoffset%22%3A%2260%22%2C%22token%22%3A%224dd8bf3b...%22%2C%22requests%22%3A%7B...%7D%7D
Content-Length: 0
Cookie: sess_token=4dd8bf3b36d25e91da0b716d209dd502d87bdb9758469e763a4259ce1f954873
```

**Methode 2: POST Body (Form-encoded)**
```http
POST /api.php
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
Content-Length: 500
Cookie: sess_token=4dd8bf3b36d25e91da0b716d209dd502d87bdb9758469e763a4259ce1f954873

q=%7B%22tzoffset%22%3A%2260%22%2C%22token%22%3A%224dd8bf3b...%22%2C%22requests%22%3A%7B...%7D%7D
```

### Token in HAR

**Werkende browser token:**
```
4dd8bf3b36d25e91da0b716d209dd502d87bdb9758469e763a4259ce1f954873
```

**HA login token (niet werkend):**
```
13e99d59f336e4c175467fecc73d4eaf41931b6ea664b864a16f5b6e942904f3
```

**Conclusie:** Verschillende tokens = verschillende sessies

---

## ❌ ONTBREKENDE DATA

### Geen auth.php request

**Reden:** HAR begint op dashboard page met bestaande sessie

**Gemist:**
- Login POST naar `/login/api/auth.php`
- Response headers (Set-Cookie?)
- auth_token waarde uit JSON response
- Vergelijking auth_token vs sess_token

### Geen cookie origin

**Vraag:** Waar komt `sess_token` cookie vandaan?

**Mogelijkheden:**
1. Set-Cookie header in auth.php response
2. Set-Cookie header in redirect response
3. JavaScript sets cookie client-side
4. Token wordt "geactiveerd" via extra request

---

## 📊 HAR ENTRIES ANALYSE

### Entry 1: Dashboard redirect
```json
{
  "request": {
    "method": "GET",
    "url": "https://dashboard.bw-log.com/?page=devices&t=d7accbe607ef99193288b39f68a1c3feaab9446f849c343235566c7f2b2f7714"
  },
  "response": {
    "status": 302,
    "headers": [
      {"name": "location", "value": "/?page=devices"}
    ]
  }
}
```

**Geen Set-Cookie headers**

### Entry 2: Dashboard page load
```json
{
  "request": {
    "method": "GET",
    "url": "https://dashboard.bw-log.com/?page=devices"
  },
  "response": {
    "status": 200,
    "headers": [
      {"name": "content-type", "value": "text/html; charset=UTF-8"}
    ]
  }
}
```

**Geen Set-Cookie headers**

### Entry 3: API calls (meerdere)

**Query string variant:**
```json
{
  "request": {
    "method": "POST",
    "url": "https://dashboard.bw-log.com/api.php?q={...}",
    "headers": [
      {"name": "content-length", "value": "0"}
    ]
  }
}
```

**POST body variant:**
```json
{
  "request": {
    "method": "POST",
    "url": "https://dashboard.bw-log.com/api.php",
    "postData": {
      "mimeType": "application/x-www-form-urlencoded; charset=UTF-8",
      "text": "q=%7B%22tzoffset%22%3A%2260%22%2C%22token%22%3A%224dd8bf3b...%22%7D"
    }
  }
}
```

---

## 🎯 VOLGENDE STAPPEN

### Verse Login HAR Nodig

**Vereisten:**
1. **Incognito window** (geen bestaande cookies)
2. **Network tab → Preserve log ON**
3. **Ga naar:** https://fresh-r.me
4. **Login** met credentials
5. **Wacht** tot dashboard volledig geladen
6. **Export:** Save all as HAR with content

### Wat we moeten zien

**In verse login HAR:**
```
1. GET https://fresh-r.me/
   → Response: redirect naar login page

2. GET https://fresh-r.me/login/index.php?page=login
   → Response: login form HTML

3. POST https://fresh-r.me/login/api/auth.php
   → Request: {"email":"...","password":"..."}
   → Response: {"authenticated":true,"auth_token":"..."}
   → Response Headers: Set-Cookie: sess_token=...? ← KRITIEK

4. GET https://dashboard.bw-log.com/?page=devices&t=...
   → Request: Cookie: sess_token=...
   → Response: dashboard HTML

5. POST https://dashboard.bw-log.com/api.php?q={...}
   → Request: Cookie: sess_token=...
   → Response: {"user_info":{...},"user_units":{...}}
```

### Analyse Vragen

**Na verse login HAR:**
1. Heeft auth.php response een Set-Cookie header?
2. Is auth_token uit JSON GELIJK aan sess_token cookie?
3. Wordt sess_token gezet door auth.php of door redirect?
4. Zijn er extra requests tussen login en dashboard?
5. Wordt token client-side gemanipuleerd door JavaScript?

---

## 📝 CONCLUSIES

### Wat we weten

✅ Browser gebruikt BEIDE API formaten (query string EN POST body)  
✅ HA code ondersteunt query string formaat  
✅ Token formaat is correct (64 hex chars)  
✅ Cookies worden correct gezet in HA code  
❌ Token van login API werkt NIET voor dashboard API

### Wat we NIET weten

❌ Waar komt werkende `sess_token` vandaan?  
❌ Is auth_token = sess_token?  
❌ Wordt token via Set-Cookie header gezet?  
❌ Is er een extra stap tussen login en API call?

### Blokkade

**Rate limit actief tot:** 18 maart ~08:06  
**Nodig voor oplossing:** Verse login HAR file met auth.php request  
**Verwachte fix:** Repliceer exacte browser token flow in HA code

---

## 🔧 IMPLEMENTATIE PLAN

**Na HAR analyse:**

1. **Identificeer token source**
   - Als Set-Cookie: Parse response headers
   - Als JavaScript: Analyseer client-side code
   - Als extra request: Repliceer die request

2. **Update HA code**
   - Implementeer correcte token extraction
   - Test met verse login
   - Verify API calls succesvol

3. **Deploy en test**
   - Deploy naar HA
   - Clear caches
   - Test complete flow
   - Verify 100% werkend

**Verwachte tijdlijn:** 1 dag na verse login HAR ontvangst
