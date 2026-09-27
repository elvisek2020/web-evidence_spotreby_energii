import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..formatovani import tvar
from ..schemas import (
    MissingDataSuggestion,
    NavrhVstup,
    PrepocetKonflikt,
    PrepocetNahled,
    PrepocetZmena,
    SpotrebaResponse,
)
from ..services import vypocty
from ..services.zaznamy import aplikuj_zmeny, nacti_vse, najdi_navrh, zaznam_z_navrhu

logger = logging.getLogger(__name__)

router = APIRouter()


def _commit(db: Session, popis: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Záznam pro toto datum již existuje")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Chyba při ukládání: %s", popis)
        raise HTTPException(status_code=500, detail="Chyba při ukládání do databáze")


@router.get("/missing-data/suggestions", response_model=list[MissingDataSuggestion])
def get_missing_data_suggestions(db: Session = Depends(get_db)):
    """Návrhy záznamů pro kalendářní měsíce bez odečtu, nejnovější první"""
    navrhy, _ = vypocty.navrhy_chybejicich(nacti_vse(db))
    return [MissingDataSuggestion(datum=navrh.datum, **navrh.hodnoty) for navrh in navrhy]


@router.post("/missing-data/create")
def create_missing_data_suggestions(db: Session = Depends(get_db)):
    """Vytvoření všech aktuálních návrhů chybějících záznamů"""
    navrhy, _ = vypocty.navrhy_chybejicich(nacti_vse(db))
    if not navrhy:
        return {"message": "Žádné chybějící záznamy k doplnění", "created": 0}

    for navrh in navrhy:
        db.add(zaznam_z_navrhu(navrh))
    _commit(db, "hromadné vytvoření chybějících záznamů")

    pocet = len(navrhy)
    logger.info("Hromadně vytvořeno %d chybějících záznamů", pocet)
    zprava = tvar(
        pocet,
        f"Byl vytvořen {pocet} chybějící záznam",
        f"Byly vytvořeny {pocet} chybějící záznamy",
        f"Bylo vytvořeno {pocet} chybějících záznamů",
    )
    return {"message": zprava, "created": pocet}


@router.post("/missing-data/create-single")
def create_single_missing_data(vstup: NavrhVstup, db: Session = Depends(get_db)):
    """Vytvoření jednoho navrženého záznamu

    Hodnoty se počítají z aktuálních dat, ne z toho, co poslal prohlížeč - stránka
    s návrhy mohla mezitím zastarat.
    """
    navrh = najdi_navrh(db, vstup.datum)
    if navrh is None:
        raise HTTPException(status_code=400, detail="Pro toto datum už návrh neexistuje, obnovte stránku")

    zaznam = zaznam_z_navrhu(navrh)
    db.add(zaznam)
    _commit(db, f"vytvoření chybějícího záznamu pro datum={vstup.datum}")
    db.refresh(zaznam)

    logger.info("Vytvořen chybějící záznam id=%s, datum=%s", zaznam.id, zaznam.datum)
    return {
        "message": "Záznam byl úspěšně vytvořen",
        "record": SpotrebaResponse.model_validate(zaznam),
    }


@router.get("/missing-data/prepocet", response_model=PrepocetNahled)
def prepocet_nahled(db: Session = Depends(get_db)):
    """Náhled odhadů, které neodpovídají okolním ručním odečtům; nic neukládá"""
    zmeny, konflikty = vypocty.prepocet_odhadu(nacti_vse(db))
    return PrepocetNahled(
        zmeny=[
            PrepocetZmena(
                id=zmena.zaznam.id,
                datum=zmena.zaznam.datum,
                meric=zmena.meter.key,
                label=zmena.meter.label,
                stara=zmena.stara,
                nova=zmena.nova,
            )
            for zmena in zmeny
        ],
        konflikty=[
            PrepocetKonflikt(id=konflikt.zaznam.id, datum=konflikt.zaznam.datum, popis=konflikt.popis)
            for konflikt in konflikty
        ],
        pocet_odhadu=len({zmena.zaznam.id for zmena in zmeny}),
    )


@router.post("/missing-data/prepocet")
def prepocet_provest(db: Session = Depends(get_db)):
    """Přepočítá všechny uložené odhady podle okolních ručních odečtů"""
    zmeny, _ = vypocty.prepocet_odhadu(nacti_vse(db))
    pocet = aplikuj_zmeny(zmeny)
    _commit(db, "přepočet odhadů")

    logger.info("Přepočteno %d odhadů", pocet)
    zprava = tvar(
        pocet,
        f"Byl přepočten {pocet} odhad",
        f"Byly přepočteny {pocet} odhady",
        f"Bylo přepočteno {pocet} odhadů",
    )
    return {"message": zprava, "prepocteno": pocet}
