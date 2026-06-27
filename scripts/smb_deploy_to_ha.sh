#!/usr/bin/env bash
# Generiek: kopieer een lokale map naar je Home Assistant config-share over SMB (macOS).
# Standaard: tar|tar (werkt op veel SMB-mounts beter dan ditto/rsync). Optioneel: --rsync.
#
# Vereist: lokale bronmap (--src) en doelpad op de share (--dst), bv. custom_components/foo of www.
#
# Inlog (eenmalig in een bestand, zie deploy.local.env.example):
#   cp scripts/deploy.local.env.example scripts/deploy.local.env
#   open -e scripts/deploy.local.env
#
# Voorbeelden:
#   ./scripts/smb_deploy_to_ha.sh --src ./custom_components/fresh_r --dst custom_components/fresh_r
#   ./scripts/smb_deploy_to_ha.sh --rsync --no-delete --src ./custom_components/fresh_r --dst custom_components/fresh_r
# Fallback-keten bij fout: tar → ditto → cp -R
#
# Credentials (centraal, buiten deze repo):
#   ~/.config/smb_ha/deploy.env
# Optioneel in een repo: scripts/deploy.local.env
#
# Eén keer installeren voor overal bruikbaar:
#   ./scripts/install_smb_deploy_to_home.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'USAGE'
Generieke SMB-deploy naar Home Assistant (macOS).

Gebruik:
  smb_deploy_to_ha.sh --src PAD_NA_LOKALE_MAP --dst PAD_OP_SHARE [opties]

Opties:
  --host HOST     (standaard: $HA_HOST of 192.168.2.5)
  --share NAAM    (standaard: $SHARE of config)
  --mount DIR     tijdelijke mountmap (standaard: ~/.cache/smb_ha_deploy_mount)
  --rsync         gebruik rsync i.p.v. tar (op sommige SMB-shares problematisch)
  --no-delete     alleen bij --rsync: rsync zonder --delete
  --full-delete   alleen bij --rsync: forceer rsync met --delete

Standaard: tar-stream naar doelmap. Zet SMB_DEPLOY_COPY=rsync in deploy.env om rsync te forceren.

Standaard wordt custom_components/.../icons overgeslagen (SMB kan die map vaak niet aanmaken).
Zet SMB_DEPLOY_INCLUDE_ICONS=1 om icons tóch mee te nemen.

Credentials: scripts/deploy.local.env of ~/.config/smb_ha/deploy.env
USAGE
}

DEPLOY_SRC="${DEPLOY_SRC:-}"
DEPLOY_DST="${DEPLOY_DST:-}"
HA_HOST="${HA_HOST:-192.168.2.5}"
SHARE="${SHARE:-config}"
DEPLOY_SMB_MOUNT="${DEPLOY_SMB_MOUNT:-${HOME}/.cache/smb_ha_deploy_mount}"
USE_RSYNC=0
RSYNC_DELETE=1
FORCE_RSYNC_DELETE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --src)   DEPLOY_SRC="$2"; shift 2 ;;
    --dst)   DEPLOY_DST="$2"; shift 2 ;;
    --host)  HA_HOST="$2"; shift 2 ;;
    --share) SHARE="$2"; shift 2 ;;
    --mount) DEPLOY_SMB_MOUNT="$2"; shift 2 ;;
    --rsync) USE_RSYNC=1; shift ;;
    --no-delete) RSYNC_DELETE=0; shift ;;
    --full-delete) FORCE_RSYNC_DELETE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "Onbekende optie: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

# Laad credentials (generiek + backward compatible)
set +u
mkdir -p "${HOME}/.config/smb_ha" 2>/dev/null || true
if [[ -f "${HOME}/.config/smb_ha/deploy.env" ]]; then
  # shellcheck source=/dev/null
  source "${HOME}/.config/smb_ha/deploy.env"
fi
if [[ -f "${HOME}/.config/fresh_r/deploy.env" ]]; then
  # shellcheck source=/dev/null
  source "${HOME}/.config/fresh_r/deploy.env"
fi
if [[ -f "${SCRIPT_DIR}/deploy.local.env" ]]; then
  # shellcheck source=/dev/null
  source "${SCRIPT_DIR}/deploy.local.env"
fi
set -u

if [[ "${SMB_DEPLOY_COPY:-}" == "rsync" ]]; then
  USE_RSYNC=1
fi
if [[ "${SMB_RSYNC_NO_DELETE:-0}" == "1" || "${SMB_RSYNC_NO_DELETE:-}" == "true" ]]; then
  RSYNC_DELETE=0
fi
if [[ "${FORCE_RSYNC_DELETE}" -eq 1 ]]; then
  RSYNC_DELETE=1
fi

# Veel SMB-mounts (macOS) kunnen geen subdirectory custom_components/fresh_r/icons aanmaken.
# Die SVG's worden door geen runtime-Python geladen — alleen optioneel voor branding.
SMB_DEPLOY_EXCLUDE_ICONS=1
if [[ "${SMB_DEPLOY_INCLUDE_ICONS:-0}" == "1" || "${SMB_DEPLOY_INCLUDE_ICONS:-}" == "true" ]]; then
  SMB_DEPLOY_EXCLUDE_ICONS=0
fi
export SMB_DEPLOY_EXCLUDE_ICONS

if [[ -z "${DEPLOY_SRC}" || -z "${DEPLOY_DST}" ]]; then
  echo "Fout: geef --src en --dst op (of zet DEPLOY_SRC en DEPLOY_DST)." >&2
  usage >&2
  exit 1
fi

if [[ ! -d "${DEPLOY_SRC}" ]]; then
  echo "Bron bestaat niet of is geen map: ${DEPLOY_SRC}" >&2
  exit 1
fi
DEPLOY_SRC="$(cd "${DEPLOY_SRC}" && pwd)"

DEPLOY_DST="${DEPLOY_DST#/}"

MNT="${DEPLOY_SMB_MOUNT}"
DST="${MNT}/${DEPLOY_DST}"

if ! command -v mount_smbfs >/dev/null 2>&1; then
  echo "mount_smbfs niet gevonden (alleen macOS)." >&2
  exit 1
fi

if [[ "${USE_RSYNC}" -eq 1 ]] && ! command -v rsync >/dev/null 2>&1; then
  echo "rsync niet gevonden (installeer rsync of laat --rsync weg voor tar)." >&2
  exit 1
fi

if ! command -v tar >/dev/null 2>&1; then
  echo "tar niet gevonden (verwacht op macOS)." >&2
  exit 1
fi

if [[ -z "${SMB_USER:-}" ]]; then
  read -r -p "SMB-gebruikersnaam [${USER}]: " _u || true
  SMB_USER="${_u:-$USER}"
fi

if [[ -z "${SMB_PASS:-}" ]]; then
  echo "" >&2
  echo "Geen SMB_PASS. Vul scripts/deploy.local.env of ~/.config/smb_ha/deploy.env" >&2
  echo "" >&2
  read -r -s -p "SMB-wachtwoord voor ${HA_HOST}: " SMB_PASS
  echo "" >&2
fi

if [[ -z "${SMB_PASS:-}" ]]; then
  echo "Geen wachtwoord — afgebroken." >&2
  exit 1
fi

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

echo "[1/4] Mount //${HA_HOST}/${SHARE} -> ${MNT}"
if ! mount_smbfs "$SMB_URL" "$MNT"; then
  echo "Mount mislukt." >&2
  exit 1
fi

cleanup() {
  echo "[4/4] Unmount ${MNT}"
  umount "$MNT" 2>/dev/null || true
}
trap cleanup EXIT

echo "[2/4] Doel: .../${DEPLOY_DST}"

# Alleen de basis-doelmap: segment-voor-segment (geen lege submappen forceren — dat faalt op jouw SMB).
_smb_mkdir_deep() {
  local root="$1"
  local rel="${2#/}"
  [[ -z "$rel" ]] && return 0
  local cur="$root"
  local rest="$rel"
  local seg
  while [[ "$rest" == */* ]]; do
    seg="${rest%%/*}"
    rest="${rest#*/}"
    cur="$cur/$seg"
    if [[ -e "$cur" && ! -d "$cur" ]]; then
      echo "    Verwijder blokkerend pad (geen map): $cur" >&2
      rm -f "$cur" 2>/dev/null || true
    fi
    mkdir "$cur" 2>/dev/null || mkdir -p "$cur" || {
      echo "Fout: kan map niet aanmaken: $cur" >&2
      return 1
    }
  done
  if [[ -n "$rest" ]]; then
    cur="$cur/$rest"
    if [[ -e "$cur" && ! -d "$cur" ]]; then
      rm -f "$cur" 2>/dev/null || true
    fi
    mkdir "$cur" 2>/dev/null || mkdir -p "$cur" || {
      echo "Fout: kan map niet aanmaken: $cur" >&2
      return 1
    }
  fi
}

_smb_mkdir_deep "$MNT" "$DEPLOY_DST"
rm -rf "${DST}/__pycache__" 2>/dev/null || true
if [[ ! -d "$DST" ]]; then
  echo "Fout: doelmap bestaat niet na aanmaken: ${DST}" >&2
  exit 1
fi

# tar|tar: maakt submappen tijdens extract. icons/ opt-out — veel SMB-fouten op .../icons.
_smb_copy_tree_tar() {
  export COPYFILE_DISABLE=1
  local ex=(
    --exclude='__pycache__'
    --exclude='.DS_Store'
    --exclude='.AppleDouble'
    --exclude='._*'
  )
  if [[ "${SMB_DEPLOY_EXCLUDE_ICONS:-1}" == "1" ]]; then
    ex+=(--exclude='icons' --exclude='./icons')
  fi
  ( cd "$1" && tar -cf - "${ex[@]}" . ) | ( cd "$2" && tar -xf - )
}

# Staging op lokale schijf (/tmp) dan naar share — SMB faait vaak op .../icons, niet op andere mappen.
_smb_copy_fallback() {
  local src="$1"
  local dst="$2"
  if [[ "${SMB_DEPLOY_EXCLUDE_ICONS:-1}" == "1" ]]; then
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/smb_ha_deploy.XXXXXX")"
    if ! _smb_copy_tree_tar "$src" "$tmp"; then
      rm -rf "$tmp"
      return 1
    fi
    if command -v ditto >/dev/null 2>&1; then
      echo "    (fallback: staging in /tmp + ditto naar share)" >&2
      if ditto "$tmp" "$dst"; then
        rm -rf "$tmp"
        return 0
      fi
    fi
    echo "    (fallback: staging + cp -R naar share)" >&2
    COPYFILE_DISABLE=1 cp -R "${tmp}/." "${dst}/"
    rm -rf "$tmp"
    return 0
  fi
  if command -v ditto >/dev/null 2>&1; then
    echo "    (fallback: ditto)" >&2
    ditto "$src" "$dst" && return 0
  fi
  echo "    (fallback: cp -R)" >&2
  COPYFILE_DISABLE=1 cp -R "${src}/." "${dst}/"
}

echo "[3/4] Kopiëren naar de share"
if [[ "${SMB_DEPLOY_EXCLUDE_ICONS:-1}" == "1" ]]; then
  echo "    (icons/ wordt overgeslagen — niet gebruikt door de integratie op HA; zie README)" >&2
fi
if [[ "${USE_RSYNC}" -eq 0 ]]; then
  echo "    (methode: tar — stream naar share; werkt vaak als ditto faalt op SMB)" >&2
  if ! _smb_copy_tree_tar "$DEPLOY_SRC" "$DST"; then
    echo "    tar mislukt — probeer fallback…" >&2
    _smb_copy_fallback "$DEPLOY_SRC" "$DST" || {
      echo "Fout: kopiëren naar ${DST} mislukt (tar, ditto en cp)." >&2
      exit 1
    }
  fi
  rm -rf "${DST}/__pycache__" 2>/dev/null || true
else
  if [[ "${RSYNC_DELETE}" -eq 1 ]]; then
    echo "    (methode: rsync met --delete)" >&2
  else
    echo "    (methode: rsync zonder --delete)" >&2
  fi
  RSYNC_CMD=(rsync -a \
    --no-perms --no-owner --no-group \
    --exclude '__pycache__' \
    --exclude '.DS_Store' \
    --exclude '.AppleDouble' \
    --exclude '._*' \
    "${DEPLOY_SRC}/" "${DST}/")
  if [[ "${SMB_DEPLOY_EXCLUDE_ICONS:-1}" == "1" ]]; then
    RSYNC_CMD=(rsync -a \
      --no-perms --no-owner --no-group \
      --exclude '__pycache__' \
      --exclude '.DS_Store' \
      --exclude '.AppleDouble' \
      --exclude '._*' \
      --exclude 'icons' \
      "${DEPLOY_SRC}/" "${DST}/")
  fi
  if [[ "${RSYNC_DELETE}" -eq 1 ]]; then
    RSYNC_CMD=(rsync -a --delete \
      --no-perms --no-owner --no-group \
      --exclude '__pycache__' \
      --exclude '.DS_Store' \
      --exclude '.AppleDouble' \
      --exclude '._*' \
      "${DEPLOY_SRC}/" "${DST}/")
    if [[ "${SMB_DEPLOY_EXCLUDE_ICONS:-1}" == "1" ]]; then
      RSYNC_CMD=(rsync -a --delete \
        --no-perms --no-owner --no-group \
        --exclude '__pycache__' \
        --exclude '.DS_Store' \
        --exclude '.AppleDouble' \
        --exclude '._*' \
        --exclude 'icons' \
        "${DEPLOY_SRC}/" "${DST}/")
    fi
  fi
  if ! "${RSYNC_CMD[@]}"; then
    echo "" >&2
    echo "rsync mislukt — fallback: tar → ditto → cp" >&2
    if ! _smb_copy_tree_tar "$DEPLOY_SRC" "$DST"; then
      _smb_copy_fallback "$DEPLOY_SRC" "$DST" || exit 1
    fi
    rm -rf "${DST}/__pycache__" 2>/dev/null || true
  fi
fi

echo ""
echo "OK: //${HA_HOST}/${SHARE}/${DEPLOY_DST}"
echo "    (bron: ${DEPLOY_SRC})"
if [[ "${SMB_DEPLOY_EXCLUDE_ICONS:-1}" == "1" ]]; then
  echo "    (icons/ niet gekopieerd — optioneel; zet SMB_DEPLOY_INCLUDE_ICONS=1 om te proberen)" >&2
fi
