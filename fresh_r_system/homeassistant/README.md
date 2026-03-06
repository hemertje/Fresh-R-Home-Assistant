# 🏠 Home Assistant Fresh-R Integration

Deze map bevat alle bestanden die je naar je Home Assistant configuratie moet kopiëren.

## 📁 Structuur

```
homeassistant/
├── custom_components/fresh_r/     ← Integration code
├── lovelace/fresh_r_dashboard.yaml  ← Dashboard config
└── packages/fresh_r_input_helpers.yaml  ← Input helpers
```

## 🚀 Installatie

### Stap 1: Kopieer Integration Code

**Kopieer naar `/config/`:**

```bash
# Linux/Mac
cp -r custom_components/fresh_r /config/custom_components/

# Windows (PowerShell als admin)
Copy-Item -Path custom_components\fresh_r -Destination C:\config\custom_components\ -Recurse -Force
```

### Stap 2: Dashboard Configuratie (Optioneel)

```bash
# Linux/Mac
cp lovelace/fresh_r_dashboard.yaml /config/lovelace/

# Windows
Copy-Item lovelace\fresh_r_dashboard.yaml C:\config\lovelace\
```

### Stap 3: Input Helpers (Optioneel)

```bash
# Linux/Mac
cp packages/fresh_r_input_helpers.yaml /config/packages/

# Windows
Copy-Item packages\fresh_r_input_helpers.yaml C:\config\packages\
```

**OF** voeg toe aan `configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

## ⚙️ Configuratie via UI

1. Herstart Home Assistant
2. Ga naar **Settings** → **Devices & Services** → **Integrations**
3. Klik **Add Integration**
4. Zoek **Fresh-R**
5. Vul je credentials in:
   - Email: jouw@email.com
   - Password: jouw_wachtwoord
   - Poll Interval: 60 (seconden)

## 🎨 Dashboard Import

1. Ga naar **Settings** → **Dashboards**
2. Klik **Add Dashboard**
3. Kies **Raw configuration editor**
4. Open `lovelace/fresh_r_dashboard.yaml`
5. Kopieer inhoud en plak in editor
6. Klik **Save**

## 📋 Bestanden Uitleg

| Bestand | Doel | Vereist? |
|---------|------|----------|
| `custom_components/fresh_r/` | Integration code | ✅ Ja |
| `lovelace/fresh_r_dashboard.yaml` | Dashboard config | ❌ Nee |
| `packages/fresh_r_input_helpers.yaml` | Datum picker helpers | ❌ Nee |

## 🔧 Voorbeeld: Compleet Kopieer Script

```bash
#!/bin/bash
# save as: install_fresh_r.sh

CONFIG_DIR="/config"  # Pas aan naar jouw HA config directory

echo "Installing Fresh-R Integration..."

# 1. Integration
cp -r homeassistant/custom_components/fresh_r "$CONFIG_DIR/custom_components/"
echo "✓ Integration copied"

# 2. Dashboard
mkdir -p "$CONFIG_DIR/lovelace"
cp homeassistant/lovelace/fresh_r_dashboard.yaml "$CONFIG_DIR/lovelace/"
echo "✓ Dashboard copied"

# 3. Input helpers
mkdir -p "$CONFIG_DIR/packages"
cp homeassistant/packages/fresh_r_input_helpers.yaml "$CONFIG_DIR/packages/"
echo "✓ Input helpers copied"

echo ""
echo "Done! Restart Home Assistant to activate."
echo "Then go to Settings → Integrations → Add Fresh-R"
```

## 🐛 Troubleshooting

### "Integration not found"
- Controleer of `custom_components/fresh_r/` correct is gekopieerd
- Herstart HA na kopiëren

### "No devices found"
- Controleer je Fresh-R credentials
- Check of je devices zichtbaar zijn in Fresh-R dashboard

### "Dashboard not showing"
- Importeer handmatig via Raw configuration editor
- Check YAML syntax

---

⬅️ [Terug naar hoofddocumentatie](../DOCUMENTATION_STRUCTURE.md)
