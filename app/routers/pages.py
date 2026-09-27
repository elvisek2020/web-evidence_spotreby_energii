"""HTML stránky aplikace"""

import math
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..formatovani import cislo, mesic_cz
from ..meters import METERS
from ..models import Spotreba
from ..services import vypocty
from ..services.zaznamy import nacti_vse
from ..templating import templates

router = APIRouter(include_in_schema=False)

ZAZNAMU_NA_STRANU = 15


def okno_stranek(strana: int, stran: int) -> list[Optional[int]]:
    """Čísla stránek pro stránkování: první, okolí aktuální stránky a poslední; None je mezera"""
    od, do = max(1, strana - 2), min(stran, strana + 2)
    stranky: list[Optional[int]] = []
    if od > 1:
        stranky.append(1)
        if od > 2:
            stranky.append(None)
    stranky.extend(range(od, do + 1))
    if do < stran:
        if do < stran - 1:
            stranky.append(None)
        stranky.append(stran)
    return stranky


@router.get("/", response_class=HTMLResponse)
def prehled(
    request: Request,
    strana: int = Query(1, ge=1),
    jen_odecty: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Hlavní stránka s přehledem záznamů"""
    zaznamy = nacti_vse(db)
    radky = vypocty.radky_s_rozdily(zaznamy, False if jen_odecty else None)
    stran = max(1, math.ceil(len(radky) / ZAZNAMU_NA_STRANU))
    # Po smazání posledního záznamu na poslední stránce se zobrazí předchozí stránka
    strana = min(strana, stran)
    zacatek = (strana - 1) * ZAZNAMU_NA_STRANU

    rucni = [zaznam for zaznam in zaznamy if not zaznam.source]
    dnes = date.today()
    posledni = rucni[-1] if rucni else None
    chybi_odecet = bool(rucni) and not any(
        (zaznam.datum.year, zaznam.datum.month) == (dnes.year, dnes.month) for zaznam in rucni
    )

    return templates.TemplateResponse(request, "index.html", {
        "radky": radky[zacatek:zacatek + ZAZNAMU_NA_STRANU],
        "strana": strana,
        "stran": stran,
        "stranky": okno_stranek(strana, stran),
        "celkem": len(radky),
        "zobrazeno_od": zacatek + 1,
        "zobrazeno_do": min(zacatek + ZAZNAMU_NA_STRANU, len(radky)),
        "jen_odecty": jen_odecty,
        "statistiky": {
            "celkem": len(zaznamy),
            "odectu": len(rucni),
            "odhadu": len(zaznamy) - len(rucni),
        },
        "posledni_odecet": posledni,
        "dni_od_odectu": (dnes - posledni.datum).days if posledni else None,
        "chybi_odecet": chybi_odecet,
        "aktualni_mesic": mesic_cz(dnes),
    })


@router.get("/evidovat", response_class=HTMLResponse)
def evidovat(request: Request, db: Session = Depends(get_db)):
    """Stránka pro přidávání nových záznamů"""
    posledni = (
        db.query(Spotreba)
        .filter(Spotreba.source.is_(False))
        .order_by(Spotreba.datum.desc())
        .first()
    )
    placeholdery = {}
    if posledni:
        for meter in METERS:
            stav = vypocty.hodnota(posledni, meter)
            if stav is not None:
                placeholdery[meter.key] = f"Poslední odečet: {cislo(stav)}"

    return templates.TemplateResponse(request, "evidovat.html", {
        "today": date.today().isoformat(),
        "posledni": posledni,
        "placeholdery": placeholdery,
    })


@router.get("/edit/{spotreba_id}", response_class=HTMLResponse)
def edit(request: Request, spotreba_id: int, db: Session = Depends(get_db)):
    """Stránka pro editaci záznamu"""
    zaznam = db.get(Spotreba, spotreba_id)
    if zaznam is None:
        raise HTTPException(status_code=404, detail="Záznam spotřeby nebyl nalezen")

    return templates.TemplateResponse(request, "edit.html", {
        "spotreba": zaznam,
        "today": date.today().isoformat(),
    })


@router.get("/grafy", response_class=HTMLResponse)
def grafy(request: Request):
    """Stránka s grafy spotřeby"""
    return templates.TemplateResponse(request, "grafy.html", {})


@router.get("/missing-data", response_class=HTMLResponse)
def chybejici_data(request: Request, db: Session = Depends(get_db)):
    """Návrhy chybějících záznamů a kontrola uložených odhadů"""
    zaznamy = nacti_vse(db)
    navrhy, preskocene = vypocty.navrhy_chybejicich(zaznamy)
    zmeny, konflikty = vypocty.prepocet_odhadu(zaznamy)

    return templates.TemplateResponse(request, "missing_data.html", {
        "navrhy": navrhy,
        "preskocene": preskocene,
        "zmeny": zmeny,
        "konflikty": konflikty,
        "pocet_zmenenych": len({zmena.zaznam.id for zmena in zmeny}),
    })
