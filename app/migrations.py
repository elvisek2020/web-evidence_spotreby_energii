"""Úprava schématu databáze při startu aplikace

Nová instalace dostane celou tabulku z modelu, existující databáze jen chybějící
sloupce a unikátní index na datum. Migrace se nespouští ručně.
"""

import logging

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from .database import Base
from . import models  # noqa: F401 - registrace tabulky v Base.metadata

logger = logging.getLogger(__name__)

# Sloupce přidané do aplikace postupně; starší instalace je nemají
_CHYBEJICI_SLOUPCE = {
    "fve": "ALTER TABLE spotreba ADD COLUMN fve DOUBLE NULL DEFAULT 0",
    "vymena_elektromer_vysoky": "ALTER TABLE spotreba ADD COLUMN vymena_elektromer_vysoky TINYINT(1) NOT NULL DEFAULT 0",
    "vymena_elektromer_nizky": "ALTER TABLE spotreba ADD COLUMN vymena_elektromer_nizky TINYINT(1) NOT NULL DEFAULT 0",
    "vymena_plynomer": "ALTER TABLE spotreba ADD COLUMN vymena_plynomer TINYINT(1) NOT NULL DEFAULT 0",
    "vymena_vodomer": "ALTER TABLE spotreba ADD COLUMN vymena_vodomer TINYINT(1) NOT NULL DEFAULT 0",
    "vymena_fve": "ALTER TABLE spotreba ADD COLUMN vymena_fve TINYINT(1) NOT NULL DEFAULT 0",
}


def ensure_schema(engine: Engine, db_name: str) -> None:
    # Tabulku vytvoří jen při nové instalaci, existující nechá beze změny
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        for column, ddl in _CHYBEJICI_SLOUPCE.items():
            exists = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema=:db AND table_name='spotreba' AND column_name=:col"
            ), {"db": db_name, "col": column}).scalar()
            if not exists:
                conn.execute(text(ddl))
                logger.info("Migrace: přidán sloupec %s", column)

        _zajisti_unikatni_datum(conn, db_name)


def _zajisti_unikatni_datum(conn: Connection, db_name: str) -> None:
    """Unikátní index na datum, pokud v tabulce nejsou duplicity

    Jméno indexu se v existujících instalacích může lišit, hledá se proto podle sloupce.
    """
    unikatni = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.statistics "
        "WHERE table_schema=:db AND table_name='spotreba' AND column_name='datum' AND non_unique=0"
    ), {"db": db_name}).scalar()
    if unikatni:
        return

    duplicity = conn.execute(text(
        "SELECT datum FROM spotreba GROUP BY datum HAVING COUNT(*) > 1 ORDER BY datum"
    )).scalars().all()
    if duplicity:
        logger.error(
            "Unikátní index na datum nelze vytvořit, v tabulce jsou duplicitní data: %s. "
            "Po jejich odstranění se index doplní při dalším startu.",
            ", ".join(str(datum) for datum in duplicity),
        )
        return

    conn.execute(text("ALTER TABLE spotreba ADD UNIQUE INDEX uq_spotreba_datum (datum)"))
    logger.info("Migrace: přidán unikátní index na datum")
