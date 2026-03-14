# KRITIEKE BEVINDING - 14 maart 2026, 10:25

## ALLE 11 AUTH METHODEN GEFAALD

### MAAR: Eén methode gaf ANDERE error!

**Methode 7: POST body met "token" field**
```
Response: {
  "user_info": {"success": false, "reason": "Invalid request. Invalid token."},
  "user_units": {"success": false, "reason": "Invalid request. Invalid token."}
}
```

**Alle andere methoden:**
```
Response: {"success": false, "reason": "Invalid request. Not authenticated."}
```

## WAT DIT BETEKENT

1. **"Not authenticated"** = API ziet GEEN authenticatie
2. **"Invalid token"** = API ZIET authenticatie maar token is FOUT

## CONCLUSIE

De API **ACCEPTEERT** token in POST body (methode 7), maar:
- De token die we sturen is INVALID
- sess_token van login response is NIET de juiste token voor API

## MOGELIJKE OORZAKEN

### 1. Token transformatie nodig
Login geeft: `auth_token` in response
Wij zetten: `sess_token` cookie op dashboard.bw-log.com
API verwacht: Een ANDERE token?

### 2. Token moet eerst "activated" worden
Login geeft token → Browser doet iets → Token wordt actief → Dan API call

### 3. We gebruiken verkeerde token
Login response bevat:
- `auth_token` in JSON body
- Mogelijk andere tokens in headers/cookies?

## ACTIE: BROWSER DEVTOOLS ANALYSE

We moeten EXACT zien wat de browser doet:

1. Login op fresh-r.me
2. Redirect naar dashboard
3. **EERSTE api.php call** - wat is de EXACTE token?

### Te checken in browser:
- Request Headers → Cookie header → EXACTE waarde
- Request Payload → Is er een token in POST body?
- Welke token wordt gebruikt? (vergelijk met login response)

## HYPOTHESE

Browser gebruikt NIET de `auth_token` uit login response, maar:
- Een cookie die AUTOMATISCH wordt gezet door de server
- Een token uit een ANDERE response header
- Een token die wordt gegenereerd door JavaScript

We moeten de browser EXACT nabootsen.
