from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from datetime import date, timedelta
from ..database import get_db
from ..models import Spotreba
from ..schemas import MissingDataSuggestion, SpotrebaCreate

router = APIRouter()

@router.get("/missing-data/suggestions", response_model=List[MissingDataSuggestion])
async def get_missing_data_suggestions(db: Session = Depends(get_db)):
    """Získání návrhů pro doplnění chybějících dat"""
    
    # Získání posledních 12 záznamů seřazených podle data
    records = db.query(Spotreba).order_by(Spotreba.datum.desc()).limit(12).all()
    
    if len(records) < 2:
        return []
    
    # Seřazení od nejstaršího k nejnovějšímu
    records.reverse()
    
    suggestions = []
    
    # Analýza mezer mezi záznamy
    for i in range(len(records) - 1):
        current_record = records[i]
        next_record = records[i + 1]
        
        # Výpočet rozdílu v datech
        date_diff = (next_record.datum - current_record.datum).days
        
        # Pokud je mezera větší než 30 dní, navrhnout interpolované hodnoty
        if date_diff > 30:
            # Najít všechny chybějící měsíce mezi záznamy
            current_year = current_record.datum.year
            current_month = current_record.datum.month
            next_year = next_record.datum.year
            next_month = next_record.datum.month
            
            # Vytvoření seznamu chybějících měsíců
            missing_months = []
            year = current_year
            month = current_month + 1  # Začít od dalšího měsíce
            
            # Oprava pro případ, kdy current_month je 12
            if month > 12:
                month = 1
                year += 1
            
            while year < next_year or (year == next_year and month < next_month):
                missing_months.append((year, month))
                month += 1
                if month > 12:
                    month = 1
                    year += 1
            
            # Výpočet průměrného přírůstku za měsíc
            months_between = len(missing_months) + 1  # +1 pro aktuální měsíc
            monthly_elektromer_vysoky = (next_record.elektromer_vysoky - current_record.elektromer_vysoky) / months_between
            monthly_elektromer_nizky = (next_record.elektromer_nizky - current_record.elektromer_nizky) / months_between
            monthly_plynomer = (next_record.plynomer - current_record.plynomer) / months_between
            monthly_vodomer = (next_record.vodomer - current_record.vodomer) / months_between
            
            # Generování návrhů pro chybějící měsíce (vždy první den v měsíci)
            for month_index, (year, month) in enumerate(missing_months, 1):
                # První den v měsíci
                suggested_date = date(year, month, 1)
                
                suggested_elektromer_vysoky = current_record.elektromer_vysoky + (monthly_elektromer_vysoky * month_index)
                suggested_elektromer_nizky = current_record.elektromer_nizky + (monthly_elektromer_nizky * month_index)
                suggested_plynomer = current_record.plynomer + (monthly_plynomer * month_index)
                suggested_vodomer = current_record.vodomer + (monthly_vodomer * month_index)
                
                # Kontrola, zda už neexistuje záznam pro toto datum
                existing = db.query(Spotreba).filter(Spotreba.datum == suggested_date).first()
                if not existing:
                    suggestions.append(MissingDataSuggestion(
                        datum=suggested_date,
                        elektromer_vysoky=round(suggested_elektromer_vysoky, 2),
                        elektromer_nizky=round(suggested_elektromer_nizky, 2),
                        plynomer=round(suggested_plynomer, 2),
                        vodomer=round(suggested_vodomer, 2),
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
                source=True
            )
            db.add(new_record)
            created_count += 1
    
    db.commit()
    
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
        source=True
    )
    
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    
    return {
        "message": "Záznam byl úspěšně vytvořen",
        "record": new_record
    }
