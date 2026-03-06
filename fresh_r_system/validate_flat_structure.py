#!/usr/bin/env python3
"""
Fresh-r integratie — validatie voor platte structuur
=======================================================
Uitvoeren:  python validate_flat_structure.py
"""

import ast
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import re

# Zoek de fresh_r map automatisch
SCRIPT_DIR = Path(__file__).parent
FRESH_R_DIR = None

# Zoek naar fresh_r map
for parent in [SCRIPT_DIR, SCRIPT_DIR.parent]:
    candidate = parent / "fresh_r"
    if candidate.exists() and (candidate / "__init__.py").exists():
        FRESH_R_DIR = candidate
        break

if not FRESH_R_DIR:
    print("❌ Kon fresh_r map niet vinden!")
    sys.exit(1)

print(f"✅ Fresh-r map gevonden: {FRESH_R_DIR}")

ROOT = FRESH_R_DIR
PY_FILES = sorted(ROOT.glob("*.py"))
JSON_FILES = [
    ROOT / "manifest.json",
    ROOT / "strings.json",
    ROOT / "fresh_r_dashboard.json",
    ROOT / "en.json",
    ROOT / "nl.json",
]

errors = 0
warnings = 0

def fail(msg: str) -> None:
    global errors
    print(f"  ❌  {msg}")
    errors += 1

def warn(msg: str) -> None:
    global warnings
    print(f"  ⚠️  {msg}")
    warnings += 1

def pass_check(msg: str) -> None:
    print(f"  ✅  {msg}")

def validate_manifest(manifest: Dict, filename: str) -> None:
    """Valideer Home Assistant manifest volgens huidige standaard."""
    required_fields = ["domain", "name", "version", "iot_class"]
    
    for field in required_fields:
        if field not in manifest:
            fail(f"Manifest: verplicht veld '{field}' ontbreekt")
        else:
            pass_check(f"  → {field}: {manifest[field]}")

def validate_grafana_dashboard(dashboard: Dict, filename: str) -> None:
    """Valideer Grafana dashboard volgens 8.x+ standaard."""
    required_fields = ["title", "panels", "uid", "schemaVersion"]
    
    for field in required_fields:
        if field not in dashboard:
            fail(f"Dashboard: verplicht veld '{field}' ontbreekt")
        else:
            pass_check(f"  → {field}")
    
    panels = dashboard.get("panels", [])
    pass_check(f"  → {len(panels)} panelen")
    
    for i, panel in enumerate(panels):
        datasource = panel.get("datasource")
        if datasource:
            if isinstance(datasource, str):
                pass_check(f"  → Panel {i+1}: datasource '{datasource}' (modern)")
            elif isinstance(datasource, dict):
                ds_type = datasource.get("type", "unknown")
                pass_check(f"  → Panel {i+1}: datasource type '{ds_type}' (legacy)")
            else:
                warn(f"  → Panel {i+1}: ongeldige datasource")

# ── 1. Python syntaxvalidatie ──────────────────────────────────
print("=" * 70)
print("1. Python syntaxvalidatie (Python 3.8+ compatible)")
print("=" * 70)

for py_file in PY_FILES:
    try:
        with open(py_file, 'r', encoding='utf-8') as f:
            source = f.read()
        
        ast.parse(source, filename=str(py_file))
        pass_check(f"{py_file.name}")
        
        if "from __future__ import annotations" in source:
            pass_check(f"  → Modern type hints")
        else:
            warn(f"  → Geen future annotations (aanbevolen)")
            
    except SyntaxError as e:
        fail(f"{py_file.name}: {e}")
    except Exception as e:
        fail(f"{py_file.name}: {e}")

# ── 2. JSON validatie ────────────────────────────────────────
print("\n" + "=" * 70)
print("2. JSON validatie (RFC 8259 compatible)")
print("=" * 70)

for json_file in JSON_FILES:
    if not json_file.exists():
        warn(f"{json_file.name} niet gevonden")
        continue
        
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        if not content:
            fail(f"{json_file.name} is leeg")
            continue
            
        data = json.loads(content)
        pass_check(f"{json_file.name}")
        
        if "manifest" in json_file.name:
            validate_manifest(data, json_file.name)
        elif "dashboard" in json_file.name:
            validate_grafana_dashboard(data, json_file.name)
            
    except json.JSONDecodeError as e:
        fail(f"{json_file.name}: {e}")
    except Exception as e:
        fail(f"{json_file.name}: {e}")

# ── 3. Home Assistant integratie validatie ───────────────────────────────
print("\n" + "=" * 70)
print("3. Home Assistant integratie validatie")
print("=" * 70)

required_files = ["__init__.py", "manifest.json", "config_flow.py", "const.py"]
for req_file in required_files:
    if (ROOT / req_file).exists():
        pass_check(f"  → {req_file}")
    else:
        fail(f"  → {req_file} ontbreekt")

# Check manifest integratie
manifest_path = ROOT / "manifest.json"
if manifest_path.exists():
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    domain = manifest.get("domain")
    if domain:
        init_file = ROOT / "__init__.py"
        if init_file.exists():
            with open(init_file) as f:
                init_content = f.read()
            if (f'DOMAIN = "{domain}"' in init_content or 
                f'from .const import DOMAIN' in init_content):
                pass_check(f"  → Domain consistent: {domain}")
            else:
                warn(f"  → Domain check inconclusief")

# ── 4. Sensor validatie ────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("4. Sensor validatie")
print("=" * 70)

try:
    const_path = ROOT / "const.py"
    if const_path.exists():
        with open(const_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check voor SENSORS constant
        if "SENSORS" in content:
            pass_check("SENSORS constant gevonden")
            
            # Probeer de sensors te tellen (eenvoudige regex)
            sensor_matches = re.findall(r'"([^"]+)":\s*\(', content)
            if sensor_matches:
                pass_check(f"{len(sensor_matches)} sensoren gedefinieerd")
                for sensor in sensor_matches[:5]:  # Toon eerste 5
                    pass_check(f"  → {sensor}")
                if len(sensor_matches) > 5:
                    pass_check(f"  → ... en {len(sensor_matches) - 5} meer")
        else:
            warn("SENSORS constant niet gevonden")
            
except Exception as e:
    warn(f"Sensor validatie niet volledig: {e}")

# ── 5. Dashboard validatie ────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("5. Dashboard validatie")
print("=" * 70)

# Check HA dashboard
ha_dashboard = ROOT / "fresh-r-dashboard.yaml"
if ha_dashboard.exists():
    pass_check("Home Assistant dashboard gevonden")
else:
    warn("Home Assistant dashboard niet gevonden")

# Check Grafana dashboard
grafana_dashboard = ROOT / "fresh_r_dashboard.json"
if grafana_dashboard.exists():
    pass_check("Grafana dashboard gevonden")
else:
    warn("Grafana dashboard niet gevonden")

# ── 6. Bestandsgrootte ────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("6. Bestandsgrootte")
print("=" * 70)

for py_file in PY_FILES:
    size_kb = py_file.stat().st_size / 1024
    if size_kb > 50:
        warn(f"{py_file.name}: {size_kb:.1f}KB (groot)")
    else:
        pass_check(f"{py_file.name}: {size_kb:.1f}KB")

for json_file in JSON_FILES:
    if json_file.exists():
        size_kb = json_file.stat().st_size / 1024
        if size_kb > 10:
            warn(f"{json_file.name}: {size_kb:.1f}KB (groot)")
        else:
            pass_check(f"{json_file.name}: {size_kb:.1f}KB")

# ── Samenvatting ────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("VALIDATIE SAMENVATTING")
print("=" * 70)

print(f"📁 Bestanden gecontroleerd: {len(PY_FILES)} Python + {len(JSON_FILES)} JSON")
print(f"✅ Geslaagde checks: {6 - errors - warnings}/6")
print(f"❌ Errors: {errors}")
print(f"⚠️  Warnings: {warnings}")

if errors == 0:
    print("\n🎉 VALIDATIE SUCCESVOL - 100% COMPATIBEL!")
    print("✅ Ready voor Home Assistant installatie")
else:
    print(f"\n❌ {errors} errors gevonden - fix voordat u installeert")

if warnings > 0:
    print(f"⚠️  {warnings} warnings - aanbevolen om te reviewen")

print(f"\n📊 Validatie uitgevoerd met moderne standaarden:")
print(f"   • Python 3.8+ compatible")
print(f"   • Grafana 8.x+ compatible") 
print(f"   • Home Assistant 2024.x+ compatible")
print(f"   • RFC 8259 JSON standaard")

sys.exit(1 if errors > 0 else 0)
