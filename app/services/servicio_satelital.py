import ee
import os
from dotenv import load_dotenv

load_dotenv()

try:
    ee.Initialize()
except Exception as e:
    print(f"⚠️ Advertencia al inicializar Earth Engine: {e}")

class ProcesadorSatelitalModular:
    def __init__(self, geojson_geometry: dict = None, fecha_inicio: str = "2025-01-01", fecha_fin: str = "2025-12-31", estado: str = None, municipio: str = None):
        self.fecha_inicio = fecha_inicio
        self.fecha_fin = fecha_fin
        
        if geojson_geometry:
            self.geom_data = geojson_geometry
            if self.geom_data.get("type") == "Feature":
                self.ee_geom = ee.Geometry(self.geom_data["geometry"])
            else:
                self.ee_geom = ee.Geometry(self.geom_data)
                
        elif estado and municipio:
            municipios_col = ee.FeatureCollection('FAO/GAUL/2015/level2')
            self.ee_geom = municipios_col \
                .filter(ee.Filter.eq('ADM1_NAME', estado)) \
                .filter(ee.Filter.eq('ADM2_NAME', municipio)) \
                .geometry()
        else:
            self.ee_geom = ee.Geometry.Polygon([[
                [-102.0, 19.5], [-101.9, 19.5], [-101.9, 19.6], [-102.0, 19.6], [-102.0, 19.5]
            ]])

    def _obtener_imagen_compuesta(self, fecha_ini: str, fecha_fin: str):
        s2 = ee.ImageCollection('COPERNICUS/S2_SR') \
            .filterBounds(self.ee_geom) \
            .filterDate(fecha_ini, fecha_fin) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
            .select(['B8', 'B4'])
        return s2.median().clip(self.ee_geom)

    def calcular_ndvi(self, imagen):
        return imagen.normalizedDifference(['B8', 'B4']).rename('NDVI')

    def procesar_para_agente_y_mapa(self):
        try:
            anio_inicio = int(self.fecha_inicio.split('-')[0])
            anio_fin = int(self.fecha_fin.split('-')[0])
            
            img_pasada = self._obtener_imagen_compuesta(f"{anio_inicio}-01-01", f"{anio_inicio}-12-31")
            img_actual = self._obtener_imagen_compuesta(f"{anio_fin}-01-01", f"{anio_fin}-12-31")
            
            ndvi_pasado = self.calcular_ndvi(img_pasada)
            ndvi_actual = self.calcular_ndvi(img_actual)
            
            diferencia_ndvi = ndvi_actual.subtract(ndvi_pasado).rename('diferencia_ndvi')
            
            stats_pasado = ndvi_pasado.reduceRegion(ee.Reducer.mean(), self.ee_geom, scale=10, maxPixels=1e9).getInfo()
            stats_actual = ndvi_actual.reduceRegion(ee.Reducer.mean(), self.ee_geom, scale=10, maxPixels=1e9).getInfo()
            
            promedio_pasado = stats_pasado.get('NDVI', 0) or 0
            promedio_actual = stats_actual.get('NDVI', 0) or 0
            diferencia = promedio_actual - promedio_pasado
            
            if diferencia < -0.15:
                clasificacion = "Posible incumplimiento"
                detalle_alerta = "Se detectó una reducción severa en el índice de vegetación (NDVI), lo que sugiere posible pérdida de cobertura forestal o cambio de uso de suelo."
            elif diferencia < -0.05:
                clasificacion = "Requiere revisión"
                detalle_alerta = "Se observa una leve disminución de vegetación que amerita inspección visual."
            else:
                clasificacion = "Cumple"
                detalle_alerta = "La cobertura vegetal se mantiene estable o muestra mejoras."

            viz_params = {
                'min': -0.4,
                'max': 0.4,
                'palette': ['red', 'yellow', 'green']
            }
            map_id = diferencia_ndvi.getMapId(viz_params)
            tile_url = map_id['tile_fetcher'].url_format

            # Obtener el centroide del polígono mediante GEE para centrar el mapa en el frontend
            centroide = self.ee_geom.centroid().coordinates().getInfo() # Retorna [longitud, latitud]

            return {
                "tile_url": tile_url,
                "capa": "diferencia_ndvi",
                "sistema": "Google Earth Engine / Sentinel-2",
                "centro_sugerido": centroide,
                "zoom_sugerido": 15,
                "estado_evaluacion": clasificacion,
                "metricas": {
                    "ndvi_historico": round(promedio_pasado, 4),
                    "ndvi_actual": round(promedio_actual, 4),
                    "delta_cambio": round(diferencia, 4),
                    "periodo_comparacion": f"{anio_inicio} vs {anio_fin}"
                },
                "diagnostico_sintetizado": detalle_alerta,
                "recomendacion_accion": "Generar expediente automático y notificar al auditor" if clasificacion != "Cumple" else "Aprobar predio sin restricciones"
            }
            
        except Exception as e:
            raise Exception(f"Error en GEE: {str(e)}")