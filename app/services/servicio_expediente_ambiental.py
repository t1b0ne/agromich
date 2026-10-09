import os
import json
import unicodedata
import ee
from app.core.gee import get_ee
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials

load_dotenv()

try:
    cred_env = None  # La inicializacion se realiza de forma perezosa en get_ee().
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
    elif False:
        ee.Initialize(project="agromich-507422")
except Exception as e:
    print(f"⚠️ Error al inicializar GEE en Expediente Ambiental: {e}")


class ExpedienteAmbientalService:
    def __init__(self, datos_predio: dict):
        get_ee()
        self.nombre_huerto = datos_predio.get("nombre_huerto", "Predio sin nombre")
        self.productor = datos_predio.get("productor", "Desconocido")
        self.municipio = datos_predio.get("municipio", "Michoacán")
        self.cultivo_declarado = self._normalizar_cultivo(datos_predio.get("cultivo", "aguacate"))
        self.anio_inicio = datos_predio.get("anio_inicio", 2018)
        self.anio_fin = datos_predio.get("anio_fin", 2026)
        
        geom_raw = datos_predio.get("geometry")
        if geom_raw.get("type") == "Feature":
            self.ee_geom = ee.Geometry(geom_raw["geometry"])
        else:
            self.ee_geom = ee.Geometry(geom_raw)

    @staticmethod
    def _normalizar_cultivo(cultivo: str) -> str:
        texto = unicodedata.normalize("NFKD", str(cultivo or ""))
        return "".join(caracter for caracter in texto if not unicodedata.combining(caracter)).lower().strip()

    @classmethod
    def _familia_cultivo(cls, cultivo: str) -> str:
        cultivo = cls._normalizar_cultivo(cultivo)
        if any(nombre in cultivo for nombre in ("fresa", "frutilla", "berry", "berries", "zarzamora", "frambuesa", "arandano")):
            return "berries"
        if "aguacate" in cultivo or "avocado" in cultivo:
            return "aguacate"
        return "desconocido"

    def _verificar_uso_suelo_urbano(self):
        try:
            dw = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1') \
                .filterBounds(self.ee_geom) \
                .filterDate(f"{self.anio_fin}-01-01", f"{self.anio_fin}-12-31") \
                .select('built') \
                .mean()
            
            stats = dw.reduceRegion(ee.Reducer.mean(), self.ee_geom, scale=10, maxPixels=1e9).getInfo()
            return bool((stats.get('built', 0) or 0) > 0.25)
        except Exception:
            return False

    def _analizar_cultivo_y_textura(self, anio: int):
        try:
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                .filterBounds(self.ee_geom) \
                .filterDate(f"{anio}-01-01", f"{anio}-12-31") \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 15)) \
                .select(['B8', 'B4', 'B3', 'B2']) \
                .median().clip(self.ee_geom)

            brillo = s2.select('B2').rename('brillo')
            textura = brillo.reduceNeighborhood(ee.Reducer.stdDev(), ee.Kernel.circle(10, 'meters')).rename('textura')
            
            stats = textura.reduceRegion(ee.Reducer.mean(), self.ee_geom, scale=10, maxPixels=1e9).getInfo()
            valor_textura = stats.get('textura', 0) or 0

            umbral_berries = float(os.getenv("CULTIVO_TEXTURA_BERRIES_UMBRAL", "22"))
            cultivo_inferido = "berries" if valor_textura >= umbral_berries else "aguacate"
            familia_declarada = self._familia_cultivo(self.cultivo_declarado)
            incongruencia = False
            
            if familia_declarada in ("aguacate", "berries") and cultivo_inferido != familia_declarada:
                incongruencia = True
                mensaje = "⚠️ Declaró 'Aguacate', pero la textura espacial es compatible con patrones de berries/macrotúneles." if familia_declarada == "aguacate" else "⚠️ Declaró un cultivo de berries, pero la textura espacial es compatible con dosel de aguacate."
            else:
                mensaje = "El cultivo declarado coincide con la clasificación preliminar por textura."

            return cultivo_inferido, round(valor_textura, 2), incongruencia, mensaje
        except Exception:
            return "desconocido", 0.0, False, "No se pudo procesar la textura"

    def _verificar_incendios_historicos(self):
        try:
            burn_coll = ee.ImageCollection('MODIS/061/MCD64A1') \
                .filterBounds(self.ee_geom) \
                .filterDate(f"{self.anio_inicio}-01-01", f"{self.anio_fin}-12-31") \
                .select('BurnDate')
            
            burned_sum = burn_coll.map(lambda img: img.gt(0).clip(self.ee_geom)).sum()
            stats = burned_sum.reduceRegion(reducer=ee.Reducer.max(), geometry=self.ee_geom, scale=500, maxPixels=1e9).getInfo()
            return bool((stats.get('BurnDate', 0) or 0) > 0)
        except Exception:
            return False

    def _obtener_series_historicas(self):
        """
        🚀 MÉTODO OPTIMIZADO: Obtiene la serie temporal completa de NDVI 
        en una sola llamada masiva a GEE (evitando bucles de llamadas individuales).
        """
        serie_ndvi = []
        try:
            # Creamos una lista de años en el servidor de Earth Engine
            anios_list = ee.List.sequence(self.anio_inicio, self.anio_fin)
            
            def calcular_ndvi_anio(y):
                y = ee.Number(y)
                start_date = ee.Date.fromYMD(y, 1, 1)
                end_date = ee.Date.fromYMD(y, 12, 31)
                
                lc = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
                    .filterBounds(self.ee_geom) \
                    .filterDate(start_date, end_date) \
                    .filter(ee.Filter.lt('CLOUD_COVER', 30)) \
                    .median().clip(self.ee_geom) \
                    .multiply(0.0000275).add(-0.2)
                
                ndvi = lc.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI')
                mean_dict = ndvi.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=self.ee_geom,
                    scale=30,
                    maxPixels=1e9
                )
                val = mean_dict.get('NDVI')
                # Manejar valores nulos con un fallback de 0
                val_seguro = ee.Algorithms.If(val, val, 0)
                
                return ee.Dictionary({
                    'anio': y,
                    'ndvi_promedio': val_seguro
                })

            # Mapeamos la función en paralelo dentro de GEE y hacemos UN SOLO .getInfo()
            resultados_ee = anios_list.map(calcular_ndvi_anio).getInfo()
            
            for item in resultados_ee:
                serie_ndvi.append({
                    "anio": int(item['anio']),
                    "ndvi_promedio": round(float(item['ndvi_promedio']), 4)
                })
        except Exception as e:
            print(f"Error procesando serie histórica optimizada: {e}")
            # Fallback vacío si falla la consulta masiva
            for anio in range(self.anio_inicio, self.anio_fin + 1):
                serie_ndvi.append({"anio": anio, "ndvi_promedio": None})

        # Verificación Hansen GFC (Pérdida forestal) en paralelo
        anios_deforestacion = []
        try:
            gfc = ee.Image('UMD/hansen/global_forest_change_2025_v1_13')
            loss_masked = gfc.select('lossyear').updateMask(gfc.select('lossyear').gt(0)).clip(self.ee_geom)
            hist = loss_masked.reduceRegion(ee.Reducer.frequencyHistogram(), self.ee_geom, scale=30, maxPixels=1e9).getInfo()
            
            for codigo in hist.get('lossyear', {}).keys():
                anios_deforestacion.append(2000 + int(float(codigo)))
        except Exception:
            pass

        return serie_ndvi, anios_deforestacion

    def generar_expediente(self):
        if self._verificar_uso_suelo_urbano():
            return {
                "estatus_expediente": "RECHAZADO",
                "motivo": "El polígono se ubica en zona urbana / infraestructura construida."
            }

        cultivo_inf, textura, incongruencia, msg_cultivo = self._analizar_cultivo_y_textura(self.anio_fin)
        serie_ndvi, anios_def = self._obtener_series_historicas()
        hubo_incendios = self._verificar_incendios_historicos()
        def_en_periodo = [a for a in anios_def if a >= self.anio_inicio]

        if len(def_en_periodo) > 0 and hubo_incendios:
            estatus_legal = "INCUMPLIMIENTO CRÍTICO (Deforestación + Incendio Provocado)"
            dictamen = f"Alerta máxima: Se detectó incendio histórico en la zona y pérdida forestal oficial durante el(los) año(s) {def_en_periodo}."
        elif len(def_en_periodo) > 0:
            estatus_legal = "INCUMPLIMIENTO CRÍTICO"
            dictamen = f"Se detectó pérdida de cobertura forestal oficial en el predio durante el(los) año(s): {def_en_periodo}."
        elif hubo_incendios:
            estatus_legal = "ADVERTENCIA POR INCENDIO HISTÓRICO"
            dictamen = "El predio registra antecedentes de fuego/incendio en el periodo evaluado. Requiere verificación de cambio de uso de suelo."
        else:
            estatus_legal = "CUMPLE"
            dictamen = "La cobertura histórica es estable, sin registros de incendios ni deforestación satelital reciente."

        return {
            "metadata_predio": {
                "nombre_huerto": self.nombre_huerto,
                "productor": self.productor,
                "municipio": self.municipio,
                "cultivo_declarado": self.cultivo_declarado,
                "periodo_evaluado": f"{self.anio_inicio} - {self.anio_fin}"
            },
            "validacion_cultivo_e_infraestructura": {
                "cultivo_inferido": cultivo_inf,
                "indice_textura_espacial": textura,
                "incongruencia_detectada": incongruencia,
                "observacion": msg_cultivo
            },
            "auditoria_ambiental_y_forestal": {
                "estatus_legal": estatus_legal,
                "dictamen_automatizado": dictamen,
                "registros_deforestacion_hansen": anios_def,
                "alerta_incendios_historicos": hubo_incendios,
                "deforestacion_en_periodo_analisis": len(def_en_periodo) > 0
            },
            "series_historicas": {
                "evolucion_ndvi_anual": serie_ndvi
            }
        }
