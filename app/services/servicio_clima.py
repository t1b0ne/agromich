import argparse
import os
import json
import requests
import unicodedata
import pandas as pd
from datetime import datetime, timedelta
import ee

def normalizar_texto(texto):
    if not texto:
        return ""
    texto_norm = unicodedata.normalize('NFD', texto)
    return ''.join(c for c in texto_norm if unicodedata.category(c) != 'Mn').strip().lower()

class ServicioClimaticoAgronomicoAvanzado:
    def __init__(self, estado="Michoacán de Ocampo", municipio=None, latitud=None, longitud=None, 
                 fecha_inicio="2024-01-01", fecha_fin="2024-12-31", temp_base_gdd=10.0, project="agromich-507422"):
        self.estado = estado
        self.municipio = municipio
        self.lat = latitud
        self.lon = longitud
        self.fecha_inicio = fecha_inicio
        self.fecha_fin = fecha_fin
        self.temp_base_gdd = temp_base_gdd
        self.project = project
        self.carpeta_salida = os.path.abspath(os.path.join("reports", "clima_avanzado"))
        os.makedirs(self.carpeta_salida, exist_ok=True)

        try:
            ee.Initialize(project=self.project)
            print(" [✓] Google Earth Engine inicializado correctamente.")
        except Exception as e:
            print(" [!] Error al inicializar Earth Engine.")
            raise e

    def _resolver_coordenadas_municipio(self):
        if self.municipio:
            print(f" --> Localizando municipio '{self.municipio}' en {self.estado}...")
            estado_fc = ee.FeatureCollection('FAO/GAUL/2015/level2').filter(ee.Filter.stringContains('ADM1_NAME', 'Michoac'))
            mun_buscado = normalizar_texto(self.municipio)
            nombres_mun = estado_fc.aggregate_array('ADM2_NAME').getInfo()
            
            nombre_oficial = next((nombre for nombre in nombres_mun if mun_buscado in normalizar_texto(nombre)), None)

            if not nombre_oficial:
                print(f" [!] No se encontró el municipio '{self.municipio}'.")
                return False

            municipio_fc = estado_fc.filter(ee.Filter.eq('ADM2_NAME', nombre_oficial))
            centroide = municipio_fc.geometry().centroid().coordinates().getInfo()
            
            self.lon, self.lat = round(centroide[0], 4), round(centroide[1], 4)
            self.nombre_oficial = nombre_oficial
            print(f" --> Municipio: '{nombre_oficial}' | Centroide: Lat {self.lat}, Lon {self.lon}")
            return True
        else:
            self.nombre_oficial = "Coordenadas Personalizadas"
            if self.lat is None or self.lon is None:
                self.lat, self.lon = 19.897, -100.444
            return True

    def _validar_y_ajustar_fechas(self):
        ayer = datetime.now() - timedelta(days=2)
        f_fin_dt = datetime.strptime(self.fecha_fin, "%Y-%m-%d")
        if f_fin_dt > ayer:
            self.fecha_fin = ayer.strftime("%Y-%m-%d")

    def obtener_datos_nasa_power(self):
        self._validar_y_ajustar_fechas()
        f_ini_str, f_fin_str = self.fecha_inicio.replace("-", ""), self.fecha_fin.replace("-", "")

        url = "https://power.larc.nasa.gov/api/temporal/daily/point"
        params = {
            "parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,ALLSKY_SFC_SW_DWN,RH2M,EVPTRNS,WS2M,T2MDEW",
            "community": "AG",
            "longitude": self.lon,
            "latitude": self.lat,
            "start": f_ini_str,
            "end": f_fin_str,
            "format": "JSON"
        }

        try:
            res = requests.get(url, params=params, timeout=30)
            if res.status_code != 200:
                print("\n [!] Error NASA POWER:", res.text)
                return None

            data = res.json().get("properties", {}).get("parameter", {})
            registros = []
            fechas = sorted(list(data.get("T2M", {}).keys()))

            for f in fechas:
                t_max = data.get("T2M_MAX", {}).get(f)
                t_min = data.get("T2M_MIN", {}).get(f)
                t_med = data.get("T2M", {}).get(f)
                viento = data.get("WS2M", {}).get(f)

                gdd = max(0, t_med - self.temp_base_gdd) if t_med is not None else 0

                registros.append({
                    "fecha": f"{f[:4]}-{f[4:6]}-{f[6:]}",
                    "temp_media_c": t_med,
                    "temp_max_c": t_max,
                    "temp_min_c": t_min,
                    "punto_rocio_c": data.get("T2MDEW", {}).get(f),
                    "precipitacion_mm": data.get("PRECTOTCORR", {}).get(f),
                    "radiacion_solar_mj_m2": data.get("ALLSKY_SFC_SW_DWN", {}).get(f),
                    "humedad_relativa_pct": data.get("RH2M", {}).get(f),
                    "evapotranspiracion_mm": data.get("EVPTRNS", {}).get(f),
                    "viento_2m_ms": viento,
                    "viento_2m_kmh": round(viento * 3.6, 2) if viento is not None else None,
                    "gdd_diario": round(gdd, 2)
                })

            return pd.DataFrame(registros)
        except Exception as e:
            print(f" [!] Error técnico: {e}")
            return None

    def ejecutar_analisis_agronomico_completo(self):
        """
        Método principal optimizado para FastAPI / Hermes.
        Genera el informe climático agronómico, guarda respaldo en disco y RETORNA el diccionario.
        """
        if not self._resolver_coordenadas_municipio():
            return {"error": f"No se encontró el municipio '{self.municipio}' en {self.estado}."}

        df = self.obtener_datos_nasa_power()
        if df is None or df.empty:
            return {"error": "No se pudieron obtener datos climáticos de NASA POWER para las coordenadas/fechas especificadas."}

        # --- Métricas Agronómicas ---
        precip_total = df['precipitacion_mm'].sum()
        et0_total = df['evapotranspiracion_mm'].sum()
        balance_hidrico = precip_total - et0_total
        gdd_acumulados = df['gdd_diario'].sum()

        dias_helada_potencial = len(df[df['temp_min_c'] <= 2.0])
        dias_estres_calor = len(df[df['temp_max_c'] >= 32.0])
        dias_optimos_fumigacion = len(df[df['viento_2m_kmh'] <= 12.0])

        resumen = {
            "ubicacion": {
                "estado": self.estado,
                "municipio": self.nombre_oficial,
                "coordenadas": {"latitud": self.lat, "longitud": self.lon}
            },
            "periodo": {"inicio": self.fecha_inicio, "fin": self.fecha_fin},
            "balance_hidrico": {
                "precipitacion_acumulada_mm": round(float(precip_total), 2),
                "evapotranspiracion_acumulada_mm": round(float(et0_total), 2),
                "balance_neto_mm": round(float(balance_hidrico), 2)
            },
            "agronomia_y_fenologia": {
                "temp_base_gdd_usada_c": self.temp_base_gdd,
                "grados_dia_acumulados_gdd": round(float(gdd_acumulados), 2),
                "dias_riesgo_helada": dias_helada_potencial,
                "dias_estres_termico_calor": dias_estres_calor,
                "dias_aptos_fumigacion": dias_optimos_fumigacion,
                "viento_promedio_kmh": round(float(df['viento_2m_kmh'].mean()), 2)
            },
            "serie_diaria": df.to_dict(orient='records')
        }

        nombre_archivo = self.nombre_oficial.lower().replace(" ", "_") if self.municipio else f"{self.lat}_{self.lon}"
        ruta_json = os.path.join(self.carpeta_salida, f"agronomo_{nombre_archivo}.json")
        ruta_csv = os.path.join(self.carpeta_salida, f"agronomo_{nombre_archivo}.csv")

        with open(ruta_json, 'w', encoding='utf-8') as f:
            json.dump(resumen, f, ensure_ascii=False, indent=4)

        df.to_csv(ruta_csv, index=False, encoding='utf-8-sig')

        print("\n" + "=" * 70)
        print(f" [✓] INFORME AGRONÓMICO COMPLETO GENERADO ({self.nombre_oficial.upper()})")
        print(f"     Precipitación Acumulada:  {precip_total:.2f} mm")
        print(f"     Evapotranspiración (ET0): {et0_total:.2f} mm")
        print(f"     Grados Día (GDD Base {self.temp_base_gdd}°C): {gdd_acumulados:.2f} GDD")
        print(f"     Días Riesgo Helada (<=2°C): {dias_helada_potencial} días")
        print(f"     Días Estrés Calor (>=32°C): {dias_estres_calor} días")
        print(f"     Días Óptimos Fumigación (Viento <=12km/h): {dias_optimos_fumigacion} días")
        print(f"  -> Archivo JSON: '{ruta_json}'")
        print(f"  -> Archivo CSV:  '{ruta_csv}'")
        print("=" * 70)

        return resumen

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Módulo Avanzado de Clima e Indicadores Agronómicos.")
    parser.add_argument("--estado", type=str, default="Michoacán de Ocampo")
    parser.add_argument("--municipio", type=str, default=None)
    parser.add_argument("--lat", type=float, default=None)
    parser.add_argument("--lon", type=float, default=None)
    parser.add_argument("--inicio", type=str, default="2024-01-01")
    parser.add_argument("--fin", type=str, default="2024-12-31")
    parser.add_argument("--temp_base", type=float, default=10.0, help="Temperatura base para GDD (ej. 10 para Maíz).")
    parser.add_argument("--project", type=str, default="agromich-507422")

    args = parser.parse_args()

    servicio = ServicioClimaticoAgronomicoAvanzado(
        estado=args.estado,
        municipio=args.municipio,
        latitud=args.lat,
        longitud=args.lon,
        fecha_inicio=args.inicio,
        fecha_fin=args.fin,
        temp_base_gdd=args.temp_base,
        project=args.project
    )
    
    # Ejecución manual por CLI
    servicio.ejecutar_analisis_agronomico_completo()