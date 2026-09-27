"""České hlášky chyb validace (API i HTML formuláře)"""

from typing import Iterable

from .formatovani import cislo_cz
from .meters import METERS

_POPISKY_POLI = {"datum": "Datum", **{meter.key: meter.label for meter in METERS}}


def popis_chyby(chyba: dict) -> str:
    """Česká hláška z jedné chyby validace Pydanticu"""
    typ = chyba.get("type", "")
    ctx = chyba.get("ctx") or {}
    if typ == "missing":
        zprava = "pole je povinné"
    elif typ == "greater_than_equal":
        zprava = f"hodnota musí být alespoň {cislo_cz(ctx.get('ge', 0))}"
    elif typ == "less_than_equal":
        zprava = f"hodnota může být nejvýše {cislo_cz(ctx.get('le', 0))}"
    elif typ.startswith(("float", "int", "finite")):
        zprava = "zadejte číslo"
    elif typ.startswith("date"):
        zprava = "zadejte platné datum"
    elif typ.startswith("bool"):
        zprava = "neplatná hodnota"
    elif typ == "json_invalid":
        zprava = "neplatný formát požadavku"
    elif typ == "value_error":
        zprava = str(chyba.get("msg", "")).removeprefix("Value error, ")
    else:
        zprava = str(chyba.get("msg", "neplatná hodnota"))

    pole = next(
        (str(cast) for cast in reversed(chyba.get("loc", ())) if isinstance(cast, str) and cast not in ("body", "query", "path")),
        None,
    )
    return f"{_POPISKY_POLI.get(pole, pole)}: {zprava}" if pole else zprava


def popis_chyb(chyby: Iterable[dict]) -> list[str]:
    """Hlášky bez opakování, v pořadí polí"""
    return list(dict.fromkeys(popis_chyby(chyba) for chyba in chyby))
