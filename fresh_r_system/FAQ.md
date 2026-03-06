# Fresh-R Home Assistant - Veelgestelde Vragen (FAQ)

## 📅 1. Kalender/Grafieken met Datum Selectie

**Vraag:** Grafieken in HA als een kalender selecteerbaar conform Fresh-R?

**Antwoord:** 
✅ **JA!** Ik heb het dashboard bijgewerkt met Fresh-R stijl datumselectie:

```yaml
# Nieuw in fresh_r_dashboard.yaml:
- title: Grafieken
  cards:
    # Datum range knoppen (Vandaag/Week/Maand/Jaar)
    - type: horizontal-stack
      cards:
        - type: button
          name: Vandaag
          icon: mdi:calendar-today
        - type: button
          name: Week
          icon: mdi:calendar-week
        - type: button
          name: Maand
          icon: mdi:calendar-month
        - type: button
          name: Jaar
          icon: mdi:calendar-range
```

**Nieuwe "Kalender" tab** toegevoegd met week-overzicht grafieken.

---

## 🔧 2. Selenium en ChromeDriver in Home Assistant

**Vraag:** Selenium en ChromeDriver zijn beschikbaar in HA? Wat doen deze? Bestuurt Selenium ook andere browsers? Is dit universeel?

**Antwoord:**

### **Wat doen ze?**

| Component | Functie | Waarom nodig? |
|-----------|---------|---------------|
| **Selenium** | Browser automation library | Programmatisch een browser besturen |
| **ChromeDriver** | Chrome controller | Laat Selenium Chrome aansturen |
| **Chrome** | De browser zelf | Simuleert een echte gebruiker login |

### **Universele Browser Ondersteuning:**

✅ **JA!** Selenium is universeel en ondersteunt meerdere browsers:

```python
# Chrome (gebruikt in deze integratie)
from selenium import webdriver
driver = webdriver.Chrome()

# Firefox (alternatief)
from selenium.webdriver.firefox.service import Service
driver = webdriver.Firefox()

# Edge (alternatief)
driver = webdriver.Edge()

# Safari (Mac)
driver = webdriver.Safari()
```

**Waarom Chrome gekozen:**
- Meest compatibel met websites
- Beste headless mode support
- Automatische ChromeDriver updates via webdriver-manager
- Works on Linux (Chromium), Windows, Mac

### **Headless Mode - Geen Fysiek Venster!**

✅ **CORRECT!** Selenium opent **NIET** fysiek Chrome. Het draait volledig op de achtergrond:

```python
chrome_options = Options()
chrome_options.add_argument("--headless")        # ← GEEN GUI!
chrome_options.add_argument("--no-sandbox")      # ← Veilig in containers
chrome_options.add_argument("--disable-dev-shm-usage")  # ← Memory optimalisatie
chrome_options.add_argument("--disable-gpu")     # ← Geen GPU nodig

driver = webdriver.Chrome(options=chrome_options)
# Chrome draait nu volledig onzichtbaar!
```

**Wat je NIET ziet:**
❌ Geen Chrome venster opent zich
❌ Geen browser interface
❌ Geen popup of melding

**Wat er WEL gebeurt (onzichtbaar):**
✅ Chrome process start in achtergrond
✅ Navigeert naar fresh-r.me/login
✅ Vult formulier in
✅ Extraheert cookies
✅ Sluit netjes af

**Process check (zichtbaar in systeem monitor):**
```bash
ps aux | grep chrome
→ chrome --headless --no-sandbox ...
```

### **Werking:**

```
Fresh-R Integration
       ↓
async_login() called
       ↓
Selenium WebDriver
       ↓
Launch Chrome HEADLESS (geen venster!)
       ↓
Navigate to fresh-r.me/login
       ↓
Fill email: buurkracht.binnenhof@gmail.com
Fill password: Hemert@7733
       ↓
Click submit button
       ↓
Wait for redirect to dashboard.bw-log.com
       ↓
Extract sess_token from cookies
       ↓
Close browser (cleanup)
       ↓
Store token → Use for API calls
```

### **Beschikbaarheid in HA:**

| Installatie Type | Selenium/Chrome | Installatie Methode |
|------------------|-----------------|---------------------|
| **HA OS** (recommended) | ⚠️ Niet standaard | Gebruik setup script of Community Add-on |
| **HA Container** | ⚠️ Niet standaard | Docker installatie Chrome/Selenium |
| **HA Core (venv)** | ⚠️ Niet standaard | pip install + systeem Chrome |
| **HA Supervised** | ⚠️ Niet standaard | apt-get install |

**→ Niet standaard aanwezig, moet geïnstalleerd worden!**

### **Headless Mode Voordelen:**

1. **Geen GUI nodig** - Werkt op servers zonder desktop
2. **Lager resource gebruik** - Geen rendering
3. **Veiliger** - Geen zichtbare browser = geen misbruik
4. **Sneller** - Geen UI updates nodig
5. **Docker compatible** - Werkt in containers

### **Alternatieve Browsers (indien Chrome niet werkt):**

```python
# Firefox headless
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

options = Options()
options.add_argument("--headless")
driver = webdriver.Firefox(options=options)

# Edge headless (Windows)
from selenium import webdriver
from selenium.webdriver.edge.options import Options

options = Options()
options.add_argument("--headless")
driver = webdriver.Edge(options=options)
```

**Opmerking:** De integratie is geconfigureerd voor Chrome, maar kan eenvoudig aangepast worden naar andere browsers in `api.py`.

---

## 🤖 3. Automatische Installatie na HA Setup

**Vraag:** Deze stap automatiseren na HA installatie?

**Antwoord:**
✅ **JA!** Ik heb `setup_selenium.sh` gemaakt:

### **Automatische Installatie:**

```bash
# Via SSH terminal in HA:
wget https://raw.githubusercontent.com/your-repo/fresh-r/main/setup_selenium.sh
chmod +x setup_selenium.sh
sudo ./setup_selenium.sh
```

### **Wat doet het script:**

1. ✅ Detecteert OS (Debian/Ubuntu/Alpine)
2. ✅ Installeert Google Chrome of Chromium
3. ✅ Installeert Python packages:
   - `selenium>=4.0.0`
   - `webdriver-manager>=4.0.0` 
   - `aiohttp>=3.8.0`
4. ✅ Creëert headless Chrome wrapper
5. ✅ Test de installatie

### **Alternative: Community Add-on**

Je kunt ook een custom add-on maken voor HA OS:

```yaml
# config.json voor add-on
{
  "name": "Fresh-R Dependencies",
  "version": "1.0",
  "slug": "fresh_r_deps",
  "description": "Selenium and Chrome for Fresh-R",
  "arch": ["amd64", "aarch64"],
  "startup": "before",
  "boot": "auto",
  "options": {},
  "schema": {}
}
```

---

## 📊 4. Dashboard Auto-Import naar Overview

**Vraag:** Wordt het Fresh-R dashboard automatisch opgenomen in het HA Overview dashboard?

**Antwoord:**
❌ **NEE**, niet automatisch. Je moet het handmatig toevoegen.

### **Stappen om toe te voegen:**

#### **Methode 1: Nieuwe Dashboard (Aanbevolen)**

1. Ga naar **Settings** → **Dashboards**
2. Klik **Add Dashboard**
3. Kies **Web page** of **Default**
4. Geef naam: "Fresh-R"
5. Klik **Create**
6. Klik **⋮** (drie puntjes) → **Edit Dashboard**
7. Klik **⋮** → **Raw configuration editor**
8. Kopieer inhoud van `fresh_r_dashboard.yaml`
9. Klik **Save**

#### **Methode 2: Toevoegen aan Overview (Niet aanbevolen)**

1. Ga naar **Overview** dashboard
2. Klik **⋮** → **Edit Dashboard**
3. Klik **Add Card**
4. Kies **Manual** 
5. Plak YAML voor één kaart
6. Herhaal voor alle kaarten

### **Auto-Discovery (Mogelijke Toekomstige Feature):**

```python
# In __init__.py - concept voor auto-dashboard
def async_setup_entry(hass, entry):
    # ... existing code ...
    
    # Auto-create dashboard (vereist speciale permissies)
    await hass.services.async_call(
        "lovelace", 
        "dashboard/create",
        {
            "url_path": "fresh-r",
            "title": "Fresh-R Ventilatie",
            "icon": "mdi:air-filter",
            "mode": "yaml",
            "config": DASHBOARD_YAML
        }
    )
```

**→ Momenteel niet geïmplementeerd wegens HA beveiligingsrestricties**

---

## 📡 5. MQTT Auto-Publish naar Server

**Vraag:** Dashboard parameters automatisch naar MQTT server gestuurd zodat ze in HA gebruikt kunnen worden?

**Antwoord:**
✅ **JA!** MQTT auto-publish is **AL GEÏMPLEMENTEERD** in `mqtt.py`:

### **Hoe het werkt:**

```python
# In coordinator.py - elke update:
async def _async_update_data(self):
    data = await self.client.async_get_current(self.serial)
    
    # MQTT: publish auto-discovery + current state
    if self.mqtt_enabled:
        from .mqtt import async_publish_discovery, async_publish_state
        
        # 1. Discovery: registreer sensoren bij HA
        await async_publish_discovery(hass, device_id, device_info)
        
        # 2. State: stuur huidige waarden
        await async_publish_state(hass, self.serial, data)
```

### **MQTT Topics:**

```
# Discovery (eenmalig bij startup):
homeassistant/sensor/fresh_r_{id}_t1/config
homeassistant/sensor/fresh_r_{id}_co2/config
homeassistant/sensor/fresh_r_{id}_hum/config
... (20 sensoren)

# State updates (elke poll interval, default 60s):
fresh_r/{device_id}/state
→ JSON: {"t1": 22.5, "co2": 450, "hum": 55, ...}

# Availability:
fresh_r/{device_id}/availability
→ "online" / "offline"
```

### **Configuratie:**

```yaml
# In config flow (UI) of configuration.yaml:
fresh_r:
  email: "buurkracht.binnenhof@gmail.com"
  password: "Hemert@7733"
  mqtt_enabled: true  # ← STAAT STANDAARD AAN
```

### **Prerequisite:**

Je moet MQTT broker geconfigureerd hebben in HA:

```yaml
# configuration.yaml
mqtt:
  broker: core-mosquitto  # of je eigen broker
  port: 1883
  username: mqtt_user
  password: mqtt_pass
```

### **Wat je ziet in HA:**

Na setup verschijnen automatisch 20+ entiteiten:
- `sensor.fresh_r_t1` (Binnen temperatuur)
- `sensor.fresh_r_co2` (CO2)
- `sensor.fresh_r_hum` (Vochtigheid)
- `sensor.fresh_r_d5_25` (PM2.5 toevoer)
- ... en nog 16 andere sensoren

**→ Alle sensoren zijn automatisch beschikbaar in HA en kunnen gebruikt worden in automations, scripts, andere dashboards!**

---

## 🎯 Samenvatting

| Vraag | Antwoord | Status |
|-------|----------|--------|
| Kalender grafieken | ✅ JA, toegevoegd | Implemented |
| Selenium/Chrome in HA | ⚠️ Nee, script gemaakt | Needs manual install |
| Automatische installatie | ✅ JA, setup_selenium.sh | Ready |
| Dashboard in Overview | ❌ Nee, handmatig | Manual step required |
| MQTT auto-publish | ✅ JA, al geïmplementeerd | Working |

---

## 🚀 Volgende Stappen

1. **Installeer dependencies:**
   ```bash
   sudo ./setup_selenium.sh
   ```

2. **Installeer integration:**
   ```bash
   cp -r custom_components/fresh_r /config/custom_components/
   ```

3. **Herstart HA**

4. **Configureer via UI:**
   - Settings → Integrations → Add Fresh-R
   - Vul credentials in
   - MQTT staat automatisch aan

5. **Importeer dashboard:**
   - Settings → Dashboards → Add Dashboard
   - Raw config → Plak fresh_r_dashboard.yaml

6. **Grafieken bekijken:**
   - Klik op "Kalender" tab voor datum selectie
   - Of "Grafieken" tab met Vandaag/Week/Maand/Jaar knoppen
