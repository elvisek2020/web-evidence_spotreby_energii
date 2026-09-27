"""Výpočty spotřeby nad záznamy měřičů

Čisté funkce bez přístupu k databázi. Pracují s čímkoli, co má atributy záznamu
tabulky spotreba (ORM model i testovací dataclass), takže jdou testovat bez DB.

Pravidla:
- Statistiky (měsíční spotřeba, roky) vycházejí jen z ručních odečtů. Odhady
  (source=True) jsou pomůcka pro tabulku a přenášejí jen příznak výměny měřiče.
- Spotřeba mezi dvěma odečty se rozpočítá rovnoměrně na dny intervalu [od, do).
- Interval, ve kterém byl vyměněn měřič, není spotřeba - stavy na sebe nenavazují.
- U FVE znamená nula chybějící údaj, interval se přemostí k další nenulové hodnotě.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Iterable, Optional, Sequence

from ..meters import METERS, Meter

# Rozdíl menší než tato mez je zaokrouhlovací šum
_PRESNOST = 0.005


def _lisi_se(puvodni: float, nova: float) -> bool:
    """Liší se hodnoty víc než o šum? U sloupců FLOAT roste šum s velikostí čísla."""
    return abs(puvodni - nova) >= max(_PRESNOST, abs(nova) * 1e-7)


def seradit(zaznamy: Iterable[Any]) -> list[Any]:
    return sorted(zaznamy, key=lambda zaznam: (zaznam.datum, zaznam.id or 0))


def hodnota(zaznam: Any, meter: Meter) -> Optional[float]:
    """Stav měřiče na záznamu, None když údaj chybí (u FVE i nula)"""
    stav = getattr(zaznam, meter.key, None)
    if stav is None or (meter.zero_is_missing and stav == 0):
        return None
    return float(stav)


def vymena(zaznam: Any, meter: Meter) -> bool:
    return bool(getattr(zaznam, meter.flag, False))


def pridej_mesic(mesic: date) -> date:
    """První den následujícího měsíce"""
    if mesic.month == 12:
        return date(mesic.year + 1, 1, 1)
    return date(mesic.year, mesic.month + 1, 1)


def posun_o_rok(den: date) -> date:
    """Stejný den o rok dříve

    29. 2. se posune na 1. 3., aby rozsahy [od, do) měly v obou letech stejnou délku.
    """
    try:
        return den.replace(year=den.year - 1)
    except ValueError:
        return date(den.year - 1, 3, 1)


def chybejici_mesice(od: date, do: date) -> list[date]:
    """Kalendářní měsíce ležící celé mezi dvěma odečty, jako jejich první dny"""
    mesice = []
    mesic = pridej_mesic(od.replace(day=1))
    while mesic < do.replace(day=1):
        mesice.append(mesic)
        mesic = pridej_mesic(mesic)
    return mesice


# --- Rozdíly v přehledu ---------------------------------------------------------


@dataclass(frozen=True)
class StavMerice:
    stav: Optional[float]
    rozdil: Optional[float]
    # Proč rozdíl chybí: vymena (nový měřič na tomto odečtu), vymena_mezi (výměna
    # na skrytém záznamu v intervalu), prvni, bez_hodnoty (FVE neevidováno)
    duvod: Optional[str]

    @property
    def vymena(self) -> bool:
        return self.duvod in ("vymena", "vymena_mezi")


@dataclass(frozen=True)
class Radek:
    zaznam: Any
    interval_dni: Optional[int]
    merice: dict[str, StavMerice]


def radky_s_rozdily(zaznamy: Iterable[Any], filtr: Optional[bool] = None) -> list[Radek]:
    """Záznamy s rozdílem oproti předchozímu zobrazenému záznamu, nejnovější první

    Počítá se přes všechna data, takže rozdíl má i poslední řádek stránky. Filtr
    (False = jen ruční odečty, True = jen odhady) záznamy skryje, výměnu měřiče
    na skrytém záznamu v intervalu ale pořád zohlední.
    """
    radky = []
    predchozi = None
    vymeny_v_intervalu: set[str] = set()
    for zaznam in seradit(zaznamy):
        vymeny_v_intervalu.update(meter.key for meter in METERS if vymena(zaznam, meter))
        if filtr is not None and bool(zaznam.source) != filtr:
            continue

        merice = {}
        for meter in METERS:
            rozdil, duvod = None, None
            if vymena(zaznam, meter):
                duvod = "vymena"
            elif predchozi is None:
                duvod = "prvni"
            elif meter.key in vymeny_v_intervalu:
                duvod = "vymena_mezi"
            else:
                pred, ted = hodnota(predchozi, meter), hodnota(zaznam, meter)
                if pred is None or ted is None:
                    duvod = "bez_hodnoty"
                else:
                    rozdil = round(ted - pred, 2)
            merice[meter.key] = StavMerice(getattr(zaznam, meter.key), rozdil, duvod)

        interval = (zaznam.datum - predchozi.datum).days if predchozi else None
        radky.append(Radek(zaznam, interval, merice))
        predchozi = zaznam
        vymeny_v_intervalu = set()

    radky.reverse()
    return radky


# --- Segmenty a rozpočet do období ---------------------------------------------


@dataclass(frozen=True)
class Segment:
    """Spotřeba mezi dvěma ručními odečty, rovnoměrně na dny [od, do)"""

    od: date
    do: date
    spotreba: float
    # Mezi odečty leží celý měsíc bez ručního odečtu, rozpočet je tedy jen odhad
    odhad: bool

    @property
    def dni(self) -> int:
        return (self.do - self.od).days


@dataclass(frozen=True)
class Vymena:
    """Interval, ve kterém byl vyměněn měřič - spotřeba v něm není známá"""

    od: date
    do: date


def segmenty(zaznamy: Iterable[Any], meter: Meter) -> tuple[list[Segment], list[Vymena]]:
    """Platné intervaly spotřeby jednoho měřiče a intervaly s výměnou

    Kotvami jsou jen ruční odečty s platnou hodnotou. Příznak výměny se sbírá ze
    všech záznamů mezi kotvami, tedy i z odhadů a záznamů s nulovým FVE.
    """
    platne: list[Segment] = []
    vymeny: list[Vymena] = []
    kotva: Optional[tuple[date, float]] = None
    vymena_od_kotvy = False
    for zaznam in seradit(zaznamy):
        if vymena(zaznam, meter):
            vymena_od_kotvy = True
        if zaznam.source:
            continue
        stav = hodnota(zaznam, meter)
        if stav is None:
            continue
        # Dva odečty se stejným datem interval netvoří, novější z nich se stane kotvou
        if kotva is not None and zaznam.datum > kotva[0]:
            if vymena_od_kotvy:
                vymeny.append(Vymena(kotva[0], zaznam.datum))
            else:
                odhad = bool(chybejici_mesice(kotva[0], zaznam.datum))
                platne.append(Segment(kotva[0], zaznam.datum, stav - kotva[1], odhad))
        kotva = (zaznam.datum, stav)
        vymena_od_kotvy = False
    return platne, vymeny


@dataclass(frozen=True)
class Soucet:
    hodnota: float
    pokryto_dni: int
    odhad: bool


def spotreba_v_rozsahu(segs: Sequence[Segment], od: date, do: date) -> Soucet:
    """Spotřeba v rozsahu [od, do) poměrně podle dní, s počtem pokrytých dní"""
    celkem, pokryto, odhad = 0.0, 0, False
    for segment in segs:
        dni = (min(segment.do, do) - max(segment.od, od)).days
        if dni <= 0:
            continue
        celkem += segment.spotreba * dni / segment.dni
        pokryto += dni
        odhad = odhad or segment.odhad
    return Soucet(celkem, pokryto, odhad)


# --- Grafy ----------------------------------------------------------------------


@dataclass(frozen=True)
class Rada:
    """Hodnoty jednoho měřiče pro graf"""

    meter: Meter
    hodnoty: list[Optional[float]]
    odhad: list[bool]
    poznamka: list[Optional[str]]


@dataclass(frozen=True)
class MesicniPrehled:
    mesice: list[date]
    rady: dict[str, Rada]


@dataclass(frozen=True)
class PrehledStavu:
    data: list[date]
    rady: dict[str, Rada]


@dataclass(frozen=True)
class Anomalie:
    """Pokles stavu bez označené výměny - překlep nebo neoznačená výměna měřiče"""

    meter: Meter
    od: date
    do: date
    spotreba: float


def uplne_mesice(zaznamy: Iterable[Any]) -> list[date]:
    """Kalendářní měsíce ležící celé mezi prvním a posledním ručním odečtem"""
    rucni = [zaznam.datum for zaznam in zaznamy if not zaznam.source]
    if len(rucni) < 2:
        return []
    prvni, posledni = min(rucni), max(rucni)
    mesic = prvni.replace(day=1)
    if mesic < prvni:
        mesic = pridej_mesic(mesic)
    mesice = []
    while pridej_mesic(mesic) <= posledni:
        mesice.append(mesic)
        mesic = pridej_mesic(mesic)
    return mesice


def mesicni(zaznamy: Iterable[Any], pocet_mesicu: Optional[int] = None) -> MesicniPrehled:
    """Spotřeba po kalendářních měsících

    Hodnota měřiče je jen u měsíce pokrytého celého platnými intervaly. Probíhající
    měsíc, začátek dat nebo měsíc s výměnou měřiče mají None s poznámkou.
    """
    serazene = seradit(zaznamy)
    mesice = uplne_mesice(serazene)
    if pocet_mesicu:
        mesice = mesice[-pocet_mesicu:]

    rady = {}
    for meter in METERS:
        platne, vymeny = segmenty(serazene, meter)
        hodnoty: list[Optional[float]] = []
        odhad: list[bool] = []
        poznamka: list[Optional[str]] = []
        for mesic in mesice:
            konec = pridej_mesic(mesic)
            soucet = spotreba_v_rozsahu(platne, mesic, konec)
            if soucet.pokryto_dni == (konec - mesic).days:
                hodnoty.append(round(soucet.hodnota, 2))
                odhad.append(soucet.odhad)
                poznamka.append(None)
            else:
                hodnoty.append(None)
                odhad.append(False)
                s_vymenou = any(v.od < konec and v.do > mesic for v in vymeny)
                poznamka.append("výměna měřiče" if s_vymenou else "bez údajů")
        rady[meter.key] = Rada(meter, hodnoty, odhad, poznamka)
    return MesicniPrehled(mesice, rady)


def stavy(zaznamy: Iterable[Any], od: Optional[date] = None) -> PrehledStavu:
    """Stavy měřičů u jednotlivých záznamů včetně odhadů (kumulativní graf)"""
    vybrane = [zaznam for zaznam in seradit(zaznamy) if od is None or zaznam.datum >= od]
    rady = {
        meter.key: Rada(
            meter,
            [hodnota(zaznam, meter) for zaznam in vybrane],
            [bool(zaznam.source) for zaznam in vybrane],
            ["výměna měřiče" if vymena(zaznam, meter) else None for zaznam in vybrane],
        )
        for meter in METERS
    }
    return PrehledStavu([zaznam.datum for zaznam in vybrane], rady)


def anomalie(zaznamy: Iterable[Any]) -> list[Anomalie]:
    """Intervaly mezi ručními odečty, kde stav klesl bez označené výměny

    Záporná spotřeba se ze statistik nevyhazuje - překlep se vyruší s následujícím
    nafouknutým intervalem a roční součet zůstane správný. Jen se na ni upozorní.
    """
    serazene = seradit(zaznamy)
    nalezene = []
    for poradi, meter in enumerate(METERS):
        platne, _ = segmenty(serazene, meter)
        nalezene.extend(
            (segment.od, poradi, Anomalie(meter, segment.od, segment.do, round(segment.spotreba, 2)))
            for segment in platne
            if segment.spotreba <= -_PRESNOST
        )
    nalezene.sort(key=lambda polozka: polozka[:2])
    return [polozka[2] for polozka in nalezene]


# --- Roky -----------------------------------------------------------------------


@dataclass(frozen=True)
class Srovnani:
    # Srovnávané období loňského roku, včetně krajních dnů
    od: date
    do: date
    loni: float
    rozdil: float
    rozdil_pct: Optional[float]
    # lepsi | horsi | stejne - u výroby FVE je vyšší hodnota lepší
    hodnoceni: str


@dataclass(frozen=True)
class RokMerice:
    hodnota: Optional[float]
    pokryto_dni: int
    uplne: bool
    odhad: bool
    srovnani: Optional[Srovnani]


@dataclass(frozen=True)
class Rok:
    rok: int
    # Období pokryté daty, včetně krajních dnů
    od: date
    do: date
    dni: int
    uplny_rok: bool
    merice: dict[str, RokMerice]


def _srovnani(meter: Meter, letos: float, loni: float, od: date, do: date) -> Srovnani:
    rozdil = letos - loni
    if abs(rozdil) < _PRESNOST:
        hodnoceni = "stejne"
    elif (rozdil > 0) == meter.vyssi_je_lepsi:
        hodnoceni = "lepsi"
    else:
        hodnoceni = "horsi"
    procenta = round(rozdil / loni * 100, 1) if loni > 0 else None
    return Srovnani(od, do - timedelta(days=1), round(loni, 2), round(rozdil, 2), procenta, hodnoceni)


def rocni(zaznamy: Iterable[Any]) -> list[Rok]:
    """Spotřeba po kalendářních letech, nejnovější první

    Každý rok se srovnává se stejným obdobím předchozího roku, u rozpracovaného
    roku tedy do stejného dne. Srovnání existuje jen tehdy, když má měřič
    pokrytá obě období celá (výměna měřiče nebo chybějící data ho zruší).
    """
    serazene = seradit(zaznamy)
    rucni = [zaznam.datum for zaznam in serazene if not zaznam.source]
    if len(rucni) < 2:
        return []
    prvni, posledni = rucni[0], rucni[-1]
    platne = {meter.key: segmenty(serazene, meter)[0] for meter in METERS}

    roky = []
    for rok in range(prvni.year, posledni.year + 1):
        od = max(date(rok, 1, 1), prvni)
        do = min(date(rok + 1, 1, 1), posledni)
        dni = (do - od).days
        if dni <= 0:
            continue

        merice = {}
        for meter in METERS:
            soucet = spotreba_v_rozsahu(platne[meter.key], od, do)
            uplne = soucet.pokryto_dni == dni
            srovnani = None
            if uplne:
                od_loni, do_loni = posun_o_rok(od), posun_o_rok(do)
                loni = spotreba_v_rozsahu(platne[meter.key], od_loni, do_loni)
                if loni.pokryto_dni == (do_loni - od_loni).days:
                    srovnani = _srovnani(meter, soucet.hodnota, loni.hodnota, od_loni, do_loni)
            merice[meter.key] = RokMerice(
                round(soucet.hodnota, 2) if soucet.pokryto_dni else None,
                soucet.pokryto_dni,
                uplne,
                soucet.odhad,
                srovnani,
            )

        uplny_rok = od == date(rok, 1, 1) and do == date(rok + 1, 1, 1)
        roky.append(Rok(rok, od, do - timedelta(days=1), dni, uplny_rok, merice))

    roky.reverse()
    return roky


# --- Odhady chybějících měsíců --------------------------------------------------


@dataclass(frozen=True)
class OdhadMerice:
    hodnota: Optional[float]
    # Proč odhad nejde spočítat: bez_souseda | vymena
    duvod: Optional[str]


def _kotvy(serazene: Sequence[Any], datum: date, meter: Meter) -> tuple[Any, Any]:
    """Nejbližší ruční odečty s platnou hodnotou před datem a po něm"""
    pred = po = None
    for zaznam in serazene:
        if zaznam.source or hodnota(zaznam, meter) is None:
            continue
        if zaznam.datum < datum:
            pred = zaznam
        elif zaznam.datum > datum:
            po = zaznam
            break
    return pred, po


def odhad_merice(serazene: Sequence[Any], datum: date, meter: Meter) -> OdhadMerice:
    """Stav měřiče k datu lineárně podle dní mezi okolními ručními odečty

    Záznamy musí být seřazené funkcí seradit.
    """
    pred, po = _kotvy(serazene, datum, meter)
    if pred is None or po is None:
        # FVE bez okolních údajů se vede jako neevidované
        if meter.zero_is_missing:
            return OdhadMerice(0.0, None)
        return OdhadMerice(None, "bez_souseda")
    if any(vymena(zaznam, meter) for zaznam in serazene if pred.datum < zaznam.datum <= po.datum):
        return OdhadMerice(None, "vymena")
    pomer = (datum - pred.datum).days / (po.datum - pred.datum).days
    zacatek, konec = hodnota(pred, meter), hodnota(po, meter)
    return OdhadMerice(round(zacatek + (konec - zacatek) * pomer, 2), None)


@dataclass(frozen=True)
class Navrh:
    datum: date
    hodnoty: dict[str, float]


@dataclass(frozen=True)
class PreskocenaMezera:
    od: date
    do: date
    mesice: list[date]
    duvody: list[str]


def _popis_duvodu(duvod: Optional[str], meter: Meter) -> str:
    if duvod == "vymena":
        return f"výměna měřiče ({meter.label})"
    return "chybí navazující ruční odečet"


def navrhy_chybejicich(zaznamy: Iterable[Any]) -> tuple[list[Navrh], list[PreskocenaMezera]]:
    """Návrhy záznamů pro kalendářní měsíce bez odečtu, nejnovější první

    Návrh se zakládá k 1. dni chybějícího měsíce a hodnoty jsou lineární odhad
    podle dní mezi okolními ručními odečty. Záznam potřebuje všechny měřiče, takže
    mezeru, kde některý odhad nejde (výměna měřiče, chybí navazující odečet),
    aplikace přeskočí a vrátí s důvodem - doplní ji uživatel ručně.
    """
    serazene = seradit(zaznamy)
    existujici = {zaznam.datum for zaznam in serazene}
    navrhy: list[Navrh] = []
    preskocene: list[PreskocenaMezera] = []

    for zacatek, konec in zip(serazene, serazene[1:]):
        mesice = [m for m in chybejici_mesice(zacatek.datum, konec.datum) if m not in existujici]
        if not mesice:
            continue

        duvody: set[str] = set()
        navrhy_mezery = []
        for mesic in mesice:
            hodnoty = {}
            for meter in METERS:
                odhad = odhad_merice(serazene, mesic, meter)
                if odhad.hodnota is None:
                    duvody.add(_popis_duvodu(odhad.duvod, meter))
                else:
                    hodnoty[meter.key] = odhad.hodnota
            if len(hodnoty) == len(METERS):
                navrhy_mezery.append(Navrh(mesic, hodnoty))

        if duvody:
            preskocene.append(PreskocenaMezera(zacatek.datum, konec.datum, mesice, sorted(duvody)))
        else:
            navrhy.extend(navrhy_mezery)

    navrhy.sort(key=lambda navrh: navrh.datum, reverse=True)
    preskocene.sort(key=lambda mezera: mezera.od, reverse=True)
    return navrhy, preskocene


# --- Přepočet uložených odhadů --------------------------------------------------


@dataclass(frozen=True)
class ZmenaOdhadu:
    zaznam: Any
    meter: Meter
    stara: Optional[float]
    nova: float


@dataclass(frozen=True)
class KonfliktOdhadu:
    zaznam: Any
    popis: str


def prepocet_odhadu(
    zaznamy: Iterable[Any], od: Optional[date] = None, do: Optional[date] = None
) -> tuple[list[ZmenaOdhadu], list[KonfliktOdhadu]]:
    """Odhady, které neodpovídají okolním ručním odečtům

    Prochází odhady s datem v otevřeném intervalu (od, do), bez mezí všechny.
    Odhad bez ručního odečtu před nebo po a měřič s výměnou mezi okolními odečty
    zůstanou beze změny a vrátí se jako konflikt.
    """
    serazene = seradit(zaznamy)
    rucni = [zaznam.datum for zaznam in serazene if not zaznam.source]
    zmeny: list[ZmenaOdhadu] = []
    konflikty: list[KonfliktOdhadu] = []

    for zaznam in serazene:
        if not zaznam.source:
            continue
        if (od is not None and zaznam.datum <= od) or (do is not None and zaznam.datum >= do):
            continue
        if not any(d < zaznam.datum for d in rucni) or not any(d > zaznam.datum for d in rucni):
            konflikty.append(KonfliktOdhadu(zaznam, "chybí ruční odečet před odhadem nebo po něm"))
            continue

        for meter in METERS:
            odhad = odhad_merice(serazene, zaznam.datum, meter)
            if odhad.hodnota is None:
                konflikty.append(KonfliktOdhadu(zaznam, f"{meter.label}: mezi okolními odečty byl vyměněn měřič"))
                continue
            stara = getattr(zaznam, meter.key)
            if stara is None or _lisi_se(float(stara), odhad.hodnota):
                zmeny.append(ZmenaOdhadu(zaznam, meter, stara, odhad.hodnota))

    return zmeny, konflikty


# --- Kontrola návaznosti nového odečtu -----------------------------------------


@dataclass(frozen=True)
class Varovani:
    meter: Meter
    # nizsi_nez_predchozi | vyssi_nez_nasledujici
    typ: str
    hodnota: float
    soused_datum: date
    soused_hodnota: float


def kontrola_navaznosti(
    zaznamy: Iterable[Any], kandidat: Any, exclude_id: Optional[int] = None
) -> list[Varovani]:
    """Varování, když nový nebo upravený odečet nenavazuje na okolní ruční odečty

    Porovnává se jen s ručními odečty, odhady se po uložení přepočítají. Výměna
    měřiče na kandidátovi nebo v intervalu k sousedovi pokles vysvětluje.
    """
    serazene = [zaznam for zaznam in seradit(zaznamy) if exclude_id is None or zaznam.id != exclude_id]
    varovani = []
    for meter in METERS:
        stav = hodnota(kandidat, meter)
        if stav is None:
            continue
        pred, po = _kotvy(serazene, kandidat.datum, meter)

        if pred is not None and stav < hodnota(pred, meter) - _PRESNOST and not vymena(kandidat, meter):
            vymena_mezi = any(
                vymena(zaznam, meter) for zaznam in serazene if pred.datum < zaznam.datum < kandidat.datum
            )
            if not vymena_mezi:
                varovani.append(Varovani(meter, "nizsi_nez_predchozi", stav, pred.datum, hodnota(pred, meter)))

        if po is not None and stav > hodnota(po, meter) + _PRESNOST:
            vymena_mezi = any(
                vymena(zaznam, meter) for zaznam in serazene if kandidat.datum < zaznam.datum <= po.datum
            )
            if not vymena_mezi:
                varovani.append(Varovani(meter, "vyssi_nez_nasledujici", stav, po.datum, hodnota(po, meter)))

    return varovani
