#!/usr/bin/env python3
"""Naplní lokální testovací instanci vymyšlenými daty přes API

Určeno pro docker-compose.test.yml. Zapisuje jen na localhost do prázdné databáze,
produkční web tím nejde omylem naplnit.

Data pokrývají situace, které aplikace řeší zvlášť: měsíční odečty 1. 1. 2024 až
1. 8. 2026, mezeru bez odečtu (únor a březen 2025), výměnu vodoměru 15. 6. 2025,
zahájení evidence FVE v květnu 2024, překlep ve vodoměru 1. 3. 2026 a jeden ručně
upravený (zastaralý) odhad.

Použití: python3 scripts/testovaci_data.py [--url http://localhost:18080]
"""

import argparse
import json
import math
import sys
import urllib.error
import urllib.request
from datetime import date
from urllib.parse import urlparse

POVOLENE_HOSTY = {"localhost", "127.0.0.1", "::1"}

ZACATEK = date(2024, 1, 1)
KONEC = date(2026, 8, 1)
MEZERA = {date(2025, 2, 1), date(2025, 3, 1)}
ZACATEK_FVE = date(2024, 5, 1)
VYMENA_VODOMERU = date(2025, 6, 15)
PREKLEP = date(2026, 3, 1)


def api(base: str, method: str, path: str, data=None):
    telo = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(
        base + path, method=method, data=telo, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read() or b"null")
    except urllib.error.HTTPError as chyba:
        sys.exit(f"{method} {path}: HTTP {chyba.code} {chyba.read().decode(errors='replace')}")


def dalsi_mesic(den: date) -> date:
    return date(den.year + (den.month == 12), den.month % 12 + 1, 1)


def prirustky(mesic: int) -> dict:
    """Měsíční spotřeba se sezónním průběhem (zima = 1, léto = -1)"""
    zima = math.cos((mesic - 1) / 12 * 2 * math.pi)
    return {
        "elektromer_vysoky": round(180 + 40 * zima),
        "elektromer_nizky": round(260 + 90 * zima),
        "plynomer": round(85 + 70 * zima),
        "vodomer": 8,
        "fve": round(400 - 300 * zima),
    }


def odecty() -> list[dict]:
    stav = {"elektromer_vysoky": 12000.0, "elektromer_nizky": 23000.0, "plynomer": 8000.0, "vodomer": 900.0, "fve": 0.0}
    vysledek = []
    datum, predchozi = ZACATEK, None
    while datum <= KONEC:
        if predchozi is not None:
            prirustek = prirustky(predchozi.month)
            for meric in ("elektromer_vysoky", "elektromer_nizky", "plynomer", "vodomer"):
                stav[meric] += prirustek[meric]
            if predchozi >= ZACATEK_FVE:
                stav["fve"] += prirustek["fve"]
        if datum == ZACATEK_FVE:
            stav["fve"] = 1500.0

        if datum not in MEZERA:
            zaznam = {"datum": datum.isoformat(), **stav}
            if datum == PREKLEP:
                zaznam["vodomer"] = stav["vodomer"] - 20
            vysledek.append(zaznam)

        if datum == VYMENA_VODOMERU.replace(day=1):
            # V polovině měsíce nový vodoměr od 1 m³, ostatní měřiče za půl měsíce
            pul = {meric: hodnota / 2 for meric, hodnota in prirustky(datum.month).items()}
            ostatni = {meric: stav[meric] + pul[meric] for meric in ("elektromer_vysoky", "elektromer_nizky", "plynomer", "fve")}
            vysledek.append({"datum": VYMENA_VODOMERU.isoformat(), **stav, **ostatni, "vodomer": 1.0, "vymena_vodomer": True})
            # Smyčka k dalšímu 1. dni přičte celý měsíc, nový vodoměr proto startuje o půlměsíc níž
            stav["vodomer"] = 1.0 - pul["vodomer"]
        predchozi = datum
        datum = dalsi_mesic(datum)
    return vysledek


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://localhost:18080", help="adresa testovací instance")
    base = parser.parse_args().url.rstrip("/")

    if urlparse(base).hostname not in POVOLENE_HOSTY:
        sys.exit(f"Skript zapisuje jen na localhost, ne na {base}")
    if api(base, "GET", "/api/spotreba/count")["count"]:
        sys.exit("Databáze už obsahuje záznamy – testovací data se plní jen do prázdné databáze")

    zaznamy = odecty()
    for zaznam in zaznamy:
        api(base, "POST", "/api/spotreba", zaznam)
    print(f"Ruční odečty: {len(zaznamy)}")

    print(api(base, "POST", "/api/missing-data/create")["message"])

    # Ručně upravený odhad - přepočet se u úpravy samotného odhadu nespouští
    odhady = api(base, "GET", "/api/spotreba?source_filter=true&limit=100")
    unor = next(odhad for odhad in odhady if odhad["datum"] == "2025-02-01")
    api(base, "PUT", f"/api/spotreba/{unor['id']}", {"elektromer_vysoky": unor["elektromer_vysoky"] + 50})
    print("Odhad k 1. 2. 2025 ručně změněn o +50 kWh (zastaralý odhad pro kontrolu přepočtu)")


if __name__ == "__main__":
    main()
