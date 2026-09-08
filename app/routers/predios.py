from fastapi import APIRouter, HTTPException
from app.services.servicio_satelital import ProcesadorSatelitalModular

router = APIRouter()

@router.post("/auditar-predio-inteligente")
def auditar_predio(payload: dict):
    try:
        # Extraer datos del request JSON
        geojson_geom = payload.get("geometry") or payload.get("geojson")
        cultivo = payload.get("cultivo", "aguacate")
        fecha_inicio = payload.get("fecha_inicio", "2025-01-01")
        fecha_fin = payload.get("fecha_fin", "2026-12-31")

        # Instanciar el procesador modular (solo datos)
        procesador = ProcesadorSatelitalModular(
            geojson_geometry=geojson_geom,
            cultivo=cultivo,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin
        )

        # Ejecutar análisis
        resultado_analisis = procesador.procesar_para_agente_y_mapa()

        # Retornar la estructura limpia basada estrictamente en datos
        return {
            "status": "success",
            "mensaje": "Auditoría multivariable completada exitosamente",
            "data": resultado_analisis
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))