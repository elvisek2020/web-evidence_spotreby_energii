from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Spotreba
from ..schemas import GrafData, YoYData
from ..services import grafy
from ..services.zaznamy import nacti_vse

router = APIRouter()

_PERIOD_DESCRIPTION = (
    "Časové období: '3months', '6months', 'year', '2years', '3years', 'all' (výchozí)"
)


@router.get("/grafy/data", response_model=GrafData)
def get_chart_data(
    db: Session = Depends(get_db),
    period: Optional[str] = Query(None, description=_PERIOD_DESCRIPTION)
):
    """Stavy měřičů u jednotlivých záznamů včetně odhadů (kumulativní graf)"""
    return grafy.data_stavy(nacti_vse(db), period)


@router.get("/grafy/monthly-diff", response_model=GrafData)
def get_monthly_diff_data(
    db: Session = Depends(get_db),
    period: Optional[str] = Query(None, description=_PERIOD_DESCRIPTION)
):
    """Spotřeba po kalendářních měsících, rozpočítaná podle dní mezi ručními odečty"""
    return grafy.data_mesicni(nacti_vse(db), period)


@router.get("/grafy/yoy", response_model=YoYData)
def get_year_over_year(db: Session = Depends(get_db)):
    """Spotřeba po letech a srovnání se stejným obdobím předchozího roku"""
    return grafy.mezirocni(nacti_vse(db))


@router.get("/grafy/summary")
def get_chart_summary(db: Session = Depends(get_db)):
    """Získání souhrnných statistik pro grafy"""
    total_records = db.query(Spotreba).count()
    manual_records = db.query(Spotreba).filter(Spotreba.source.is_(False)).count()
    auto_records = db.query(Spotreba).filter(Spotreba.source.is_(True)).count()
    last_record = db.query(Spotreba).order_by(Spotreba.datum.desc()).first()
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
