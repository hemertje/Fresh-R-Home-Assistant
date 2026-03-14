# Fresh-R API Authentication Analysis
## Datum: 14 maart 2026, 09:37

## 🔍 PROBLEEM
API geeft: `{"success":false,"reason":"Invalid request. Not authenticated."}`

## 📊 HUIDIGE SITUATIE (uit logs van 09:34)

### Login succesvol:
```
✅ Login API response: {"authenticated": true, "auth_token": "..."}
✅ sess_token cookie gezet op dashboard.bw-log.com
✅ Cookie in jar: sess_token = 16a68d0ccd1f0440f8db859a113c8aad9b4a28770d620402274272f3bc38277b
```

### API Request:
```
POST https://dashboard.bw-log.com/api.php
Headers:
  Content-Type: application/x-www-form-urlencoded
  Accept: application/json, */*
  User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
  Cookie: sess_token=16a68d0ccd1f0440f8db859a113c8aad9b4a28770d620402274272f3bc38277b

Body:
  q={"tzoffset":"60","requests":{"user_info":{...},"user_units":{...}}}
```

### API Response:
```
Status: 200
Body: {"success":false,"reason":"Invalid request. Not authenticated."}
```

## ❓ VRAGEN

1. **Wordt de Cookie header ECHT meegestuurd?**
   - Code zet: `"Cookie": f"sess_token={sess_token}"`
   - Maar zien we dit in de ACTUAL HTTP request?
   - **ACTIE:** Log request headers toegevoegd (regel 908)

2. **Is sess_token het ENIGE dat nodig is?**
   - Browser stuurt mogelijk: `Cookie: sess_token=...; PHPSESSID=...; andere=...`
   - Wij sturen: `Cookie: sess_token=...`
   - **MOGELIJK PROBLEEM:** PHPSESSID ontbreekt?

3. **Is de Cookie syntax correct?**
   - Wij: `Cookie: sess_token=abc123`
   - Moet het zijn: `Cookie: sess_token=abc123; Path=/; Domain=dashboard.bw-log.com`?

4. **Verwacht de API een andere auth methode?**
   - Authorization header?
   - Token in POST body (hebben we al geprobeerd - werkte niet)?
   - Andere header?

## 🎯 VOLGENDE STAPPEN

### STAP 1: Verify Cookie header wordt meegestuurd
- Code update: Request Headers logging toegevoegd
- Deploy: GEDAAN
- Test: WACHTEN OP USER
- Verwacht in logs: `Request Headers: {"Cookie": "sess_token=..."}`

### STAP 2: Als Cookie header ER IS maar API zegt "Not authenticated"
Mogelijke oorzaken:
- PHPSESSID cookie ontbreekt
- Cookie format verkeerd
- API verwacht andere auth methode
- Token is verlopen tussen login en API call
- Domain/Path mismatch

### STAP 3: Als Cookie header NIET in logs staat
- Code bug: header wordt niet gezet
- aiohttp overschrijft onze header
- Andere technische issue

## 📋 BROWSER DEVTOOLS VERGELIJKING NODIG

**WAT WE MOETEN WETEN:**
Bij een succesvolle api.php call in de browser:

1. **Request Headers → Cookie:**
   - Welke cookies worden meegestuurd?
   - Alleen sess_token of ook PHPSESSID?
   - Exacte format?

2. **Request Payload:**
   - Exact dezelfde JSON als wij sturen?
   - Andere velden?

3. **Response:**
   - Wat is de succesvolle response?
   - Welke velden bevat het?

**ZONDER DEZE DATA BLIJVEN WE GISSEN.**
