from pydantic import BaseModel, Field, validator
from datetime import date
from typing import Optional

class SpotrebaBase(BaseModel):
    """Základní schéma pro spotřebu"""
    datum: date
    elektromer_vysoky: float = Field(..., ge=0, description="Stav elektroměru vysoký tarif v kWh")
    elektromer_nizky: float = Field(..., ge=0, description="Stav elektroměru nízký tarif v kWh")
    plynomer: float = Field(..., ge=0, description="Stav plynoměru v m³")
    vodomer: float = Field(..., ge=0, description="Stav vodoměru v m³")
    source: bool = Field(default=False, description="Zdroj dat: False = manuální, True = automaticky doplněné")

    @validator('datum')
    def validate_datum(cls, v):
        """Validace data - nesmí být v budoucnosti"""
        if v > date.today():
            raise ValueError('Datum nesmí být v budoucnosti')
        return v

class SpotrebaCreate(SpotrebaBase):
    """Schéma pro vytvoření nového záznamu"""
    pass

class SpotrebaUpdate(BaseModel):
    """Schéma pro aktualizaci záznamu"""
    datum: Optional[date] = None
    elektromer_vysoky: Optional[float] = Field(None, ge=0)
    elektromer_nizky: Optional[float] = Field(None, ge=0)
    plynomer: Optional[float] = Field(None, ge=0)
    vodomer: Optional[float] = Field(None, ge=0)
    source: Optional[bool] = None

    @validator('datum')
    def validate_datum(cls, v):
        if v is not None and v > date.today():
            raise ValueError('Datum nesmí být v budoucnosti')
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

class MissingDataSuggestion(BaseModel):
    """Schéma pro návrh chybějících dat"""
    datum: date
    elektromer_vysoky: float
    elektromer_nizky: float
    plynomer: float
    vodomer: float
    source: bool = True  # Vždy automaticky doplněné

class ChartData(BaseModel):
    """Schéma pro data grafů"""
    labels: list[str]  # Měsíce
    elektromer_vysoky: list[float]
    elektromer_nizky: list[float]
    plynomer: list[float]
    vodomer: list[float]
    source_flags: list[bool]  # Označení zdroje dat pro každý měsíc
