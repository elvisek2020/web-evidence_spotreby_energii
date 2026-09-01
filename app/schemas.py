from pydantic import BaseModel, Field, validator
from datetime import date
from typing import Optional

MAX_METER_VALUE = 9_999_999.99

class SpotrebaBase(BaseModel):
    """Základní schéma pro spotřebu"""
    datum: date
    elektromer_vysoky: float = Field(..., ge=0, le=MAX_METER_VALUE, description="Stav elektroměru vysoký tarif v kWh")
    elektromer_nizky: float = Field(..., ge=0, le=MAX_METER_VALUE, description="Stav elektroměru nízký tarif v kWh")
    plynomer: float = Field(..., ge=0, le=MAX_METER_VALUE, description="Stav plynoměru v m³")
    vodomer: float = Field(..., ge=0, le=MAX_METER_VALUE, description="Stav vodoměru v m³")
    fve: Optional[float] = Field(default=0, ge=0, le=MAX_METER_VALUE, description="Stav počítadla výroby FVE v kWh (kumulativní, 0 = neevidováno)")
    source: bool = Field(default=False, description="Zdroj dat: False = manuální, True = automaticky doplněné")
    vymena_elektromer_vysoky: bool = Field(default=False, description="U tohoto odečtu byl nasazen nový elektroměr (vysoký tarif)")
    vymena_elektromer_nizky: bool = Field(default=False, description="U tohoto odečtu byl nasazen nový elektroměr (nízký tarif)")
    vymena_plynomer: bool = Field(default=False, description="U tohoto odečtu byl nasazen nový plynoměr")
    vymena_vodomer: bool = Field(default=False, description="U tohoto odečtu byl nasazen nový vodoměr")
    vymena_fve: bool = Field(default=False, description="U tohoto odečtu bylo nasazeno nové počítadlo FVE")

    @validator('datum')
    def validate_datum(cls, v):
        if v > date.today():
            raise ValueError('Datum nesmí být v budoucnosti')
        if v < date(2000, 1, 1):
            raise ValueError('Datum nesmí být před rokem 2000')
        return v

class SpotrebaCreate(SpotrebaBase):
    """Schéma pro vytvoření nového záznamu

    Na vstupu je počítadlo FVE povinné stejně jako ostatní měřiče. V SpotrebaBase
    zůstává volitelné, protože z něj dědí i odpověď a historické záznamy mají fve
    prázdné.
    """
    fve: float = Field(..., ge=0, le=MAX_METER_VALUE, description="Stav počítadla výroby FVE v kWh (kumulativní, 0 = neevidováno)")

class SpotrebaUpdate(BaseModel):
    """Schéma pro aktualizaci záznamu"""
    datum: Optional[date] = None
    elektromer_vysoky: Optional[float] = Field(None, ge=0, le=MAX_METER_VALUE)
    elektromer_nizky: Optional[float] = Field(None, ge=0, le=MAX_METER_VALUE)
    plynomer: Optional[float] = Field(None, ge=0, le=MAX_METER_VALUE)
    vodomer: Optional[float] = Field(None, ge=0, le=MAX_METER_VALUE)
    fve: Optional[float] = Field(None, ge=0, le=MAX_METER_VALUE)
    source: Optional[bool] = None
    vymena_elektromer_vysoky: Optional[bool] = None
    vymena_elektromer_nizky: Optional[bool] = None
    vymena_plynomer: Optional[bool] = None
    vymena_vodomer: Optional[bool] = None
    vymena_fve: Optional[bool] = None

    @validator('datum')
    def validate_datum(cls, v):
        if v is not None and v > date.today():
            raise ValueError('Datum nesmí být v budoucnosti')
        if v is not None and v < date(2000, 1, 1):
            raise ValueError('Datum nesmí být před rokem 2000')
        return v

class SpotrebaResponse(SpotrebaBase):
    """Schéma pro odpověď s daty spotřeby"""
    id: int
    
    class Config:
        from_attributes = True

class SpotrebaWithDiff(SpotrebaResponse):
    """Schéma pro spotřebu s vypočítanými rozdíly"""
    diff_elektromer_vysoky: Optional[float] = None
    diff_elektromer_nizky: Optional[float] = None
    diff_plynomer: Optional[float] = None
    diff_vodomer: Optional[float] = None
    diff_fve: Optional[float] = None

class MissingDataSuggestion(BaseModel):
    """Schéma pro návrh chybějících dat"""
    datum: date
    elektromer_vysoky: float = Field(..., ge=0, le=MAX_METER_VALUE)
    elektromer_nizky: float = Field(..., ge=0, le=MAX_METER_VALUE)
    plynomer: float = Field(..., ge=0, le=MAX_METER_VALUE)
    vodomer: float = Field(..., ge=0, le=MAX_METER_VALUE)
    fve: float = Field(default=0, ge=0, le=MAX_METER_VALUE)
    source: bool = True  # Vždy automaticky doplněné

    @validator('datum')
    def validate_datum(cls, v):
        if v > date.today():
            raise ValueError('Datum nesmí být v budoucnosti')
        if v < date(2000, 1, 1):
            raise ValueError('Datum nesmí být před rokem 2000')
        return v

class ChartData(BaseModel):
    """Schéma pro data grafů

    Hodnota None znamená přerušení řady - u měsíční spotřeby vzniká tam, kde byl
    vyměněn měřič a rozdíl oproti předchozímu odečtu není spotřeba.
    """
    labels: list[str]  # Měsíce
    elektromer_vysoky: list[Optional[float]]
    elektromer_nizky: list[Optional[float]]
    plynomer: list[Optional[float]]
    vodomer: list[Optional[float]]
    fve: list[Optional[float]]
    source_flags: list[bool]  # Označení zdroje dat pro každý měsíc
