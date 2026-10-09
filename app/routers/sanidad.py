from fastapi import APIRouter, Depends, HTTPException
from app.core.security import require_api_key
from app.schemas.sanidad import SolicitudSanidad

try:
    from app.services.servicio_sanidad import ServicioSanidadYProgramasEstatales
except ImportError:
    ServicioSanidadYProgramasEstatales = None

router = APIRouter(prefix="/api/v1/sanidad", tags=["Sanidad y Programas"])

@router.post("/consulta", dependencies=[Depends(require_api_key)], summary="Consulta alertas fitosanitarias y programas")
def consultar_sanidad(datos: SolicitudSanidad):
    if not ServicioSanidadYProgramasEstatales:
        raise HTTPException(status_code=500, detail="Módulo Sanidad no disponible.")
    servicio = ServicioSanidadYProgramasEstatales(
        estado=datos.estado,
        municipio=datos.municipio,
        cultivo=datos.cultivo
    )
    return servicio.generar_reporte()
