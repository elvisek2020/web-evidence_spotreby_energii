import logging
import os
from datetime import date

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from .database import get_db, engine
from .routers import spotreba, grafy, missing_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Evidování spotřeby",
    description="Aplikace pro sledování spotřeby energií (elektřina, plyn, voda)",
    version="2.1.0",
    docs_url=None,
    redoc_url=None,
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
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# Mount statických souborů
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Konfigurace Jinja2 templatů
templates = Jinja2Templates(directory="app/templates")

# Registrace routerů
app.include_router(spotreba.router, prefix="/api", tags=["spotreba"])
app.include_router(grafy.router, prefix="/api", tags=["grafy"])
app.include_router(missing_data.router, prefix="/api", tags=["missing-data"])

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    """Hlavní stránka s přehledem dat"""
    from .routers.spotreba import get_spotreba_list
    
    # Získání dat pro hlavní stránku
    spotreba_data = await get_spotreba_list(db=db, limit=12, offset=0, source_filter=None)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "spotreba_data": spotreba_data,
        "app_title": "Evidování spotřeby"
    })

@app.get("/evidovat", response_class=HTMLResponse)
async def evidovat_page(request: Request, db: Session = Depends(get_db)):
    """Stránka pro přidávání nových záznamů"""
    from .models import Spotreba
    from sqlalchemy import desc
    latest = db.query(Spotreba).order_by(desc(Spotreba.datum)).first()
    return templates.TemplateResponse("evidovat.html", {
        "request": request,
        "app_title": "Evidování spotřeby",
        "today": date.today().isoformat(),
        "latest": latest
    })

@app.get("/edit/{spotreba_id}", response_class=HTMLResponse)
async def edit_page(request: Request, spotreba_id: int, db: Session = Depends(get_db)):
    """Stránka pro editaci záznamu"""
    from .routers.spotreba import get_spotreba
    
    spotreba_data = await get_spotreba(spotreba_id=spotreba_id, db=db)
    
    return templates.TemplateResponse("edit.html", {
        "request": request,
        "spotreba": spotreba_data,
        "app_title": "Evidování spotřeby",
        "today": date.today().isoformat()
    })

@app.get("/grafy", response_class=HTMLResponse)
async def grafy_page(request: Request):
    """Stránka s grafy spotřeby"""
    return templates.TemplateResponse("grafy.html", {
        "request": request,
        "app_title": "Evidování spotřeby"
    })

@app.get("/missing-data", response_class=HTMLResponse)
async def missing_data_page(request: Request, db: Session = Depends(get_db)):
    """Stránka pro automatické doplnění chybějících dat"""
    from .routers.missing_data import get_missing_data_suggestions
    
    suggestions = await get_missing_data_suggestions(db=db)
    
    return templates.TemplateResponse("missing_data.html", {
        "request": request,
        "suggestions": suggestions,
        "app_title": "Evidování spotřeby"
    })

@app.get("/health")
async def health_check():
    """Healthcheck endpoint pro Docker - ověřuje i připojení k DB"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        logger.exception("Health check: databáze nedostupná")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "disconnected"},
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
