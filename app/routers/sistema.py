from importlib.util import find_spec

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.sistema import EstadoServicio, EstadoSistema

router = APIRouter(prefix="/api/v1/sistema", tags=["Sistema"])


@router.get("/salud", response_model=EstadoSistema, summary="Comprobación básica de disponibilidad")
def salud() -> EstadoSistema:
    """Liveness probe: no realiza llamadas remotas ni consume cuotas externas."""
    return EstadoSistema(
        estado="ok",
        version="2.0.0",
        servicios=[EstadoServicio(nombre="api", disponible=True)],
    )


@router.get("/preparacion", response_model=EstadoSistema, summary="Comprueba dependencias de ejecución")
def preparacion() -> EstadoSistema:
    settings = get_settings()
    services = [
        EstadoServicio(nombre="earth_engine", disponible=bool(settings["earthengine_project"]), detalle="Proyecto configurado"),
        EstadoServicio(nombre="selenium", disponible=find_spec("selenium") is not None),
        EstadoServicio(nombre="reportes_pdf", disponible=find_spec("reportlab") is not None),
    ]
    return EstadoSistema(
        estado="ok" if all(item.disponible for item in services) else "degradado",
        version="2.0.0",
        servicios=services,
    )
