from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import List, Dict, Any, Optional
from datetime import date, timedelta
from collections import defaultdict
from ..database import get_db
from ..models import Spotreba
from ..schemas import ChartData

router = APIRouter()

@router.get("/grafy/data", response_model=ChartData)
async def get_chart_data(
    db: Session = Depends(get_db),
    period: Optional[str] = Query(None, description="Časové období: 'year' (poslední rok), '2years' (poslední 2 roky), 'all' (všechno)")
):
    """Získání dat pro grafy spotřeby - zobrazuje kumulativní hodnoty měřičů (celkové stavy)"""
    
    # Určení časového filtru
    if period == "year":
        # Poslední rok
        cutoff_date = date.today() - timedelta(days=365)
        query = db.query(Spotreba).filter(Spotreba.datum >= cutoff_date)
    elif period == "2years":
        # Poslední 2 roky
        cutoff_date = date.today() - timedelta(days=730)
        query = db.query(Spotreba).filter(Spotreba.datum >= cutoff_date)
    else:
        # Všechno (výchozí)
        query = db.query(Spotreba)
    
    # Získání záznamů seřazených podle data
    records = query.order_by(Spotreba.datum.desc()).all()
    
    if not records:
        return ChartData(
            labels=[],
            elektromer_vysoky=[],
            elektromer_nizky=[],
            plynomer=[],
            vodomer=[],
            source_flags=[]
        )
    
    # Seřazení od nejstaršího k nejnovějšímu
    records = sorted(records, key=lambda x: x.datum)
    
    # Příprava dat pro grafy
    labels = []
    elektromer_vysoky = []
    elektromer_nizky = []
    plynomer = []
    vodomer = []
    source_flags = []
    
    for i, record in enumerate(records):
        # Formátování data pro zobrazení
        date_str = record.datum.strftime('%d.%m.%Y')
        labels.append(date_str)
        
        # Použití kumulativních hodnot (celkové stavy měřičů)
        elektromer_vysoky.append(record.elektromer_vysoky)
        elektromer_nizky.append(record.elektromer_nizky)
        plynomer.append(record.plynomer)
        vodomer.append(record.vodomer)
        source_flags.append(record.source)
    
    return ChartData(
        labels=labels,
        elektromer_vysoky=elektromer_vysoky,
        elektromer_nizky=elektromer_nizky,
        plynomer=plynomer,
        vodomer=vodomer,
        source_flags=source_flags
    )

@router.get("/grafy/yoy")
async def get_year_over_year(db: Session = Depends(get_db)):
    """Meziroční porovnání spotřeby -- pro každý rok vypočítá roční spotřebu"""
    records = db.query(Spotreba).order_by(Spotreba.datum.asc()).all()
    if not records:
        return {"years": []}

    by_year: dict[int, list] = defaultdict(list)
    for r in records:
        by_year[r.datum.year].append(r)

    years_data = []
    for year in sorted(by_year.keys()):
        recs = by_year[year]
        first = recs[0]
        last = recs[-1]
        years_data.append({
            "year": year,
            "months_count": len(recs),
            "elektromer_vysoky": round(last.elektromer_vysoky - first.elektromer_vysoky, 2),
            "elektromer_nizky": round(last.elektromer_nizky - first.elektromer_nizky, 2),
            "plynomer": round(last.plynomer - first.plynomer, 2),
            "vodomer": round(last.vodomer - first.vodomer, 2),
        })

    return {"years": years_data}

@router.get("/grafy/summary")
async def get_chart_summary(db: Session = Depends(get_db)):
    """Získání souhrnných statistik pro grafy"""
    
    # Celkový počet záznamů
    total_records = db.query(Spotreba).count()
    
    # Počet manuálních vs. automatických záznamů
    manual_records = db.query(Spotreba).filter(Spotreba.source == False).count()
    auto_records = db.query(Spotreba).filter(Spotreba.source == True).count()
    
    # Poslední záznam
    last_record = db.query(Spotreba).order_by(Spotreba.datum.desc()).first()
    
    # První záznam
    first_record = db.query(Spotreba).order_by(Spotreba.datum.asc()).first()
    
    return {
        "total_records": total_records,
        "manual_records": manual_records,
        "auto_records": auto_records,
        "date_range": {
            "first": first_record.datum if first_record else None,
            "last": last_record.datum if last_record else None
        }
    }
