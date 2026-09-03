from fastapi import APIRouter, HTTPException
from app.schemas.agro_schemas import SolicitudSuelo

try:
    from app.services.servicio_suelo import ExtractorSIAPDirecto
except ImportError:
    ExtractorSIAPDirecto = None

router = APIRouter(prefix="/api/v1/suelo", tags=["Suelo y Socioeconómico"])

@router.post("/analisis")
def analizar_suelo(datos: SolicitudSuelo):
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