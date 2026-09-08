import os
import json
import unicodedata
import ee
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials

load_dotenv()

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
    else:
        ee.Initialize(project="agromich-507422")
except Exception as e:
    print(f"⚠️ Error al inicializar GEE en Expediente Ambiental: {e}")


class ExpedienteAmbientalService:
    def __init__(self, datos_predio: dict):
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
        """Normaliza nombres de cultivo para comparar aguacate y berries."""
        texto = unicodedata.normalize("NFKD", str(cultivo or ""))
        return "".join(caracter for caracter in texto if not unicodedata.combining(caracter)).lower().strip()

    @classmethod
    def _familia_cultivo(cls, cultivo: str) -> str:
        cultivo = cls._normalizar_cultivo(cultivo)
        if any(nombre in cultivo for nombre in (
            "fresa", "frutilla", "berry", "berries", "zarzamora", "frambuesa", "arandano"
        )):
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

            # La textura se usa como indicador de alerta, no como prueba
            # definitiva. El umbral puede calibrarse sin modificar el código.
            umbral_berries = float(os.getenv("CULTIVO_TEXTURA_BERRIES_UMBRAL", "22"))
            cultivo_inferido = "berries" if valor_textura >= umbral_berries else "aguacate"
            familia_declarada = self._familia_cultivo(self.cultivo_declarado)
            incongruencia = False
            mensaje = "Clasificación preliminar basada en textura; requiere validación agronómica."

            if familia_declarada in ("aguacate", "berries") and cultivo_inferido != familia_declarada:
                incongruencia = True
                if familia_declarada == "aguacate":
                    mensaje = "⚠️ Declaró 'Aguacate', pero la textura espacial es compatible con patrones de berries/macrotúneles."
                else:
                    mensaje = "⚠️ Declaró un cultivo de berries, pero la textura espacial es compatible con dosel de aguacate."
            elif familia_declarada in ("aguacate", "berries"):
                mensaje = "El cultivo declarado coincide con la clasificación preliminar por textura."
            else:
                mensaje = "Clasificación preliminar basada en textura; requiere validación agronómica."

            return cultivo_inferido, round(valor_textura, 2), incongruencia, mensaje
        except Exception:
            return "desconocido", 0.0, False, "No se pudo procesar la textura"

    def _verificar_incendios_historicos(self):
        """
        Verifica cicatrices de fuego e incendios previos en el predio 
        usando el dataset de Áreas Quemadas de MODIS (MODIS/061/MCD64A1).
        """
        try:
            burn_coll = ee.ImageCollection('MODIS/061/MCD64A1') \
                .filterBounds(self.ee_geom) \
                .filterDate(f"{self.anio_inicio}-01-01", f"{self.anio_fin}-12-31") \
                .select('BurnDate')
            
            # Si hay píxeles con fecha de quema mayor a 0 dentro del polígono
            burned_sum = burn_coll.map(lambda img: img.gt(0).clip(self.ee_geom)).sum()
            stats = burned_sum.reduceRegion(
                reducer=ee.Reducer.max(),
                geometry=self.ee_geom,
                scale=500,
                maxPixels=1e9
            ).getInfo()
            
            # Si la suma máxima indica presencia de fuego en al menos un periodo
            max_burned = stats.get('BurnDate', 0) or 0
            return bool(max_burned > 0)
        except Exception as e:
            print(f"Error consultando incendios MODIS: {e}")
            return False

    def _obtener_series_historicas(self):
        """Obtiene la serie temporal de NDVI y verifica deforestación histórica (Hansen)"""
        serie_ndvi = []
        for anio in range(self.anio_inicio, self.anio_fin + 1):
            try:
                lc = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
                    .filterBounds(self.ee_geom) \
                    .filterDate(f"{anio}-01-01", f"{anio}-12-31") \
                    .filter(ee.Filter.lt('CLOUD_COVER', 25)) \
                    .median().clip(self.ee_geom) \
                    .multiply(0.0000275).add(-0.2)
                
                ndvi = lc.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI')
                stats = ndvi.reduceRegion(ee.Reducer.mean(), self.ee_geom, scale=30, maxPixels=1e9).getInfo()
                serie_ndvi.append({"anio": anio, "ndvi_promedio": round(stats.get('NDVI', 0) or 0, 4)})
            except Exception:
                serie_ndvi.append({"anio": anio, "ndvi_promedio": None})

        # Verificación Hansen GFC (Pérdida forestal)
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

        # Análisis de cultivo actual y texturas
        cultivo_inf, textura, incongruencia, msg_cultivo = self._analizar_cultivo_y_textura(self.anio_fin)

        # Series históricas, deforestación e incendios
        serie_ndvi, anios_def = self._obtener_series_historicas()
        hubo_incendios = self._verificar_incendios_historicos()
        def_en_periodo = [a for a in anios_def if a >= self.anio_inicio]

        # Dictamen legal robusto considerando incendios y deforestación
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
