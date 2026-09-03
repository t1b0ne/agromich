from fastapi import APIRouter, HTTPException
from app.schemas.agro_schemas import SolicitudClima

try:
    from app.services.servicio_clima import ServicioClimaticoAgronomicoAvanzado
except ImportError:
    ServicioClimaticoAgronomicoAvanzado = None

router = APIRouter(prefix="/api/v1/clima", tags=["Clima Agronómico"])

@router.post("/analisis")
def analizar_clima(datos: SolicitudClima):
    if not ServicioClimaticoAgronomicoAvanzado:
        raise HTTPException(status_code=500, detail="Módulo Climático no disponible.")
    servicio = ServicioClimaticoAgronomicoAvanzado(
        estado=datos.estado,
        municipio=datos.municipio,
        latitud=datos.latitud,
        longitud=datos.longitud,
        fecha_inicio=datos.fecha_inicio,
        fecha_fin=datos.fecha_fin,
        temp_base_gdd=datos.temp_base_gdd
    )
    res = servicio.ejecutar_analisis_agronomico_completo()
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res