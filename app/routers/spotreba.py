import csv
import io
import logging
from contextlib import contextmanager
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..formatovani import cislo_input
from ..formulare import popis_varovani
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
from ..services.zaznamy import DuplicitniDatum, nacti_vse, smaz_zaznam, uprav_zaznam, vytvor_zaznam

logger = logging.getLogger(__name__)

router = APIRouter()


@contextmanager
def _chyby_ukladani(popis: str):
    """Chyby služby jako HTTP odpovědi API"""
    try:
        yield
    except DuplicitniDatum as chyba:
        raise HTTPException(status_code=400, detail=str(chyba)) from chyba
    except SQLAlchemyError as chyba:
        logger.exception("Chyba při ukládání: %s", popis)
        raise HTTPException(status_code=500, detail="Chyba při ukládání do databáze") from chyba


def _s_rozdily(radek: vypocty.Radek) -> SpotrebaWithDiff:
    data = SpotrebaResponse.model_validate(radek.zaznam).model_dump()
    data["fve"] = radek.zaznam.fve or 0
    data.update({f"diff_{key}": stav.rozdil for key, stav in radek.merice.items()})
    return SpotrebaWithDiff(**data)


def _nacti(db: Session, spotreba_id: int) -> Spotreba:
    zaznam = db.get(Spotreba, spotreba_id)
    if not zaznam:
        raise HTTPException(status_code=404, detail="Záznam spotřeby nebyl nalezen")
    return zaznam


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


@router.post("/spotreba/kontrola", response_model=KontrolaVysledek)
def kontrola_navaznosti(vstup: KontrolaVstup, db: Session = Depends(get_db)):
    """Varování, když odečet nenavazuje na okolní ruční odečty; nic neukládá"""
    varovani = vypocty.kontrola_navaznosti(nacti_vse(db), vstup, exclude_id=vstup.id)
    return KontrolaVysledek(varovani=[
        KontrolaVarovani(
            meric=polozka.meter.key,
            label=polozka.meter.label,
            jednotka=polozka.meter.jednotka,
            typ=polozka.typ,
            hodnota=polozka.hodnota,
            soused_datum=polozka.soused_datum,
            soused_hodnota=polozka.soused_hodnota,
            zprava=popis_varovani(polozka),
        )
        for polozka in varovani
    ])


@router.get("/spotreba/{spotreba_id}", response_model=SpotrebaResponse)
def get_spotreba(spotreba_id: int, db: Session = Depends(get_db)):
    """Získání konkrétního záznamu spotřeby"""
    return _nacti(db, spotreba_id)


@router.post("/spotreba", response_model=SpotrebaUlozeno)
def create_spotreba(spotreba: SpotrebaCreate, db: Session = Depends(get_db)):
    """Vytvoření nového záznamu; u ručního odečtu se přepočítají okolní odhady"""
    with _chyby_ukladani("vytvoření záznamu"):
        zaznam, prepocteno = vytvor_zaznam(db, spotreba.model_dump())
    logger.info("Vytvořen záznam id=%s, datum=%s, přepočteno odhadů %d", zaznam.id, zaznam.datum, prepocteno)
    return SpotrebaUlozeno(**SpotrebaResponse.model_validate(zaznam).model_dump(), prepocteno_odhadu=prepocteno)


@router.put("/spotreba/{spotreba_id}", response_model=SpotrebaUlozeno)
def update_spotreba(
    spotreba_id: int,
    spotreba_update: SpotrebaUpdate,
    db: Session = Depends(get_db)
):
    """Aktualizace záznamu; změna ručního odečtu přepočítá okolní odhady"""
    zaznam = _nacti(db, spotreba_id)
    with _chyby_ukladani(f"aktualizace záznamu id={spotreba_id}"):
        prepocteno = uprav_zaznam(db, zaznam, spotreba_update.model_dump(exclude_unset=True))
    logger.info("Aktualizován záznam id=%s, přepočteno odhadů %d", spotreba_id, prepocteno)
    return SpotrebaUlozeno(**SpotrebaResponse.model_validate(zaznam).model_dump(), prepocteno_odhadu=prepocteno)


@router.delete("/spotreba/{spotreba_id}")
def delete_spotreba(spotreba_id: int, db: Session = Depends(get_db)):
    """Smazání záznamu; po smazání ručního odečtu se přepočítají okolní odhady"""
    zaznam = _nacti(db, spotreba_id)
    with _chyby_ukladani(f"smazání záznamu id={spotreba_id}"):
        prepocteno = smaz_zaznam(db, zaznam)
    logger.info("Smazán záznam id=%s, přepočteno odhadů %d", spotreba_id, prepocteno)
    return {"message": "Záznam byl úspěšně smazán", "prepocteno_odhadu": prepocteno}
