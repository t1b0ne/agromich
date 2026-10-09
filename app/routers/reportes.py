import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.core.security import require_api_key
from app.repositories import ReportsRepository
from app.schemas.reportes import SolicitudReporte
from app.schemas.reportes_catalogo import ReporteGenerado
from app.services.servicio_reportes import ServicioReportes

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/reportes", tags=["Reportes y Descargas"])


@router.post("/generar", dependencies=[Depends(require_api_key)], response_class=FileResponse, summary="Genera y descarga un reporte")
def generar_reporte(solicitud: SolicitudReporte):
    try:
        path = ServicioReportes().generar(
            titulo=solicitud.titulo,
            estado=solicitud.estado,
            municipio=solicitud.municipio,
            servicios=solicitud.servicios,
            incluir_historial=solicitud.incluir_historial,
            datos_adicionales=solicitud.datos_adicionales,
            formato=solicitud.formato,
        )
        media_type = "application/pdf" if solicitud.formato == "pdf" else "text/html"
        return FileResponse(path, media_type=media_type, filename=path.name)
    except RuntimeError as exc:
        logger.warning("No se genero el reporte: %s", exc)
        raise HTTPException(status_code=503, detail="Servicio de generación de reportes no disponible") from exc
    except Exception:
        logger.exception("Error generando reporte")
        raise HTTPException(status_code=500, detail="No fue posible generar el reporte")


@router.get("", response_model=list[ReporteGenerado], dependencies=[Depends(require_api_key)], summary="Lista reportes generados")
def listar_reportes() -> list[ReporteGenerado]:
    repository = ReportsRepository()
    return [
        ReporteGenerado(
            archivo=path.name,
            formato=path.suffix[1:].lower(),
            tamano_bytes=path.stat().st_size,
            creado_en=datetime.fromtimestamp(path.stat().st_mtime),
        )
        for path in repository.generated_files()
    ]


@router.get("/{archivo}/descarga", dependencies=[Depends(require_api_key)], response_class=FileResponse, summary="Descarga un reporte generado")
def descargar_reporte(archivo: str):
    repository = ReportsRepository()
    try:
        path = repository.generated_file(archivo)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    media_type = "application/pdf" if path.suffix.lower() == ".pdf" else "text/html"
    return FileResponse(path, media_type=media_type, filename=path.name)
