import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Databázová konfigurace z environment variables
DB_HOST = os.getenv("DB_HOST", "10.100.10.11")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_DATABASE = os.getenv("DB_DATABASE", "spotreba-data")
DB_USER = os.getenv("DB_USER", "spotreba-data")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Spotreba-Data-2020")

# Vytvoření databázového URL
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_DATABASE}"

# Vytvoření engine
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Nastavit na True pro debug SQL dotazů
    pool_pre_ping=True,  # Automatické testování připojení
    pool_recycle=3600,   # Recyklace připojení každou hodinu
)

# Vytvoření session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base třída pro modely
Base = declarative_base()

def get_db():
    """Dependency pro získání databázové session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
