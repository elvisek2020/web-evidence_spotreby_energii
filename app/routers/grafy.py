from dataclasses import asdict
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..formatovani import datum_cz, mesic_cz, mesic_kratky
from ..models import Spotreba
from ..schemas import GrafAnomalie, GrafData, GrafRada, YoYData, YoYRok
from ..services import vypocty
from ..services.zaznamy import nacti_vse

router = APIRouter()

# Délka období kumulativního grafu ve dnech; None = bez omezení
_PERIOD_DAYS = {
    "3months": 90,
    "6months": 180,
    "year": 365,
    "2years": 730,
    "3years": 1095,
    "all": None,
}

# Měsíční graf ukazuje zvolený počet posledních úplných měsíců
_PERIOD_MONTHS = {
    "3months": 3,
    "6months": 6,
    "year": 12,
    "2years": 24,
    "3years": 36,
    "all": None,
}

_PERIOD_DESCRIPTION = (
    "Časové období: '3months', '6months', 'year', '2years', '3years', 'all' (výchozí)"
)


def _rady(rady: dict[str, vypocty.Rada]) -> dict[str, GrafRada]:
    return {
        key: GrafRada(
            label=rada.meter.label,
            jednotka=rada.meter.jednotka,
            barva=rada.meter.barva,
            osa=rada.meter.osa,
            hodnoty=rada.hodnoty,
            odhad=rada.odhad,
            poznamka=rada.poznamka,
        )
        for key, rada in rady.items()
    }


def _anomalie(zaznamy: list[Spotreba]) -> list[GrafAnomalie]:
    return [
        GrafAnomalie(
            meric=anomalie.meter.key,
            label=anomalie.meter.label,
            jednotka=anomalie.meter.jednotka,
            od=anomalie.od,
            do=anomalie.do,
            spotreba=anomalie.spotreba,
        )
        for anomalie in vypocty.anomalie(zaznamy)
    ]


@router.get("/grafy/data", response_model=GrafData)
def get_chart_data(
    db: Session = Depends(get_db),
    period: Optional[str] = Query(None, description=_PERIOD_DESCRIPTION)
):
    """Stavy měřičů u jednotlivých záznamů včetně odhadů (kumulativní graf)"""
    zaznamy = nacti_vse(db)
    dni = _PERIOD_DAYS.get(period or "all")
    od = date.today() - timedelta(days=dni) if dni else None
    prehled = vypocty.stavy(zaznamy, od)
    popisky = [datum_cz(datum) for datum in prehled.data]
    return GrafData(popisky=popisky, popisky_dlouhe=popisky, rady=_rady(prehled.rady), anomalie=_anomalie(zaznamy))


@router.get("/grafy/monthly-diff", response_model=GrafData)
def get_monthly_diff_data(
    db: Session = Depends(get_db),
    period: Optional[str] = Query(None, description=_PERIOD_DESCRIPTION)
):
    """Spotřeba po kalendářních měsících, rozpočítaná podle dní mezi ručními odečty"""
    zaznamy = nacti_vse(db)
    prehled = vypocty.mesicni(zaznamy, _PERIOD_MONTHS.get(period or "all"))
    return GrafData(
        popisky=[mesic_kratky(mesic) for mesic in prehled.mesice],
        popisky_dlouhe=[mesic_cz(mesic) for mesic in prehled.mesice],
        rady=_rady(prehled.rady),
        anomalie=_anomalie(zaznamy),
    )


@router.get("/grafy/yoy", response_model=YoYData)
def get_year_over_year(db: Session = Depends(get_db)):
    """Spotřeba po letech a srovnání se stejným obdobím předchozího roku"""
    return YoYData(roky=[YoYRok(**asdict(rok)) for rok in vypocty.rocni(nacti_vse(db))])


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
