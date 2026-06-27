#!/usr/bin/env bash
# Lokale controle vóór SMB-deploy (geen netwerk, geen mount).
# Exit 0 = bronmap en scripts zien er goed uit.
#
#   ./scripts/verify_fresh_r_deploy_ready.sh
#
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FR="${ROOT}/custom_components/fresh_r" 

ERR=0
ok() { echo "  OK: $1"; }
fail() { echo "  FOUT: $1" >&2; ERR=1; }

echo "== Fresh-R deploy — lokale controle (repo: ${ROOT})"
echo ""

[[ -d "$FR" ]] || fail "Ontbrekend: custom_components/fresh_r"
[[ -d "$FR" ]] && ok "Map custom_components/fresh_r bestaat"

[[ -f "$FR/manifest.json" ]] || fail "Ontbrekend: custom_components/fresh_r/manifest.json"
[[ -f "$FR/manifest.json" ]] && ok "manifest.json aanwezig"

[[ -f "$FR/__init__.py" ]] || fail "Ontbrekend: custom_components/fresh_r/__init__.py"
[[ -f "$FR/__init__.py" ]] && ok "__init__.py aanwezig"

[[ -f "$SCRIPT_DIR/smb_deploy_to_ha.sh" ]] || fail "Ontbrekend: scripts/smb_deploy_to_ha.sh"
[[ -x "$SCRIPT_DIR/smb_deploy_to_ha.sh" ]] || fail "Niet uitvoerbaar: chmod +x scripts/smb_deploy_to_ha.sh"
[[ -x "$SCRIPT_DIR/smb_deploy_to_ha.sh" ]] && ok "smb_deploy_to_ha.sh uitvoerbaar"

[[ -f "$SCRIPT_DIR/install_smb_deploy_to_home.sh" ]] || fail "Ontbrekend: scripts/install_smb_deploy_to_home.sh"
[[ -x "$SCRIPT_DIR/install_smb_deploy_to_home.sh" ]] || fail "Niet uitvoerbaar: chmod +x scripts/install_smb_deploy_to_home.sh"
[[ -x "$SCRIPT_DIR/install_smb_deploy_to_home.sh" ]] && ok "install_smb_deploy_to_home.sh uitvoerbaar"

if [[ -f "${HOME}/.local/bin/smb_deploy_to_ha.sh" ]]; then
  ok "~/.local/bin/smb_deploy_to_ha.sh bestaat (na install)"
else
  echo "  (tip: ./scripts/install_smb_deploy_to_home.sh om script naar ~/.local/bin te kopiëren)"
fi

if [[ -f "${HOME}/.config/smb_ha/deploy.env" ]]; then
  ok "~/.config/smb_ha/deploy.env bestaat"
else
  echo "  (tip: ./scripts/smb_deploy_fresh_r_interactive.sh of maak deploy.env — zie docs/DEPLOY_HA_SMB.md)"
fi

echo ""
if [[ "$ERR" -eq 0 ]]; then
  echo "RESULTAAT: lokale controle geslaagd. Volgende stap (op aparte regels, geen comment achter cd):"
  echo "  ./scripts/smb_deploy_to_ha.sh --src ./custom_components/fresh_r --dst custom_components/fresh_r"
  echo "Zie: docs/DEPLOY_HA_SMB.md (Definition of Done)"
  exit 0
fi
echo "RESULTAAT: controle gefaald — los bovenstaande punten op." >&2
exit 1
