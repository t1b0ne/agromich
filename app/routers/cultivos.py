import logging
from datetime import date
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.security import require_api_key
from app.schemas.agro_schemas import validar_geojson
from app.services.servicio_clasificacion_cultivos import ClasificadorCultivosService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/cultivos", tags=["Clasificacion de Cultivos"])


class SolicitudClasificacion(BaseModel):
    geometry: Dict[str, Any]
    cultivo: str = Field(default="aguacate", min_length=2, max_length=80)
    anio: int = Field(default_factory=lambda: date.today().year, ge=2017, le=date.today().year)

    @field_validator("geometry")
    @classmethod
    def validar_geometria(cls, value):
        return validar_geojson(value)


@router.post("/clasificar-y-verificar", dependencies=[Depends(require_api_key)])
def clasificar_predio_cultivo(payload: SolicitudClasificacion):
    try:
        resultado = ClasificadorCultivosService(
            geojson_geometry=payload.geometry, cultivo_declarado=payload.cultivo, anio=payload.anio,
        ).analizar_cultivo()
        return {"status": "success", "mensaje": "Clasificacion ejecutada", "resultado": resultado}
    except RuntimeError as exc:
        logger.warning("Servicio geoespacial no disponible: %s", exc)
        raise HTTPException(status_code=503, detail="Servicio geoespacial no disponible") from exc
    except Exception:
        logger.exception("Error no controlado clasificando cultivo")
        raise HTTPException(status_code=502, detail="No fue posible clasificar el cultivo")
