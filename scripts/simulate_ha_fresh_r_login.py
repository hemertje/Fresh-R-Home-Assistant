#!/usr/bin/env python3
# fresh_r_simulator v2 — laadt api.py via importlib (geen homeassistant nodig).
# Check: regel ~149 moet `api_mod = _load_fresh_r_api_only()` zijn, NIET `from custom_components.fresh_r.api import`.
"""Simuleer Home Assistant: zelfde login als de integratie (FreshRApiClient.async_login).

Gebruik (vanaf de repo-root):

  export FRESH_R_EMAIL='jij@voorbeeld.nl'
  export FRESH_R_PASSWORD='...'
  PYTHONPATH=. python3 scripts/simulate_ha_fresh_r_login.py

Optioneel uitgebreide HTTP-log (zoals DEEP_DEBUG in api.py):

  FRESH_R_DEEP_DEBUG=1 PYTHONPATH=. python3 scripts/simulate_ha_fresh_r_login.py

Geen wachtwoord in dit bestand zetten; alleen omgevingsvariabelen.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

# Repo-root (voor pad naar api.py / const.py)
_ROOT = Path(__file__).resolve().parent.parent


def _load_fresh_r_api_only():
    """Laad alleen ``api.py`` (+ ``const.py``). Sla ``fresh_r/__init__.py`` over — die importeert Home Assistant.

    Zonder deze truc: ``from custom_components.fresh_r.api import …`` triggert eerst ``__init__.py``.
    """
    import importlib.util
    import types

    fr = _ROOT / "custom_components" / "fresh_r"
    for name, p in (
        ("custom_components", _ROOT / "custom_components"),
        ("custom_components.fresh_r", fr),
    ):
        if name not in sys.modules:
            m = types.ModuleType(name)
            m.__path__ = [str(p)]
            sys.modules[name] = m

    def _exec(name: str, path: Path):
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Kan {name} niet laden vanuit {path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod

    _exec("custom_components.fresh_r.const", fr / "const.py")
    return _exec("custom_components.fresh_r.api", fr / "api.py")


def _ha_like_logging() -> None:
    """Vergelijkbaar met veel HA-core logregels: naam + bericht, UTC-tijd."""
    fmt = (
        "%(asctime)s %(levelname)s (%(name)s) %(message)s"
    )
    logging.basicConfig(level=logging.DEBUG, format=fmt, datefmt="%Y-%m-%d %H:%M:%S")
    # Standaard lawaai omlaag
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.client").setLevel(logging.WARNING)
    # Integratie: alles zichtbaar zoals bij logger in HA
    for name in (
        "custom_components.fresh_r",
        "custom_components.fresh_r.api",
    ):
        logging.getLogger(name).setLevel(logging.DEBUG)


def _mask_secret(value: str, keep_start: int = 8, keep_end: int = 4) -> str:
    if not value or len(value) <= keep_start + keep_end:
        return "***"
    return f"{value[:keep_start]}…{value[-keep_end:]}"


def _log_session_as_ha(client, log: logging.Logger) -> None:
    """Samenvatting na login: token + cookie-namen (waarden gemaskeerd)."""
    tok = getattr(client, "_token", None)
    if tok:
        log.info(
            "── Resultaat (zoals HA na async_login): token=%s (lengte=%s)",
            _mask_secret(tok),
            len(tok),
        )
    else:
        log.warning("── Geen self._token gezet na login.")

    sess = getattr(client, "_session", None)
    if not sess or sess.closed:
        log.warning("── Geen actieve _session.")
        return

    jar = sess.cookie_jar
    rows = []
    try:
        for c in jar:
            key = getattr(c, "key", "?")
            v = getattr(c, "value", "") or ""
            try:
                dom = c["domain"]
            except Exception:
                dom = getattr(c, "domain", "")
            if len(v) > 16 and all(ch in "0123456789abcdefABCDEF" for ch in v):
                disp = _mask_secret(v)
            elif len(v) > 8:
                disp = v[:4] + "…"
            else:
                disp = "***"
            rows.append(f"  • {key}={disp} (domain={dom})")
    except Exception as err:  # noqa: BLE001
        log.debug("Cookie-iteratie: %s", err)
        return

    if rows:
        log.info("── Cookie jar (dashboard/fresh-r), waarden gemaskeerd:\n%s", "\n".join(rows))
    else:
        log.info("── Cookie jar: leeg na login (onverwacht).")


async def _run() -> int:
    email = os.environ.get("FRESH_R_EMAIL", "").strip()
    password = os.environ.get("FRESH_R_PASSWORD", "")
    if not email or not password:
        print(
            "Zet FRESH_R_EMAIL en FRESH_R_PASSWORD (export in de shell).",
            file=sys.stderr,
        )
        return 2

    _ha_like_logging()
    log = logging.getLogger("simulate_ha")

    try:
        import aiohttp
    except ImportError:
        print(
            "Installeer aiohttp:  python3 -m pip install 'aiohttp>=3.8.0'",
            file=sys.stderr,
        )
        return 2

    try:
        api_mod = _load_fresh_r_api_only()
    except Exception as err:  # noqa: BLE001
        print(f"Kan fresh_r/api.py niet laden: {err}", file=sys.stderr)
        return 2

    if os.environ.get("FRESH_R_DEEP_DEBUG", "").strip() in ("1", "true", "yes"):
        api_mod.DEEP_DEBUG = True
        log.info("FRESH_R_DEEP_DEBUG=1 → api.py DEEP_DEBUG actief (veel HTTP-details).")

    FreshRApiClient = api_mod.FreshRApiClient
    FreshRAuthError = api_mod.FreshRAuthError
    FreshRConnectionError = api_mod.FreshRConnectionError
    FreshRRateLimitError = api_mod.FreshRRateLimitError

    log.info("── Start: zelfde codepad als Home Assistant (async_login(force=True))")
    log.info("── E-mail: %s", email)

    # Dummy HA-sessie: echte API gebruikt client._get_session() intern.
    async with aiohttp.ClientSession() as ha_session:
        client = FreshRApiClient(email, password, ha_session, hass=None)
        try:
            await client.async_login(force=True)
            log.info("── async_login: geslaagd.")
            _log_session_as_ha(client, log)

            ok = await client._test_token()  # noqa: SLF001 — bewuste test na login
            log.info("── _test_token() na login: %s", "OK" if ok else "MISLUKT")
            return 0 if ok else 1
        except FreshRAuthError as err:
            log.error("── FreshRAuthError: %s", err)
            _log_session_as_ha(client, log)
            return 1
        except FreshRConnectionError as err:
            log.error("── FreshRConnectionError: %s", err)
            return 1
        except FreshRRateLimitError as err:
            log.error("── Rate limit: %s — wacht enige tijd en probeer opnieuw.", err)
            return 3
        finally:
            await client.async_close()
            log.info("── Sessie gesloten.")


def main() -> None:
    try:
        raise SystemExit(asyncio.run(_run()))
    except KeyboardInterrupt:
        print("\nAfgebroken.", file=sys.stderr)
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
