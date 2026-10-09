import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_api_key
from app.schemas.clima import SolicitudClima
from app.services.servicio_clima import ServicioClimaticoAgronomicoAvanzado

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/clima", tags=["Clima Agronomico"])


@router.post("/analisis", dependencies=[Depends(require_api_key)])
def analizar_clima(datos: SolicitudClima):
    try:
        servicio = ServicioClimaticoAgronomicoAvanzado(
            estado=datos.estado, municipio=datos.municipio, latitud=datos.latitud,
            longitud=datos.longitud, fecha_inicio=datos.fecha_inicio.isoformat(),
            fecha_fin=datos.fecha_fin.isoformat(), temp_base_gdd=datos.temp_base_gdd,
        )
        resultado = servicio.ejecutar_analisis_agronomico_completo()
        if "error" in resultado:
            raise HTTPException(status_code=422, detail=resultado["error"])
        return resultado
    except HTTPException:
        raise
    except RuntimeError as exc:
        logger.warning("Servicio de clima no disponible: %s", exc)
        raise HTTPException(status_code=503, detail="Servicio de clima no disponible") from exc
    except Exception:
        logger.exception("Error no controlado en analisis climatico")
        raise HTTPException(status_code=502, detail="No fue posible completar el analisis climatico")
