import os
import json
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
    print(f"⚠️ Error al inicializar Earth Engine: {e}")


class ClasificadorCultivosService:
    def __init__(self, geojson_geometry: dict, cultivo_declarado: str = "aguacate", anio: int = 2025):
        self.cultivo_declarado = cultivo_declarado.lower()
        self.anio = anio
        
        if geojson_geometry.get("type") == "Feature":
            self.ee_geom = ee.Geometry(geojson_geometry["geometry"])
        else:
            self.ee_geom = ee.Geometry(geojson_geometry)

    def _verificar_uso_suelo_urbano(self):
        """
        Verifica mediante ESRI 10-Meter Land Cover si el predio colinda o está 
        en una zona construida/urbana para evitar falsos positivos.
        Clase 7 en ESRI Land Cover = Built Area (Área Construida / Urbana)
        """
        try:
            # Usar dataset global de cobertura de suelo de ESRI (resolución 10m)
            lc_collection = ee.ImageCollection(" proyectos / esri / 2020 / land_cover") # o dataset público equivalente
            # Usaremos el dataset público oficial de ESRI Land Cover en GEE:
            lc_image = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1') \
                .filterBounds(self.ee_geom) \
                .filterDate(f"{self.anio}-01-01", f"{self.anio}-12-31") \
                .select('built') \
                .mean()
            
            stats = lc_image.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=self.ee_geom,
                scale=10,
                maxPixels=1e9
            ).getInfo()
            
            built_score = stats.get('built', 0) or 0
            # Si el puntaje de área construida supera el 25% del polígono, es zona urbana
            return bool(built_score > 0.25)
        except Exception:
            # Fallback seguro si falla el dataset secundario
            return False

    def _obtener_imagen_reciente(self):
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterBounds(self.ee_geom) \
            .filterDate(f"{self.anio}-01-01", f"{self.anio}-12-31") \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 15)) \
            .select(['B8', 'B4', 'B3', 'B2'])
        return s2.median().clip(self.ee_geom)

    def analizar_cultivo(self):
        try:
            # 1. FILTRO PREVIO DE ZONA URBANA
            if self._verificar_uso_suelo_urbano():
                return {
                    "cultivo_declarado": self.cultivo_declarado,
                    "cultivo_inferido": "zona_urbana_o_infraestructura",
                    "incongruencia_detectada": True,
                    "diagnostico": "❌ Rechazado: El análisis espacial detectó que el polígono se encuentra en una zona urbana o construida, no en terreno agrícola.",
                    "parametros_analisis": {
                        "razon_rechazo": "Filtro de exclusión urbana activado"
                    }
                }

            # 2. PROCESAMIENTO NORMAL DE VEGETACIÓN Y TEXTURA SI PASA EL FILTRO
            imagen = self._obtener_imagen_reciente()
            
            brillo = imagen.select('B2').rename('brillo')
            textura = brillo.reduceNeighborhood(
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

            evi = imagen.expression(
                '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
                {
                    'NIR': imagen.select('B8'),
                    'RED': imagen.select('B4'),
                    'BLUE': imagen.select('B2')
                }
            ).rename('EVI')

            stats_evi = evi.reduceRegion(ee.Reducer.mean(), self.ee_geom, scale=10, maxPixels=1e9).getInfo()
            promedio_evi = stats_evi.get('EVI', 0) or 0

            cultivo_inferido = "berries" if valor_textura < 140 else "aguacate"
            
            incongruencia = False
            mensaje = "El cultivo declarado coincide con la firma espectral y geométrica detectada."

            if "aguacate" in self.cultivo_declarado and cultivo_inferido == "berries":
                incongruencia = True
                mensaje = "⚠️ Alerta: El productor declaró 'Aguacate', pero la firma satelital muestra patrones de infraestructura plástica (Macrotúneles de Berries)."
            elif "berry" in self.cultivo_declarado and cultivo_inferido == "aguacate":
                incongruencia = True
                mensaje = "⚠️ Alerta: El productor declaró 'Berries', pero la firma satelital muestra dosel arbóreo disperso (Aguacate o forestal)."

            return {
                "cultivo_declarado": self.cultivo_declarado,
                "cultivo_inferido": cultivo_inferido,
                "incongruencia_detectada": incongruencia,
                "diagnostico": mensaje,
                "parametros_analisis": {
                    "indice_textura_espacial": round(valor_textura, 2),
                    "evi_promedio": round(promedio_evi, 4),
                    "anio_evaluado": self.anio
                }
            }

        except Exception as e:
            raise Exception(f"Error al procesar la clasificación de cultivos: {str(e)}")