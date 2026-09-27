"""Zpracování HTML formulářů: převod polí, hlášky po přesměrování, návratové adresy"""

from typing import Mapping, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .formatovani import cislo_cz, datum_kratke, tvar
from .meters import METERS


def data_z_formulare(pole: Mapping[str, str]) -> dict:
    """Pole formuláře odečtu jako vstup pro SpotrebaCreate

    Prázdná pole se vynechají, takže je validace ohlásí jako povinná. Desetinná
    čárka a mezery mezi tisíci se tolerují. Zaškrtávací pole mají hodnotu "1".
    """
    data: dict = {}
    datum = pole.get("datum", "").strip()
    if datum:
        data["datum"] = datum
    for meter in METERS:
        text = pole.get(meter.key, "").strip().replace(",", ".").replace(" ", "").replace(" ", "")
        if text:
            data[meter.key] = text
    data["source"] = pole.get("source") == "1"
    for meter in METERS:
        data[meter.flag] = pole.get(meter.flag) == "1"
    return data


def _pocet(text: Optional[str]) -> int:
    try:
        return max(0, int(text or 0))
    except ValueError:
        return 0


def zprava_po_akci(parametry: Mapping[str, str]) -> Optional[tuple[str, str]]:
    """Hláška pro stránku, na kterou akce přesměrovala (typ alertu a text)

    Server po uložení přesměruje s kódem v URL (?ok=ulozeno&prepocteno=2); text
    se skládá tady, aby do URL nešlo podstrčit libovolnou zprávu.
    """
    kod = parametry.get("ok")
    pocet = _pocet(parametry.get("pocet"))
    prepocteno = _pocet(parametry.get("prepocteno"))
    dovetek = f" Přepočítané odhady v okolí: {prepocteno}." if prepocteno else ""

    if kod == "ulozeno":
        return "success", "Odečet byl uložen." + dovetek
    if kod == "upraveno":
        return "success", "Záznam byl upraven." + dovetek
    if kod == "smazano":
        return "success", "Záznam byl smazán." + dovetek
    if kod == "vytvoreno":
        return "success", tvar(
            pocet,
            f"Byl vytvořen {pocet} odhad.",
            f"Byly vytvořeny {pocet} odhady.",
            f"Bylo vytvořeno {pocet} odhadů.",
        )
    if kod == "prepocteno":
        return "success", tvar(
            pocet,
            f"Byl přepočten {pocet} odhad.",
            f"Byly přepočteny {pocet} odhady.",
            f"Bylo přepočteno {pocet} odhadů.",
        )
    if parametry.get("chyba") == "navrh":
        return "error", "Návrh pro toto datum už neexistuje – data se mezitím změnila."
    return None


def bezpecna_cesta(cesta: Optional[str], vychozi: str = "/") -> str:
    """Návratová adresa jen v rámci aplikace (žádné přesměrování na cizí web)"""
    if not cesta or not cesta.startswith("/") or cesta.startswith("//") or "\\" in cesta:
        return vychozi
    return cesta


def s_parametry(cesta: str, **parametry) -> str:
    """Adresa s doplněnými parametry dotazu; hodnoty None se vynechají"""
    cast = urlsplit(cesta)
    dotaz = dict(parse_qsl(cast.query))
    dotaz.update({klic: str(hodnota) for klic, hodnota in parametry.items() if hodnota is not None})
    return urlunsplit(("", "", cast.path or "/", urlencode(dotaz), ""))


def popis_varovani(varovani) -> str:
    """Věta varování kontroly návaznosti pro uživatele"""
    jednotka = varovani.meter.jednotka
    soused = "předchozí" if varovani.typ == "nizsi_nez_predchozi" else "následující"
    porovnani = "méně" if varovani.typ == "nizsi_nez_predchozi" else "více"
    return (
        f"{varovani.meter.label}: {cislo_cz(varovani.hodnota)} {jednotka} je {porovnani} než {soused} odečet "
        f"{cislo_cz(varovani.soused_hodnota)} {jednotka} ze dne {datum_kratke(varovani.soused_datum)}"
    )
