from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from app.services.servicio_expediente_ambiental import ExpedienteAmbientalService

router = APIRouter(prefix="/api/v1/expediente", tags=["Expediente de Cumplimiento Ambiental"])

class SolicitudExpediente(BaseModel):
    nombre_huerto: str = Field(..., description="Nombre del huerto")
    productor: str = Field(..., description="Nombre del productor")
    municipio: str = Field("Uruapan", description="Municipio en Michoacán")
    cultivo: str = Field("aguacate", description="Cultivo declarado")
    geometry: Dict[str, Any] = Field(..., description="Polígono en GeoJSON")
    anio_inicio: Optional[int] = Field(2018)
    anio_fin: Optional[int] = Field(2026)

@router.post("/generar-completo")
def generar_expediente_completo(payload: SolicitudExpediente):
    """
    Endpoint maestro que empaqueta todos los datos analíticos para alimentar al agente de IA
    o emitir el expediente de cumplimiento ambiental formal.
    """
    try:
        servicio = ExpedienteAmbientalService(payload.dict())
        expediente = servicio.generar_expediente()

        return {
            "status": "success",
            "mensaje": "Expediente maestro generado correctamente para procesamiento por Agente",
            "expediente": expediente
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))