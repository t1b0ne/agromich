from fastapi import APIRouter, HTTPException
import traceback
from app.schemas.agro_schemas import SolicitudSatelital

# Importamos directamente para que cualquier fallo interno se revele al instante
from app.services.servicio_satelital import ProcesadorSatelitalModular

router = APIRouter(prefix="/api/v1/satelite", tags=["Análisis Satelital"])

@router.post("/analisis")
def analizar_satelite(datos: SolicitudSatelital):
    try:
        procesador = ProcesadorSatelitalModular(
            estado=datos.estado,
            municipio=datos.municipio,
            fecha_inicio=datos.fecha_inicio,
            fecha_fin=datos.fecha_fin
        )
        return procesador.procesar()
    except Exception as e:
        # Esto imprimirá la ruta exacta del error en rojo en tu terminal de Uvicorn
        print("🔥 ERROR CRÍTICO EN EL PROCESADOR SATELITAL:")
        traceback.print_exc()
        
        # Esto te mostrará el mensaje exacto del error en la respuesta HTTP (Swagger)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")