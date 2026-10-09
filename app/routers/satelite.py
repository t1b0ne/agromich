import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_api_key
from app.schemas.satelite import SolicitudSatelital
from app.services.servicio_satelital import ProcesadorSatelitalModular

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/satelite", tags=["Analisis Satelital"])


@router.post("/analisis", dependencies=[Depends(require_api_key)])
def analizar_satelite(datos: SolicitudSatelital):
    """Analiza exclusivamente la geometria proporcionada por el cliente."""
    try:
        procesador = ProcesadorSatelitalModular(
            geojson_geometry=datos.geometry,
            cultivo=datos.cultivo,
            fecha_inicio=datos.fecha_inicio.isoformat(),
            fecha_fin=datos.fecha_fin.isoformat(),
        )
        return procesador.procesar_para_agente_y_mapa()
    except RuntimeError as exc:
        logger.warning("Servicio satelital no disponible: %s", exc)
        raise HTTPException(status_code=503, detail="Servicio satelital no disponible") from exc
    except Exception:
        logger.exception("Error no controlado en analisis satelital")
        raise HTTPException(status_code=502, detail="No fue posible completar el analisis satelital")
