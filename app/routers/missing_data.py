import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import extract, func
from typing import List
from datetime import date
from ..database import get_db
from ..models import Spotreba
from ..schemas import MissingDataSuggestion

logger = logging.getLogger(__name__)

router = APIRouter()

def _missing_months(start: date, end: date) -> list[tuple[int, int]]:
    """Kalendářní měsíce mezi dvěma odečty, které nemají vlastní záznam"""
    months = []
    year, month = start.year, start.month + 1
    if month > 12:
        year, month = year + 1, 1

    while (year, month) < (end.year, end.month):
        months.append((year, month))
        month += 1
        if month > 12:
            year, month = year + 1, 1

    return months

def _interpolate(start_value: float, end_value: float, ratio: float) -> float:
    """Lineární dopočet hodnoty mezi dvěma odečty"""
    return round(start_value + (end_value - start_value) * ratio, 2)

def _estimate_fve(db: Session, month: int, start_value: float, end_value: float, ratio: float) -> float:
    """Odhad měsíční výroby FVE

    Výroba je silně sezónní, takže lineární přechod mezi sousedními odečty
    dává nesmyslné hodnoty. Přednost proto má průměr stejného kalendářního
    měsíce z ručních odečtů. Nuly se ignorují, protože záznamy pořízené před
    zavedením sloupce fve ho mají nastavený na 0.
    """
    seasonal_average = db.query(func.avg(Spotreba.fve)).filter(
        extract("month", Spotreba.datum) == month,
        Spotreba.source.is_(False),
        Spotreba.fve > 0,
    ).scalar()

    if seasonal_average is not None:
        return round(float(seasonal_average), 2)

    return _interpolate(start_value, end_value, ratio)

@router.get("/missing-data/suggestions", response_model=List[MissingDataSuggestion])
async def get_missing_data_suggestions(db: Session = Depends(get_db)):
    """Získání návrhů pro doplnění chybějících dat"""
    
    records = db.query(Spotreba).order_by(Spotreba.datum).all()
    
    if len(records) < 2:
        return []
    
    existing_dates = {record.datum for record in records}
    suggestions = []
    
    # Analýza mezer mezi sousedními odečty
    for current_record, next_record in zip(records, records[1:]):
        missing_months = _missing_months(current_record.datum, next_record.datum)
        if not missing_months:
            continue
        
        gap_days = (next_record.datum - current_record.datum).days
        
        # Návrhy se zakládají vždy k prvnímu dni chybějícího měsíce
        for year, month in missing_months:
            suggested_date = date(year, month, 1)
            if suggested_date in existing_dates:
                continue
            
            # Váha podle skutečné pozice data v mezeře, ne podle pořadí měsíce
            ratio = (suggested_date - current_record.datum).days / gap_days
            
            suggestions.append(MissingDataSuggestion(
                datum=suggested_date,
                elektromer_vysoky=_interpolate(current_record.elektromer_vysoky, next_record.elektromer_vysoky, ratio),
                elektromer_nizky=_interpolate(current_record.elektromer_nizky, next_record.elektromer_nizky, ratio),
                plynomer=_interpolate(current_record.plynomer, next_record.plynomer, ratio),
                vodomer=_interpolate(current_record.vodomer, next_record.vodomer, ratio),
                fve=_estimate_fve(db, month, current_record.fve or 0, next_record.fve or 0, ratio),
                source=True
            ))
    
    return suggestions

@router.post("/missing-data/create")
async def create_missing_data_suggestions(db: Session = Depends(get_db)):
    """Automatické vytvoření všech navržených chybějících záznamů"""
    
    suggestions = await get_missing_data_suggestions(db=db)
    
    if not suggestions:
        return {"message": "Žádné chybějící záznamy k doplnění", "created": 0}
    
    created_count = 0
    
    for suggestion in suggestions:
        # Kontrola, zda už neexistuje záznam pro toto datum
        existing = db.query(Spotreba).filter(Spotreba.datum == suggestion.datum).first()
        if not existing:
            # Vytvoření nového záznamu
            new_record = Spotreba(
                datum=suggestion.datum,
                elektromer_vysoky=suggestion.elektromer_vysoky,
                elektromer_nizky=suggestion.elektromer_nizky,
                plynomer=suggestion.plynomer,
                vodomer=suggestion.vodomer,
                fve=suggestion.fve,
                source=True
            )
            db.add(new_record)
            created_count += 1
    
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Chyba při hromadném vytváření chybějících záznamů")
        raise HTTPException(status_code=500, detail="Chyba při ukládání do databáze")
    
    logger.info("Hromadně vytvořeno %d chybějících záznamů", created_count)
    return {
        "message": f"Bylo vytvořeno {created_count} chybějících záznamů",
        "created": created_count
    }

@router.post("/missing-data/create-single")
async def create_single_missing_data(
    suggestion: MissingDataSuggestion,
    db: Session = Depends(get_db)
):
    """Vytvoření jednoho konkrétního chybějícího záznamu"""
    
    # Kontrola, zda už neexistuje záznam pro toto datum
    existing = db.query(Spotreba).filter(Spotreba.datum == suggestion.datum).first()
    if existing:
        raise HTTPException(status_code=400, detail="Záznam pro toto datum již existuje")
    
    # Vytvoření nového záznamu
    new_record = Spotreba(
        datum=suggestion.datum,
        elektromer_vysoky=suggestion.elektromer_vysoky,
        elektromer_nizky=suggestion.elektromer_nizky,
        plynomer=suggestion.plynomer,
        vodomer=suggestion.vodomer,
        fve=suggestion.fve,
        source=True
    )
    
    db.add(new_record)
    try:
        db.commit()
        db.refresh(new_record)
    except Exception:
        db.rollback()
        logger.exception("Chyba při vytváření chybějícího záznamu pro datum=%s", suggestion.datum)
        raise HTTPException(status_code=500, detail="Chyba při ukládání do databáze")
    
    logger.info("Vytvořen chybějící záznam id=%s, datum=%s", new_record.id, new_record.datum)
    return {
        "message": "Záznam byl úspěšně vytvořen",
        "record": new_record
    }
