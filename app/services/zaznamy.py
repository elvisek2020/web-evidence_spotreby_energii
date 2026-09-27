"""Operace nad záznamy v databázi, které stojí na výpočetní vrstvě"""

from datetime import date
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from ..models import Spotreba
from . import vypocty


def nacti_vse(db: Session) -> list[Spotreba]:
    """Všechny záznamy vzestupně podle data

    Domácnost má stovky záznamů, výpočty proto pracují nad celou historií.
    """
    return db.query(Spotreba).order_by(Spotreba.datum, Spotreba.id).all()


def aplikuj_zmeny(zmeny: Iterable[vypocty.ZmenaOdhadu]) -> int:
    """Zapíše přepočtené hodnoty do odhadů, vrací počet upravených záznamů"""
    upravene = set()
    for zmena in zmeny:
        setattr(zmena.zaznam, zmena.meter.key, zmena.nova)
        upravene.add(zmena.zaznam.id)
    return len(upravene)


def prepocitej_okoli(db: Session, dotcena_data: Iterable[date]) -> int:
    """Přepočítá odhady v mezeře kolem změněných ručních odečtů

    Rozsah vede od posledního ručního odečtu před dotčenými daty po první ruční
    odečet za nimi a počítá se nad daty po změně. Commit zůstává na volajícím,
    aby změna i přepočet proběhly v jedné transakci.
    """
    data = list(dotcena_data)
    # Session nemá autoflush, dotaz níže musí vidět právě provedenou změnu
    db.flush()
    zaznamy = nacti_vse(db)
    rucni = [zaznam.datum for zaznam in zaznamy if not zaznam.source]
    od = max((datum for datum in rucni if datum < min(data)), default=None)
    do = min((datum for datum in rucni if datum > max(data)), default=None)
    zmeny, _ = vypocty.prepocet_odhadu(zaznamy, od, do)
    return aplikuj_zmeny(zmeny)


def najdi_navrh(db: Session, datum: date) -> Optional[vypocty.Navrh]:
    """Aktuální návrh chybějícího záznamu k danému datu"""
    navrhy, _ = vypocty.navrhy_chybejicich(nacti_vse(db))
    return next((navrh for navrh in navrhy if navrh.datum == datum), None)


def zaznam_z_navrhu(navrh: vypocty.Navrh) -> Spotreba:
    return Spotreba(datum=navrh.datum, source=True, **navrh.hodnoty)
