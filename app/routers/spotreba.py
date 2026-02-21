import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.params import Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from typing import List, Optional
from datetime import date, timedelta
from ..database import get_db
from ..models import Spotreba
from ..schemas import SpotrebaCreate, SpotrebaUpdate, SpotrebaResponse, SpotrebaWithDiff

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/spotreba", response_model=List[SpotrebaWithDiff])
async def get_spotreba_list(
    db: Session = Depends(get_db),
    limit: int = Query(12, ge=1, le=100),
    offset: int = Query(0, ge=0, description="Počet záznamů k přeskočení pro stránkování"),
    source_filter: Optional[bool] = Query(None, description="Filtr podle zdroje dat: None=all, False=manuální, True=automatické")
):
    """Získání seznamu záznamů spotřeby s vypočítanými rozdíly"""
    
    # Základní dotaz
    query = db.query(Spotreba)
    
    # Aplikace filtru podle zdroje dat
    if source_filter is not None:
        query = query.filter(Spotreba.source == source_filter)
    
    # Seřazení podle data (nejnovější první) a omezení počtu s offsetem
    spotreba_records = query.order_by(desc(Spotreba.datum)).offset(offset).limit(limit).all()
    
    # Převod na response model s vypočítanými rozdíly
    result = []
    for i, record in enumerate(spotreba_records):
        record_dict = {
            "id": record.id,
            "datum": record.datum,
            "elektromer_vysoky": record.elektromer_vysoky,
            "elektromer_nizky": record.elektromer_nizky,
            "plynomer": record.plynomer,
            "vodomer": record.vodomer,
            "source": record.source,
            "diff_elektromer_vysoky": None,
            "diff_elektromer_nizky": None,
            "diff_plynomer": None,
            "diff_vodomer": None
        }
        
        # Výpočet rozdílů s předchozím záznamem
        if i < len(spotreba_records) - 1:
            prev_record = spotreba_records[i + 1]
            record_dict["diff_elektromer_vysoky"] = record.elektromer_vysoky - prev_record.elektromer_vysoky
            record_dict["diff_elektromer_nizky"] = record.elektromer_nizky - prev_record.elektromer_nizky
            record_dict["diff_plynomer"] = record.plynomer - prev_record.plynomer
            record_dict["diff_vodomer"] = record.vodomer - prev_record.vodomer
        
        result.append(SpotrebaWithDiff(**record_dict))
    
    return result

@router.get("/spotreba/count")
async def get_spotreba_count(
    db: Session = Depends(get_db),
    source_filter: Optional[bool] = Query(None, description="Filtr podle zdroje dat: None=all, False=manuální, True=automatické")
):
    """Získání celkového počtu záznamů spotřeby"""
    
    # Základní dotaz
    query = db.query(Spotreba)
    
    # Aplikace filtru podle zdroje dat
    if source_filter is not None:
        query = query.filter(Spotreba.source == source_filter)
    
    # Počet záznamů
    count = query.count()
    
    return {"count": count}

@router.get("/spotreba/{spotreba_id}", response_model=SpotrebaResponse)
async def get_spotreba(spotreba_id: int, db: Session = Depends(get_db)):
    """Získání konkrétního záznamu spotřeby"""
    spotreba = db.query(Spotreba).filter(Spotreba.id == spotreba_id).first()
    if not spotreba:
        raise HTTPException(status_code=404, detail="Záznam spotřeby nebyl nalezen")
    return spotreba

@router.post("/spotreba", response_model=SpotrebaResponse)
async def create_spotreba(spotreba: SpotrebaCreate, db: Session = Depends(get_db)):
    """Vytvoření nového záznamu spotřeby"""
    
    # Kontrola, zda už existuje záznam pro dané datum
    existing = db.query(Spotreba).filter(Spotreba.datum == spotreba.datum).first()
    if existing:
        raise HTTPException(status_code=400, detail="Záznam pro toto datum již existuje")
    
    db_spotreba = Spotreba(**spotreba.dict())
    db.add(db_spotreba)
    try:
        db.commit()
        db.refresh(db_spotreba)
    except Exception:
        db.rollback()
        logger.exception("Chyba při vytváření záznamu")
        raise HTTPException(status_code=500, detail="Chyba při ukládání do databáze")
    
    logger.info("Vytvořen záznam id=%s, datum=%s", db_spotreba.id, db_spotreba.datum)
    return db_spotreba

@router.put("/spotreba/{spotreba_id}", response_model=SpotrebaResponse)
async def update_spotreba(
    spotreba_id: int, 
    spotreba_update: SpotrebaUpdate, 
    db: Session = Depends(get_db)
):
    """Aktualizace záznamu spotřeby"""
    
    # Najít existující záznam
    db_spotreba = db.query(Spotreba).filter(Spotreba.id == spotreba_id).first()
    if not db_spotreba:
        raise HTTPException(status_code=404, detail="Záznam spotřeby nebyl nalezen")
    
    # Kontrola, zda nové datum nekonfliktuje s existujícím záznamem
    if spotreba_update.datum and spotreba_update.datum != db_spotreba.datum:
        existing = db.query(Spotreba).filter(
            and_(Spotreba.datum == spotreba_update.datum, Spotreba.id != spotreba_id)
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Záznam pro toto datum již existuje")
    
    update_data = spotreba_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_spotreba, field, value)
    
    try:
        db.commit()
        db.refresh(db_spotreba)
    except Exception:
        db.rollback()
        logger.exception("Chyba při aktualizaci záznamu id=%s", spotreba_id)
        raise HTTPException(status_code=500, detail="Chyba při ukládání do databáze")
    
    logger.info("Aktualizován záznam id=%s", spotreba_id)
    return db_spotreba

@router.delete("/spotreba/{spotreba_id}")
async def delete_spotreba(spotreba_id: int, db: Session = Depends(get_db)):
    """Smazání záznamu spotřeby"""
    
    db_spotreba = db.query(Spotreba).filter(Spotreba.id == spotreba_id).first()
    if not db_spotreba:
        raise HTTPException(status_code=404, detail="Záznam spotřeby nebyl nalezen")
    
    db.delete(db_spotreba)
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Chyba při mazání záznamu id=%s", spotreba_id)
        raise HTTPException(status_code=500, detail="Chyba při mazání z databáze")
    
    logger.info("Smazán záznam id=%s", spotreba_id)
    return {"message": "Záznam byl úspěšně smazán"}
