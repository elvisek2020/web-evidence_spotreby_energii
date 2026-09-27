"""Formátování čísel a dat pro české prostředí (Jinja filtry, texty hlášek, CSV)"""

from datetime import date
from typing import Optional

MESICE = (
    "leden", "únor", "březen", "duben", "květen", "červen",
    "červenec", "srpen", "září", "říjen", "listopad", "prosinec",
)


def datum_cz(den: Optional[date]) -> str:
    """01.09.2026 - formát tabulek"""
    return den.strftime("%d.%m.%Y") if den else ""


def datum_kratke(den: Optional[date]) -> str:
    """1. 9. 2026 - formát do vět"""
    return f"{den.day}. {den.month}. {den.year}" if den else ""


def den_mesic(den: date) -> str:
    """1. 9. - den a měsíc bez roku"""
    return f"{den.day}. {den.month}."


def mesic_cz(den: date) -> str:
    """září 2026"""
    return f"{MESICE[den.month - 1]} {den.year}"


def mesic_kratky(den: date) -> str:
    """09/2026 - popisek osy grafu"""
    return f"{den.month:02d}/{den.year}"


def cislo_input(hodnota: Optional[float]) -> str:
    """Přesná hodnota pro předvyplnění pole input type=number

    Celé číslo bez desetin, jinak nejvýš dvě desetinná místa s tečkou. Zaokrouhlení
    na celé číslo by při uložení formuláře tiše přepsalo uložený stav.
    """
    if hodnota is None:
        return ""
    text = f"{round(float(hodnota), 2):.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def cislo_cz(hodnota: float, desetin: int = 2) -> str:
    """Číslo s mezerou mezi tisíci a desetinnou čárkou, bez zbytečných nul"""
    text = f"{float(hodnota):,.{desetin}f}".replace(",", " ").replace(".", ",")
    if "," in text:
        text = text.rstrip("0").rstrip(",")
    return text


def tvar(pocet: int, jeden: str, dva_az_ctyri: str, pet_a_vice: str) -> str:
    """Tvar slova podle počtu (1 odhad, 2 odhady, 5 odhadů)"""
    if pocet == 1:
        return jeden
    if 2 <= pocet <= 4:
        return dva_az_ctyri
    return pet_a_vice


def pocet(pocet: int, jeden: str, dva_az_ctyri: str, pet_a_vice: str) -> str:
    """Číslo se slovem ve správném tvaru: 1 odečet, 3 odečty, 31 odečtů"""
    return f"{pocet} {tvar(pocet, jeden, dva_az_ctyri, pet_a_vice)}"


def pocet_dni(pocet: int) -> str:
    if pocet == 1:
        return "1 den"
    if 2 <= pocet <= 4:
        return f"{pocet} dny"
    return f"{pocet} dní"


def pred_dny(pocet: int) -> str:
    """Kolik dní uplynulo, do věty: dnes / včera / před 5 dny"""
    if pocet <= 0:
        return "dnes"
    if pocet == 1:
        return "včera"
    return f"před {pocet} dny"
