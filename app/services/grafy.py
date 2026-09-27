"""Data grafů a meziročního porovnání - sdílí je JSON API i stránka Grafy"""

from dataclasses import asdict
from datetime import date, timedelta
from typing import Any, Iterable, Optional

from ..formatovani import datum_cz, mesic_cz, mesic_kratky
from ..schemas import GrafAnomalie, GrafData, GrafRada, YoYData, YoYRok
from . import vypocty

# Volby období: klíč, popisek; stavy se omezují ve dnech, měsíční graf v úplných měsících
OBDOBI = (
    ("3months", "3 měsíce", 90, 3),
    ("6months", "6 měsíců", 180, 6),
    ("year", "1 rok", 365, 12),
    ("2years", "2 roky", 730, 24),
    ("3years", "3 roky", 1095, 36),
    ("all", "Vše", None, None),
)
_DNY = {klic: dny for klic, _, dny, _ in OBDOBI}
_MESICE = {klic: mesice for klic, _, _, mesice in OBDOBI}


def _rady(rady: dict[str, vypocty.Rada]) -> dict[str, GrafRada]:
    return {
        key: GrafRada(
            label=rada.meter.label,
            jednotka=rada.meter.jednotka,
            hodnoty=rada.hodnoty,
            odhad=rada.odhad,
            poznamka=rada.poznamka,
        )
        for key, rada in rady.items()
    }


def anomalie(zaznamy: Iterable[Any]) -> list[GrafAnomalie]:
    return [
        GrafAnomalie(
            meric=nalez.meter.key,
            label=nalez.meter.label,
            jednotka=nalez.meter.jednotka,
            od=nalez.od,
            do=nalez.do,
            spotreba=nalez.spotreba,
        )
        for nalez in vypocty.anomalie(zaznamy)
    ]


def data_mesicni(zaznamy: list[Any], obdobi: Optional[str]) -> GrafData:
    """Spotřeba po kalendářních měsících, rozpočítaná podle dní mezi ručními odečty"""
    prehled = vypocty.mesicni(zaznamy, _MESICE.get(obdobi or "all"))
    return GrafData(
        popisky=[mesic_kratky(mesic) for mesic in prehled.mesice],
        popisky_dlouhe=[mesic_cz(mesic) for mesic in prehled.mesice],
        rady=_rady(prehled.rady),
        anomalie=anomalie(zaznamy),
    )


def data_stavy(zaznamy: list[Any], obdobi: Optional[str]) -> GrafData:
    """Stavy měřičů u jednotlivých záznamů včetně odhadů"""
    dni = _DNY.get(obdobi or "all")
    prehled = vypocty.stavy(zaznamy, date.today() - timedelta(days=dni) if dni else None)
    popisky = [datum_cz(datum) for datum in prehled.data]
    return GrafData(popisky=popisky, popisky_dlouhe=popisky, rady=_rady(prehled.rady), anomalie=anomalie(zaznamy))


def mezirocni(zaznamy: list[Any]) -> YoYData:
    """Spotřeba po letech a srovnání se stejným obdobím předchozího roku"""
    return YoYData(roky=[YoYRok(**asdict(rok)) for rok in vypocty.rocni(zaznamy)])
