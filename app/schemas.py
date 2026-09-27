from datetime import date
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_METER_VALUE = 9_999_999.99

StavMerice = Annotated[float, Field(ge=0, le=MAX_METER_VALUE)]


def _over_datum(v: date) -> date:
    if v > date.today():
        raise ValueError("nesmí být v budoucnosti")
    if v < date(2000, 1, 1):
        raise ValueError("nesmí být před rokem 2000")
    return v


# --- Vstupy ---------------------------------------------------------------------


class SpotrebaCreate(BaseModel):
    """Schéma pro vytvoření nového záznamu

    Počítadlo FVE je povinné stejně jako ostatní měřiče, 0 znamená neevidováno.
    """
    datum: date
    elektromer_vysoky: StavMerice
    elektromer_nizky: StavMerice
    plynomer: StavMerice
    vodomer: StavMerice
    fve: StavMerice
    source: bool = False
    vymena_elektromer_vysoky: bool = False
    vymena_elektromer_nizky: bool = False
    vymena_plynomer: bool = False
    vymena_vodomer: bool = False
    vymena_fve: bool = False

    @field_validator("datum")
    @classmethod
    def validate_datum(cls, v: date) -> date:
        return _over_datum(v)


class SpotrebaUpdate(BaseModel):
    """Schéma pro aktualizaci záznamu - vynechaná pole se nemění"""
    datum: Optional[date] = None
    elektromer_vysoky: Optional[StavMerice] = None
    elektromer_nizky: Optional[StavMerice] = None
    plynomer: Optional[StavMerice] = None
    vodomer: Optional[StavMerice] = None
    fve: Optional[StavMerice] = None
    source: Optional[bool] = None
    vymena_elektromer_vysoky: Optional[bool] = None
    vymena_elektromer_nizky: Optional[bool] = None
    vymena_plynomer: Optional[bool] = None
    vymena_vodomer: Optional[bool] = None
    vymena_fve: Optional[bool] = None

    @field_validator("*", mode="before")
    @classmethod
    def zakaz_null(cls, v):
        # Sloupce jsou v DB povinné, explicitní null by skončil chybou při ukládání
        if v is None:
            raise ValueError("nesmí být prázdné")
        return v

    @field_validator("datum")
    @classmethod
    def validate_datum(cls, v: date) -> date:
        return _over_datum(v)


class KontrolaVstup(BaseModel):
    """Odečet ke kontrole návaznosti na okolní ruční odečty (id se vynechá při editaci)"""
    id: Optional[int] = None
    datum: date
    elektromer_vysoky: Optional[float] = None
    elektromer_nizky: Optional[float] = None
    plynomer: Optional[float] = None
    vodomer: Optional[float] = None
    fve: Optional[float] = None
    vymena_elektromer_vysoky: bool = False
    vymena_elektromer_nizky: bool = False
    vymena_plynomer: bool = False
    vymena_vodomer: bool = False
    vymena_fve: bool = False


class NavrhVstup(BaseModel):
    """Vytvoření jednoho navrženého záznamu - hodnoty dopočítá server z aktuálních dat"""
    datum: date


# --- Odpovědi -------------------------------------------------------------------


class SpotrebaResponse(BaseModel):
    """Schéma pro odpověď s daty spotřeby"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    datum: date
    elektromer_vysoky: float
    elektromer_nizky: float
    plynomer: float
    vodomer: float
    fve: Optional[float] = 0
    source: bool
    vymena_elektromer_vysoky: bool
    vymena_elektromer_nizky: bool
    vymena_plynomer: bool
    vymena_vodomer: bool
    vymena_fve: bool


class SpotrebaWithDiff(SpotrebaResponse):
    """Schéma pro spotřebu s rozdílem oproti předchozímu záznamu"""
    diff_elektromer_vysoky: Optional[float] = None
    diff_elektromer_nizky: Optional[float] = None
    diff_plynomer: Optional[float] = None
    diff_vodomer: Optional[float] = None
    diff_fve: Optional[float] = None


class SpotrebaUlozeno(SpotrebaResponse):
    """Uložený záznam a počet odhadů přepočtených kvůli změně"""
    prepocteno_odhadu: int = 0


class KontrolaVarovani(BaseModel):
    meric: str
    label: str
    jednotka: str
    typ: str  # nizsi_nez_predchozi | vyssi_nez_nasledujici
    hodnota: float
    soused_datum: date
    soused_hodnota: float
    zprava: str


class KontrolaVysledek(BaseModel):
    varovani: list[KontrolaVarovani]


class MissingDataSuggestion(BaseModel):
    """Schéma pro návrh chybějících dat"""
    datum: date
    elektromer_vysoky: float
    elektromer_nizky: float
    plynomer: float
    vodomer: float
    fve: float = 0
    source: bool = True  # Vždy automaticky doplněné


class GrafRada(BaseModel):
    label: str
    jednotka: str
    hodnoty: list[Optional[float]]
    odhad: list[bool]
    poznamka: list[Optional[str]]


class GrafAnomalie(BaseModel):
    meric: str
    label: str
    jednotka: str
    od: date
    do: date
    spotreba: float


class GrafData(BaseModel):
    """Data grafu: popisky osy X a řada hodnot pro každý měřič

    None v hodnotách přerušuje řadu (měsíc s výměnou měřiče, chybějící údaj),
    důvod je v poznámce. Anomálie jsou poklesy stavu bez označené výměny.
    """
    popisky: list[str]
    popisky_dlouhe: list[str]
    rady: dict[str, GrafRada]
    anomalie: list[GrafAnomalie]


class YoYSrovnani(BaseModel):
    od: date
    do: date
    loni: float
    rozdil: float
    rozdil_pct: Optional[float]
    hodnoceni: str  # lepsi | horsi | stejne


class YoYMeric(BaseModel):
    hodnota: Optional[float]
    pokryto_dni: int
    uplne: bool
    odhad: bool
    srovnani: Optional[YoYSrovnani]


class YoYRok(BaseModel):
    rok: int
    od: date
    do: date
    dni: int
    uplny_rok: bool
    merice: dict[str, YoYMeric]


class YoYData(BaseModel):
    roky: list[YoYRok]  # nejnovější rok první


class PrepocetZmena(BaseModel):
    id: int
    datum: date
    meric: str
    label: str
    stara: Optional[float]
    nova: float


class PrepocetKonflikt(BaseModel):
    id: int
    datum: date
    popis: str


class PrepocetNahled(BaseModel):
    zmeny: list[PrepocetZmena]
    konflikty: list[PrepocetKonflikt]
    pocet_odhadu: int
