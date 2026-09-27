"""Sdílená konfigurace Jinja2 šablon: cesty, verze aplikace, globální proměnné a filtry"""

import json
import logging
from pathlib import Path

from fastapi.templating import Jinja2Templates

from . import formatovani
from .meters import METERS

logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
TEMPLATES_DIR = APP_DIR / "templates"

APP_TITLE = "Evidování spotřeby"


def _nacti_verzi() -> str:
    """Verze z static/version.json, zvyšuje se ručně při vydání"""
    try:
        return json.loads((STATIC_DIR / "version.json").read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        logger.warning("Verzi aplikace se nepodařilo načíst ze static/version.json")
        return "n/a"


APP_VERSION = _nacti_verzi()

templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.globals.update(
    APP_TITLE=APP_TITLE,
    APP_VERSION=APP_VERSION,
    METERS=METERS,
    METERS_INFO=[meter.jako_slovnik() for meter in METERS],
)
templates.env.filters.update(
    datum_cz=formatovani.datum_cz,
    datum_kratke=formatovani.datum_kratke,
    mesic_cz=formatovani.mesic_cz,
    mesic_kratky=formatovani.mesic_kratky,
    cislo=formatovani.cislo,
    cislo_input=formatovani.cislo_input,
    cislo_cz=formatovani.cislo_cz,
    pocet_dni=formatovani.pocet_dni,
    pred_dny=formatovani.pred_dny,
)
