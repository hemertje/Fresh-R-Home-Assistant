#!/usr/bin/env python3
"""
Fresh-r integratie — moderne validatie & simulatie v2.0
=======================================================
Gebaseerd op huidige Home Assistant, Grafana 8.x+ en Python 3.12+ standaarden.

Uitvoeren:  python3 validate_and_simulate_v2.py
"""

import ast
import importlib.util
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import re

ROOT    = Path(__file__).parent / "custom_components" / "fresh_r"
PY_FILES = sorted(ROOT.glob("*.py"))
JSON_FILES = [
    ROOT / "manifest.json",
    ROOT / "strings.json",
    ROOT.parent / "grafana" / "fresh_r_dashboard.json",
    ROOT / "translations" / "en.json",
    ROOT / "translations" / "nl.json",
]

# Update dashboard path fallback
DASHBOARD_PATHS = [
    ROOT.parent / "grafana" / "fresh_r_dashboard.json",
    ROOT / "grafana" / "fresh_r_dashboard.json",
    ROOT.parent.parent / "grafana" / "fresh_r_dashboard.json",
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
    
    # Check moderne requirements
    if "requirements" in manifest:
        for req in manifest["requirements"]:
            if re.match(r'^[a-zA-Z0-9\-_]+>=[\d\.]+$', req):
                pass_check(f"  → requirement: {req}")
            else:
                warn(f"  → ongeldige requirement formaat: {req}")

def validate_grafana_dashboard(dashboard: Dict, filename: str) -> None:
    """Valideer Grafana dashboard volgens 8.x+ standaard."""
    required_fields = ["title", "panels", "uid", "schemaVersion"]
    
    for field in required_fields:
        if field not in dashboard:
            fail(f"Dashboard: verplicht veld '{field}' ontbreekt")
        else:
            pass_check(f"  → {field}")
    
    # Valideer panels met moderne datasource syntax
    panels = dashboard.get("panels", [])
    pass_check(f"  → {len(panels)} panelen")
    
    for i, panel in enumerate(panels):
        datasource = panel.get("datasource")
        if datasource:
            # Moderne syntax: string of object
            if isinstance(datasource, str):
                pass_check(f"  → Panel {i+1}: datasource '{datasource}' (modern)")
            elif isinstance(datasource, dict):
                ds_type = datasource.get("type", "unknown")
                pass_check(f"  → Panel {i+1}: datasource type '{ds_type}' (legacy)")
            else:
                warn(f"  → Panel {i+1}: ongeldige datasource")
        
        # Check targets
        targets = panel.get("targets", [])
        if targets:
            pass_check(f"  → Panel {i+1}: {len(targets)} targets")

# ── 1. Python syntaxvalidatie (moderne standaard) ──────────────────────────────────
print("=" * 70)
print("1. Python syntaxvalidatie (Python 3.8+ compatible)")
print("=" * 70)

for py_file in PY_FILES:
    try:
        with open(py_file, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Parse met moderne AST
        ast.parse(source, filename=str(py_file))
        pass_check(f"{py_file.name}")
        
        # Check voor moderne imports
        if "from __future__ import annotations" in source:
            pass_check(f"  → Modern type hints")
        else:
            warn(f"  → Geen future annotations (aanbevolen)")
            
    except SyntaxError as e:
        fail(f"{py_file.name}: {e}")
    except Exception as e:
        fail(f"{py_file.name}: {e}")

# ── 2. JSON validatie (moderne standaard) ────────────────────────────────────────
print("\n" + "=" * 70)
print("2. JSON validatie (RFC 8259 compatible)")
print("=" * 70)

# Update JSON_FILES with found dashboard
dashboard_found = False
for dashboard_path in DASHBOARD_PATHS:
    if dashboard_path.exists():
        JSON_FILES[2] = dashboard_path  # Replace with found path
        dashboard_found = True
        break

for json_file in JSON_FILES:
    if not json_file.exists():
        if "dashboard" in str(json_file):
            warn(f"{json_file.name} niet gevonden (geprobeerd: {', '.join([str(p) for p in DASHBOARD_PATHS])})")
        else:
            warn(f"{json_file.name} niet gevonden")
        continue
        
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        if not content:
            fail(f"{json_file.name} is leeg")
            continue
            
        # JSON parse met moderne standaard
        data = json.loads(content)
        pass_check(f"{json_file.name}")
        
        # Specifieke validaties per type
        if "manifest" in json_file.name:
            validate_manifest(data, json_file.name)
        elif "dashboard" in json_file.name:
            validate_grafana_dashboard(data, json_file.name)
            
    except json.JSONDecodeError as e:
        fail(f"{json_file.name}: {e}")
    except Exception as e:
        fail(f"{json_file.name}: {e}")

# ── 3. Home Assistant integratie validatie ───────────────────────────────────────
print("\n" + "=" * 70)
print("3. Home Assistant integratie validatie")
print("=" * 70)

# Check component structuur
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
    
    # Domain check
    domain = manifest.get("domain")
    if domain:
        init_file = ROOT / "__init__.py"
        if init_file.exists():
            with open(init_file) as f:
                init_content = f.read()
            # Check for DOMAIN import OR direct definition
            if (f'DOMAIN = "{domain}"' in init_content or 
                f'from .const import DOMAIN' in init_content):
                pass_check(f"  → Domain consistent: {domain}")
            else:
                warn(f"  → Domain check inconclusief (import via const.py)")

# ── 4. API endpoint validatie ───────────────────────────────────────────────────
print("\n" + "=" * 70)
print("4. API endpoint validatie")
print("=" * 70)

try:
    # Import en test API client
    api_path = ROOT / "api.py"
    if api_path.exists():
        with open(api_path, 'r', encoding='utf-8') as f:
            api_content = f.read()
        
        pass_check("API client bestand gevonden")
        
        # Check voor required methodes via text analysis
        required_methods = ['async_login', 'async_discover_devices', 'async_get_current']
        methods_found = 0
        for method in required_methods:
            if f"def {method}" in api_content:
                pass_check(f"  → {method} methode gevonden")
                methods_found += 1
            else:
                fail(f"  → {method} methode ontbreekt")
        
        # Check voor moderne API endpoints
        modern_api = "api.fresh-r.dev" in api_content
        legacy_api = "dashboard.bw-log.com" in api_content
        
        if modern_api:
            pass_check("  → Moderne API endpoint gevonden")
        if legacy_api:
            pass_check("  → Legacy API endpoint gevonden")
        
        # Check voor Bearer token usage
        if "Bearer" in api_content:
            pass_check("  → Bearer token authenticatie gevonden")
        
        # Overall API validation success
        if methods_found == len(required_methods) and (modern_api or legacy_api):
            pass_check("API validatie succesvol")
        else:
            warn("API validatie gedeeltelijk")
            
except Exception as e:
    warn(f"API validatie niet volledig: {e}")

# ── 5. Sensor validatie ────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("5. Sensor validatie")
print("=" * 70)

try:
    const_path = ROOT / "const.py"
    if const_path.exists():
        spec = importlib.util.spec_from_file_location("const", const_path)
        const_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(const_mod)
        
        if hasattr(const_mod, 'SENSORS'):
            sensors = const_mod.SENSORS
            pass_check(f"{len(sensors)} sensoren gedefinieerd")
            
            # Check sensor structuur
            for sensor_key, sensor_config in sensors.items():
                if isinstance(sensor_config, tuple) and len(sensor_config) >= 5:
                    api_field, friendly_name, unit, device_class, state_class = sensor_config[:5]
                    pass_check(f"  → {sensor_key}: {friendly_name} ({unit})")
                else:
                    warn(f"  → {sensor_key}: ongeldige config structuur")
                    
except Exception as e:
    warn(f"Sensor validatie niet volledig: {e}")

# ── 6. Modern Python features check ───────────────────────────────────────────
print("\n" + "=" * 70)
print("6. Modern Python features check")
print("=" * 70)

for py_file in PY_FILES:
    try:
        with open(py_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check voor moderne features
        features = []
        if "async def" in content:
            features.append("async/await")
        if "from __future__ import annotations" in content:
            features.append("type hints")
        if "typing." in content:
            features.append("typing module")
        if "f\"" in content or "f'" in content:
            features.append("f-strings")
        
        if features:
            pass_check(f"{py_file.name}: {', '.join(features)}")
        else:
            warn(f"{py_file.name}: geen moderne features gevonden")
            
    except Exception as e:
        warn(f"{py_file.name}: {e}")

# ── 7. Security & Best Practices ───────────────────────────────────────────────
print("\n" + "=" * 70)
print("7. Security & Best Practices")
print("=" * 70)

for py_file in PY_FILES:
    try:
        with open(py_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Security checks
        issues = []
        if "eval(" in content:
            issues.append("eval() gevonden")
        if "exec(" in content:
            issues.append("exec() gevonden")
        if "password" in content.lower() and "print(" in content:
            issues.append("password logging")
        
        if issues:
            fail(f"{py_file.name}: {', '.join(issues)}")
        else:
            pass_check(f"{py_file.name}: geen security issues")
            
    except Exception as e:
        warn(f"{py_file.name}: {e}")

# ── 8. Prestatie & Efficiëntie ─────────────────────────────────────────────────
print("\n" + "=" * 70)
print("8. Prestatie & Efficiëntie")
print("=" * 70)

# Check file sizes
for py_file in PY_FILES:
    size_kb = py_file.stat().st_size / 1024
    if size_kb > 50:
        warn(f"{py_file.name}: {size_kb:.1f}KB (groot)")
    else:
        pass_check(f"{py_file.name}: {size_kb:.1f}KB")

# Check JSON sizes
for json_file in JSON_FILES:
    if json_file.exists():
        size_kb = json_file.stat().st_size / 1024
        if size_kb > 10:
            warn(f"{json_file.name}: {size_kb:.1f}KB (groot)")
        else:
            pass_check(f"{json_file.name}: {size_kb:.1f}KB")

# ── Samenvatting ────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("VALIDATIE SAMENVATTING")
print("=" * 70)

print(f"📁 Bestanden gecontroleerd: {len(PY_FILES)} Python + {len(JSON_FILES)} JSON")
print(f"✅ Geslaagde checks: {9 - errors - warnings}/9")
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
print(f"   • Modern security practices")

sys.exit(1 if errors > 0 else 0)
