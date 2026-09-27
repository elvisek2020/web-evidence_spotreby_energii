from sqlalchemy import Column, Integer, Date, Double, Boolean
from .database import Base

class Spotreba(Base):
    """Model pro tabulku spotreba"""
    __tablename__ = "spotreba"

    id = Column(Integer, primary_key=True, index=True)
    # Unikátnost data dostane nová instalace z create_all, existující DB ji doplní migrace
    datum = Column(Date, nullable=False, unique=True, index=True)
    elektromer_vysoky = Column(Double, nullable=False)
    elektromer_nizky = Column(Double, nullable=False)
    plynomer = Column(Double, nullable=False)
    vodomer = Column(Double, nullable=False)
    # Kumulativní počítadlo výroby na střídači, 0 = neevidováno
    fve = Column(Double, nullable=True, default=0)
    source = Column(Boolean, default=False, nullable=False)  # False = manuální, True = automaticky doplněné

    # Příznak, že u tohoto odečtu byl nasazen nový měřič - stav proto nenavazuje
    # na předchozí záznam a rozdíl se nesmí počítat jako spotřeba
    vymena_elektromer_vysoky = Column(Boolean, default=False, nullable=False)
    vymena_elektromer_nizky = Column(Boolean, default=False, nullable=False)
    vymena_plynomer = Column(Boolean, default=False, nullable=False)
    vymena_vodomer = Column(Boolean, default=False, nullable=False)
    vymena_fve = Column(Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<Spotreba(id={self.id}, datum={self.datum}, elektromer_vysoky={self.elektromer_vysoky})>"
