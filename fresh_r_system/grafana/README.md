# 📊 Grafana Fresh-R Dashboards

Deze map bevat pre-geconfigureerde Grafana dashboards voor je Fresh-R ventilatie systeem.

## 📁 Structuur

```
grafana/
├── dashboards/
│   ├── overview.json       ← Hoofd overzicht dashboard
│   └── details.json        ← Detail analyse dashboard
└── docs/
    └── GRAFANA_README.md   ← Complete setup guide
```

## 🚀 Quick Start

### 1. Importeer Dashboards

1. Open Grafana → **Dashboards** → **Import**
2. Klik **Upload JSON file**
3. Selecteer `dashboards/overview.json`
4. Kies je **InfluxDB** data source
5. Klik **Import**
6. Herhaal voor `dashboards/details.json`

### 2. Configureer Data Source

**InfluxDB toevoegen:**
1. **Configuration** → **Data Sources** → **Add data source**
2. Kies **InfluxDB**
3. Vul in:
   - URL: `http://localhost:8086`
   - Database: `homeassistant`
   - (Optioneel) User/Password
4. Klik **Save & Test**

## 📋 Dashboard Overzicht

### Overview Dashboard (`overview.json`)

**Real-time metrics met gauges:**
- 🌡️ Temperaturen (binnen, buiten, toevoer)
- 💨 CO2 niveau
- 💧 Luchtvochtigheid
- 🌫️ PM2.5 / PM1.0 / PM0.3
- 🔄 Ventilatie debiet
- ⚡ Warmteterugwinning

**24-uurs historie grafieken:**
- Temperatuur trends
- Luchtkwaliteit over tijd
- PM2.5 ontwikkeling

### Details Dashboard (`details.json`)

**Uitgebreide sensor analyse:**
- Alle temperatuur sensoren (t1, t2, t3, t4, dp)
- Luchtkwaliteit (CO2, humidity)
- PM fijnstof per locatie (binnen/buiten/toevoer)
- Ventilatie debiet historie
- Energie metrics (W)
- Tabel met alle huidige waarden

## 🎨 Kleurcodering (Alerts)

| Metric | Groen | Geel | Oranje | Rood |
|--------|-------|------|--------|------|
| **Temperatuur** | 18-25°C | <18 of >25 | - | <10 of >30 |
| **CO2** | <800 ppm | 800-1200 | 1200-1500 | >1500 |
| **Luchtvochtigheid** | 30-60% | >60 | - | <30 |
| **PM2.5** | <10 µg/m³ | 10-25 | - | >25 |

## 🔧 Vereisten

- **Grafana** 8.0+ geïnstalleerd
- **InfluxDB** data source met Fresh-R data
- **Home Assistant** InfluxDB integratie geconfigureerd

## 📖 Gedetailleerde Documentatie

Zie [docs/GRAFANA_README.md](docs/GRAFANA_README.md) voor:
- Stap-voor-stap installatie
- Query voorbeelden
- Troubleshooting
- Advanced configuratie

---

⬅️ [Terug naar hoofddocumentatie](../DOCUMENTATION_STRUCTURE.md)
