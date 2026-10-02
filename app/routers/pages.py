"""HTML stránky aplikace

Formuláře se odesílají klasicky: POST → přesměrování → GET. Výsledek akce nese
adresa jako kód (?ok=ulozeno&prepocteno=2) a cílová stránka ho vypíše jako alert.
"""

import math
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..database import get_db
from ..formatovani import cislo_cz, cislo_input, datum_kratke, mesic_cz
from ..formulare import bezpecna_cesta, data_z_formulare, popis_varovani, s_parametry, zprava_po_akci
from ..meters import METERS
from ..models import Spotreba
from ..schemas import SpotrebaCreate
from ..services import grafy as grafy_data
from ..services import vypocty
from ..services.zaznamy import (
    DuplicitniDatum,
    nacti_vse,
    prepocitej_vsechny_odhady,
    smaz_zaznam,
    uprav_zaznam,
    vytvor_navrh,
    vytvor_vsechny_navrhy,
    vytvor_zaznam,
)
from ..templating import templates
from ..validace import popis_chyb

router = APIRouter(include_in_schema=False)

ZAZNAMU_NA_STRANU = 15


async def formular(request: Request) -> dict[str, str]:
    """Pole odeslaného HTML formuláře"""
    data = await request.form()
    return {klic: str(hodnota) for klic, hodnota in data.items()}


def _stranka(request: Request, sablona: str, kontext: dict, status_code: int = 200):
    kontext.setdefault("zprava", zprava_po_akci(request.query_params))
    return templates.TemplateResponse(request, sablona, kontext, status_code=status_code)


def _presmeruj(cesta: str) -> RedirectResponse:
    return RedirectResponse(cesta, status_code=303)


def _nacti_zaznam(db: Session, spotreba_id: int) -> Spotreba:
    zaznam = db.get(Spotreba, spotreba_id)
    if zaznam is None:
        raise HTTPException(status_code=404, detail="Záznam spotřeby nebyl nalezen")
    return zaznam


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


# --- Přehled -------------------------------------------------------------------


@router.get("/prehled", response_class=HTMLResponse)
def prehled(
    request: Request,
    strana: int = Query(1, ge=1),
    jen_odecty: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Přehled záznamů s rozdíly"""
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

    return _stranka(request, "index.html", {
        "current_tab": "prehled",
        "radky": radky[zacatek:zacatek + ZAZNAMU_NA_STRANU],
        "strana": strana,
        "stran": stran,
        "stranky": okno_stranek(strana, stran),
        "celkem": len(radky),
        "zobrazeno_od": zacatek + 1,
        "zobrazeno_do": min(zacatek + ZAZNAMU_NA_STRANU, len(radky)),
        "jen_odecty": jen_odecty,
        "statistiky": {"odectu": len(rucni), "odhadu": len(zaznamy) - len(rucni)},
        "posledni_odecet": posledni,
        "dni_od_odectu": (dnes - posledni.datum).days if posledni else None,
        "chybi_odecet": chybi_odecet,
        "aktualni_mesic": mesic_cz(dnes),
        # Kam se vrátit po smazání záznamu z této stránky
        "zpet": s_parametry("/prehled", strana=strana if strana > 1 else None, jen_odecty=1 if jen_odecty else None),
    })


@router.post("/smazat/{spotreba_id}")
def smazat(spotreba_id: int, pole: dict = Depends(formular), db: Session = Depends(get_db)):
    """Smazání záznamu z přehledu nebo z editace (potvrzuje modal data-confirm)"""
    prepocteno = smaz_zaznam(db, _nacti_zaznam(db, spotreba_id))
    cil = bezpecna_cesta(pole.get("zpet"), "/prehled")
    return _presmeruj(s_parametry(cil, ok="smazano", prepocteno=prepocteno or None))


# --- Formulář odečtu (nový i úprava) -------------------------------------------


def _hodnoty_zaznamu(zaznam: Spotreba) -> dict[str, str]:
    """Pole formuláře předvyplněná přesnými hodnotami záznamu"""
    hodnoty = {"datum": zaznam.datum.isoformat(), "source": "1" if zaznam.source else ""}
    for meter in METERS:
        hodnoty[meter.key] = cislo_input(getattr(zaznam, meter.key) or 0)
        hodnoty[meter.flag] = "1" if getattr(zaznam, meter.flag) else ""
    return hodnoty


def _predchozi_odecet(db: Session, zaznam: Optional[Spotreba]) -> Optional[Spotreba]:
    """Poslední ruční odečet před upravovaným záznamem, u nového odečtu poslední vůbec"""
    dotaz = db.query(Spotreba).filter(Spotreba.source.is_(False))
    if zaznam is not None:
        dotaz = dotaz.filter(Spotreba.datum < zaznam.datum)
    return dotaz.order_by(Spotreba.datum.desc()).first()


def _napovedy(predchozi: Optional[Spotreba]) -> dict[str, str]:
    """Stavy předchozího ručního odečtu jako nápověda pod poli formuláře"""
    if predchozi is None:
        return {}
    napovedy = {}
    for meter in METERS:
        stav = vypocty.hodnota(predchozi, meter)
        if stav is not None:
            napovedy[meter.key] = f"Předchozí odečet {datum_kratke(predchozi.datum)}: {cislo_cz(stav)} {meter.jednotka}"
    return napovedy


def _formular_odectu(
    request: Request,
    db: Session,
    zaznam: Optional[Spotreba],
    hodnoty: dict[str, str],
    status_code: int = 200,
    **kontext,
):
    sablona = "edit.html" if zaznam is not None else "evidovat.html"
    predchozi = _predchozi_odecet(db, zaznam)
    varovani = kontext.pop("varovani", [])
    return _stranka(request, sablona, {
        "current_tab": "prehled" if zaznam is not None else "evidovat",
        "zaznam": zaznam,
        # Desetinná čárka by v poli type=number zmizela
        "hodnoty": {klic: hodnota.replace(",", ".") for klic, hodnota in hodnoty.items()},
        "napovedy": _napovedy(predchozi),
        # U nového odečtu poslední ruční stavy jako placeholder (celá čísla, pole má step=1)
        "placeholdery": {
            meter.key: str(round(getattr(predchozi, meter.key) or 0)) for meter in METERS
        } if predchozi is not None and zaznam is None else {},
        "today": date.today().isoformat(),
        "varovani": [popis_varovani(polozka) for polozka in varovani],
        "pokles": any(polozka.typ == "nizsi_nez_predchozi" for polozka in varovani),
        **kontext,
    }, status_code=status_code)


def _ulozit_odecet(request: Request, db: Session, pole: dict, zaznam: Optional[Spotreba]):
    """Uložení formuláře odečtu

    Když odečet nenavazuje na okolní ruční odečty, formulář se vrátí s varováním
    a volbou „Uložit přesto“ / „Uložit jako výměnu měřiče“ (pole potvrzeni).
    """
    try:
        vstup = SpotrebaCreate.model_validate(data_z_formulare(pole))
    except ValidationError as chyba:
        return _formular_odectu(request, db, zaznam, pole, status_code=422, chyby=popis_chyb(chyba.errors()))

    varovani = vypocty.kontrola_navaznosti(nacti_vse(db), vstup, exclude_id=zaznam.id if zaznam else None)
    potvrzeni = pole.get("potvrzeni")
    if varovani and potvrzeni not in ("presto", "vymena"):
        return _formular_odectu(request, db, zaznam, pole, varovani=varovani)

    data = vstup.model_dump()
    if potvrzeni == "vymena":
        for polozka in varovani:
            if polozka.typ == "nizsi_nez_predchozi":
                data[polozka.meter.flag] = True

    try:
        if zaznam is None:
            _, prepocteno = vytvor_zaznam(db, data)
            kod = "ulozeno"
        else:
            prepocteno = uprav_zaznam(db, zaznam, data)
            kod = "upraveno"
    except DuplicitniDatum as chyba:
        return _formular_odectu(request, db, zaznam, pole, status_code=409, duplicita=chyba.existujici_id or 0)

    return _presmeruj(s_parametry("/prehled", ok=kod, prepocteno=prepocteno or None))


@router.get("/evidovat", response_class=HTMLResponse)
def evidovat(request: Request, db: Session = Depends(get_db)):
    """Formulář nového odečtu; stavy posledního ručního odečtu jsou v polích jako placeholder"""
    return _formular_odectu(request, db, None, {"datum": date.today().isoformat()})


@router.post("/evidovat", response_class=HTMLResponse)
def evidovat_ulozit(request: Request, pole: dict = Depends(formular), db: Session = Depends(get_db)):
    return _ulozit_odecet(request, db, pole, None)


@router.get("/edit/{spotreba_id}", response_class=HTMLResponse)
def edit(request: Request, spotreba_id: int, db: Session = Depends(get_db)):
    """Formulář úpravy záznamu"""
    zaznam = _nacti_zaznam(db, spotreba_id)
    return _formular_odectu(request, db, zaznam, _hodnoty_zaznamu(zaznam))


@router.post("/edit/{spotreba_id}", response_class=HTMLResponse)
def edit_ulozit(request: Request, spotreba_id: int, pole: dict = Depends(formular), db: Session = Depends(get_db)):
    return _ulozit_odecet(request, db, pole, _nacti_zaznam(db, spotreba_id))


# --- Grafy ---------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
@router.get("/grafy", response_class=HTMLResponse)
def grafy(
    request: Request,
    rezim: str = Query("mesice"),
    obdobi: str = Query("year"),
    db: Session = Depends(get_db),
):
    """Výchozí stránka: měsíční spotřeba nebo stavy měřičů, meziroční porovnání"""
    if rezim not in ("mesice", "stavy"):
        rezim = "mesice"
    if obdobi not in {klic for klic, *_ in grafy_data.OBDOBI}:
        obdobi = "year"

    zaznamy = nacti_vse(db)
    data = grafy_data.data_mesicni(zaznamy, obdobi) if rezim == "mesice" else grafy_data.data_stavy(zaznamy, obdobi)
    return _stranka(request, "grafy.html", {
        "current_tab": "grafy",
        "rezim": rezim,
        "obdobi": obdobi,
        "volby_obdobi": [(klic, popisek) for klic, popisek, *_ in grafy_data.OBDOBI],
        "graf": data,
        # Anomálie stránka nezobrazuje, vrací je jen JSON API
        "graf_json": data.model_dump(mode="json", exclude={"anomalie"}),
        "roky": vypocty.rocni(zaznamy),
    })


# --- Chybějící data ------------------------------------------------------------


@router.get("/missing-data", response_class=HTMLResponse)
def chybejici_data(request: Request, db: Session = Depends(get_db)):
    """Návrhy chybějících záznamů a kontrola uložených odhadů"""
    zaznamy = nacti_vse(db)
    navrhy, preskocene = vypocty.navrhy_chybejicich(zaznamy)
    zmeny, konflikty = vypocty.prepocet_odhadu(zaznamy)

    return _stranka(request, "missing_data.html", {
        "current_tab": "chybejici",
        "navrhy": navrhy,
        "preskocene": preskocene,
        "zmeny": zmeny,
        "konflikty": konflikty,
        "pocet_zmenenych": len({zmena.zaznam.id for zmena in zmeny}),
    })


@router.post("/missing-data/vytvorit")
def vytvorit_navrh(pole: dict = Depends(formular), db: Session = Depends(get_db)):
    """Vytvoření jednoho návrhu; hodnoty se dopočítají z aktuálních dat"""
    try:
        datum = date.fromisoformat(pole.get("datum", ""))
    except ValueError:
        raise HTTPException(status_code=400, detail="Neplatné datum návrhu") from None
    try:
        zaznam = vytvor_navrh(db, datum)
    except DuplicitniDatum:
        zaznam = None
    if zaznam is None:
        return _presmeruj("/missing-data?chyba=navrh")
    return _presmeruj("/missing-data?ok=vytvoreno&pocet=1")


@router.post("/missing-data/vytvorit-vse")
def vytvorit_vsechny_navrhy(db: Session = Depends(get_db)):
    pocet = vytvor_vsechny_navrhy(db)
    return _presmeruj(s_parametry("/missing-data", ok="vytvoreno", pocet=pocet))


@router.post("/missing-data/prepocet")
def prepocitat_odhady(db: Session = Depends(get_db)):
    pocet = prepocitej_vsechny_odhady(db)
    return _presmeruj(s_parametry("/missing-data", ok="prepocteno", pocet=pocet))
