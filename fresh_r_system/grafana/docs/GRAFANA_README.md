# Fresh-R Grafana Dashboards

Complete Grafana dashboard collection for Fresh-R ventilation systems.

## 📦 Dashboards Inbegrepen

### 1. `grafana_dashboard_overview.json`
**Hoofddashboard** - Real-time overzicht met gauges en metrics
- 🌡️ Temperaturen (binnen, buiten, toevoer)
- 💨 CO2 niveau met kleurcodering
- 💧 Luchtvochtigheid
- 🌫️ PM2.5, PM1.0, PM0.3 fijnstof
- 🔄 Ventilatie debiet en warmteterugwinning
- 📊 24-uurs geschiedenis grafieken

### 2. `grafana_dashboard_details.json`
**Detaildashboard** - Uitgebreide sensor analyse
- Alle temperatuur sensoren (t1, t2, t3, t4, dew point)
- Luchtkwaliteit sensoren (CO2, humidity)
- PM fijnstof per locatie (binnen, buiten, toevoer)
- Ventilatie debiet historie
- Energie metrics (warmteterugwinning, verliezen)
- Tabel met alle huidige waarden

## 🔧 Installatie

### Stap 1: InfluxDB Data Source Configureren

1. Ga naar **Configuration** → **Data Sources**
2. Klik **Add data source**
3. Kies **InfluxDB**
4. Vul in:
   - **URL**: `http://localhost:8086` (of je InfluxDB URL)
   - **Database**: `homeassistant`
   - **User**: (optioneel)
   - **Password**: (optioneel)
   - **HTTP Method**: `GET`
5. Klik **Save & Test**

### Stap 2: Dashboards Importeren

#### Methode 1: Via JSON Import

1. Ga naar **Dashboards** → **Manage**
2. Klik **Import**
3. Kies een optie:
   - **Upload JSON file**: Selecteer `grafana_dashboard_overview.json`
   - **Import via panel json**: Kopieer de JSON inhoud
4. Kies je **InfluxDB** data source
5. Klik **Import**

6. Herhaal voor `grafana_dashboard_details.json`

#### Methode 2: Via API (CLI)

```bash
# Set Grafana API key
export GRAFANA_API_KEY="your-api-key"

# Import overview dashboard
curl -X POST \
  http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GRAFANA_API_KEY" \
  -d @grafana_dashboard_overview.json

# Import details dashboard
curl -X POST \
  http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GRAFANA_API_KEY" \
  -d @grafana_dashboard_details.json
```

### Stap 3: Home Assistant InfluxDB Configureren

Zorg dat je Home Assistant integratie data naar InfluxDB schrijft:

```yaml
# In je configuration.yaml of in de Fresh-R integratie configuratie
influxdb:
  host: localhost
  port: 8086
  database: homeassistant
  username: homeassistant
  password: your_password
  max_retries: 3
  default_measurement: fresh_r
```

OF configureer het in de Fresh-R integratie UI:

1. Ga naar **Settings** → **Devices & Services** → **Fresh-R**
2. Klik **Configure**
3. Vink **InfluxDB Enabled** aan
4. Vul je InfluxDB details in:
   - Host: `localhost`
   - Port: `8086`
   - Database: `homeassistant`
   - Token: (optioneel voor InfluxDB v2)
   - Org: (optioneel voor InfluxDB v2)
   - Username: (optioneel)
   - Password: (optioneel)

## 📊 Dashboard Features

### Overzicht Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│  🌡️ TEMPERATUREN        💨 CO2              💧 VOGTIGHEID       │
│  ┌─────┐               ┌─────┐            ┌─────┐             │
│  │ 22° │               │ 450 │            │ 55% │             │
│  └─────┘               └─────┘            └─────┘             │
├─────────────────────────────────────────────────────────────────┤
│  🌫️ PM2.5          🌫️ PM1.0          🌫️ PM0.3               │
│  Toev: 5 µg/m³      Toev: 3 µg/m³      Toev: 1200 #/0.1l       │
│  Buit: 15 µg/m³     Buit: 8 µg/m³      Buit: 3500 #/0.1l       │
│  Bin: 3 µg/m³       Bin: 2 µg/m³       Bin: 800 #/0.1l         │
├─────────────────────────────────────────────────────────────────┤
│  🔄 DEBIET: 120 m³/h    ⚡ WARMTE TERUG: 450 W                  │
├─────────────────────────────────────────────────────────────────┤
│  📊 24-uurs grafieken                                           │
│  [Temperatuur] [CO2/Humidity] [PM2.5]                          │
└─────────────────────────────────────────────────────────────────┘
```

### Details Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│  🌡️ TEMPERATUUR SENSOREN      💨 LUCHTKWALITEIT                 │
│  [t1] [t2] [t3] [t4] [dp]     [CO2] [Humidity]                 │
├─────────────────────────────────────────────────────────────────┤
│  🌫️ PM2.5      🌫️ PM1.0      🌫️ PM0.3                          │
│  [Grafieken per locatie]                                        │
├─────────────────────────────────────────────────────────────────┤
│  🔄 DEBIET HISTORIE           ⚡ ENERGIE METRICS               │
│  [Flow over tijd]             [Warmte/Verlies/Winst]           │
├─────────────────────────────────────────────────────────────────┤
│  📋 ALLE SENSOREN TABEL                                         │
│  [Huidige waarden van alle 20+ sensoren]                       │
└─────────────────────────────────────────────────────────────────┘
```

## 🎨 Kleurcodering (Alerts)

### Temperaturen
- 🟢 **Groen**: 18-25°C (comfortabel)
- 🟡 **Geel**: <18°C of >25°C (opmerkelijk)
- 🔴 **Rood**: <10°C of >30°C (extreem)

### CO2 Niveau
- 🟢 **Groen**: <800 ppm (goed)
- 🟡 **Geel**: 800-1200 ppm (matig)
- 🟠 **Oranje**: 1200-1500 ppm (slecht)
- 🔴 **Rood**: >1500 ppm (gevaarlijk)

### Luchtvochtigheid
- 🔴 **Rood**: <30% (te droog)
- 🟢 **Groen**: 30-60% (ideaal)
- 🟡 **Geel**: >60% (te vochtig)

### PM2.5 Fijnstof
- 🟢 **Groen**: <10 µg/m³ (goed)
- 🟡 **Geel**: 10-25 µg/m³ (matig)
- 🔴 **Rood**: >25 µg/m³ (slecht)

## 📈 Metrics Uitleg

| Metric | Eenheid | Beschrijving |
|--------|---------|--------------|
| t1 | °C | Binnen temperatuur |
| t2 | °C | Buiten temperatuur |
| t3 | °C | Toevoer temperatuur |
| t4 | °C | Afvoer temperatuur |
| dp | °C | Dauwpunt |
| co2 | ppm | CO2 concentratie |
| hum | % | Relatieve vochtigheid |
| flow | m³/h | Ventilatie debiet |
| d1_25 | µg/m³ | Binnen PM2.5 |
| d4_25 | µg/m³ | Buiten PM2.5 |
| d5_25 | µg/m³ | Toevoer PM2.5 |
| heat_recovered | W | Warmteterugwinning vermogen |
| vent_loss | W | Ventilatie warmteverlies |
| energy_loss | W | Totale energie verlies |

## 🔍 Query Voorbeelden

### Laatste waarde ophalen
```sql
SELECT last("value") FROM "fresh_r" WHERE "entity_id" = 'fresh_r_t1'
```

### Gemiddelde over 24 uur
```sql
SELECT mean("value") FROM "fresh_r" WHERE "entity_id" = 'fresh_r_co2' AND time > now() - 24h
```

### Maximum waarde vandaag
```sql
SELECT max("value") FROM "fresh_r" WHERE "entity_id" = 'fresh_r_d5_25' AND time > now() - 1d
```

## 🐛 Troubleshooting

### "No data" in Grafana

1. Check InfluxDB data source connection
2. Verify Home Assistant is writing to InfluxDB:
   ```bash
   influx -database homeassistant -execute 'SHOW MEASUREMENTS'
   ```
3. Check Fresh-R integration InfluxDB settings
4. Verify Fresh-R sensors are updating in Home Assistant

### Dashboard variabelen werken niet

1. Zorg dat de `device` tag correct is ingesteld
2. Check InfluxDB query in template variable:
   ```sql
   SHOW TAG VALUES FROM "fresh_r" WITH KEY = "device"
   ```

### Grafieken zijn leeg

1. Verander tijdsbereik (rechtsboven) naar "Last 6 hours"
2. Check dat data daadwerkelijk in InfluxDB is:
   ```bash
   influx -database homeassistant -execute 'SELECT * FROM "fresh_r" LIMIT 5'
   ```

## 📚 Bestanden

```
fresh_r_zip/
├── grafana_dashboard_overview.json    # Hoofd overzicht dashboard
├── grafana_dashboard_details.json     # Details analyse dashboard
├── fresh_r_dashboard.yaml             # Home Assistant Lovelace dashboard
└── README.md                          # Deze handleiding
```

## 🔄 Updates

Om dashboards te updaten:

1. Exporteer huidige dashboard (voor backup)
2. Importeer nieuwe JSON versie
3. Herconfigureer data source indien nodig
4. Test alle panelen

## 🙏 Credits

- Dashboards geïnspireerd door Fresh-R.me interface
- Kleurcodering gebaseerd op WHO/EPA luchtkwaliteit richtlijnen
- Grafana 8.0+ compatible

## 📞 Support

Voor vragen of problemen:
1. Check deze handleiding
2. Raadpleeg Home Assistant logs
3. Verifieer InfluxDB connectiviteit
4. Open een issue op GitHub
