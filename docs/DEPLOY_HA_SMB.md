# Deploy Fresh-R naar Home Assistant (macOS + SMB) — plan

Dit document is het **vaste plan** (geen ad-hoc “proberen”). Houd je eraan in volgorde.

## Doel

| Wat | Waar |
|-----|------|
| Bron | Lokale repo: `custom_components/fresh_r/` |
| Doel op HA | Share `config` → pad `custom_components/fresh_r/` |
| Standaard | **`tar \| tar`** naar de doelmap (zie `scripts/smb_deploy_to_ha.sh`; fallback: ditto, `cp -R`) |

## Fase 0 — Eén repo, vaste tooling

1. Werk in **één** clone van dit project (geen dubbele mappen met verschillende scripts).
2. Scripts uitvoerbaar: `chmod +x scripts/smb_deploy_to_ha.sh scripts/install_smb_deploy_to_home.sh scripts/deploy_to_ha_smb.sh` (indien nodig).
3. Eén keer: `./scripts/install_smb_deploy_to_home.sh` → kopieert `smb_deploy_to_ha.sh` naar `~/.local/bin/`.
4. Zet in `~/.zshrc` (indien nodig): `export PATH="$HOME/.local/bin:$PATH"`.

## Fase 1 — Credentials (eenmalig / centraal)

- Bestand: `~/.config/smb_ha/deploy.env` (rechten `600`).
- Variabelen: `SMB_USER`, `SMB_PASS`, `HA_HOST`, `SHARE=config`.
- **Geen** wachtwoorden in git (`deploy.local.env` staat in `.gitignore`).

Optioneel repo-lokaal: `scripts/deploy.local.env` (kopieer van `deploy.local.env.example`).

## Fase 2 — Deploy (standaardpad)

**Standaard:** `tar` (stream naar share) — **geen** `--rsync` tenzij je dat bewust wilt.

```bash
cd /pad/naar/deze/repo
./scripts/smb_deploy_to_ha.sh --src ./custom_components/fresh_r --dst custom_components/fresh_r
```

Of via wrapper:

```bash
./scripts/deploy_to_ha_smb.sh
```

Of interactief (vraagt SMB-user/pass en schrijft `deploy.env`):

```bash
./scripts/smb_deploy_fresh_r_interactive.sh
```

**Rsync alleen** als expliciete keuze:

```bash
./scripts/smb_deploy_to_ha.sh --rsync --no-delete --src ./custom_components/fresh_r --dst custom_components/fresh_r
```

Of in `deploy.env`: `export SMB_DEPLOY_COPY=rsync`.

## Fase 3 — Definition of Done (deploy geslaagd)

**Op de Mac (terminal):**

1. Script eindigt met exit code **0**.
2. Eindregel: `OK: //<HA_HOST>/<SHARE>/<DEPLOY_DST>` (bijv. `OK: //192.168.2.5/config/custom_components/fresh_r`).
3. Er staat `(methode: tar — ...)` tenzij je `--rsync` gebruikt.

**Op Home Assistant (na deploy):**

1. **Instellingen → Systeem → Herstart** (of “Ontwikkelhulpmiddelen” → YAML herladen als je alleen custom components wijzigde — volledige herstart is het zekerst).
2. **Instellingen → Apparaten en diensten → Integraties** → Fresh-R zonder foutmelding; sensoren worden niet permanent `unavailable` door ontbrekende bestanden (dan deploy mislukt of verkeerde map).

**Checklist (afvinken):**

- [ ] `verify_fresh_r_deploy_ready.sh` lokaal groen (geen SMB)
- [ ] `install_smb_deploy_to_home.sh` minstens één keer na scriptwijzigingen
- [ ] Deploy-commando zonder `--rsync` (tenzij bewust)
- [ ] Terminal toont `OK: //...`
- [ ] HA herstart + integratie laadt

## Fase 4 — Escalatie (alleen als Fase 2 faalt)

1. **Diagnose share:** In Finder of HA file editor: bestaat `config/custom_components` als map? Is `fresh_r` een **map**, geen bestand?
2. **Rechten:** SMB-gebruiker mag schrijven in `config/custom_components/`.
3. **Rommel:** Verwijder vreemde bestanden op de share (bijv. oude `.sdr`) die niet in de repo zitten; **niet** in de integratie op lossen.
4. **Lege doelmap:** Hernoem `custom_components/fresh_r` op de share tijdelijk en deploy opnieuw (tar/ditto/cp).
5. **Alternatief:** SSH/SCP naar HA (add-on) — alleen als projectbeslissing; SMB op Mac blijft dan buiten scope.

## `icons/` op SMB

De map `custom_components/fresh_r/icons/` (SVG’s) wordt door **geen** Python-code van de integratie geladen. Op veel macOS+SMB-koppelingen **faalt** het aanmaken van die subdirectory.

**Standaard** slaat het deploy-script `icons/` over. Dat is voldoende voor een werkende integratie. Wil je ze tóch mee kopiëren: `SMB_DEPLOY_INCLUDE_ICONS=1` in `deploy.env` (vaak blijft het dan alsnog falen op de share).

## Wat we niet meer doen

- Geen eindeloze `mkdir`-trucs voor elke submap op SMB; standaard is **tar** die mappen tijdens extract aanmaakt (met uitzondering van optioneel overgeslagen `icons/`).
- Geen default “rsync eerst” op problematische SMB-stacks.

## Veelvoorkomende fout: `cd: too many arguments`

Plak **geen** uitleg op dezelfde regel als `cd` als je shell het pad splitst. Gebruik:

```bash
cd /Users/hemertje/Development/fresh-r-home-assistant
./scripts/verify_fresh_r_deploy_ready.sh
```

## Zie ook

- `README.md` → sectie “Deploy naar Home Assistant”
- `scripts/deploy.local.env.example`
