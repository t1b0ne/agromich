import os
import json
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ==============================================================================
# IMPORTACIÓN DE LOS 4 SERVICIOS CON MANEJO DE EXCEPCIONES
# ==============================================================================
try:
    from app.services.servicio_satelital import ProcesadorSatelitalModular
except ImportError:
    ProcesadorSatelitalModular = None

try:
    from app.services.servicio_suelo import ExtractorSIAPDirecto
except ImportError:
    ExtractorSIAPDirecto = None

try:
    from app.services.servicio_clima import ServicioClimaticoAgronomicoAvanzado
except ImportError:
    ServicioClimaticoAgronomicoAvanzado = None

try:
    from app.services.servicio_sanidad import ServicioSanidadYProgramasEstatales
except ImportError:
    ServicioSanidadYProgramasEstatales = None

# ==============================================================================
# CONFIGURACIÓN DE FASTAPI
# ==============================================================================
app = FastAPI(
    title="AgroMich API - Inteligencia Territorial y Agronómica",
    description="API REST para análisis satelital, edáfico, climático y socioeconómico de Michoacán.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# MODELOS DE ENTRADA (SCHEMAS)
# ==============================================================================
class SolicitudSatelital(BaseModel):
    estado: str = Field(default="Michoacán de Ocampo")
    municipio: Optional[str] = Field(default=None)
    fecha_inicio: str = Field(default="2025-01-01")
    fecha_fin: str = Field(default="2025-12-31")

class SolicitudSuelo(BaseModel):
    estado: str = Field(default="Michoacán de Ocampo", description="Nombre del estado (ej. Michoacán de Ocampo, Jalisco)")
    tipo_consulta: str = Field(default="municipio", description="municipio o entidad")
    ciclo: str = Field(default="Ciclicos - Perennes")
    modalidad: str = Field(default="Riego + Temporal")
    cultivo: str = Field(default="Resumen cultivos")

class SolicitudClima(BaseModel):
    estado: str = Field(default="Michoacán de Ocampo")
    municipio: Optional[str] = Field(default=None)
    latitud: Optional[float] = Field(default=None)
    longitud: Optional[float] = Field(default=None)
    fecha_inicio: str = Field(default="2024-01-01")
    fecha_fin: str = Field(default="2024-12-31")
    temp_base_gdd: float = Field(default=10.0)

class SolicitudSanidad(BaseModel):
    estado: str = Field(default="Michoacán de Ocampo")
    municipio: Optional[str] = Field(default=None)
    cultivo: Optional[str] = Field(default=None)

# ==============================================================================
# ENDPOINTS
# ==============================================================================

@app.get("/", tags=["Salud del Sistema"])
def read_root():
    return {"status": "online", "servicio": "AgroMich API", "version": "1.0.0"}

# --- 1. MÓDULO SATELITAL ---
@app.post("/api/v1/satelite/analisis", tags=["Análisis Satelital"])
def analizar_satelite_post(datos: SolicitudSatelital):
    if not ProcesadorSatelitalModular:
        raise HTTPException(status_code=500, detail="Módulo Satelital no disponible.")
    procesador = ProcesadorSatelitalModular(
        estado=datos.estado,
        municipio=datos.municipio,
        fecha_inicio=datos.fecha_inicio,
        fecha_fin=datos.fecha_fin
    )
    return procesador.procesar()

# --- 2. MÓDULO DE SUELO / SIAP ---
@app.post("/api/v1/suelo/analisis", tags=["Suelo y Socioeconómico"])
def analizar_suelo_post(datos: SolicitudSuelo):
    if not ExtractorSIAPDirecto:
        raise HTTPException(status_code=500, detail="Módulo de Suelo no disponible.")
    extractor = ExtractorSIAPDirecto(
        estado=datos.estado,
        tipo_consulta=datos.tipo_consulta,
        ciclo=datos.ciclo,
        modalidad=datos.modalidad,
        cultivo=datos.cultivo
    )
    return extractor.ejecutar_extraccion()

# --- 3. MÓDULO CLIMÁTICO ---
@app.post("/api/v1/clima/analisis", tags=["Clima Agronómico"])
def analizar_clima_post(datos: SolicitudClima):
    if not ServicioClimaticoAgronomicoAvanzado:
        raise HTTPException(status_code=500, detail="Módulo Climático no disponible.")
    servicio = ServicioClimaticoAgronomicoAvanzado(
        estado=datos.estado,
        municipio=datos.municipio,
        latitud=datos.latitud,
        longitud=datos.longitud,
        fecha_inicio=datos.fecha_inicio,
        fecha_fin=datos.fecha_fin,
        temp_base_gdd=datos.temp_base_gdd
    )
    res = servicio.ejecutar_analisis_agronomico_completo()
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

# --- 4. MÓDULO SANIDAD Y PROGRAMAS ---
@app.post("/api/v1/sanidad-y-programas", tags=["Sanidad y Programas"])
def consultar_sanidad_post(datos: SolicitudSanidad):
    if not ServicioSanidadYProgramasEstatales:
        raise HTTPException(status_code=500, detail="Módulo Sanidad no disponible.")
    servicio = ServicioSanidadYProgramasEstatales(
        estado=datos.estado,
        municipio=datos.municipio,
        cultivo=datos.cultivo
    )
    return servicio.generar_reporte()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_api:app", host="0.0.0.0", port=8000, reload=True)