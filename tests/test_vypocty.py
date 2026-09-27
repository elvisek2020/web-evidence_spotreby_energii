"""Testy výpočetní vrstvy - běží bez databáze"""

from dataclasses import dataclass, replace
from datetime import date
from typing import Optional

import pytest

from app.services import vypocty as v


@dataclass
class Z:
    """Zjednodušený záznam se stejnými atributy jako model Spotreba"""

    datum: date
    elektromer_vysoky: float = 0.0
    elektromer_nizky: float = 0.0
    plynomer: float = 0.0
    vodomer: float = 0.0
    fve: Optional[float] = 0.0
    source: bool = False
    vymena_elektromer_vysoky: bool = False
    vymena_elektromer_nizky: bool = False
    vymena_plynomer: bool = False
    vymena_vodomer: bool = False
    vymena_fve: bool = False
    id: Optional[int] = None


def mesicne(od: date, pocet: int, prirustek: float = 100.0) -> list[Z]:
    """Ruční odečty k 1. dni měsíce s konstantním přírůstkem elektřiny VT"""
    zaznamy = []
    mesic = od
    for i in range(pocet):
        zaznamy.append(Z(mesic, elektromer_vysoky=i * prirustek, id=i + 1))
        mesic = v.pridej_mesic(mesic)
    return zaznamy


# --- Pomocné funkce -------------------------------------------------------------


def test_posun_o_rok_bezny_den():
    assert v.posun_o_rok(date(2026, 1, 1)) == date(2025, 1, 1)
    assert v.posun_o_rok(date(2026, 9, 15)) == date(2025, 9, 15)


def test_posun_o_rok_29_unor_na_1_brezen():
    # Rozsah [1. 1., 29. 2. 2028) má 59 dní, stejně jako [1. 1., 1. 3. 2027)
    assert v.posun_o_rok(date(2028, 2, 29)) == date(2027, 3, 1)


def test_chybejici_mesice():
    assert v.chybejici_mesice(date(2025, 1, 15), date(2025, 4, 15)) == [date(2025, 2, 1), date(2025, 3, 1)]
    assert v.chybejici_mesice(date(2025, 1, 31), date(2025, 2, 1)) == []
    assert v.chybejici_mesice(date(2025, 12, 1), date(2026, 2, 1)) == [date(2026, 1, 1)]


# --- Rozdíly v přehledu ---------------------------------------------------------


def test_rozdily_nejnovejsi_prvni_a_nejstarsi_bez_rozdilu():
    radky = v.radky_s_rozdily(mesicne(date(2025, 1, 1), 3))
    assert [r.zaznam.datum for r in radky] == [date(2025, 3, 1), date(2025, 2, 1), date(2025, 1, 1)]
    assert radky[0].merice["elektromer_vysoky"].rozdil == 100
    # Rozdíl má i záznam, který by byl na stránce poslední
    assert radky[1].merice["elektromer_vysoky"].rozdil == 100
    assert radky[2].merice["elektromer_vysoky"].duvod == "prvni"
    assert radky[0].interval_dni == 28


def test_rozdil_vymena_na_radku_jen_u_dotceneho_merice():
    zaznamy = mesicne(date(2025, 1, 1), 3)
    zaznamy[2] = replace(zaznamy[2], vodomer=5, vymena_vodomer=True)
    radek = v.radky_s_rozdily(zaznamy)[0]
    assert radek.merice["vodomer"].rozdil is None
    assert radek.merice["vodomer"].duvod == "vymena"
    assert radek.merice["vodomer"].vymena
    assert radek.merice["elektromer_vysoky"].rozdil == 100


def test_filtr_jen_rucni_scita_pres_skryte_odhady():
    zaznamy = [
        Z(date(2025, 1, 1), elektromer_vysoky=100, id=1),
        Z(date(2025, 2, 1), elektromer_vysoky=150, source=True, id=2),
        Z(date(2025, 3, 1), elektromer_vysoky=200, id=3),
    ]
    radky = v.radky_s_rozdily(zaznamy, filtr=False)
    assert [r.zaznam.id for r in radky] == [3, 1]
    assert radky[0].merice["elektromer_vysoky"].rozdil == 100
    assert radky[0].interval_dni == 59


def test_filtr_jen_rucni_zohledni_vymenu_na_skrytem_odhadu():
    zaznamy = [
        Z(date(2025, 1, 1), vodomer=500, id=1),
        Z(date(2025, 2, 1), vodomer=2, source=True, vymena_vodomer=True, id=2),
        Z(date(2025, 3, 1), vodomer=10, id=3),
    ]
    radek = v.radky_s_rozdily(zaznamy, filtr=False)[0]
    assert radek.merice["vodomer"].rozdil is None
    assert radek.merice["vodomer"].duvod == "vymena_mezi"
    assert radek.merice["elektromer_vysoky"].duvod is None


def test_rozdil_fve_s_nulou_chybi():
    zaznamy = [Z(date(2025, 1, 1), fve=0, id=1), Z(date(2025, 2, 1), fve=1200, id=2)]
    radek = v.radky_s_rozdily(zaznamy)[0]
    assert radek.merice["fve"].rozdil is None
    assert radek.merice["fve"].duvod == "bez_hodnoty"


# --- Měsíční spotřeba -----------------------------------------------------------


def test_mesice_pri_odectech_k_prvnimu_dni():
    zaznamy = [
        Z(date(2025, 1, 1), elektromer_vysoky=0, id=1),
        Z(date(2025, 2, 1), elektromer_vysoky=100, id=2),
        Z(date(2025, 3, 1), elektromer_vysoky=250, id=3),
    ]
    prehled = v.mesicni(zaznamy)
    # Odečet z 1. 3. uzavírá únor, březen ještě neskončil
    assert prehled.mesice == [date(2025, 1, 1), date(2025, 2, 1)]
    assert prehled.rady["elektromer_vysoky"].hodnoty == [100, 150]
    assert prehled.rady["elektromer_vysoky"].odhad == [False, False]


def test_mesice_pri_odectech_uprostred_mesice_rozpocitaji_dny():
    zaznamy = [
        Z(date(2025, 1, 15), elektromer_vysoky=0, id=1),
        Z(date(2025, 2, 15), elektromer_vysoky=310, id=2),
        Z(date(2025, 3, 15), elektromer_vysoky=590, id=3),
        Z(date(2025, 4, 15), elektromer_vysoky=900, id=4),
    ]
    prehled = v.mesicni(zaznamy)
    assert prehled.mesice == [date(2025, 2, 1), date(2025, 3, 1)]
    unor, brezen = prehled.rady["elektromer_vysoky"].hodnoty
    # 310 × 14/31 + 280 × 14/28 a 280 × 14/28 + 310 × 17/31
    assert unor == pytest.approx(280)
    assert brezen == pytest.approx(310)
    assert unor + brezen == pytest.approx(590)


def test_mezera_bez_odectu_se_rozpocita_a_oznaci_jako_odhad():
    zaznamy = [
        Z(date(2025, 1, 1), elektromer_vysoky=0, id=1),
        Z(date(2025, 4, 1), elektromer_vysoky=900, id=2),
    ]
    rada = v.mesicni(zaznamy).rady["elektromer_vysoky"]
    assert rada.hodnoty == [pytest.approx(310), pytest.approx(280), pytest.approx(310)]
    assert rada.odhad == [True, True, True]


def test_zastaraly_odhad_statistiky_neovlivni():
    zaznamy = [
        Z(date(2025, 1, 1), elektromer_vysoky=0, id=1),
        Z(date(2025, 2, 1), elektromer_vysoky=999, source=True, id=2),
        Z(date(2025, 4, 1), elektromer_vysoky=900, id=3),
    ]
    rada = v.mesicni(zaznamy).rady["elektromer_vysoky"]
    assert rada.hodnoty == [pytest.approx(310), pytest.approx(280), pytest.approx(310)]


def test_vymena_uprostred_mesice_vyradi_jen_dotceny_mesic_a_merice():
    zaznamy = mesicne(date(2025, 1, 1), 5)
    for i, zaznam in enumerate(zaznamy):
        zaznam.vodomer = 100 + i * 10
    # Nový vodoměr nasazený 15. 3.; od dubna pokračuje z nového stavu
    zaznamy.insert(3, Z(date(2025, 3, 15), elektromer_vysoky=250, vodomer=1, vymena_vodomer=True, id=10))
    zaznamy[4].vodomer = 5
    zaznamy[5].vodomer = 12
    prehled = v.mesicni(zaznamy)
    assert prehled.mesice == [date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1), date(2025, 4, 1)]
    voda = prehled.rady["vodomer"]
    assert voda.hodnoty == [10, 10, None, 7]
    assert voda.poznamka[2] == "výměna měřiče"
    # Elektřinu výměna vodoměru neovlivní
    assert prehled.rady["elektromer_vysoky"].hodnoty == [100, 100, 100, 100]


def test_prestupny_unor_ma_29_dni():
    zaznamy = [
        Z(date(2024, 2, 1), elektromer_vysoky=0, id=1),
        Z(date(2024, 3, 1), elektromer_vysoky=290, id=2),
    ]
    prehled = v.mesicni(zaznamy)
    assert prehled.mesice == [date(2024, 2, 1)]
    assert prehled.rady["elektromer_vysoky"].hodnoty == [290]


def test_obdobi_v_mesicich_konci_poslednim_uplnym_mesicem():
    # Odečty 1. 1. - 1. 10., poslední úplný měsíc je září
    prehled = v.mesicni(mesicne(date(2025, 1, 1), 10), pocet_mesicu=3)
    assert prehled.mesice == [date(2025, 7, 1), date(2025, 8, 1), date(2025, 9, 1)]


@pytest.mark.parametrize("pocet", [0, 1])
def test_malo_dat_da_prazdny_graf(pocet):
    prehled = v.mesicni(mesicne(date(2025, 1, 1), pocet))
    assert prehled.mesice == []
    assert prehled.rady["elektromer_vysoky"].hodnoty == []


def test_fve_nula_na_zacatku_chybi_a_uprostred_se_premosti():
    zaznamy = [
        Z(date(2025, 1, 1), fve=0, id=1),
        Z(date(2025, 2, 1), fve=0, id=2),
        Z(date(2025, 3, 1), fve=1000, id=3),
        Z(date(2025, 4, 1), fve=0, id=4),
        Z(date(2025, 5, 1), fve=1610, id=5),
    ]
    rada = v.mesicni(zaznamy).rady["fve"]
    assert rada.hodnoty[:2] == [None, None]
    assert rada.poznamka[:2] == ["bez údajů", "bez údajů"]
    assert rada.hodnoty[2] == pytest.approx(610 * 31 / 61)
    assert rada.hodnoty[3] == pytest.approx(610 * 30 / 61)
    assert rada.odhad[2:] == [True, True]


def test_zaporny_prirustek_zustane_a_hlasi_se_jako_anomalie():
    zaznamy = [
        Z(date(2025, 1, 1), vodomer=100, id=1),
        Z(date(2025, 2, 1), vodomer=110, id=2),
        Z(date(2025, 3, 1), vodomer=50, id=3),
        Z(date(2025, 4, 1), vodomer=130, id=4),
    ]
    assert v.mesicni(zaznamy).rady["vodomer"].hodnoty == [10, -60, 80]
    nalezene = v.anomalie(zaznamy)
    assert len(nalezene) == 1
    assert (nalezene[0].meter.key, nalezene[0].od, nalezene[0].spotreba) == ("vodomer", date(2025, 2, 1), -60)


def test_duplicitni_datum_s_vymenou_nerozbije_vypocet():
    zaznamy = [
        Z(date(2025, 1, 1), vodomer=100, id=1),
        Z(date(2025, 2, 1), vodomer=150, id=2),
        Z(date(2025, 2, 1), vodomer=3, vymena_vodomer=True, id=3),
        Z(date(2025, 3, 1), vodomer=20, id=4),
    ]
    assert v.mesicni(zaznamy).rady["vodomer"].hodnoty == [50, 17]


def test_stavy_pro_kumulativni_graf():
    zaznamy = [
        Z(date(2025, 1, 1), fve=0, id=1),
        Z(date(2025, 2, 1), fve=500, source=True, id=2),
        Z(date(2025, 3, 1), fve=900, vymena_fve=True, id=3),
    ]
    prehled = v.stavy(zaznamy, od=date(2025, 1, 15))
    assert prehled.data == [date(2025, 2, 1), date(2025, 3, 1)]
    assert prehled.rady["fve"].hodnoty == [500, 900]
    assert prehled.rady["fve"].odhad == [True, False]
    assert prehled.rady["fve"].poznamka == [None, "výměna měřiče"]
    assert v.stavy(zaznamy).rady["fve"].hodnoty[0] is None


# --- Roky -----------------------------------------------------------------------


def test_rok_zahrnuje_interval_pres_prelom_roku():
    # Regrese: dříve se interval 1. 12. -> 1. 1. nezapočítal a rok měl 11 měsíců
    roky = v.rocni(mesicne(date(2024, 1, 1), 13))
    assert [r.rok for r in roky] == [2024]
    rok = roky[0]
    assert rok.uplny_rok
    assert rok.merice["elektromer_vysoky"].hodnota == 1200
    assert rok.merice["elektromer_vysoky"].uplne


def test_rozpracovany_rok_se_srovnava_do_stejneho_dne():
    zaznamy = mesicne(date(2025, 1, 1), 21)  # do 1. 9. 2026
    roky = v.rocni(zaznamy)
    assert [r.rok for r in roky] == [2026, 2025]
    letos = roky[0]
    assert not letos.uplny_rok
    assert (letos.od, letos.do) == (date(2026, 1, 1), date(2026, 8, 31))
    srovnani = letos.merice["elektromer_vysoky"].srovnani
    assert (srovnani.od, srovnani.do) == (date(2025, 1, 1), date(2025, 8, 31))
    assert srovnani.loni == 800
    assert letos.merice["elektromer_vysoky"].hodnota == 800
    assert srovnani.hodnoceni == "stejne"
    # Rok 2025 nemá s čím srovnat, data začínají v lednu 2025
    assert roky[1].merice["elektromer_vysoky"].srovnani is None


def test_hodnoceni_podle_druhu_merice():
    # Letos dvojnásobná spotřeba elektřiny (horší) i dvojnásobná výroba FVE (lepší)
    zaznamy = [Z(date(2025, 1, 1), elektromer_vysoky=10000, fve=5000, id=1)]
    for i in range(20):
        predchozi = zaznamy[-1]
        nasobek = 2 if predchozi.datum.year == 2026 else 1
        zaznamy.append(Z(
            v.pridej_mesic(predchozi.datum),
            elektromer_vysoky=predchozi.elektromer_vysoky + 100 * nasobek,
            fve=predchozi.fve + 50 * nasobek,
            id=i + 2,
        ))
    letos = v.rocni(zaznamy)[0]
    elektrina, fve = letos.merice["elektromer_vysoky"].srovnani, letos.merice["fve"].srovnani
    assert (elektrina.loni, elektrina.rozdil, elektrina.rozdil_pct) == (800, 800, 100.0)
    assert elektrina.hodnoceni == "horsi"
    assert fve.hodnoceni == "lepsi"


def test_srovnani_s_nulovou_lonskou_spotrebou_nema_procenta():
    zaznamy = mesicne(date(2025, 1, 1), 21)
    for zaznam in zaznamy:
        zaznam.vodomer = 10 if zaznam.datum.year == 2026 and zaznam.datum.month > 1 else 0
    srovnani = v.rocni(zaznamy)[0].merice["vodomer"].srovnani
    assert srovnani.loni == 0
    assert srovnani.rozdil_pct is None
    assert srovnani.hodnoceni == "horsi"


def test_rok_s_vymenou_je_neuplny_a_bez_srovnani():
    zaznamy = mesicne(date(2025, 1, 1), 21)
    for i, zaznam in enumerate(zaznamy):
        zaznam.vodomer = 100 + i * 10 if i < 6 else 1 + (i - 6) * 2
    zaznamy[6].vymena_vodomer = True  # 1. 7. 2025 nový vodoměr
    roky = {r.rok: r for r in v.rocni(zaznamy)}
    assert not roky[2025].merice["vodomer"].uplne
    assert roky[2025].merice["vodomer"].srovnani is None
    # Loňské období s výměnou nejde srovnat ani s letoškem
    assert roky[2026].merice["vodomer"].uplne
    assert roky[2026].merice["vodomer"].srovnani is None
    assert roky[2026].merice["elektromer_vysoky"].srovnani is not None


def test_fve_od_poloviny_roku():
    zaznamy = mesicne(date(2025, 1, 1), 21)
    for i, zaznam in enumerate(zaznamy):
        zaznam.fve = 0 if zaznam.datum < date(2025, 6, 1) else 1000 + i * 100
    roky = {r.rok: r for r in v.rocni(zaznamy)}
    fve_2025 = roky[2025].merice["fve"]
    assert not fve_2025.uplne
    assert fve_2025.pokryto_dni == 214  # 1. 6. - 31. 12.
    assert fve_2025.hodnota == 700
    assert roky[2026].merice["fve"].srovnani is None


def test_malo_dat_nema_roky():
    assert v.rocni(mesicne(date(2025, 1, 1), 1)) == []


# --- Návrhy chybějících měsíců --------------------------------------------------


def test_navrhy_podle_dni_k_prvnimu_dni_mesice():
    zaznamy = [
        Z(date(2025, 1, 15), elektromer_vysoky=0, id=1),
        Z(date(2025, 4, 15), elektromer_vysoky=900, id=2),
    ]
    navrhy, preskocene = v.navrhy_chybejicich(zaznamy)
    assert preskocene == []
    assert [n.datum for n in navrhy] == [date(2025, 3, 1), date(2025, 2, 1)]
    assert navrhy[1].hodnoty["elektromer_vysoky"] == pytest.approx(170)  # 17 z 90 dní
    assert navrhy[0].hodnoty["elektromer_vysoky"] == pytest.approx(450)  # 45 z 90 dní


def test_navrh_vychazi_z_rucnich_odectu_ne_z_odhadu():
    zaznamy = [
        Z(date(2025, 1, 1), elektromer_vysoky=0, id=1),
        Z(date(2025, 2, 1), elektromer_vysoky=999, source=True, id=2),
        Z(date(2025, 4, 1), elektromer_vysoky=900, id=3),
    ]
    navrhy, _ = v.navrhy_chybejicich(zaznamy)
    assert [n.datum for n in navrhy] == [date(2025, 3, 1)]
    assert navrhy[0].hodnoty["elektromer_vysoky"] == pytest.approx(590)


def test_mezera_s_vymenou_se_preskoci_s_duvodem():
    zaznamy = [
        Z(date(2025, 1, 1), vodomer=500, id=1),
        Z(date(2025, 4, 1), vodomer=3, vymena_vodomer=True, id=2),
    ]
    navrhy, preskocene = v.navrhy_chybejicich(zaznamy)
    assert navrhy == []
    assert len(preskocene) == 1
    assert preskocene[0].mesice == [date(2025, 2, 1), date(2025, 3, 1)]
    assert preskocene[0].duvody == ["výměna měřiče (Vodoměr)"]


def test_mezera_bez_navazujiciho_rucniho_odectu():
    zaznamy = [
        Z(date(2025, 1, 1), id=1),
        Z(date(2025, 2, 1), source=True, id=2),
        Z(date(2025, 4, 1), source=True, id=3),
    ]
    navrhy, preskocene = v.navrhy_chybejicich(zaznamy)
    assert navrhy == []
    assert preskocene[0].duvody == ["chybí navazující ruční odečet"]


def test_navrh_fve_neevidovane_je_nula():
    zaznamy = [
        Z(date(2025, 1, 1), fve=0, id=1),
        Z(date(2025, 3, 1), fve=800, id=2),
    ]
    navrhy, _ = v.navrhy_chybejicich(zaznamy)
    assert navrhy[0].hodnoty["fve"] == 0


# --- Přepočet odhadů ------------------------------------------------------------


def _mezera_s_odhady():
    return [
        Z(date(2025, 1, 1), elektromer_vysoky=0, id=1),
        Z(date(2025, 2, 1), elektromer_vysoky=111, source=True, id=2),
        Z(date(2025, 3, 1), elektromer_vysoky=222, source=True, id=3),
        Z(date(2025, 4, 1), elektromer_vysoky=900, id=4),
    ]


def _aplikuj(zmeny):
    for zmena in zmeny:
        setattr(zmena.zaznam, zmena.meter.key, zmena.nova)


def test_prepocet_opravi_zastarale_odhady():
    zaznamy = _mezera_s_odhady()
    zmeny, konflikty = v.prepocet_odhadu(zaznamy)
    assert konflikty == []
    assert {(z.zaznam.id, z.meter.key): z.nova for z in zmeny} == {
        (2, "elektromer_vysoky"): 310,
        (3, "elektromer_vysoky"): 590,
    }


def test_prepocet_je_idempotentni():
    zaznamy = _mezera_s_odhady()
    _aplikuj(v.prepocet_odhadu(zaznamy)[0])
    assert v.prepocet_odhadu(zaznamy) == ([], [])


def test_prepocet_jen_v_zadanem_rozsahu():
    zaznamy = _mezera_s_odhady()
    zmeny, _ = v.prepocet_odhadu(zaznamy, od=date(2025, 2, 1), do=date(2025, 4, 1))
    assert [z.zaznam.id for z in zmeny] == [3]


def test_pridani_rucniho_odectu_mezi_odhady():
    zaznamy = _mezera_s_odhady()
    _aplikuj(v.prepocet_odhadu(zaznamy)[0])
    zaznamy.append(Z(date(2025, 2, 15), elektromer_vysoky=200, id=5))
    zmeny = {z.zaznam.id: z.nova for z in v.prepocet_odhadu(zaznamy)[0]}
    assert zmeny[2] == pytest.approx(200 * 31 / 45, abs=0.005)
    assert zmeny[3] == pytest.approx(200 + 700 * 14 / 45, abs=0.005)


def test_smazani_posledniho_rucniho_odectu_vytvori_konflikt():
    zaznamy = _mezera_s_odhady()[:3]
    zmeny, konflikty = v.prepocet_odhadu(zaznamy)
    assert zmeny == []
    assert [k.zaznam.id for k in konflikty] == [2, 3]


def test_prevod_odhadu_na_rucni_odecet_z_nej_udela_kotvu():
    zaznamy = _mezera_s_odhady()
    zaznamy[1].source = False
    zaznamy[1].elektromer_vysoky = 400
    zmeny = {z.zaznam.id: z.nova for z in v.prepocet_odhadu(zaznamy)[0]}
    assert zmeny == {3: pytest.approx(400 + 500 * 28 / 59, abs=0.005)}


def test_prepocet_s_vymenou_nemeni_dotceny_meric():
    zaznamy = [
        Z(date(2025, 1, 1), elektromer_vysoky=0, vodomer=500, id=1),
        Z(date(2025, 2, 1), elektromer_vysoky=1, vodomer=1, source=True, id=2),
        Z(date(2025, 3, 1), elektromer_vysoky=590, vodomer=4, vymena_vodomer=True, id=3),
    ]
    zmeny, konflikty = v.prepocet_odhadu(zaznamy)
    assert [(z.zaznam.id, z.meter.key) for z in zmeny] == [(2, "elektromer_vysoky")]
    assert len(konflikty) == 1
    assert "Vodoměr" in konflikty[0].popis


def test_prepocet_vynuluje_fve_pred_zahajenim_evidence():
    zaznamy = [
        Z(date(2025, 1, 1), fve=0, id=1),
        Z(date(2025, 2, 1), fve=350, source=True, id=2),
        Z(date(2025, 3, 1), fve=0, id=3),
    ]
    zmeny, _ = v.prepocet_odhadu(zaznamy)
    assert [(z.meter.key, z.stara, z.nova) for z in zmeny] == [("fve", 350, 0)]


# --- Kontrola návaznosti --------------------------------------------------------


def _okoli():
    return [
        Z(date(2025, 1, 1), elektromer_vysoky=1000, fve=5000, id=1),
        Z(date(2025, 2, 1), elektromer_vysoky=1100, fve=5100, source=True, id=2),
        Z(date(2025, 3, 1), elektromer_vysoky=1200, fve=5200, id=3),
    ]


def test_kontrola_nizsi_nez_predchozi_rucni():
    kandidat = Z(date(2025, 4, 1), elektromer_vysoky=900, fve=5300)
    varovani = v.kontrola_navaznosti(_okoli(), kandidat)
    assert [(w.meter.key, w.typ, w.soused_datum) for w in varovani] == [
        ("elektromer_vysoky", "nizsi_nez_predchozi", date(2025, 3, 1))
    ]


def test_kontrola_porovnava_jen_s_rucnimi_odecty():
    # 15. 2. je pod odhadem z 1. 2., ale nad ručním odečtem z 1. 1. - v pořádku
    kandidat = Z(date(2025, 2, 15), elektromer_vysoky=1090, fve=5150)
    assert v.kontrola_navaznosti(_okoli(), kandidat) == []


def test_kontrola_vymena_na_kandidatovi_pokles_vysvetli():
    kandidat = Z(date(2025, 4, 1), elektromer_vysoky=3, fve=5300, vymena_elektromer_vysoky=True)
    assert v.kontrola_navaznosti(_okoli(), kandidat) == []


def test_kontrola_vyssi_nez_nasledujici():
    kandidat = Z(date(2025, 2, 15), elektromer_vysoky=1500, fve=5150)
    varovani = v.kontrola_navaznosti(_okoli(), kandidat)
    assert [(w.meter.key, w.typ, w.soused_datum) for w in varovani] == [
        ("elektromer_vysoky", "vyssi_nez_nasledujici", date(2025, 3, 1))
    ]


def test_kontrola_pri_editaci_neporovnava_se_sebou():
    kandidat = Z(date(2025, 3, 1), elektromer_vysoky=1150, fve=5200)
    assert v.kontrola_navaznosti(_okoli(), kandidat, exclude_id=3) == []


def test_kontrola_nekontroluje_neevidovane_fve():
    kandidat = Z(date(2025, 4, 1), elektromer_vysoky=1300, fve=0)
    assert v.kontrola_navaznosti(_okoli(), kandidat) == []
