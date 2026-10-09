import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_api_key
from app.schemas.predios import SolicitudPredio
from app.services.servicio_satelital import ProcesadorSatelitalModular

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/predios", tags=["Predios y Auditorias"])


@router.post("/auditar", dependencies=[Depends(require_api_key)], summary="Audita un predio mediante datos satelitales")
def auditar_predio(payload: SolicitudPredio):
    try:
        procesador = ProcesadorSatelitalModular(
            geojson_geometry=payload.geojson,
            cultivo=payload.cultivo,
            fecha_inicio=payload.fecha_inicio_auditoria.isoformat(),
            fecha_fin=payload.fecha_fin_auditoria.isoformat(),
        )
        return {
            "status": "success",
            "mensaje": "Auditoria multivariable completada",
            "data": procesador.procesar_para_agente_y_mapa(),
        }
    except RuntimeError as exc:
        logger.warning("Servicio satelital no disponible: %s", exc)
        raise HTTPException(status_code=503, detail="Servicio satelital no disponible") from exc
    except Exception:
        logger.exception("Error no controlado en auditoria de predio")
        raise HTTPException(status_code=502, detail="No fue posible auditar el predio")
