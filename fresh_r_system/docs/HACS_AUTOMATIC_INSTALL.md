# HACS Automatic Installation Guide

Dit document legt uit hoe de Fresh-R integratie automatische installatie ondersteunt en wat de beperkingen zijn.

## 🤖 Wat werkt WEL automatisch via HACS?

### 1. ✅ Python Packages (Auto-installed door HA)
```json
// manifest.json
"requirements": [
  "aiohttp>=3.8.0",
  "selenium>=4.0.0",        
  "webdriver-manager>=4.0.0"
]
```

**Deze worden automatisch geïnstalleerd wanneer je de integratie toevoegt!**

### 2. ✅ Integration Code
- Alle Python files in `custom_components/fresh_r/`
- Config flow voor UI setup
- Alle sensoren en coordinators

### 3. ✅ Dependency Check & Error Messages
De integratie checkt nu automatisch of alles werkt en geeft duidelijke instructies:
```
Fresh-R dependencies not available:
- Chrome not found

Please install Chrome/Chromium:
- HA OS: Install 'SSH & Web Terminal' add-on, then run:
  apk add --no-cache chromium chromium-chromedriver
- Debian/Ubuntu: sudo apt-get install chromium-browser
```

---

## ⚠️ Wat werkt NIET automatisch?

### ❌ Chrome/Chromium Browser
**Waarom niet?**
- Dit is een **systeem binary** (geen Python package)
- HACS/HA kunnen geen OS-level packages installeren
- Vereist admin/root rechten
- Verschilt per OS (apt, apk, choco, etc.)

**Vergelijking met andere integraties:**

| Integratie | Systeem Dependency | Oplossing |
|------------|-------------------|-----------|
| **Fresh-R** | Chrome | Handmatig installeren |
| **Spotify** | Geen | Volledig automatisch |
| **Google Cast** | Geen | Volledig automatisch |
| **Camera (FFmpeg)** | FFmpeg | Soms handmatig |
| **Scrape** | Geen | Volledig automatisch |

---

## 🎯 Hoe andere "volledig automatische" apps dit doen

### Strategie 1: Geen systeem dependencies
De meeste HACS integraties die "volledig automatisch" zijn, hebben **geen** systeem-level dependencies nodig. Ze gebruiken:
- Pure Python libraries
- Home Assistant's ingebouwde HTTP client
- Websockets
- MQTT

### Strategie 2: Bundelen van binaries (zeldzaam)
Sommige integraties bundelen pre-compiled binaries:
```
custom_components/integration/
├── __init__.py
├── bin/
│   └── binary_file  ← Bundeled met integratie
```

**Probleem voor Fresh-R:** Chrome is 100MB+, te groot voor HACS.

### Strategie 3: Alternatieve benadering
Sommige integraties gebruiken **alternatieven** voor browsers:
```python
# In plaats van Selenium + Chrome:
- aiohttp voor HTTP requests
- httpx voor async requests  
- BeautifulSoup voor HTML parsing
```

**Voor Fresh-R:** Dit werkt niet omdat Fresh-R een **JavaScript login** heeft die Selenium nodig heeft.

---

## ✅ Huidige Status: "Semi-automatisch"

### Wat je MOET handmatig doen (één keer):

```bash
# 1. Chrome installeren (systeem-level)
# HA OS:
apk add --no-cache chromium chromium-chromedriver

# Debian/Ubuntu:
sudo apt-get install chromium-browser

# Windows:
# Download van https://www.google.com/chrome/
```

### Wat er DAARNA automatisch gebeurt:

```
HACS Download
    ↓
Python packages auto-install (selenium, webdriver-manager)
    ↓
HA Restart
    ↓
Dependency check (geeft instructies als Chrome mist)
    ↓
Configuratie via UI
    ↓
✅ Token refresh ieder uur (volledig automatisch)
```

---

## 🔧 Oplossingen voor toekomst

### Optie 1: Home Assistant Add-on (Docker)
Maak een aparte **Add-on** die Chrome bundelt:

```yaml
# config.json voor Add-on
{
  "name": "Fresh-R Chrome",
  "version": "1.0",
  "slug": "fresh_r_chrome",
  "description": "Chrome for Fresh-R integration",
  "arch": ["amd64", "aarch64"],
  "startup": "before",
  "boot": "auto",
  "image": "ghcr.io/custom-components/fresh-r-chrome"
}
```

**Voordelen:**
- Chrome in eigen container
- Volledig automatisch
- Geïsoleerd van HA

**Nadelen:**
- Meer onderhoud
- Complexere setup
- Alleen voor HA OS/Supervised

### Optie 2: OAuth/API Token (bouwstenen aanwezig)
Als Fresh-R ooit een **API token** systeem krijgt (zonder browser login):
- Volledig automatische installatie
- Geen Chrome nodig

**Status:** Fresh-R biedt dit momenteel niet aan.

---

## 📋 Samenvatting

| Component | Installatie | Reden |
|-----------|-------------|-------|
| Integration code | ✅ Auto (HACS) | Python files |
| Python packages | ✅ Auto (HA) | pip in manifest.json |
| Chrome/Chromium | ❌ Handmatig | Systeem binary |
| Configuratie | ❌ Handmatig | UI invoer |
| Token refresh | ✅ Auto | Na setup |

**Fresh-R is nu "semi-automatisch":**
- Één keer Chrome installeren (handmatig)
- Alles daarna automatisch ✅

---

## 🚀 Actiepunten voor gebruiker

1. **HACS toevoegen:** Kan nu al! Custom repository toevoegen
2. **Chrome installeren:** Eén keer handmatig (per OS instructies)
3. **Genieten:** Alles daarna werkt automatisch

Wil je dat ik de Add-on oplossing uitwerk voor volledige automatisering?
