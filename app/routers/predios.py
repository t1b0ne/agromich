from fastapi import APIRouter, HTTPException
from app.schemas.agro_schemas import SolicitudPredio
from app.services.servicio_satelital import ProcesadorSatelitalModular

router = APIRouter(
    prefix="/api/v1/predios",
    tags=["Auditoría de Predios e Inteligencia Territorial"]
)

@router.post("/auditar-predio-inteligente")
def auditar_predio_inteligente(solicitud: SolicitudPredio):
    try:
        # Instanciar el procesador satelital modular con el GeoJSON del predio
        procesador = ProcesadorSatelitalModular(
            geojson_geometry=solicitud.geojson,
            fecha_inicio=solicitud.fecha_inicio_auditoria,
            fecha_fin=solicitud.fecha_fin_auditoria
        )
        
        # Ejecutar el análisis en Google Earth Engine
        resultado_analisis = procesador.procesar_para_agente_y_mapa()
        
        # Construir la respuesta modular unificada
        return {
            "status": "success",
            "predio_info": {
                "nombre_huerto": solicitud.nombre_huerto,
                "productor": solicitud.productor,
                "cultivo": solicitud.cultivo,
                "municipio": solicitud.municipio
            },
            "salida_para_agente": {
                "estado_evaluacion": resultado_analisis["estado_evaluacion"],
                "metricas": resultado_analisis["metricas"],
                "diagnostico_sintetizado": resultado_analisis["diagnostico_sintetizado"],
                "recomendacion_accion": resultado_analisis["recomendacion_accion"]
            },
            "visualizacion_mapa": {
                "tile_url": resultado_analisis["tile_url"],
                "capa": resultado_analisis["capa"],
                "sistema": resultado_analisis["sistema"],
                "centro_sugerido": resultado_analisis["centro_sugerido"],
                "zoom_sugerido": resultado_analisis["zoom_sugerido"],
                "geometria_original": solicitud.geojson
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))