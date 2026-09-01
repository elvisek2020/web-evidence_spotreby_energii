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

def _consumption(previous_value: float, current_value: float, replaced: bool) -> Optional[float]:
    """Spotřeba mezi dvěma odečty, nebo None pokud byl mezitím vyměněn měřič"""
    if replaced:
        return None
    return round(current_value - previous_value, 2)

def _fve_production(previous_value: Optional[float], current_value: Optional[float], replaced: bool) -> Optional[float]:
    """Výroba FVE mezi dvěma odečty

    Počítadlo střídače je kumulativní stejně jako ostatní měřiče. Nula znamená
    chybějící údaj, protože záznamy pořízené před zavedením sloupce fve ho mají
    nastavený na 0 - rozdíl proti nim by vyrobil falešný skok.
    """
    if replaced or not previous_value or not current_value:
        return None
    return round(current_value - previous_value, 2)

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
    fve = []
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
        fve.append(record.fve if record.fve else None)
        source_flags.append(record.source)
    
    return ChartData(
        labels=labels,
        elektromer_vysoky=elektromer_vysoky,
        elektromer_nizky=elektromer_nizky,
        plynomer=plynomer,
        vodomer=vodomer,
        fve=fve,
        source_flags=source_flags
    )

@router.get("/grafy/monthly-diff", response_model=ChartData)
async def get_monthly_diff_data(
    db: Session = Depends(get_db),
    period: Optional[str] = Query(None, description="Časové období: 'year' (poslední rok), '2years' (poslední 2 roky), 'all' (všechno)")
):
    """Získání dat pro grafy spotřeby - zobrazuje skutečnou měsíční spotřebu (přírůstky)"""
    
    # Pro výpočet rozdílů potřebujeme o jeden záznam více do minulosti
    if period == "year":
        cutoff_date = date.today() - timedelta(days=365 + 31)
    elif period == "2years":
        cutoff_date = date.today() - timedelta(days=730 + 31)
    else:
        cutoff_date = None
        
    query = db.query(Spotreba)
    if cutoff_date:
        query = query.filter(Spotreba.datum >= cutoff_date)
        
    records = query.order_by(Spotreba.datum.asc()).all()
    
    if not records or len(records) < 2:
        return ChartData(
            labels=[], elektromer_vysoky=[], elektromer_nizky=[],
            plynomer=[], vodomer=[], fve=[], source_flags=[]
        )
        
    labels = []
    el_vysoky = []
    el_nizky = []
    plyn = []
    voda = []
    fve = []
    source_flags = []
    
    # Výpočet rozdílů mezi po sobě jdoucími záznamy
    for i in range(1, len(records)):
        prev = records[i-1]
        curr = records[i]
        
        # Oříznutí výsledků přesně na požadované období (pokud jsme brali záznam navíc)
        if period == "year" and curr.datum < date.today() - timedelta(days=365):
            continue
        if period == "2years" and curr.datum < date.today() - timedelta(days=730):
            continue
            
        labels.append(curr.datum.strftime('%d.%m.%Y'))
        el_vysoky.append(_consumption(prev.elektromer_vysoky, curr.elektromer_vysoky, curr.vymena_elektromer_vysoky))
        el_nizky.append(_consumption(prev.elektromer_nizky, curr.elektromer_nizky, curr.vymena_elektromer_nizky))
        plyn.append(_consumption(prev.plynomer, curr.plynomer, curr.vymena_plynomer))
        voda.append(_consumption(prev.vodomer, curr.vodomer, curr.vymena_vodomer))
        fve.append(_fve_production(prev.fve, curr.fve, curr.vymena_fve))
        source_flags.append(curr.source)
        
    return ChartData(
        labels=labels,
        elektromer_vysoky=el_vysoky,
        elektromer_nizky=el_nizky,
        plynomer=plyn,
        vodomer=voda,
        fve=fve,
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

    # Roční spotřeba se skládá z přírůstků mezi odečty, aby šlo vynechat
    # intervaly s výměnou měřiče, kde skok stavu není spotřeba
    meters = ("elektromer_vysoky", "elektromer_nizky", "plynomer", "vodomer")

    years_data = []
    for year in sorted(by_year.keys()):
        recs = by_year[year]
        totals = {meter: 0.0 for meter in meters}
        fve_total = 0.0

        for prev, curr in zip(recs, recs[1:]):
            for meter in meters:
                if getattr(curr, f"vymena_{meter}"):
                    continue
                totals[meter] += getattr(curr, meter) - getattr(prev, meter)

            production = _fve_production(prev.fve, curr.fve, curr.vymena_fve)
            if production is not None:
                fve_total += production

        years_data.append({
            "year": year,
            "months_count": len(recs),
            **{meter: round(value, 2) for meter, value in totals.items()},
            "fve": round(fve_total, 2),
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
