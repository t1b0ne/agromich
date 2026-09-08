import os
import json
import ee
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials

load_dotenv()

# Inicialización segura de Google Earth Engine usando las credenciales del .env
try:
    cred_env = os.getenv("EARTHENGINE_CREDENTIALS")
    
    if cred_env:
        creds_dict = json.loads(cred_env)
        
        credentials = Credentials(
            token=None,
            refresh_token=creds_dict.get("refresh_token"),
            client_id=creds_dict.get("client_id"),
            client_secret=creds_dict.get("client_secret"),
            token_uri=creds_dict.get("token_uri"),
            scopes=creds_dict.get("scopes")
        )
        
        ee.Initialize(credentials=credentials, project=creds_dict.get("project", "agromich-507422"))
        print("✅ Google Earth Engine inicializado exitosamente con credenciales del .env")
    else:
        ee.Initialize(project="agromich-507422")
        print("⚠️ Inicializado con proyecto predeterminado (sin credenciales explícitas en .env)")

except Exception as e:
    print(f"⚠️ Error crítico al inicializar Earth Engine: {e}")


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
            # Polígono por defecto en Uruapan, Michoacán
            self.ee_geom = ee.Geometry.Polygon([[
                [-102.065, 19.412],
                [-102.055, 19.412],
                [-102.055, 19.422],
                [-102.065, 19.422],
                [-102.065, 19.412]
            ]])

    def _obtener_imagen_compuesta(self, fecha_ini: str, fecha_fin: str):
        s2 = ee.ImageCollection('COPERNICUS/S2_SR') \
            .filterBounds(self.ee_geom) \
            .filterDate(fecha_ini, fecha_fin) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
            .select(['B8', 'B4']) # Bandas de Infrarrojo Cercano y Rojo para NDVI
        return s2.median().clip(self.ee_geom)

    def calcular_ndvi(self, imagen):
        return imagen.normalizedDifference(['B8', 'B4']).rename('NDVI')

    def verificar_alerta_deforestacion_global(self):
        """
        Cruza el polígono con el dataset histórico global de pérdida forestal (Hansen/UMD)
        """
        try:
            gfc = ee.Image('UMD/hansen/global_forest_change_2023_v1_11')
            loss = gfc.select('loss')
            
            loss_en_predio = loss.clip(self.ee_geom).reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=self.ee_geom,
                scale=30,
                maxPixels=1e9
            ).getInfo()
            
            total_perdida_píxeles = loss_en_predio.get('loss', 0) or 0
            return bool(total_perdida_píxeles > 0)
        except Exception:
            return False

    def procesar_para_agente_y_mapa(self):
        try:
            anio_inicio = int(self.fecha_inicio.split('-')[0])
            anio_fin = int(self.fecha_fin.split('-')[0])
            
            # Obtener imágenes y calcular NDVI histórico vs actual
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
            
            # Validación institucional cruzada
            historial_deforestacion = self.verificar_alerta_deforestacion_global()

            # Lógica de clasificación para el Agente
            if historial_deforestacion and diferencia < -0.10:
                clasificacion = "Incumplimiento Crítico"
                detalle_alerta = "Alerta institucional: Se detectó pérdida histórica de cobertura forestal cruzada con una disminución severa de NDVI. Posible cambio de uso de suelo ilegal."
            elif diferencia < -0.15:
                clasificacion = "Posible incumplimiento"
                detalle_alerta = "Se detectó una reducción severa en el índice de vegetación (NDVI), lo que sugiere posible pérdida de cobertura vegetal."
            elif diferencia < -0.05:
                clasificacion = "Requiere revisión"
                detalle_alerta = "Se observa una leve disminución de vegetación que amerita inspección visual."
            else:
                clasificacion = "Cumple"
                detalle_alerta = "La cobertura vegetal se mantiene estable o muestra mejoras sin alertas de deforestación."

            # Parámetros visuales para la capa ráster de teselas
            viz_params = {
                'min': -0.4,
                'max': 0.4,
                'palette': ['red', 'yellow', 'green']
            }
            map_id = diferencia_ndvi.getMapId(viz_params)
            tile_url = map_id['tile_fetcher'].url_format

            # Obtener el centroide en formato [longitud, latitud] para centrar el mapa en el frontend
            centroide = self.ee_geom.centroid().coordinates().getInfo()

            return {
                "tile_url": tile_url,
                "capa": "diferencia_ndvi",
                "sistema": "Google Earth Engine / Sentinel-2 + UMD Hansen",
                "centro_sugerido": centroide,
                "zoom_sugerido": 15,
                "estado_evaluacion": clasificacion,
                "metricas": {
                    "ndvi_historico": round(promedio_pasado, 4),
                    "ndvi_actual": round(promedio_actual, 4),
                    "delta_cambio": round(diferencia, 4),
                    "alerta_deforestacion_historica": historial_deforestacion,
                    "periodo_comparacion": f"{anio_inicio} vs {anio_fin}"
                },
                "diagnostico_sintetizado": detalle_alerta,
                "recomendacion_accion": "Bloquear certificación y notificar a la autoridad ambiental" if "Incumplimiento" in clasificacion else "Aprobar predio sin restricciones"
            }
            
        except Exception as e:
            raise Exception(f"Error en GEE avanzado: {str(e)}")