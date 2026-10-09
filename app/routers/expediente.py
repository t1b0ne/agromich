import logging
from datetime import date
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.security import require_api_key
from app.schemas.expediente import SolicitudImagenesHistoricas
from app.schemas.agro_schemas import validar_geojson
from app.services.servicio_expediente import ServicioExpediente
from app.services.servicio_expediente_ambiental import ExpedienteAmbientalService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/expediente", tags=["Expediente"])


class SolicitudExpediente(BaseModel):
    nombre_huerto: str = Field(..., min_length=2, max_length=120)
    productor: str = Field(..., min_length=2, max_length=120)
    municipio: str = Field(default="Uruapan", min_length=2, max_length=100)
    cultivo: str = Field(default="aguacate", min_length=2, max_length=80)
    geometry: Dict[str, Any]
    anio_inicio: int = Field(default=2018, ge=1984, le=date.today().year)
    anio_fin: int = Field(default_factory=lambda: date.today().year, ge=1984, le=date.today().year)

    @field_validator("geometry")
    @classmethod
    def validar_geometria(cls, value):
        return validar_geojson(value)

    @model_validator(mode="after")
    def validar_anios(self):
        if self.anio_inicio > self.anio_fin:
            raise ValueError("anio_inicio debe ser menor o igual a anio_fin")
        return self


@router.post("/generar-completo", dependencies=[Depends(require_api_key)])
def generar_expediente_completo(payload: SolicitudExpediente):
    try:
        expediente = ExpedienteAmbientalService(payload.model_dump()).generar_expediente()
        return {"status": "success", "mensaje": "Expediente generado", "expediente": expediente}
    except RuntimeError as exc:
        logger.warning("Servicio geoespacial no disponible: %s", exc)
        raise HTTPException(status_code=503, detail="Servicio geoespacial no disponible") from exc
    except Exception:
        logger.exception("Error no controlado generando expediente")
        raise HTTPException(status_code=502, detail="No fue posible generar el expediente")


@router.post("/imagenes-historicas", dependencies=[Depends(require_api_key)])
def generar_imagenes_historicas(solicitud: SolicitudImagenesHistoricas):
    try:
        return ServicioExpediente(
            geometry=solicitud.geometry, mes_inicio=solicitud.mes_inicio, mes_fin=solicitud.mes_fin,
        ).generar(solicitud.anios)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        logger.exception("Error no controlado generando imagenes historicas")
        raise HTTPException(status_code=502, detail="No fue posible generar las imagenes historicas")
