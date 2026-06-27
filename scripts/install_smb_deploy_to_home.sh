#!/usr/bin/env bash
# Installeer de GENERIEKE SMB-deploy buiten deze repo:
#   - script  -> ~/.local/bin/smb_deploy_to_ha.sh  (overal aanroepbaar)
#   - voorbeeld inlog -> ~/.config/smb_ha/deploy.env.example
#   - als deploy.env nog niet bestaat: kopieer voorbeeld naar ~/.config/smb_ha/deploy.env
#
# Eén keer uitvoeren vanuit een willekeurige clone van dit project:
#   ./scripts/install_smb_deploy_to_home.sh
#
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
CFG_DIR="${HOME}/.config/smb_ha"

mkdir -p "$BIN_DIR" "$CFG_DIR"

install -m 0755 "${SCRIPT_DIR}/smb_deploy_to_ha.sh" "${BIN_DIR}/smb_deploy_to_ha.sh"
install -m 0644 "${SCRIPT_DIR}/deploy.local.env.example" "${CFG_DIR}/deploy.env.example"

if [[ ! -f "${CFG_DIR}/deploy.env" ]]; then
  cp "${CFG_DIR}/deploy.env.example" "${CFG_DIR}/deploy.env"
  echo "Aangemaakt: ${CFG_DIR}/deploy.env  — vul SMB_USER en SMB_PASS in."
else
  echo "Bestaand gelaten: ${CFG_DIR}/deploy.env"
fi

echo ""
echo "Klaar. Voeg evt. toe aan ~/.zshrc of ~/.bash_profile (als ~/.local/bin nog niet in PATH staat):"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo ""
echo "Gebruik vanuit ELKE projectmap:"
echo "  smb_deploy_to_ha.sh --src ./custom_components/mijn_integratie --dst custom_components/mijn_integratie"
echo ""
