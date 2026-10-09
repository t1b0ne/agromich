from fastapi import APIRouter, Depends, HTTPException
from app.core.security import require_api_key
from app.schemas.suelo import SolicitudSuelo

try:
    from app.services.servicio_suelo import ExtractorSIAPDirecto
except ImportError:
    ExtractorSIAPDirecto = None

router = APIRouter(prefix="/api/v1/suelo", tags=["Suelo y Socioeconómico"])

@router.post("/analisis", dependencies=[Depends(require_api_key)])
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
