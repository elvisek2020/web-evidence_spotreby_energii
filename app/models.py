from sqlalchemy import Column, Integer, Date, Float, Boolean
from sqlalchemy.sql import func
from .database import Base

class Spotreba(Base):
    """Model pro tabulku spotreba"""
    __tablename__ = "spotreba"
    
    id = Column(Integer, primary_key=True, index=True)
    datum = Column(Date, nullable=False, index=True)
    elektromer_vysoky = Column(Float, nullable=False)
    elektromer_nizky = Column(Float, nullable=False)
    plynomer = Column(Float, nullable=False)
    vodomer = Column(Float, nullable=False)
    fve = Column(Float, nullable=True, default=0)
    source = Column(Boolean, default=False, nullable=False)  # False = manuální, True = automaticky doplněné

    # Příznak, že u tohoto odečtu byl nasazen nový měřič - stav proto nenavazuje
    # na předchozí záznam a rozdíl se nesmí počítat jako spotřeba
    vymena_elektromer_vysoky = Column(Boolean, default=False, nullable=False)
    vymena_elektromer_nizky = Column(Boolean, default=False, nullable=False)
    vymena_plynomer = Column(Boolean, default=False, nullable=False)
    vymena_vodomer = Column(Boolean, default=False, nullable=False)
    
    def __repr__(self):
        return f"<Spotreba(id={self.id}, datum={self.datum}, elektromer_vysoky={self.elektromer_vysoky})>"
