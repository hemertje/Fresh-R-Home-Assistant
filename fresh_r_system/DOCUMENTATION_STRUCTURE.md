# Fresh-R Integration - Document Structuur

Dit project bevat alle benodigde bestanden voor de Fresh-R Home Assistant integratie, georganiseerd per functie.

## 📁 Mappenstructuur

```
fresh_r_homeassistant_integration/
├── 📂 homeassistant/          ← Kopieer naar je HA config
│   ├── 📂 custom_components/
│   │   └── 📂 fresh_r/       ← Integration code
│   ├── 📂 lovelace/
│   │   └── fresh_r_dashboard.yaml
│   └── 📂 packages/
│       └── fresh_r_input_helpers.yaml
│
├── 📂 grafana/              ← Importeer in Grafana
│   ├── 📂 dashboards/
│   │   ├── overview.json
│   │   └── details.json
│   └── 📂 docs/
│       └── GRAFANA_README.md
│
├── 📂 docs/                 ← Documentatie
│   ├── FAQ_EN.md
│   ├── FAQ_NL.md
│   ├── CHANGELOG.md
│   └── CONTRIBUTING.md
│
├── 📂 scripts/              ← Installatie scripts
│   ├── setup_selenium.sh
│   └── setup_selenium.ps1
│
├── 📂 images/               ← Screenshots & logo's
│   ├── logo.png
│   ├── dashboard_preview.png
│   └── grafana_screenshot.png
│
├── README.md                ← Start hier!
├── LICENSE
├── hacs.json
└── info.md
```

## 🚀 Snelstart

### 1. Home Assistant Setup

**Kopieer naar `/config/`:**
```bash
# Linux/Mac
cp -r homeassistant/custom_components/fresh_r /config/custom_components/
cp homeassistant/lovelace/fresh_r_dashboard.yaml /config/lovelace/
cp homeassistant/packages/fresh_r_input_helpers.yaml /config/packages/

# Of gebruik HACS (aanbevolen)
# HACS → Integrations → Zoek "Fresh-R" → Download
```

### 2. Grafana Setup

**Importeer dashboards:**
1. Ga naar Grafana → Dashboards → Import
2. Upload `grafana/dashboards/overview.json`
3. Upload `grafana/dashboards/details.json`
4. Configureer InfluxDB data source

Zie `grafana/docs/GRAFANA_README.md` voor details.

### 3. Dependencies Installeren

**Linux:**
```bash
cd scripts/
sudo ./setup_selenium.sh
```

**Windows:**
```powershell
cd scripts/
.\setup_selenium.ps1
```

## 📖 Gedetailleerde Documentatie

| Document | Locatie | Doel |
|----------|---------|------|
| **Start Guide** | `README.md` | Begin hier |
| **FAQ (EN)** | `docs/FAQ_EN.md` | Veelgestelde vragen (Engels) |
| **FAQ (NL)** | `docs/FAQ_NL.md` | Veelgestelde vragen (Nederlands) |
| **Changelog** | `docs/CHANGELOG.md` | Versie geschiedenis |
| **Grafana Guide** | `grafana/docs/GRAFANA_README.md` | Grafana setup |
| **Contributing** | `docs/CONTRIBUTING.md` | Bijdragen aan project |

## 🎯 Per Component

### Home Assistant
- **Locatie:** `homeassistant/`
- **Doel:** Integration code, dashboard config, input helpers
- **Installatie:** Kopieer naar `/config/` of gebruik HACS

### Grafana
- **Locatie:** `grafana/`
- **Doel:** Dashboard JSONs en documentatie
- **Installatie:** Importeer JSONs in Grafana UI

### Scripts
- **Locatie:** `scripts/`
- **Doel:** Automatische installatie van dependencies
- **Installatie:** Run één keer na HA setup

### Documentatie
- **Locatie:** `docs/`
- **Doel:** Alle guides, FAQ, changelog
- **Gebruik:** Lees voor installatie/troubleshooting

## 📦 ZIP Package

Voor eenvoudige installatie is er een ZIP package:

```bash
# Download en extract
unzip fresh_r.zip
cd fresh_r/

# Kopieer HA files
cp -r homeassistant/custom_components/fresh_r /config/custom_components/
```

## 🔧 Ondersteuning

- **Issues:** [GitHub Issues](https://github.com/custom-components/fresh-r/issues)
- **Discussions:** [GitHub Discussions](https://github.com/custom-components/fresh-r/discussions)
- **Wiki:** [GitHub Wiki](https://github.com/custom-components/fresh-r/wiki)

---

<div align="center">

**📦 Organized for easy installation!**

</div>
