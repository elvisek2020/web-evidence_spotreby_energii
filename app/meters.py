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
    barva: str
    # Barva přepínače v Tailwind třídách (bg-<barva>-100 apod.)
    tw_barva: str
    # Nula znamená chybějící údaj, ne skutečný stav (počítadlo FVE před zavedením evidence)
    zero_is_missing: bool = False
    # Vyšší hodnota je dobrá zpráva (výroba), u spotřeby naopak
    vyssi_je_lepsi: bool = False

    @property
    def flag(self) -> str:
        """Sloupec s příznakem výměny měřiče"""
        return f"vymena_{self.key}"

    @property
    def osa(self) -> str:
        """Osa grafu podle jednotky - kWh a m³ mají řádově jiné hodnoty"""
        return "m3" if self.jednotka == "m³" else "kwh"

    def jako_slovnik(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "kratky": self.kratky,
            "jednotka": self.jednotka,
            "barva": self.barva,
            "osa": self.osa,
            "vyssi_je_lepsi": self.vyssi_je_lepsi,
        }


METERS = (
    Meter("elektromer_vysoky", "Elektroměr vysoký tarif", "El. vysoký", "kWh", "#3B82F6", "blue"),
    Meter("elektromer_nizky", "Elektroměr nízký tarif", "El. nízký", "kWh", "#EF4444", "red"),
    Meter("plynomer", "Plynoměr", "Plyn", "m³", "#F59E0B", "yellow"),
    Meter("vodomer", "Vodoměr", "Voda", "m³", "#10B981", "green"),
    Meter(
        "fve", "Počítadlo FVE", "FVE", "kWh", "#8B5CF6", "purple",
        zero_is_missing=True, vyssi_je_lepsi=True,
    ),
)

METERS_BY_KEY = {meter.key: meter for meter in METERS}
