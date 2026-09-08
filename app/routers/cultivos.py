from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from app.services.servicio_clasificacion_cultivos import ClasificadorCultivosService

router = APIRouter(prefix="/api/v1/cultivos", tags=["Clasificación de Cultivos"])

class SolicitudClasificacion(BaseModel):
    geometry: Dict[str, Any] = Field(..., description="Geometría en formato GeoJSON (Polygon o Feature)")
    cultivo: str = Field("aguacate", description="Cultivo declarado por el productor (ej. aguacate, berries, zarzamora)")
    anio: Optional[int] = Field(2025, description="Año de análisis satelital")

@router.post("/clasificar-y-verificar")
def clasificar_predio_cultivo(payload: SolicitudClasificacion):
    """
    Endpoint especializado para diferenciar mediante GEE si un predio 
    corresponde a Aguacate (dosel arbóreo) o Berries (macrotúneles).
    """
    try:
        clasificador = ClasificadorCultivosService(
            geojson_geometry=payload.geometry,
            cultivo_declarado=payload.cultivo,
            anio=payload.anio
        )
        
        resultado = clasificador.analizar_cultivo()

        return {
            "status": "success",
            "mensaje": "Clasificación multiespectral y textural ejecutada con éxito",
            "resultado": resultado
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))