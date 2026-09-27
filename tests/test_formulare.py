"""Testy zpracování HTML formulářů - běží bez databáze"""

from datetime import date
from types import SimpleNamespace

from app.formulare import bezpecna_cesta, data_z_formulare, popis_varovani, s_parametry, zprava_po_akci
from app.meters import METERS_BY_KEY


def test_formular_prazdna_pole_vynecha_a_ciste_cislo():
    data = data_z_formulare({
        "datum": "2026-09-01",
        "elektromer_vysoky": "17 760,5",
        "plynomer": " ",
        "source": "1",
        "vymena_vodomer": "1",
    })
    assert data["datum"] == "2026-09-01"
    assert data["elektromer_vysoky"] == "17760.5"
    assert "plynomer" not in data
    assert data["source"] is True
    assert data["vymena_vodomer"] is True
    assert data["vymena_plynomer"] is False


def test_zprava_po_ulozeni_s_prepoctem():
    assert zprava_po_akci({"ok": "ulozeno", "prepocteno": "2"}) == (
        "success", "Odečet byl uložen. Přepočítané odhady v okolí: 2."
    )
    assert zprava_po_akci({"ok": "smazano"}) == ("success", "Záznam byl smazán.")


def test_zprava_ma_spravny_tvar_poctu():
    assert zprava_po_akci({"ok": "vytvoreno", "pocet": "1"})[1] == "Byl vytvořen 1 odhad."
    assert zprava_po_akci({"ok": "vytvoreno", "pocet": "3"})[1] == "Byly vytvořeny 3 odhady."
    assert zprava_po_akci({"ok": "prepocteno", "pocet": "7"})[1] == "Bylo přepočteno 7 odhadů."


def test_neznamy_kod_ani_nesmysl_nic_nezobrazi():
    assert zprava_po_akci({}) is None
    assert zprava_po_akci({"ok": "<script>"}) is None
    assert zprava_po_akci({"ok": "vytvoreno", "pocet": "abc"})[1] == "Bylo vytvořeno 0 odhadů."


def test_navrat_jen_v_ramci_aplikace():
    assert bezpecna_cesta("/?strana=2&jen_odecty=1") == "/?strana=2&jen_odecty=1"
    assert bezpecna_cesta("https://evil.example") == "/"
    assert bezpecna_cesta("//evil.example") == "/"
    assert bezpecna_cesta("/\\evil.example") == "/"
    assert bezpecna_cesta(None) == "/"


def test_parametry_se_pridaji_k_existujicim():
    assert s_parametry("/?strana=2", ok="smazano", prepocteno=None) == "/?strana=2&ok=smazano"
    assert s_parametry("/", strana=None) == "/"


def test_popis_varovani():
    varovani = SimpleNamespace(
        meter=METERS_BY_KEY["plynomer"],
        typ="nizsi_nez_predchozi",
        hodnota=10600.0,
        soused_datum=date(2026, 8, 1),
        soused_hodnota=10635.0,
    )
    assert popis_varovani(varovani) == (
        "Plynoměr: 10 600 m³ je méně než předchozí odečet 10 635 m³ ze dne 1. 8. 2026"
    )
