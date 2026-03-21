#!/usr/bin/env bash
# Deploy custom_components/fresh_r naar Home Assistant via SMB.
#
# Methode A — share al gemount (Finder → smb://<host>/config):
#   ./deploy_fresh_r.sh
#
# Methode B — smbclient (Homebrew: brew install samba):
#   export SMB_PASSWORD='jouw-samba-wachtwoord'
#   ./deploy_fresh_r.sh
#   Of: SMB_AUTH_FILE=~/.config/hass-smb-credentials  (username= / password=)
#
# Windows: deploy_fresh_r.bat

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${SCRIPT_DIR}/custom_components/fresh_r"
RSYNC_DEST="${HA_DEPLOY_DEST:-/Volumes/config/custom_components/fresh_r}"

SMB_SERVER="${SMB_SERVER:-192.168.2.5}"
SMB_SHARE="${SMB_SHARE:-config}"
SMB_USER="${SMB_USER:-homeassistant}"

_find_smbclient() {
  if command -v smbclient >/dev/null 2>&1; then
    command -v smbclient
    return 0
  fi
  local p
  for p in \
    /opt/homebrew/opt/samba/bin/smbclient \
    /usr/local/opt/samba/bin/smbclient \
    /opt/homebrew/bin/smbclient \
    /usr/local/bin/smbclient
  do
    if [[ -x "$p" ]]; then
      echo "$p"
      return 0
    fi
  done
  return 1
}

_deploy_rsync() {
  echo "→ Methode: rsync naar gemounte share → $RSYNC_DEST"
  rm -rf "${RSYNC_DEST}/__pycache__" 2>/dev/null || true
  mkdir -p "$RSYNC_DEST/translations" "$RSYNC_DEST/icons"
  rsync -a --delete \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    "${SRC}/" "${RSYNC_DEST}/"
}

_deploy_smbclient() {
  local smbclient_bin="$1"
  shift
  local auth_args=("$@")

  echo "→ Methode: smbclient → //$SMB_SERVER/$SMB_SHARE → custom_components/fresh_r"
  echo "   (wachtwoord: SMB_PASSWORD of bestand ~/.config/hass-smb-credentials)"

  # Tar-stream naar Linux-SMB (forward slashes); oude __pycache__ blijft staan maar wordt niet overschreven door tar-exclude
  ( cd "${SCRIPT_DIR}/custom_components" && \
    tar --exclude='__pycache__' --exclude='*.pyc' -cf - fresh_r ) \
    | "$smbclient_bin" "//$SMB_SERVER/$SMB_SHARE" "${auth_args[@]}" "${SMB_EXTRA[@]}" \
      -c "cd custom_components; tar xf -"

  echo "   Upload voltooid."
}

if [[ ! -d "$SRC" ]]; then
  echo "ERROR: Bronmap ontbreekt: $SRC"
  exit 1
fi

# --- Auth voor smbclient ---
SMB_AUTH_ARGS=()
SMB_EXTRA=( ${SMB_EXTRA_OPTS:-} )
if [[ "${SMB_GUEST:-0}" == "1" ]] || [[ "${SMB_USE_GUEST:-0}" == "1" ]]; then
  SMB_AUTH_ARGS=(-N)
elif [[ -n "${SMB_AUTH_FILE:-}" ]] && [[ -f "$SMB_AUTH_FILE" ]]; then
  SMB_AUTH_ARGS=(-A "$SMB_AUTH_FILE")
elif [[ -n "${SMB_PASSWORD:-}" ]]; then
  SMB_AUTH_ARGS=(-U "${SMB_USER}%${SMB_PASSWORD}")
elif [[ -f "${HOME}/.config/hass-smb-credentials" ]]; then
  SMB_AUTH_ARGS=(-A "${HOME}/.config/hass-smb-credentials")
fi

# 1) rsync als /Volumes/config beschikbaar is
if [[ -d "$(dirname "$RSYNC_DEST")" ]] && [[ -w "$(dirname "$RSYNC_DEST")" ]] 2>/dev/null; then
  _deploy_rsync
  echo "→ Klaar. Herstart Home Assistant."
  echo "   Versie: $(grep '"version"' "${RSYNC_DEST}/manifest.json" | head -1)"
  exit 0
fi

# 2) smbclient
SC="$(_find_smbclient || true)"
if [[ -z "$SC" ]]; then
  echo "ERROR: Geen gemounte share ($RSYNC_DEST) en geen smbclient."
  echo "       Installeer:  brew install samba"
  echo "       Of mount:    Finder → smb://${SMB_SERVER}/${SMB_SHARE}"
  exit 1
fi

if [[ ${#SMB_AUTH_ARGS[@]} -eq 0 ]]; then
  echo "ERROR: SMB-referentie ontbreekt voor smbclient."
  echo "       export SMB_PASSWORD='...'"
  echo "       of maak ~/.config/hass-smb-credentials met:"
  echo "         username=${SMB_USER}"
  echo "         password=..."
  exit 1
fi

_deploy_smbclient "$SC" "${SMB_AUTH_ARGS[@]}"

echo "→ Klaar. Herstart Home Assistant (Instellingen → Systeem → Herstart)."
echo "   Controleer in HA dat custom_components/fresh_r/manifest.json versie 2.2.4 heeft."
