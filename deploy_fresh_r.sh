#!/usr/bin/env bash
# Deploy custom_components/fresh_r naar Home Assistant via SMB.
#
# Methode A — share al gemount (Finder → smb://<host>/config):
#   ./deploy_fresh_r.sh
#
# Methode B — smbclient (Homebrew: brew install samba):
#   ./deploy_fresh_r.sh
#   (wachtwoord: eerst macOS-sleutelhanger, anders SMB_PASSWORD / ~/.config/hass-smb-credentials)
#
# Sleutelhanger: bij eerste Finder-verbinding met smb://192.168.2.5 opgeslagen wachtwoord wordt
# automatisch gelezen (security find-internet-password). Eerste keer kan macOS om toestemming vragen.
# Uitzetten: SMB_SKIP_KEYCHAIN=1
#
# Windows: deploy_fresh_r.bat

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${SCRIPT_DIR}/custom_components/fresh_r"
RSYNC_DEST="${HA_DEPLOY_DEST:-/Volumes/config/custom_components/fresh_r}"

SMB_SERVER="${SMB_SERVER:-192.168.2.5}"
SMB_SHARE="${SMB_SHARE:-config}"
SMB_USER="${SMB_USER:-homeassistant}"
# set -u: altijd gezet vóór "${SMB_EXTRA[@]}" in subshells/pipelines
SMB_AUTH_ARGS=()
SMB_EXTRA=()

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

# Leest SMB-wachtwoord uit macOS Keychain (opgeslagen bij Verbinden met server).
_password_from_macos_keychain() {
  local host="${SMB_SERVER:-192.168.2.5}"
  local account="${SMB_KEYCHAIN_ACCOUNT:-$SMB_USER}"
  local p=""
  # Typisch voor SMB/CIFS in Finder
  p=$(security find-internet-password -s "$host" -a "$account" -w 2>/dev/null) && [[ -n "$p" ]] && { printf '%s' "$p"; return 0; }
  p=$(security find-internet-password -s "$host" -w 2>/dev/null) && [[ -n "$p" ]] && { printf '%s' "$p"; return 0; }
  # Soms als generic (verschillende macOS-versies)
  p=$(security find-generic-password -s "$host" -a "$account" -w 2>/dev/null) && [[ -n "$p" ]] && { printf '%s' "$p"; return 0; }
  p=$(security find-generic-password -l "smb://${host}" -w 2>/dev/null) && [[ -n "$p" ]] && { printf '%s' "$p"; return 0; }
  p=$(security find-generic-password -l "smb://${host}/${SMB_SHARE}" -w 2>/dev/null) && [[ -n "$p" ]] && { printf '%s' "$p"; return 0; }
  return 1
}

_build_smb_auth_args() {
  SMB_AUTH_ARGS=()
  SMB_EXTRA=()
  if [[ -n "${SMB_EXTRA_OPTS:-}" ]]; then
    # shellcheck disable=SC2206
    SMB_EXTRA=( ${SMB_EXTRA_OPTS} )
  fi
  if [[ "${SMB_GUEST:-0}" == "1" ]] || [[ "${SMB_USE_GUEST:-0}" == "1" ]]; then
    SMB_AUTH_ARGS=(-N)
  elif [[ -n "${SMB_AUTH_FILE:-}" ]] && [[ -f "$SMB_AUTH_FILE" ]]; then
    SMB_AUTH_ARGS=(-A "$SMB_AUTH_FILE")
  elif [[ -n "${SMB_PASSWORD:-}" ]]; then
    SMB_AUTH_ARGS=(-U "${SMB_USER}%${SMB_PASSWORD}")
  elif [[ -f "${HOME}/.config/hass-smb-credentials" ]]; then
    SMB_AUTH_ARGS=(-A "${HOME}/.config/hass-smb-credentials")
  fi
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
  local base="$SCRIPT_DIR/custom_components/fresh_r"
  local batch
  batch=$(mktemp)
  # shellcheck disable=SC2064
  trap "rm -f '$batch'" RETURN

  echo "→ Methode: smbclient (batch mkdir+put) → //$SMB_SERVER/$SMB_SHARE/custom_components/fresh_r"
  echo "   (Homebrew smbclient heeft geen tar-modus zonder libarchive — daarom per bestand)"

  {
    echo "cd custom_components"
    echo "mkdir fresh_r"
    echo "cd fresh_r"
    # mkdir alleen laatste segment na cd fresh_r (smbclient accepteert geen fresh_r/icons in één mkdir op alle servers)
    find "$base" -mindepth 1 -type d 2>/dev/null | while IFS= read -r d; do
      rel="${d#$base/}"
      echo "$rel"
    done | awk -F/ '{print NF-1, $0}' | sort -n | cut -d' ' -f2- | while IFS= read -r rel; do
      [[ -n "$rel" ]] && printf 'mkdir "%s"\n' "${rel//\"/\\\"}"
    done
    find "$base" -type f ! -path '*/__pycache__/*' ! -name '*.pyc' -print0 |
      while IFS= read -r -d '' f; do
        rel="${f#$base/}"
        printf 'put "%s" "%s"\n' "${f//\"/\\\"}" "${rel//\"/\\\"}"
      done
  } >"$batch"

  "$smbclient_bin" "//$SMB_SERVER/$SMB_SHARE" "${auth_args[@]}" -b 8192 <"$batch"

  # Sommige SMB-stacks falen op mkdir icons in één batch — fallback per SVG
  if [[ -d "$base/icons" ]]; then
    for svg in "$base/icons"/*; do
      [[ -f "$svg" ]] || continue
      bn=$(basename "$svg")
      "$smbclient_bin" "//$SMB_SERVER/$SMB_SHARE" "${auth_args[@]}" \
        -c "cd custom_components/fresh_r; mkdir icons; put \"$svg\" \"icons/$bn\"" 2>/dev/null \
        || "$smbclient_bin" "//$SMB_SERVER/$SMB_SHARE" "${auth_args[@]}" \
          -c "cd custom_components/fresh_r/icons; put \"$svg\" \"$bn\"" 2>/dev/null \
        || echo "   (waarschuwing) kon niet uploaden: icons/$bn — kopieer handmatig of gebruik deploy_fresh_r.bat"
    done
  fi

  echo "   Upload voltooid."
}

if [[ ! -d "$SRC" ]]; then
  echo "ERROR: Bronmap ontbreekt: $SRC"
  exit 1
fi

_build_smb_auth_args

# 1) rsync als /Volumes/config beschikbaar is
if [[ -d "$(dirname "$RSYNC_DEST")" ]] && [[ -w "$(dirname "$RSYNC_DEST")" ]] 2>/dev/null; then
  _deploy_rsync
  echo "→ Klaar. Herstart Home Assistant."
  echo "   Versie: $(grep '"version"' "${RSYNC_DEST}/manifest.json" | head -1)"
  exit 0
fi

# 2) smbclient — zo nodig wachtwoord uit Keychain (geen rsync)
SC="$(_find_smbclient || true)"
if [[ -z "$SC" ]]; then
  echo "ERROR: Geen gemounte share ($RSYNC_DEST) en geen smbclient."
  echo "       Installeer:  brew install samba"
  echo "       Of mount:    Finder → smb://${SMB_SERVER}/${SMB_SHARE}"
  exit 1
fi

if [[ ${#SMB_AUTH_ARGS[@]} -eq 0 ]] && [[ "$(uname -s)" == "Darwin" ]] && [[ "${SMB_SKIP_KEYCHAIN:-0}" != "1" ]]; then
  if KC=$(_password_from_macos_keychain); then
    export SMB_PASSWORD="$KC"
    echo "→ Wachtwoord uit macOS-sleutelhanger (Keychain) voor //$SMB_SERVER"
    _build_smb_auth_args
  fi
fi

if [[ ${#SMB_AUTH_ARGS[@]} -eq 0 ]]; then
  echo "ERROR: SMB-referentie ontbreekt voor smbclient."
  echo "       Zorg dat het wachtwoord in Sleutelhangertoegang staat (SMB naar ${SMB_SERVER}), of:"
  echo "       export SMB_PASSWORD='...'"
  echo "       of: ~/.config/hass-smb-credentials  (username= / password=)"
  echo "       Of: SMB_SKIP_KEYCHAIN=1 overslaan en handmatig wachtwoord zetten."
  exit 1
fi

# Extra smbclient-opties (SMB_EXTRA_OPTS) samenvoegen — niet in functie met local + set -u combineren
CLIENT_SMB_ARGS=("${SMB_AUTH_ARGS[@]}")
if [[ -n "${SMB_EXTRA+x}" ]] && [[ ${#SMB_EXTRA[@]} -gt 0 ]]; then
  CLIENT_SMB_ARGS+=("${SMB_EXTRA[@]}")
fi
_deploy_smbclient "$SC" "${CLIENT_SMB_ARGS[@]}"

echo "→ Klaar. Herstart Home Assistant (Instellingen → Systeem → Herstart)."
echo "   Controleer in HA dat custom_components/fresh_r/manifest.json versie 2.2.4 heeft."
