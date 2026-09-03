import sys
import os

# Asegurar que la raíz del proyecto esté en el path de Python para importar los servicios
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importar los routers modulares
from app.routers import satelite, suelo, clima, sanidad

app = FastAPI(
    title="AgroMich API - Inteligencia Territorial y Agronómica",
    description="API REST modular para agentes autónomos (Hermes/Eve).",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar los routers
app.include_router(satelite.router)
app.include_router(suelo.router)
app.include_router(clima.router)
app.include_router(sanidad.router)

@app.get("/", tags=["Salud del Sistema"])
def read_root():
    return {"status": "online", "architecture": "modular", "version": "2.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)