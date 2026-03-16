# Fresh-R Cookie Persistence Analyse

## OBSERVATIE (14 maart 2026, 15:04)

**User rapporteert:**
- Type `www.fresh-r.me` in browser → Direct redirect naar `https://dashboard.bw-log.com/?page=devices`
- Logout → Kan niet meer inloggen (rate limit?)
- Suggestie: Persistent cookie?

## TE ONDERZOEKEN

### 1. Browser DevTools Cookie Analyse

**Stappen:**
```
1. Open Chrome → F12 → Application tab → Cookies
2. Check cookies voor fresh-r.me domain:
   - PHPSESSID
   - sess_token
   - Andere cookies?

3. Check cookies voor dashboard.bw-log.com domain:
   - PHPSESSID
   - sess_token
   - Andere cookies?

4. Noteer voor ELKE cookie:
   - Name
   - Value (eerste 20 chars)
   - Domain
   - Path
   - Expires / Max-Age
   - HttpOnly
   - Secure
   - SameSite
```

### 2. Logout Gedrag

**Test:**
```
1. Voor logout:
   - Screenshot alle cookies (Application tab)
   
2. Klik Logout

3. Na logout:
   - Screenshot alle cookies opnieuw
   - Welke cookies zijn verwijderd?
   - Welke cookies blijven bestaan?
```

### 3. Auto-Redirect Mechanisme

**Hypotheses:**

#### A. Server-side redirect op basis van cookie
```
Browser → GET https://fresh-r.me
Server checkt: PHPSESSID cookie aanwezig?
  JA → HTTP 302 redirect naar dashboard
  NEE → Toon login pagina
```

#### B. Client-side JavaScript redirect
```
Browser → GET https://fresh-r.me
Server → HTML met JavaScript
JavaScript checkt: Cookie aanwezig?
  JA → window.location = dashboard
  NEE → Toon login form
```

**Test welke:**
- Kijk in Network tab naar eerste request naar fresh-r.me
- Status code 302/301? → Server-side
- Status code 200 met HTML? → Client-side

### 4. Rate Limit vs Cookie Issue

**Vraag:** Is "kan niet inloggen" door:
- A. Rate limit (Too many login attempts)
- B. Cookie nog aanwezig (auto-redirect, geen login form)
- C. Beide?

**Test:**
```
1. Clear ALL cookies voor fresh-r.me en dashboard.bw-log.com
2. Ga naar fresh-r.me
3. Zie je login form? → Cookie was het probleem
4. Zie je "Too many attempts"? → Rate limit actief
```

## IMPLICATIES VOOR INTEGRATIE

### Scenario 1: Persistent Cookie Werkt
**Als cookie lang geldig blijft:**
- ✅ Minder login requests nodig
- ✅ Token blijft langer geldig
- ✅ Minder kans op rate limit
- ⚠️ Moet cookie expiry detecteren
- ⚠️ Moet cookie refresh implementeren

### Scenario 2: Cookie Expiry is Kort
**Als cookie snel verloopt:**
- ⚠️ Frequente re-authentication nodig
- ⚠️ Meer kans op rate limit
- ✅ Security: korte sessie
- ✅ Minder state management

### Scenario 3: Logout Cleared Cookie Niet Volledig
**Als logout sommige cookies laat staan:**
- 🐛 Bug in Fresh-R logout
- ⚠️ Kan leiden tot inconsistente state
- ⚠️ Mogelijk security issue

## AANBEVOLEN TESTS

### Test 1: Cookie Levensduur
```
1. Login via browser
2. Noteer cookie expiry tijd
3. Wacht X uur
4. Refresh dashboard
5. Nog steeds ingelogd? → Cookie levensduur = X+ uur
```

### Test 2: Cookie Scope
```
1. Check welke domains cookies hebben:
   - fresh-r.me
   - dashboard.bw-log.com
   - Beide?
   
2. Check cookie Path:
   - / (hele domain)
   - /login/ (alleen login)
   - /api/ (alleen API)
```

### Test 3: Manual Cookie Clear
```
1. Login via browser
2. F12 → Application → Cookies
3. Delete ALLE cookies voor fresh-r.me
4. Delete ALLE cookies voor dashboard.bw-log.com
5. Refresh pagina
6. Wordt je uitgelogd? → Cookie is auth mechanisme
```

## VOOR HOME ASSISTANT INTEGRATIE

### Huidige Implementatie Check

**Vraag:** Slaan we cookies op tussen HA restarts?

**Antwoord:** NEE - aiohttp.ClientSession is in-memory

**Implicatie:**
- Elke HA restart = nieuwe login
- Elke integration reload = nieuwe login
- Kan rate limit triggeren bij frequente restarts

### Mogelijke Verbetering: Cookie Persistence

**Optie A: Save cookies to file**
```python
# Bij shutdown
cookies = {c.key: c.value for c in session.cookie_jar}
with open('cookies.json', 'w') as f:
    json.dump(cookies, f)

# Bij startup
with open('cookies.json', 'r') as f:
    cookies = json.load(f)
    session.cookie_jar.update_cookies(cookies)
```

**Optie B: Use HA storage**
```python
from homeassistant.helpers.storage import Store

store = Store(hass, 1, "fresh_r_cookies")
await store.async_save(cookies)
cookies = await store.async_load()
```

**Security Overwegingen:**
- ⚠️ Cookies bevatten auth token
- ⚠️ Moet encrypted storage gebruiken
- ⚠️ Moet expiry checken
- ✅ Vermindert login frequency
- ✅ Vermindert rate limit risk

## VOLGENDE STAPPEN

1. **User doet browser cookie analyse:**
   - Screenshot cookies voor/na logout
   - Noteer expiry times
   - Test manual cookie clear

2. **Bepaal cookie strategie:**
   - Korte sessie → Accepteer frequente re-auth
   - Lange sessie → Implementeer cookie persistence

3. **Update integratie indien nodig:**
   - Add cookie storage
   - Add expiry detection
   - Add refresh logic

## VRAGEN VOOR USER

1. **Zie je login form na cookie clear?**
   - JA → Cookie was het probleem
   - NEE → Rate limit nog actief

2. **Wat is cookie expiry tijd?**
   - Check in DevTools → Application → Cookies → Expires

3. **Blijft cookie na browser restart?**
   - Close browser volledig
   - Open opnieuw
   - Ga naar fresh-r.me
   - Nog steeds auto-redirect?

4. **Wat gebeurt bij logout?**
   - Welke cookies worden verwijderd?
   - Welke blijven bestaan?
