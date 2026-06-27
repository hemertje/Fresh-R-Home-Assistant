#!/usr/bin/env bash
# Eén-commando deploy: custom_components/fresh_r -> Home Assistant over SMB (macOS).
# Geen handmatig slepen in Finder; rsync met --delete houdt bron en doel gelijk.
#
# Gebruik (in Terminal):
#   cd /pad/naar/Fresh-R-Home-Assistant
#   ./scripts/deploy_to_ha_smb.sh
#
# Het script vraagt zo nodig om SMB-gebruikersnaam en wachtwoord (wachtwoord: verborgen invoer).
# Optioneel vooraf zetten: SMB_USER, SMB_PASS, HA_HOST, SHARE
#
set -euo pipefail

HA_HOST="${HA_HOST:-192.168.2.5}"
SHARE="${SHARE:-config}"
DEST_SUBPATH="${DEST_SUBPATH:-custom_components/fresh_r}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC="$REPO_ROOT/custom_components/fresh_r"

MNT="${DEPLOY_SMB_MOUNT:-$REPO_ROOT/.smb_ha_mount}"
DST="$MNT/$DEST_SUBPATH"

if [[ ! -d "$SRC" ]]; then
  echo "Bronmap ontbreekt: $SRC" >&2
  exit 1
fi

if ! command -v mount_smbfs >/dev/null 2>&1; then
  echo "mount_smbfs niet gevonden (alleen macOS)." >&2
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync niet gevonden." >&2
  exit 1
fi

# --- Credentials (interactief als niet gezet; wachtwoord niet in shell history) ---
if [[ -z "${SMB_USER:-}" ]]; then
  read -r -p "SMB-gebruikersnaam [${USER}]: " _u || true
  SMB_USER="${_u:-$USER}"
fi

if [[ -z "${SMB_PASS:-}" ]]; then
  read -r -s -p "SMB-wachtwoord voor ${HA_HOST}: " SMB_PASS
  echo "" >&2
fi

if [[ -z "${SMB_PASS}" ]]; then
  echo "Geen wachtwoord ingevoerd." >&2
  exit 1
fi

# SMB-URL met correct ge-encode user/pass (speciale tekens in wachtwoord)
export SMB_USER SMB_PASS HA_HOST SHARE
SMB_URL="$(python3 - <<'PY'
import os, urllib.parse
u = urllib.parse.quote(os.environ["SMB_USER"], safe="")
p = urllib.parse.quote(os.environ["SMB_PASS"], safe="")
host = os.environ["HA_HOST"]
share = os.environ["SHARE"]
print(f"smb://{u}:{p}@{host}/{share}")
PY
)"

umount "$MNT" 2>/dev/null || true
mkdir -p "$MNT"

echo "[1/4] Mount //${HA_HOST}/${SHARE} -> $MNT"
if ! mount_smbfs "$SMB_URL" "$MNT"; then
  echo "Mount mislukt. Controleer gebruikersnaam/wachtwoord en share-naam (SHARE=${SHARE})." >&2
  exit 1
fi

cleanup() {
  echo "[4/4] Unmount $MNT"
  umount "$MNT" 2>/dev/null || true
}
trap cleanup EXIT

echo "[2/4] Verwijder __pycache__ op doel"
rm -rf "$DST/__pycache__" 2>/dev/null || true

echo "[3/4] rsync (bron -> HA, inclusief verwijderen oude bestanden in doel)"
mkdir -p "$DST"
rsync -a --delete \
  --exclude '__pycache__' \
  --exclude '.DS_Store' \
  "$SRC/" "$DST/"

echo ""
echo "OK: bestanden staan op //${HA_HOST}/${SHARE}/${DEST_SUBPATH}"
echo "    Herstart nu Home Assistant (Instellingen -> Systeem -> Herstarten)."
if [[ -f "$DST/manifest.json" ]]; then
  echo "    manifest.json aanwezig op doel."
fi
