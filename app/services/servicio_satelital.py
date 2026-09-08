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
    def __init__(self, geojson_geometry: dict = None, cultivo: str = "aguacate", fecha_inicio: str = "2025-01-01", fecha_fin: str = "2026-12-31"):
        self.cultivo_declarado = cultivo.lower()
        self.fecha_inicio = fecha_inicio
        self.fecha_fin = fecha_fin
        
        if geojson_geometry:
            self.geom_data = geojson_geometry
            if self.geom_data.get("type") == "Feature":
                self.ee_geom = ee.Geometry(self.geom_data["geometry"])
            else:
                self.ee_geom = ee.Geometry(self.geom_data)
        else:
            # Polígono por defecto en Uruapan, Michoacán
            self.ee_geom = ee.Geometry.Polygon([[
                [-102.065, 19.412], [-102.055, 19.412],
                [-102.055, 19.422], [-102.065, 19.422],
                [-102.065, 19.412]
            ]])

    def _obtener_imagen_compuesta(self, fecha_ini: str, fecha_fin: str):
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterBounds(self.ee_geom) \
            .filterDate(fecha_ini, fecha_fin) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
            .select(['B8', 'B4', 'B3', 'B2'])
        return s2.median().clip(self.ee_geom)

    def calcular_ndvi(self, imagen):
        return imagen.normalizedDifference(['B8', 'B4']).rename('NDVI')

    def analizar_patron_geometrico(self, imagen):
        """
        Analiza la textura espacial para diferenciar patrones de macrotúneles (berries) 
        vs dosel arbóreo disperso (aguacate).
        """
        try:
            brillo = imagen.select('B2').rename('brillo')
            textura = brillo.neighborhoodReduce(
                reducer=ee.Reducer.stdDev(),
                kernel=ee.Kernel.circle(10, 'meters')
            ).rename('textura')

            stats_textura = textura.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=self.ee_geom,
                scale=10,
                maxPixels=1e9
            ).getInfo()

            valor_textura = stats_textura.get('textura', 0) or 0
            patron_detectado = "berries" if valor_textura < 150 else "aguacate"
            
            return patron_detectado, round(valor_textura, 2)
        except Exception:
            return "desconocido", 0.0

    def verificar_alerta_deforestacion_global(self):
        """
        Cruza el polígono con el dataset histórico global de pérdida forestal (Hansen/UMD)
        """
        try:
            gfc = ee.Image('UMD/hansen/global_forest_change_2025_v1_13')
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

    def obtener_auditoria_multivariable(self):
        """
        Extrae metadatos de Sentinel, EVI, topografía (NASA NASADEM) y evapotranspiración (MODIS).
        """
        try:
            anio = self.fecha_fin.split('-')[0]
            
            s2_collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                .filterBounds(self.ee_geom) \
                .filterDate(f"{anio}-01-01", f"{anio}-12-31") \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
            
            primer_imagen = s2_collection.first()
            metadatos_s2 = {
                "id_escena": primer_imagen.get('SPACECRAFT_NAME').getInfo() if primer_imagen else "Desconocido",
                "fecha_adquisicion": ee.Date(primer_imagen.get('system:time_start')).format('YYYY-MM-dd').getInfo() if primer_imagen else None,
                "nubes_porcentaje": primer_imagen.get('CLOUDY_PIXEL_PERCENTAGE').getInfo() if primer_imagen else 0.0
            }

            img_s2 = s2_collection.median().clip(self.ee_geom)
            
            # EVI (Enhanced Vegetation Index)
            evi = img_s2.expression(
                '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
                {
                    'NIR': img_s2.select('B8'),
                    'RED': img_s2.select('B4'),
                    'BLUE': img_s2.select('B2')
                }
            ).rename('EVI')

            stats_evi = evi.reduceRegion(ee.Reducer.mean(), self.ee_geom, scale=10, maxPixels=1e9).getInfo()
            promedio_evi = stats_evi.get('EVI', 0) or 0

            # Elevación y Pendiente (NASA NASADEM)
            dem = ee.Image('NASA/NASADEM_HGT/001').select('elevation')
            elevacion_clip = dem.clip(self.ee_geom)
            pendiente = ee.Terrain.slope(elevacion_clip)
            
            stats_terreno = ee.Image.cat([elevacion_clip, pendiente]).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=self.ee_geom,
                scale=30,
                maxPixels=1e9
            ).getInfo()
            
            elevacion_prom = stats_terreno.get('elevation', 0) or 0
            pendiente_prom = stats_terreno.get('slope', 0) or 0
            alerta_pendiente = bool(pendiente_prom > 15.0)

            # Evapotranspiración (MODIS MOD16A2GF)
            modis_et = ee.ImageCollection('MODIS/061/MOD16A2GF') \
                .filterBounds(self.ee_geom) \
                .filterDate(f"{anio}-01-01", f"{anio}-12-31") \
                .select('ET')
            
            evapotranspiracion_anual = 0.0
            if modis_et.size().getInfo() > 0:
                et_mean = modis_et.mean().multiply(0.1).clip(self.ee_geom)
                stats_et = et_mean.reduceRegion(reducer=ee.Reducer.mean(), geometry=self.ee_geom, scale=500, maxPixels=1e9).getInfo()
                evapotranspiracion_anual = stats_et.get('ET', 0) or 0

            return {
                "metadatos_sentinel": metadatos_s2,
                "vegetacion_avanzada": {
                    "evi_promedio": round(promedio_evi, 4)
                },
                "topografia_suelo": {
                    "elevacion_msnm": round(elevacion_prom, 2),
                    "pendiente_grados": round(pendiente_prom, 2),
                    "alerta_pendiente_excesiva": alerta_pendiente
                },
                "hidrologia": {
                    "evapotranspiracion_anual_mm": round(evapotranspiracion_anual, 2)
                }
            }
        except Exception as e:
            print(f"Error en auditoría multivariable: {e}")
            return {}

    def procesar_para_agente_y_mapa(self):
        try:
            anio_inicio = int(self.fecha_inicio.split('-')[0])
            anio_fin = int(self.fecha_fin.split('-')[0])
            
            img_actual = self._obtener_imagen_compuesta(f"{anio_fin}-01-01", f"{anio_fin}-12-31")
            img_pasada = self._obtener_imagen_compuesta(f"{anio_inicio}-01-01", f"{anio_inicio}-12-31")
            
            ndvi_pasado = self.calcular_ndvi(img_pasada)
            ndvi_actual = self.calcular_ndvi(img_actual)
            diferencia_ndvi = ndvi_actual.subtract(ndvi_pasado).rename('diferencia_ndvi')
            
            # Validación geométrica y de cultivo
            patron_espacial, score_textura = self.analizar_patron_geometrico(img_actual)
            
            alerta_incongruencia = False
            mensaje_incongruencia = "El patrón geométrico e infraestructura coinciden con el cultivo declarado."
            
            if "aguacate" in self.cultivo_declarado and patron_espacial == "berries":
                alerta_incongruencia = True
                mensaje_incongruencia = "⚠️ Incongruencia detectada: Declaró 'Aguacate', pero la firma geométrica muestra patrones de macrotúneles (Berries)."
            elif "berry" in self.cultivo_declarado and patron_espacial == "aguacate":
                alerta_incongruencia = True
                mensaje_incongruencia = "⚠️ Incongruencia detectada: Declaró 'Berries', pero la textura espacial muestra dosel arbóreo (Aguacate)."

            # Métricas de NDVI y multivariables
            stats_p = ndvi_pasado.reduceRegion(ee.Reducer.mean(), self.ee_geom, scale=10, maxPixels=1e9).getInfo()
            stats_a = ndvi_actual.reduceRegion(ee.Reducer.mean(), self.ee_geom, scale=10, maxPixels=1e9).getInfo()
            prom_p = stats_p.get('NDVI', 0) or 0
            prom_a = stats_a.get('NDVI', 0) or 0
            diferencia = prom_a - prom_p

            historial_deforestacion = self.verificar_alerta_deforestacion_global()
            datos_multivariables = self.obtener_auditoria_multivariable()

            if alerta_incongruencia:
                clasificacion = "Requiere revisión por incongruencia"
            elif historial_deforestacion and diferencia < -0.10:
                clasificacion = "Incumplimiento Crítico"
            elif diferencia < -0.15:
                clasificacion = "Posible incumplimiento"
            else:
                clasificacion = "Cumple"

            centroide = self.ee_geom.centroid().coordinates().getInfo()

            return {
                "sistema": "Google Earth Engine / Sentinel-2 + NASADEM + MODIS (Datos puros)",
                "centro_sugerido": centroide,
                "zoom_sugerido": 15,
                "estado_evaluacion": clasificacion,
                "metricas": {
                    "cultivo_declarado": self.cultivo_declarado,
                    "cultivo_inferido": patron_espacial,
                    "incongruencia_detectada": alerta_incongruencia,
                    "ndvi_historico": round(prom_p, 4),
                    "ndvi_actual": round(prom_a, 4),
                    "delta_cambio": round(diferencia, 4),
                    "alerta_deforestacion_historica": historial_deforestacion,
                    **datos_multivariables
                },
                "diagnostico_sintetizado": mensaje_incongruencia,
                "recomendacion_accion": "Verificar en campo y bloquear certificación temporalmente" if clasificacion != "Cumple" else "Aprobar predio sin restricciones"
            }
            
        except Exception as e:
            raise Exception(f"Error en procesamiento de datos satelitales: {str(e)}")