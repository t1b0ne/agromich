from fastapi import APIRouter, HTTPException
from app.schemas.agro_schemas import SolicitudSanidad

try:
    from app.services.servicio_sanidad import ServicioSanidadYProgramasEstatales
except ImportError:
    ServicioSanidadYProgramasEstatales = None

router = APIRouter(prefix="/api/v1", tags=["Sanidad y Programas"])

@router.post("/sanidad-y-programas")
def consultar_sanidad(datos: SolicitudSanidad):
    if not ServicioSanidadYProgramasEstatales:
        raise HTTPException(status_code=500, detail="Módulo Sanidad no disponible.")
    servicio = ServicioSanidadYProgramasEstatales(
        estado=datos.estado,
        municipio=datos.municipio,
        cultivo=datos.cultivo
    )
    return servicio.generar_reporte()