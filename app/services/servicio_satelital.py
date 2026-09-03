import argparse
import os
import json
import unicodedata
import pandas as pd
import ee
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials

# Carga automática del archivo .env si existe en local
load_dotenv()

def normalizar_texto(texto):
    """Elimina acentos y convierte a minúsculas para búsquedas comparativas."""
    if not texto:
        return ""
    texto_norm = unicodedata.normalize('NFD', texto)
    texto_sin_acentos = ''.join(c for c in texto_norm if unicodedata.category(c) != 'Mn')
    return texto_sin_acentos.strip().lower()

class ProcesadorSatelitalModular:
    def __init__(self, estado="Michoacán de Ocampo", municipio=None, fecha_inicio="2025-01-01", fecha_fin="2025-12-31", project="agromich-507422", nombre_salida=None):
        self.estado = estado
        self.municipio = municipio
        self.fecha_inicio = fecha_inicio
        self.fecha_fin = fecha_fin
        self.project = project
        
        if not nombre_salida:
            if self.municipio:
                clean_mun = normalizar_texto(self.municipio).replace(" ", "_")
                self.nombre_salida = f"reporte_municipal_{clean_mun}"
            else:
                self.nombre_salida = "reporte_estatal_general"
        else:
            self.nombre_salida = nombre_salida

        self.carpeta_salida = os.path.abspath(os.path.join("reports", "procesados"))
        os.makedirs(self.carpeta_salida, exist_ok=True)
        
        # Inicialización estricta basada exclusivamente en la variable de entorno / .env
        try:
            credenciales_json = os.environ.get("EARTHENGINE_CREDENTIALS")
            
            if not credenciales_json:
                raise ValueError("No se encontró la variable de entorno 'EARTHENGINE_CREDENTIALS'. Asegúrate de configurarla en tu archivo .env o en el panel de Render.")

            cred_dict = json.loads(credenciales_json)
            
            # Autenticación oficial utilizando Google OAuth2 Credentials
            credentials = Credentials(
                token=None,  # Se autogenerará de forma segura usando el refresh_token
                refresh_token=cred_dict.get("refresh_token"),
                client_id=cred_dict.get("client_id"),
                client_secret=cred_dict.get("client_secret"),
                token_uri="https://oauth2.googleapis.com/token",
                scopes=cred_dict.get("scopes", ["https://www.googleapis.com/auth/earthengine"])
            )
            
            # Tomamos el proyecto del JSON o del parámetro por defecto
            project_id = cred_dict.get("project", self.project)
            
            ee.Initialize(credentials=credentials, project=project_id)
            print(f" [✓] Earth Engine inicializado correctamente usando la variable de entorno (Proyecto: {project_id}).")
            
        except Exception as e:
            print(f" [!] Error crítico al inicializar Earth Engine por credenciales de entorno: {e}")
            raise e

    def procesar(self):
        """
        Método principal optimizado para FastAPI / Hermes.
        Procesa los datos satelitales, guarda respaldo en disco y RETORNA el diccionario.
        """
        if self.municipio:
            return self._procesar_municipio_especifico()
        else:
            return self._procesar_estado_general()

    def _agregar_indices_agricolas(self, imagen):
        """Calcula los índices espectrales directamente en cada imagen individual."""
        ndvi = imagen.normalizedDifference(['B8', 'B4']).rename('NDVI')
        ndwi = imagen.normalizedDifference(['B8', 'B11']).rename('NDWI')
        ndre = imagen.normalizedDifference(['B8A', 'B5']).rename('NDRE')
        savi = imagen.expression(
            '((NIR - RED) / (NIR + RED + 0.5)) * 1.5', {
                'NIR': imagen.select('B8').divide(10000),
                'RED': imagen.select('B4').divide(10000)
            }).rename('SAVI')
        return imagen.addBands([ndvi, ndwi, ndre, savi])

    def _obtener_poligono_municipio(self):
        """Obtiene la FeatureCollection del municipio emparejando nombres cliente-servidor."""
        estado_fc = (ee.FeatureCollection('FAO/GAUL/2015/level2')
                     .filter(ee.Filter.stringContains('ADM1_NAME', 'Michoac')))

        mun_buscado = normalizar_texto(self.municipio)
        
        nombres_mun_earthengine = estado_fc.aggregate_array('ADM2_NAME').getInfo()
        
        nombre_oficial = None
        for nombre in nombres_mun_earthengine:
            if mun_buscado in normalizar_texto(nombre):
                nombre_oficial = nombre
                break

        if not nombre_oficial:
            return None, None

        municipio_fc = estado_fc.filter(ee.Filter.eq('ADM2_NAME', nombre_oficial))
        return municipio_fc, nombre_oficial

    def _procesar_municipio_especifico(self):
        print("\n" + "=" * 70)
        print(f" SERVICIO: ANÁLISIS ESPECÍFICO DE MUNICIPIO ({self.municipio.upper()}, {self.estado.upper()})")
        print(f" Periodo: {self.fecha_inicio} a {self.fecha_fin}")
        print("=" * 70)

        municipio_fc, nombre_oficial = self._obtener_poligono_municipio()

        if not municipio_fc:
            print(f" [!] No se encontró el municipio '{self.municipio}' en {self.estado}.")
            return {"error": f"No se encontró el municipio '{self.municipio}' en {self.estado}."}

        print(f" --> Municipio localizado oficialmente en GAUL como: '{nombre_oficial}'")
        geometria_mun = municipio_fc.geometry()

        print(f" --> Consultando imágenes Sentinel-2 sobre {nombre_oficial}...")
        coleccion = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(geometria_mun)
                     .filterDate(self.fecha_inicio, self.fecha_fin)
                     .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
                     .map(self._agregar_indices_agricolas))

        total_imagenes = coleccion.size().getInfo()
        if total_imagenes == 0:
            print(" [!] No se encontraron imágenes Sentinel-2 para el periodo/municipio indicado.")
            return {"error": "No se encontraron imágenes Sentinel-2 para el periodo e indicaciones seleccionadas."}

        print(f" --> Procesando {total_imagenes} imágenes para la serie de tiempo municipal...")

        def extraer_metricas_fecha(imagen):
            stats = imagen.select(['NDVI', 'NDWI', 'NDRE', 'SAVI']).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometria_mun,
                scale=200,
                maxPixels=1e9
            )
            return ee.Feature(None, {
                'fecha': imagen.date().format('YYYY-MM-dd'),
                'ndvi': stats.get('NDVI'),
                'ndwi': stats.get('NDWI'),
                'ndre': stats.get('NDRE'),
                'savi': stats.get('SAVI')
            })

        resultados = coleccion.map(extraer_metricas_fecha).getInfo().get('features', [])

        registros = []
        for f in resultados:
            props = f['properties']
            if props.get('ndvi') is not None:
                registros.append({
                    'fecha': props['fecha'],
                    'ndvi': round(props['ndvi'], 4),
                    'estres_hidrico_ndwi': round(props['ndwi'], 4),
                    'nitrogeno_ndre': round(props['ndre'], 4),
                    'savi': round(props['savi'], 4)
                })

        if not registros:
            print(" [!] No se lograron calcular métricas para las fechas disponibles.")
            return {"error": "No se lograron calcular métricas para las fechas disponibles."}

        df = pd.DataFrame(registros).sort_values(by='fecha')

        resumen_mun = {
            "tipo_reporte": "Especifico por Municipio",
            "estado": self.estado,
            "municipio": nombre_oficial,
            "periodo": {"inicio": self.fecha_inicio, "fin": self.fecha_fin},
            "total_tomas_evaluadas": len(df),
            "resumen_promedios": {
                "ndvi_promedio": round(float(df['ndvi'].mean()), 4),
                "ndvi_maximo": round(float(df['ndvi'].max()), 4),
                "ndwi_humedad_promedio": round(float(df['estres_hidrico_ndwi'].mean()), 4),
                "ndre_nitrogeno_promedio": round(float(df['nitrogeno_ndre'].mean()), 4)
            },
            "serie_temporal": registros
        }

        ruta_json = os.path.join(self.carpeta_salida, f"{self.nombre_salida}.json")
        ruta_csv = os.path.join(self.carpeta_salida, f"{self.nombre_salida}.csv")
        
        with open(ruta_json, 'w', encoding='utf-8') as f:
            json.dump(resumen_mun, f, ensure_ascii=False, indent=4)
        
        df.to_csv(ruta_csv, index=False, encoding='utf-8-sig')

        print("\n" + "=" * 70)
        print(f" [✓] REPORTE MUNICIPAL ({nombre_oficial.upper()}) GENERADO CON ÉXITO")
        print(f"     Tomas procesadas: {len(df)}")
        print(f"     NDVI Promedio: {df['ndvi'].mean():.4f}")
        print(f"  -> Archivo JSON: '{ruta_json}'")
        print(f"  -> Archivo CSV:  '{ruta_csv}'")
        print("=" * 70)
        
        return resumen_mun

    def _procesar_estado_general(self):
        print("\n" + "=" * 70)
        print(f" SERVICIO: ANÁLISIS ESTATAL GENERAL Y COMPARATIVA MUNICIPAL ({self.estado.upper()})")
        print(f" Periodo: {self.fecha_inicio} a {self.fecha_fin}")
        print("=" * 70)

        municipios_fc = (ee.FeatureCollection('FAO/GAUL/2015/level2')
                         .filter(ee.Filter.stringContains('ADM1_NAME', 'Michoac')))

        geometria_estatal = municipios_fc.geometry()

        print(" --> Obteniendo colección Sentinel-2 y calculando índices espectrales...")
        coleccion = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(geometria_estatal)
                     .filterDate(self.fecha_inicio, self.fecha_fin)
                     .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
                     .map(self._agregar_indices_agricolas))

        if coleccion.size().getInfo() == 0:
            print(" [!] No se encontraron imágenes Sentinel-2 disponibles para este periodo.")
            return {"error": "No se encontraron imágenes Sentinel-2 disponibles para este periodo."}

        mosaico_indices = coleccion.select(['NDVI', 'NDWI', 'NDRE', 'SAVI']).median()

        print(" --> Calculando métricas de todos los municipios en Google Cloud...")
        def reducir_municipio(feature):
            stats = mosaico_indices.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=feature.geometry(),
                scale=500,
                maxPixels=1e9
            )
            return ee.Feature(None, {
                'municipio': feature.get('ADM2_NAME'),
                'ndvi': stats.get('NDVI'),
                'ndwi': stats.get('NDWI'),
                'ndre': stats.get('NDRE')
            })

        resultados = municipios_fc.map(reducir_municipio).getInfo().get('features', [])

        registros = []
        for f in resultados:
            props = f['properties']
            if props.get('ndvi') is not None:
                registros.append({
                    'municipio': props['municipio'],
                    'ndvi': round(props['ndvi'], 4),
                    'estres_hidrico_ndwi': round(props['ndwi'], 4),
                    'nitrogeno_ndre': round(props['ndre'], 4)
                })

        if not registros:
            print(" [!] No se obtuvieron datos válidos para los municipios.")
            return {"error": "No se obtuvieron datos válidos para los municipios."}

        df = pd.DataFrame(registros).sort_values(by='ndvi', ascending=False)

        resumen_estatal = {
            "tipo_reporte": "General Estatal",
            "estado": self.estado,
            "periodo": {"inicio": self.fecha_inicio, "fin": self.fecha_fin},
            "total_municipios": len(df),
            "promedios_estatales": {
                "ndvi_promedio": round(float(df['ndvi'].mean()), 4),
                "ndwi_promedio": round(float(df['estres_hidrico_ndwi'].mean()), 4)
            },
            "top_3_municipios_verdes": df.head(3)[['municipio', 'ndvi']].to_dict(orient='records'),
            "desglose_todos_municipios": df.to_dict(orient='records')
        }

        ruta_json = os.path.join(self.carpeta_salida, f"{self.nombre_salida}.json")
        ruta_csv = os.path.join(self.carpeta_salida, f"{self.nombre_salida}_municipios.csv")

        with open(ruta_json, 'w', encoding='utf-8') as f:
            json.dump(resumen_estatal, f, ensure_ascii=False, indent=4)

        df.to_csv(ruta_csv, index=False, encoding='utf-8-sig')

        print("\n" + "=" * 70)
        print(f" [✓] REPORTE ESTATAL GENERAL COMPLETADO")
        print(f"     Municipios comparados: {len(df)}")
        print(f"     NDVI Estatal Promedio: {df['ndvi'].mean():.4f}")
        print(f"  -> Archivo JSON: '{ruta_json}'")
        print(f"  -> Archivo CSV:  '{ruta_csv}'")
        print("=" * 70)
        
        return resumen_estatal

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Análisis Satelital Agrícola Seleccionable (Estatal o Municipal).")
    parser.add_argument("--estado", type=str, default="Michoacán de Ocampo", help="Estado a analizar.")
    parser.add_argument("--municipio", type=str, default=None, help="Nombre del municipio específico.")
    parser.add_argument("--inicio", type=str, default="2025-01-01", help="Fecha inicial YYYY-MM-DD.")
    parser.add_argument("--fin", type=str, default="2025-12-31", help="Fecha final YYYY-MM-DD.")
    parser.add_argument("--project", type=str, default="agromich-507422", help="Proyecto de Google Cloud.")
    parser.add_argument("--salida", type=str, default=None, help="Nombre del archivo de salida.")

    args = parser.parse_args()

    procesador = ProcesadorSatelitalModular(
        estado=args.estado,
        municipio=args.municipio,
        fecha_inicio=args.inicio,
        fecha_fin=args.fin,
        project=args.project,
        nombre_salida=args.salida
    )
    
    procesador.procesar()