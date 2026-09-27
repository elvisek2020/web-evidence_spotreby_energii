"""Operace nad záznamy v databázi, které stojí na výpočetní vrstvě

Sdílí je JSON API i HTML formuláře: vytvoření, úprava a smazání záznamu
s přepočtem okolních odhadů v jedné transakci, návrhy a hromadný přepočet.
"""

from datetime import date
from typing import Iterable, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Spotreba
from . import vypocty


class DuplicitniDatum(Exception):
    """Pro datum už existuje jiný záznam"""

    def __init__(self, existujici_id: Optional[int] = None):
        super().__init__("Záznam pro toto datum již existuje")
        self.existujici_id = existujici_id


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


def _zaznam_k_datu(db: Session, datum: date, krome_id: Optional[int] = None) -> Optional[Spotreba]:
    dotaz = db.query(Spotreba).filter(Spotreba.datum == datum)
    if krome_id is not None:
        dotaz = dotaz.filter(Spotreba.id != krome_id)
    return dotaz.first()


def _potvrdit(db: Session, dotcena_data: Optional[set[date]]) -> int:
    """Přepočítá odhady kolem změněných ručních odečtů a potvrdí transakci

    Vrací počet přepočtených odhadů. Při chybě transakci vrátí.
    """
    try:
        prepocteno = prepocitej_okoli(db, dotcena_data) if dotcena_data else 0
        db.commit()
    except IntegrityError as chyba:
        db.rollback()
        raise DuplicitniDatum() from chyba
    except Exception:
        db.rollback()
        raise
    return prepocteno


def vytvor_zaznam(db: Session, data: dict) -> tuple[Spotreba, int]:
    """Nový záznam; u ručního odečtu se přepočítají okolní odhady"""
    existujici = _zaznam_k_datu(db, data["datum"])
    if existujici:
        raise DuplicitniDatum(existujici.id)
    zaznam = Spotreba(**data)
    db.add(zaznam)
    prepocteno = _potvrdit(db, None if zaznam.source else {zaznam.datum})
    db.refresh(zaznam)
    return zaznam, prepocteno


def uprav_zaznam(db: Session, zaznam: Spotreba, zmeny: dict) -> int:
    """Úprava záznamu; změna ručního odečtu (i převod mezi odečtem a odhadem)
    přepočítá okolní odhady, úprava samotného odhadu ne"""
    novy_datum = zmeny.get("datum")
    if novy_datum and novy_datum != zaznam.datum:
        existujici = _zaznam_k_datu(db, novy_datum, krome_id=zaznam.id)
        if existujici:
            raise DuplicitniDatum(existujici.id)

    puvodni_datum, puvodni_source = zaznam.datum, zaznam.source
    for pole, hodnota in zmeny.items():
        setattr(zaznam, pole, hodnota)
    dotcena = None if puvodni_source and zaznam.source else {puvodni_datum, zaznam.datum}
    prepocteno = _potvrdit(db, dotcena)
    db.refresh(zaznam)
    return prepocteno


def smaz_zaznam(db: Session, zaznam: Spotreba) -> int:
    """Smazání záznamu; po smazání ručního odečtu se přepočítají okolní odhady"""
    dotcena = None if zaznam.source else {zaznam.datum}
    db.delete(zaznam)
    return _potvrdit(db, dotcena)


def zaznam_z_navrhu(navrh: vypocty.Navrh) -> Spotreba:
    return Spotreba(datum=navrh.datum, source=True, **navrh.hodnoty)


def vytvor_navrh(db: Session, datum: date) -> Optional[Spotreba]:
    """Vytvoří aktuální návrh chybějícího záznamu k datu; None, když návrh už neexistuje

    Hodnoty se počítají z aktuálních dat, ne z toho, co bylo na stránce s návrhy.
    """
    navrhy, _ = vypocty.navrhy_chybejicich(nacti_vse(db))
    navrh = next((navrh for navrh in navrhy if navrh.datum == datum), None)
    if navrh is None:
        return None
    zaznam = zaznam_z_navrhu(navrh)
    db.add(zaznam)
    _potvrdit(db, None)
    db.refresh(zaznam)
    return zaznam


def vytvor_vsechny_navrhy(db: Session) -> int:
    """Vytvoří všechny aktuální návrhy chybějících záznamů, vrací jejich počet"""
    navrhy, _ = vypocty.navrhy_chybejicich(nacti_vse(db))
    for navrh in navrhy:
        db.add(zaznam_z_navrhu(navrh))
    _potvrdit(db, None)
    return len(navrhy)


def prepocitej_vsechny_odhady(db: Session) -> int:
    """Přepočítá všechny uložené odhady podle okolních ručních odečtů"""
    zmeny, _ = vypocty.prepocet_odhadu(nacti_vse(db))
    pocet = aplikuj_zmeny(zmeny)
    _potvrdit(db, None)
    return pocet
