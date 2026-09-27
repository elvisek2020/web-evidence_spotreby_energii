import csv
import io
import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..formatovani import cislo_cz, cislo_input, datum_kratke
from ..meters import METERS
from ..models import Spotreba
from ..schemas import (
    KontrolaVarovani,
    KontrolaVstup,
    KontrolaVysledek,
    SpotrebaCreate,
    SpotrebaResponse,
    SpotrebaUlozeno,
    SpotrebaUpdate,
    SpotrebaWithDiff,
)
from ..services import vypocty
from ..services.zaznamy import nacti_vse, prepocitej_okoli

logger = logging.getLogger(__name__)

router = APIRouter()

_DUPLICITNI_DATUM = "Záznam pro toto datum již existuje"


def _s_rozdily(radek: vypocty.Radek) -> SpotrebaWithDiff:
    data = SpotrebaResponse.model_validate(radek.zaznam).model_dump()
    data["fve"] = radek.zaznam.fve or 0
    data.update({f"diff_{key}": stav.rozdil for key, stav in radek.merice.items()})
    return SpotrebaWithDiff(**data)


def _potvrdit(db: Session, dotcena_data: Optional[set[date]], popis: str) -> int:
    """Přepočítá odhady kolem změněných ručních odečtů a potvrdí transakci

    Vrací počet přepočtených odhadů.
    """
    try:
        prepocteno = prepocitej_okoli(db, dotcena_data) if dotcena_data else 0
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=_DUPLICITNI_DATUM)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Chyba při ukládání: %s", popis)
        raise HTTPException(status_code=500, detail="Chyba při ukládání do databáze")
    return prepocteno


@router.get("/spotreba", response_model=List[SpotrebaWithDiff])
def get_spotreba_list(
    db: Session = Depends(get_db),
    limit: int = Query(12, ge=1, le=100),
    offset: int = Query(0, ge=0, description="Počet záznamů k přeskočení pro stránkování"),
    source_filter: Optional[bool] = Query(None, description="Filtr podle zdroje dat: None=all, False=manuální, True=automatické")
):
    """Seznam záznamů s rozdílem oproti předchozímu záznamu, nejnovější první

    Rozdíly se počítají přes celou historii, takže je má i poslední záznam stránky.
    """
    radky = vypocty.radky_s_rozdily(nacti_vse(db), source_filter)
    return [_s_rozdily(radek) for radek in radky[offset:offset + limit]]


@router.get("/spotreba/count")
def get_spotreba_count(
    db: Session = Depends(get_db),
    source_filter: Optional[bool] = Query(None, description="Filtr podle zdroje dat: None=all, False=manuální, True=automatické")
):
    """Získání celkového počtu záznamů spotřeby"""
    query = db.query(Spotreba)
    if source_filter is not None:
        query = query.filter(Spotreba.source == source_filter)
    return {"count": query.count()}


def _csv_cislo(hodnota: Optional[float]) -> str:
    return "" if hodnota is None else cislo_input(hodnota).replace(".", ",")


@router.get("/spotreba/export.csv")
def export_csv(db: Session = Depends(get_db)):
    """Všechny záznamy jako CSV pro Excel (středník, desetinná čárka, UTF-8 s BOM)"""
    vystup = io.StringIO()
    writer = csv.writer(vystup, delimiter=";", lineterminator="\r\n")
    writer.writerow([
        "Datum",
        *(f"{meter.label} ({meter.jednotka})" for meter in METERS),
        "Zdroj",
        *(f"Výměna – {meter.label}" for meter in METERS),
    ])
    for zaznam in nacti_vse(db):
        writer.writerow([
            zaznam.datum.strftime("%d.%m.%Y"),
            *(_csv_cislo(getattr(zaznam, meter.key)) for meter in METERS),
            "odhad" if zaznam.source else "odečet",
            *("ano" if getattr(zaznam, meter.flag) else "" for meter in METERS),
        ])
    return Response(
        content="﻿" + vystup.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="spotreba-{date.today().isoformat()}.csv"'},
    )


def _varovani(varovani: vypocty.Varovani) -> KontrolaVarovani:
    meter, jednotka = varovani.meter, varovani.meter.jednotka
    soused = "předchozí" if varovani.typ == "nizsi_nez_predchozi" else "následující"
    porovnani = "méně" if varovani.typ == "nizsi_nez_predchozi" else "více"
    zprava = (
        f"{meter.label}: {cislo_cz(varovani.hodnota)} {jednotka} je {porovnani} než {soused} odečet "
        f"{cislo_cz(varovani.soused_hodnota)} {jednotka} ze dne {datum_kratke(varovani.soused_datum)}"
    )
    return KontrolaVarovani(
        meric=meter.key,
        label=meter.label,
        jednotka=jednotka,
        typ=varovani.typ,
        hodnota=varovani.hodnota,
        soused_datum=varovani.soused_datum,
        soused_hodnota=varovani.soused_hodnota,
        zprava=zprava,
    )


@router.post("/spotreba/kontrola", response_model=KontrolaVysledek)
def kontrola_navaznosti(vstup: KontrolaVstup, db: Session = Depends(get_db)):
    """Varování, když odečet nenavazuje na okolní ruční odečty; nic neukládá"""
    varovani = vypocty.kontrola_navaznosti(nacti_vse(db), vstup, exclude_id=vstup.id)
    return KontrolaVysledek(varovani=[_varovani(polozka) for polozka in varovani])


@router.get("/spotreba/{spotreba_id}", response_model=SpotrebaResponse)
def get_spotreba(spotreba_id: int, db: Session = Depends(get_db)):
    """Získání konkrétního záznamu spotřeby"""
    spotreba = db.get(Spotreba, spotreba_id)
    if not spotreba:
        raise HTTPException(status_code=404, detail="Záznam spotřeby nebyl nalezen")
    return spotreba


@router.post("/spotreba", response_model=SpotrebaUlozeno)
def create_spotreba(spotreba: SpotrebaCreate, db: Session = Depends(get_db)):
    """Vytvoření nového záznamu; u ručního odečtu se přepočítají okolní odhady"""
    if db.query(Spotreba).filter(Spotreba.datum == spotreba.datum).first():
        raise HTTPException(status_code=400, detail=_DUPLICITNI_DATUM)

    db_spotreba = Spotreba(**spotreba.model_dump())
    db.add(db_spotreba)
    dotcena = None if db_spotreba.source else {db_spotreba.datum}
    prepocteno = _potvrdit(db, dotcena, "vytvoření záznamu")
    db.refresh(db_spotreba)

    logger.info("Vytvořen záznam id=%s, datum=%s, přepočteno odhadů %d", db_spotreba.id, db_spotreba.datum, prepocteno)
    return SpotrebaUlozeno(**SpotrebaResponse.model_validate(db_spotreba).model_dump(), prepocteno_odhadu=prepocteno)


@router.put("/spotreba/{spotreba_id}", response_model=SpotrebaUlozeno)
def update_spotreba(
    spotreba_id: int,
    spotreba_update: SpotrebaUpdate,
    db: Session = Depends(get_db)
):
    """Aktualizace záznamu; změna ručního odečtu přepočítá okolní odhady"""
    db_spotreba = db.get(Spotreba, spotreba_id)
    if not db_spotreba:
        raise HTTPException(status_code=404, detail="Záznam spotřeby nebyl nalezen")

    update_data = spotreba_update.model_dump(exclude_unset=True)
    novy_datum = update_data.get("datum")
    if novy_datum and novy_datum != db_spotreba.datum:
        existing = db.query(Spotreba).filter(
            and_(Spotreba.datum == novy_datum, Spotreba.id != spotreba_id)
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=_DUPLICITNI_DATUM)

    puvodni_datum, puvodni_source = db_spotreba.datum, db_spotreba.source
    for field, value in update_data.items():
        setattr(db_spotreba, field, value)

    # Úprava samotného odhadu okolí nemění, změna ručního odečtu i převod mezi odečtem a odhadem ano
    dotcena = None if puvodni_source and db_spotreba.source else {puvodni_datum, db_spotreba.datum}
    prepocteno = _potvrdit(db, dotcena, f"aktualizace záznamu id={spotreba_id}")
    db.refresh(db_spotreba)

    logger.info("Aktualizován záznam id=%s, přepočteno odhadů %d", spotreba_id, prepocteno)
    return SpotrebaUlozeno(**SpotrebaResponse.model_validate(db_spotreba).model_dump(), prepocteno_odhadu=prepocteno)


@router.delete("/spotreba/{spotreba_id}")
def delete_spotreba(spotreba_id: int, db: Session = Depends(get_db)):
    """Smazání záznamu; po smazání ručního odečtu se přepočítají okolní odhady"""
    db_spotreba = db.get(Spotreba, spotreba_id)
    if not db_spotreba:
        raise HTTPException(status_code=404, detail="Záznam spotřeby nebyl nalezen")

    dotcena = None if db_spotreba.source else {db_spotreba.datum}
    db.delete(db_spotreba)
    prepocteno = _potvrdit(db, dotcena, f"smazání záznamu id={spotreba_id}")

    logger.info("Smazán záznam id=%s, přepočteno odhadů %d", spotreba_id, prepocteno)
    return {"message": "Záznam byl úspěšně smazán", "prepocteno_odhadu": prepocteno}
