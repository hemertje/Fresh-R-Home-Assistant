#!/usr/bin/env bash
# Deploy custom_components/fresh_r to Home Assistant (macOS + SMB share "config")
#
# 1. In Finder: Cmd+K → smb://192.168.2.5/config  (login als je Samba-user)
# 2. Zorg dat de share als /Volumes/config verschijnt (of zet HA_DEPLOY_DEST)
# 3: ./deploy_fresh_r.sh
#
# Of: gebruik deploy_fresh_r.bat op Windows met \\192.168.2.5\config

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${SCRIPT_DIR}/custom_components/fresh_r"
DEST="${HA_DEPLOY_DEST:-/Volumes/config/custom_components/fresh_r}"

if [[ ! -d "$SRC" ]]; then
  echo "ERROR: Bronmap ontbreekt: $SRC"
  exit 1
fi

if [[ ! -d "$(dirname "$DEST")" ]] || [[ ! -w "$(dirname "$DEST")" ]] 2>/dev/null; then
  echo "ERROR: SMB-share 'config' is niet gemount of niet beschrijfbaar."
  echo "       Finder → Verbinden met server → smb://192.168.2.5/config"
  echo "       Of: export HA_DEPLOY_DEST=/pad/naar/jouw/gemounte/config/custom_components/fresh_r"
  exit 1
fi

echo "→ Verwijderen __pycache__ op HA…"
rm -rf "${DEST}/__pycache__" 2>/dev/null || true

echo "→ Kopiëren naar: $DEST"
mkdir -p "$DEST/translations" "$DEST/icons"
rsync -a --delete \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  "${SRC}/" "${DEST}/"

echo "→ Klaar. Herstart Home Assistant (Instellingen → Systeem → Herstart)."
echo "   Versie in manifest: $(grep '"version"' "${DEST}/manifest.json" | head -1)"
