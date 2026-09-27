import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from .database import DB_DATABASE, engine
from .formatovani import cislo_cz
from .meters import METERS
from .migrations import ensure_schema
from .routers import grafy, missing_data, pages, spotreba
from .templating import APP_TITLE, APP_VERSION, STATIC_DIR, templates

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_schema(engine, DB_DATABASE)
    yield


app = FastAPI(
    title=APP_TITLE,
    description="Aplikace pro sledování spotřeby energií (elektřina, plyn, voda, FVE)",
    version=APP_VERSION,
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")
ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS if o.strip()]

if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

# Mount statických souborů
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Registrace routerů
app.include_router(spotreba.router, prefix="/api", tags=["spotreba"])
app.include_router(grafy.router, prefix="/api", tags=["grafy"])
app.include_router(missing_data.router, prefix="/api", tags=["missing-data"])
app.include_router(pages.router)


# --- Chyby: JSON pro API, HTML stránka pro prohlížeč ------------------------------

_POPISKY_POLI = {"datum": "Datum", **{meter.key: meter.label for meter in METERS}}


def _je_api(request: Request) -> bool:
    return request.url.path.startswith(("/api/", "/static/"))


def _popis_chyby(chyba: dict) -> str:
    """Česká hláška z jedné chyby validace"""
    typ = chyba.get("type", "")
    ctx = chyba.get("ctx") or {}
    if typ == "missing":
        zprava = "pole je povinné"
    elif typ == "greater_than_equal":
        zprava = f"hodnota musí být alespoň {cislo_cz(ctx.get('ge', 0))}"
    elif typ == "less_than_equal":
        zprava = f"hodnota může být nejvýše {cislo_cz(ctx.get('le', 0))}"
    elif typ.startswith(("float", "int", "finite")):
        zprava = "zadejte číslo"
    elif typ.startswith("date"):
        zprava = "zadejte platné datum"
    elif typ.startswith("bool"):
        zprava = "neplatná hodnota"
    elif typ == "json_invalid":
        zprava = "neplatný formát požadavku"
    elif typ == "value_error":
        zprava = str(chyba.get("msg", "")).removeprefix("Value error, ")
    else:
        zprava = str(chyba.get("msg", "neplatná hodnota"))

    pole = next(
        (str(cast) for cast in reversed(chyba.get("loc", ())) if isinstance(cast, str) and cast not in ("body", "query", "path")),
        None,
    )
    return f"{_POPISKY_POLI.get(pole, pole)}: {zprava}" if pole else zprava


def _chybova_stranka(request: Request, status: int, nadpis: str, zprava: str):
    return templates.TemplateResponse(
        request, "chyba.html", {"status": status, "nadpis": nadpis, "zprava": zprava}, status_code=status
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    zprava = "; ".join(dict.fromkeys(_popis_chyby(chyba) for chyba in exc.errors()))
    if _je_api(request):
        return JSONResponse(status_code=422, content={"detail": zprava})
    return _chybova_stranka(request, 400, "Neplatný požadavek", zprava)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler_html(request: Request, exc: StarletteHTTPException):
    if _je_api(request):
        return await http_exception_handler(request, exc)
    if exc.status_code == 404:
        return _chybova_stranka(request, 404, "Stránka nenalezena", "Stránka nebo záznam neexistuje.")
    return _chybova_stranka(request, exc.status_code, "Chyba", str(exc.detail))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Traceback zaloguje server, výjimka se po odeslání odpovědi propaguje dál
    if _je_api(request):
        return JSONResponse(status_code=500, content={"detail": "Interní chyba serveru"})
    return _chybova_stranka(request, 500, "Chyba serveru", "Něco se pokazilo, zkuste to prosím znovu.")


@app.get("/health")
def health_check():
    """Healthcheck endpoint pro Docker - ověřuje i připojení k DB"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected", "version": APP_VERSION}
    except Exception:
        logger.exception("Health check: databáze nedostupná")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "disconnected"},
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
