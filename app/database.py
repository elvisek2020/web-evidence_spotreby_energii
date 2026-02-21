import os
import sys
import logging
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

_REQUIRED_ENV_VARS = ["DB_HOST", "DB_PORT", "DB_DATABASE", "DB_USER", "DB_PASSWORD"]

_missing = [var for var in _REQUIRED_ENV_VARS if not os.getenv(var)]
if _missing:
    logger.critical("Chybí povinné environment variables: %s", ", ".join(_missing))
    sys.exit(1)

DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ["DB_PORT"]
DB_DATABASE = os.environ["DB_DATABASE"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]

DATABASE_URL = (
    f"mysql+pymysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
    f"@{DB_HOST}:{DB_PORT}/{quote_plus(DB_DATABASE)}"
)

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10,
    connect_args={"connect_timeout": 10},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Dependency pro získání databázové session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
