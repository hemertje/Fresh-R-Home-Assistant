# 🔧 Installatie Scripts

Scripts voor handmatige installatie van dependencies.

## ⚠️ BELANGRIJK: Dependencies Installeren NIET Automatisch!

❌ **Home Assistant installeert deze dependencies NIET automatisch!**

De `manifest.json` specificeert wel welke packages nodig zijn (`selenium`, `webdriver-manager`, `aiohttp`), maar HA installeert deze **niet** vanwege:
- Systeem-afhankelijke binaries (Chrome/Chromium)
- Veiligheidsrestricties
- Geen pip installatie in bepaalde HA installaties (HA OS, Container)

✅ **Je MOET dit script handmatig uitvoeren!**

---

## 📁 Bestanden

| Bestand | Platform | Doel |
|---------|----------|------|
| **setup_selenium.sh** | 🐧 Linux / 🍎 Mac | Chrome + Selenium + Python packages |
| **setup_selenium.ps1** | 🪟 Windows PowerShell | Chrome + Selenium + Python packages |

## 🤔 Waarom twee scripts?

**Verschillende besturingssystemen = Verschillende commando's:**

| OS | Script | Package Manager | Chrome Installatie |
|----|--------|---------------|-------------------|
| **Linux (Debian/Ubuntu)** | `.sh` | `apt-get` | `google-chrome-stable` |
| **Linux (Alpine/HA OS)** | `.sh` | `apk` | `chromium` |
| **Mac** | `.sh` | `brew` | `google-chrome` |
| **Windows** | `.ps1` | `choco` of direct | Chrome installer |

**Windows kan geen Bash (.sh) scripts uitvoeren zonder extra software (WSL/Git Bash).**
Daarom is er een native PowerShell (.ps1) script voor Windows gebruikers.

---

## 🚀 Gebruik

### 🐧 Linux / 🍎 Mac (Terminal)

```bash
cd scripts/
sudo ./setup_selenium.sh
```

**Wat doet het:**
1. Detecteert je Linux distributie (Debian/Ubuntu/Alpine)
2. Installeert Chrome/Chromium via package manager
3. Installeert Python packages via pip3
4. Test de installatie

### 🪟 Windows (PowerShell als Administrator)

```powershell
cd scripts\
.\setup_selenium.ps1
```

**Wat doet het:**
1. Download Chrome installer
2. Installeert Chrome (indien niet aanwezig)
3. Installeert Python packages via pip
4. Configureert environment

**⚠️ Windows gebruikers:** Rechts-klik PowerShell → "Run as Administrator"

---

## 📦 Wat wordt geïnstalleerd?

### System Packages (eenmalig)
- **Google Chrome** of **Chromium** browser
- **ChromeDriver** (wordt automatisch geüpdatet door webdriver-manager)

### Python Packages (na elke HA update checken!)
- `selenium>=4.0.0` - Browser automation
- `webdriver-manager>=4.0.0` - Automatische driver updates
- `aiohttp>=3.8.0` - Async HTTP client

**Let op:** Deze packages moeten geïnstalleerd zijn in de Python omgeving die HA gebruikt!

---

## 🎯 Wanneer uitvoeren?

| Situatie | Actie |
|----------|-------|
| **Eerste installatie** | ✅ **VERPLICHT** - Run script |
| **Na HA OS update** | ✅ Run script opnieuw (packages kunnen verdwenen zijn) |
| **Na HA Core update** | ⚠️ Check of packages nog werken |
| **Alles werkt** | ❌ Niet nodig |

### Stappenplan:

```
1. Installeer Home Assistant
   ↓
2. [VERPLICHT] Run setup_selenium.sh (Linux/Mac) of .ps1 (Windows)
   ↓
3. Herstart HA
   ↓
4. Kopieer integration naar custom_components/
   ↓
5. Herstart HA
   ↓
6. Configureer Fresh-R via UI
```

---

## 🐛 Troubleshooting

### "Permission denied" (Linux/Mac)
```bash
chmod +x setup_selenium.sh
sudo ./setup_selenium.sh
```

### "Chrome not found" (Linux)
Script detecteert OS automatisch:
- **Debian/Ubuntu**: `apt-get install google-chrome-stable`
- **Alpine/HA OS**: `apk add chromium`

### "pip not found"
```bash
# Debian/Ubuntu
sudo apt-get install python3-pip

# Alpine
apk add py3-pip
```

### "ExecutionPolicy" fout (Windows PowerShell)
```powershell
# Tijdelijk policy wijzigen (run als admin)
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\setup_selenium.ps1
```

---

## 🔧 Handmatige Installatie (als script faalt)

### Linux: Debian/Ubuntu

```bash
# Chrome installeren
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt-get update
sudo apt-get install -y google-chrome-stable chromium-chromedriver

# Python packages in HA omgeving
pip3 install selenium webdriver-manager aiohttp
# OF als HA in virtualenv zit:
sudo -u homeassistant -H -s
source /srv/homeassistant/bin/activate
pip install selenium webdriver-manager aiohttp
```

### Linux: Alpine (HA OS)

```bash
# Toegang via SSH/Terminal add-on
apk add --no-cache chromium chromium-chromedriver py3-pip
pip3 install selenium webdriver-manager aiohttp
```

### Mac

```bash
# Chrome via Homebrew
brew install --cask google-chrome

# Python packages
pip3 install selenium webdriver-manager aiohttp
```

### Windows

```powershell
# Chrome downloaden en installeren
# Ga naar: https://www.google.com/chrome/
# Download en installeer

# Python packages
pip install selenium webdriver-manager aiohttp
```

---

## ✅ Verificatie

Test of alles werkt:

```python
python3 -c "from selenium import webdriver; print('✅ Selenium OK')"
python3 -c "import webdriver_manager; print('✅ WebDriver Manager OK')"
python3 -c "import aiohttp; print('✅ aiohttp OK')"
```

**Alle drie moeten "OK" printen zonder errors!**

---

## 💡 Alternatief: Docker Compose (voor HA Container)

Als je HA in Docker runt, voeg toe aan `docker-compose.yml`:

```yaml
services:
  homeassistant:
    image: ghcr.io/home-assistant/home-assistant:stable
    volumes:
      - ./config:/config
    # Chrome + dependencies in container
    environment:
      - CHROME_BIN=/usr/bin/chromium
    # OF gebruik custom image met Chrome pre-installed
```

---

⬅️ [Terug naar hoofddocumentatie](../DOCUMENTATION_STRUCTURE.md)
