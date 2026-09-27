"""Definice měřičů - jediné místo, kde je pětice měřičů popsaná

Model, schémata a migrace mají sloupce vypsané explicitně (smlouva s DB a API),
veškerá logika, šablony i frontend ale čtou měřiče odsud.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Meter:
    key: str
    label: str
    kratky: str
    jednotka: str
    # Pořadí barvy řady grafu (token --color-series-<slot> v app.css)
    slot: int
    # Graf, ve kterém se měřič zobrazuje (viz SKUPINY_GRAFU) - jeden graf má jednu osu a jednotku
    graf: str
    # Nula znamená chybějící údaj, ne skutečný stav (počítadlo FVE před zavedením evidence)
    zero_is_missing: bool = False
    # Vyšší hodnota je dobrá zpráva (výroba), u spotřeby naopak
    vyssi_je_lepsi: bool = False

    @property
    def flag(self) -> str:
        """Sloupec s příznakem výměny měřiče"""
        return f"vymena_{self.key}"

    def jako_slovnik(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "kratky": self.kratky,
            "jednotka": self.jednotka,
            "slot": self.slot,
            "graf": self.graf,
        }


# Barvy (sloty) jsou z validované kategorické palety: VT, NT a FVE sdílejí graf,
# proto dostaly první tři sloty, které projdou kontrolou rozlišitelnosti ve dvojicích
METERS = (
    Meter("elektromer_vysoky", "Elektroměr vysoký tarif", "El. vysoký", "kWh", 1, "elektrina"),
    Meter("elektromer_nizky", "Elektroměr nízký tarif", "El. nízký", "kWh", 2, "elektrina"),
    Meter("plynomer", "Plynoměr", "Plyn", "m³", 4, "plyn"),
    Meter("vodomer", "Vodoměr", "Voda", "m³", 7, "voda"),
    Meter(
        "fve", "Počítadlo FVE", "FVE", "kWh", 3, "elektrina",
        zero_is_missing=True, vyssi_je_lepsi=True,
    ),
)

METERS_BY_KEY = {meter.key: meter for meter in METERS}

# Grafy na stránce Grafy: klíč, nadpis a jednotka osy (měřiče jiných jednotek se nemíchají)
SKUPINY_GRAFU = (
    ("elektrina", "Elektřina a výroba FVE", "kWh"),
    ("plyn", "Plyn", "m³"),
    ("voda", "Voda", "m³"),
)
