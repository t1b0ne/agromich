from fastapi import APIRouter, HTTPException
from app.schemas.agro_schemas import SolicitudSatelital

try:
    from app.services.servicio_satelital import ProcesadorSatelitalModular
except ImportError:
    ProcesadorSatelitalModular = None

router = APIRouter(prefix="/api/v1/satelite", tags=["Análisis Satelital"])

@router.post("/analisis")
def analizar_satelite(datos: SolicitudSatelital):
    if not ProcesadorSatelitalModular:
        raise HTTPException(status_code=500, detail="Módulo Satelital no disponible.")
    procesador = ProcesadorSatelitalModular(
        estado=datos.estado,
        municipio=datos.municipio,
        fecha_inicio=datos.fecha_inicio,
        fecha_fin=datos.fecha_fin
    )
    return procesador.procesar()