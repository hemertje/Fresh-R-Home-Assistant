# HA-overzicht (levend)

**Doel:** één plek voor “wat hangt waaraan”, zodat nieuwe korte chats niet opnieuw het hele huis moeten reconstrueren.

**Gebruik:** nieuwe chat → `@docs/HA-OVERZICHT.md` → taak doen → hier 2–5 regels bijwerken als er iets wezenlijks wijzigt.

**Niet:** dump van alle entities. Wel: systemen, relaties, recente wijzigingen, open punten.

Laatst bijgewerkt: 2026-08-21

---

## Relatiekaart (voorbeeld)

```text
[HA Core]
   ├── Fresh-R (custom integration, deze repo)
   ├── UniFi Network Application (addon) ──► UniFi controller / APs
   ├── Terminal & SSH (addon)
   ├── Zendure (Gielz + Node-RED proxy) ──► 2× SolarFlow  (zie docs/Zendure-…)
   └── Backups (native / generational)
```

Andere YAML/packages staan vaak in **DAO-Algemeen** / **DAO_Zendure** — niet alles in deze Fresh-R-repo.

---

## Addons / integraties

| Systeem | Rol | Notities |
|--------|-----|----------|
| Fresh-R | Ventilatie / sensors | Bron: deze repo; deploy via `docs/DEPLOY_HA_SMB.md` |
| UniFi Network Application | Netwerk in HA | *Voorbeeld 2026-08-21:* addon ≈5.2.0; app/controller ≈10.5.67 — **verifieer in HA vóór je dit als feit gebruikt** |
| Terminal & SSH | Shell in HA | *Voorbeeld:* 10.4.x — spot-check SSH na update |
| Zendure / zenSDK | Batterij / solar | Proxy-repo apart; samenvatting: `docs/Zendure-zenSDK-proxy-samenvatting.md` |

---

## Netwerk / UniFi

- **Relatie:** UniFi-addon in HA ↔ controller/UI ↔ devices (APs, switches).
- **Update-ritueel (voorbeeld):** backup → addon updaten → UI + device-connectivity checken.
- **Open / risico:** na major addon-update eerst controller-login en één AP-status controleren.

---

## Energie

- Zendure via HA-integratie + eventueel Node-RED proxy (2 devices als 1).
- Detail en flow: `docs/Zendure-zenSDK-proxy-samenvatting.md`.
- WP / DHW / EV: vaak in DAO-docs, niet hier herhalen.

---

## Backups

- Vóór addon-/core-updates: HA-backup.
- Spot-check na update: één kritieke automation of SSH/web terminal.

---

## Recente wijzigingen (voorbeeldregels)

| Datum | Wat | Check |
|-------|-----|--------|
| 2026-08-21 | UniFi Network Application 5.1.1→5.2.0 (voorbeeld) | UI + devices |
| 2026-08-21 | Terminal & SSH 10.3→10.4 (voorbeeld) | SSH + web terminal |
| 2026-08-21 | Model-dumps uit Fresh-R-repo gehaald; `.gitignore` | — |

*(Vervang “voorbeeld” door echte versies zodra je ze in HA hebt bevestigd.)*

---

## Open punten

- [ ] Versienummers hierboven live verifiëren in HA Supervisor
- [ ] Link toevoegen naar DAO-Algemeen package-paden die jij vaak raakt
- [ ] Eventueel korte “wie praat met wie” voor Fresh-R MQTT/Influx als je dat gebruikt

---

## Gerelateerde docs in deze repo

- `docs/DEPLOY_HA_SMB.md` — deploy
- `docs/Zendure-zenSDK-proxy-samenvatting.md` — energie-proxy
- `docs/FAQ.md` — Fresh-R integratie-FAQ
- `README.md` — installatie Fresh-R
