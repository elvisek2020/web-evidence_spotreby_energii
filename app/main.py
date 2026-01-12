from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from .database import get_db
from .routers import spotreba, grafy, missing_data
import os

# Vytvoření FastAPI aplikace
app = FastAPI(
    title="Evidování spotřeby",
    description="Aplikace pro sledování spotřeby energií (elektřina, plyn, voda)",
    version="2.0.0",
    docs_url=None,  # Zakázání Swagger UI
    redoc_url=None  # Zakázání ReDoc
)

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
async def evidovat_page(request: Request):
    """Stránka pro přidávání nových záznamů"""
    return templates.TemplateResponse("evidovat.html", {
        "request": request,
        "app_title": "Evidování spotřeby"
    })

@app.get("/edit/{spotreba_id}", response_class=HTMLResponse)
async def edit_page(request: Request, spotreba_id: int, db: Session = Depends(get_db)):
    """Stránka pro editaci záznamu"""
    from .routers.spotreba import get_spotreba
    
    spotreba_data = await get_spotreba(spotreba_id=spotreba_id, db=db)
    
    return templates.TemplateResponse("edit.html", {
        "request": request,
        "spotreba": spotreba_data,
        "app_title": "Evidování spotřeby"
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
    """Healthcheck endpoint pro Docker"""
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
