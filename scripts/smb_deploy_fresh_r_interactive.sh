#!/usr/bin/env bash
# Interactief: vraagt SMB-gebruikersnaam en wachtwoord, deployt Fresh-R naar HA.
# Voer UIT in Terminal op je Mac (dubbelklik werkt meestal niet voor wachtwoord-invoer).
#
# Gebruik:
#   cd /pad/naar/fresh-r-home-assistant
#   chmod +x scripts/smb_deploy_fresh_r_interactive.sh
#   ./scripts/smb_deploy_fresh_r_interactive.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SMB_BIN="${HOME}/.local/bin/smb_deploy_to_ha.sh"
if [[ ! -x "$SMB_BIN" ]]; then
  SMB_BIN="${SCRIPT_DIR}/smb_deploy_to_ha.sh"
fi
if [[ ! -f "$SMB_BIN" ]]; then
  echo "Ontbrekend: scripts/smb_deploy_to_ha.sh of voer uit: ./scripts/install_smb_deploy_to_home.sh" >&2
  exit 1
fi
chmod +x "$SMB_BIN" 2>/dev/null || true

echo ""
echo "=== SMB-login voor Home Assistant (${HA_HOST:-192.168.2.5}) ==="
echo ""

read -r -p "Gebruikersnaam (SMB): " SMB_USER
read -r -s -p "Wachtwoord: " SMB_PASS
echo "" >&2

if [[ -z "${SMB_USER}" || -z "${SMB_PASS}" ]]; then
  echo "Gebruikersnaam en wachtwoord zijn verplicht." >&2
  exit 1
fi

export SMB_USER SMB_PASS
export HA_HOST="${HA_HOST:-192.168.2.5}"
export SHARE="${SHARE:-config}"

# Veilig opslaan voor volgende keren (rechten alleen voor jou)
export CFG="${HOME}/.config/smb_ha/deploy.env"
mkdir -p "$(dirname "$CFG")"
python3 - <<'PY'
import os
p = os.path.expanduser(os.environ["CFG"])
os.makedirs(os.path.dirname(p), exist_ok=True)
u = os.environ["SMB_USER"]
w = os.environ["SMB_PASS"]
h = os.environ.get("HA_HOST", "192.168.2.5")
s = os.environ.get("SHARE", "config")
lines = [
    "# Automatisch aangemaakt door smb_deploy_fresh_r_interactive.sh",
    f"export SMB_USER={u!r}",
    f"export SMB_PASS={w!r}",
    f"export HA_HOST={h!r}",
    f"export SHARE={s!r}",
    "",
]
with open(p, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
os.chmod(p, 0o600)
print("Opgeslagen (alleen voor jou leesbaar):", p)
PY

echo ""
echo "=== Deploy Fresh-R → HA ==="
# Deploy gebruikt standaard ditto (zie smb_deploy_to_ha.sh). --no-delete helpt alleen bij SMB_DEPLOY_COPY=rsync.
exec "$SMB_BIN" --no-delete --src "${REPO_ROOT}/custom_components/fresh_r" --dst custom_components/fresh_r
