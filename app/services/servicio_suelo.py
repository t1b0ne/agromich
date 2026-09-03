import argparse
import json
import os
import time
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class ExtractorSIAPDirecto:
    def __init__(self, estado="Michoacán de Ocampo", tipo_consulta="municipio", ciclo="Ciclicos - Perennes", modalidad="Riego + Temporal", cultivo="Resumen cultivos"):
        self.estado = estado.strip()
        self.tipo_consulta = tipo_consulta.lower()
        self.ciclo = ciclo.strip()
        self.modalidad = modalidad.strip()
        self.cultivo = cultivo.strip()
        
        # Carpeta de salida organizada dentro de 'reports'
        self.carpeta_salida = os.path.abspath(os.path.join("reports", "suelo_y_socioeconomico"))
        os.makedirs(self.carpeta_salida, exist_ok=True)
        
        # Nombre dinámico y ruta final del archivo JSON
        nombre_estado_slug = self.estado.lower().replace(" ", "_")
        cultivo_slug = self.cultivo.lower().replace(" ", "_")
        nombre_archivo = f"siap_{nombre_estado_slug}_{self.tipo_consulta}_{cultivo_slug}.json"
        
        self.archivo_json = os.path.join(self.carpeta_salida, nombre_archivo)
        self.url = "https://nube.agricultura.gob.mx/avance_agricola/"

    def _iniciar_driver(self):
        """Inicializa el navegador Selenium en modo headless."""
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        return webdriver.Chrome(options=options)

    def _seleccionar_opcion_dropdown(self, driver, element_id, valor_buscar, nombre_campo):
        """Helper para seleccionar una opción en un <select> por coincidencia de texto."""
        try:
            wait = WebDriverWait(driver, 10)
            select_elem = wait.until(EC.presence_of_element_located((By.ID, element_id)))
            select_obj = Select(select_elem)
            
            opcion_encontrada = False
            for option in select_obj.options:
                texto_opcion = option.text.strip()
                if valor_buscar.lower() in texto_opcion.lower():
                    select_obj.select_by_visible_text(texto_opcion)
                    opcion_encontrada = True
                    print(f"    [✓] {nombre_campo}: '{texto_opcion}'")
                    break
            
            if not opcion_encontrada:
                print(f"    [!] Advertencia: No se encontró '{valor_buscar}' en {nombre_campo}. Se usará la opción actual por defecto.")
            
            driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", select_elem)
            time.sleep(1.5)
            return True
        except Exception as e:
            print(f"    [!] Error al seleccionar {nombre_campo}: {e}")
            return False

    def obtener_tabla_html_directa(self):
        print("\n" + "=" * 60)
        print(" EXTRACCIÓN DIRECTA SIAP (MODO SILENCIOSO/HEADLESS)")
        print(f" Estado: {self.estado.upper()} | Tipo: {self.tipo_consulta.upper()}")
        print(f" Ciclo: {self.ciclo} | Modalidad: {self.modalidad} | Cultivo: {self.cultivo}")
        print("=" * 60)
        
        driver = self._iniciar_driver()
        try:
            print(" --> Cargando portal del SIAP...")
            driver.get(self.url)
            wait = WebDriverWait(driver, 25)

            time.sleep(2)
            try:
                wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "blockUI")))
            except Exception:
                pass

            # 1. Seleccionar tipo de reporte
            if self.tipo_consulta == "municipio":
                print(" --> 1. Marcando 'Por Distrito - Municipio'...")
                radio_id = "opcionDDRMpio2"
            else:
                print(" --> 1. Marcando 'Por Entidad Federativa'...")
                radio_id = "opcionDDRMpio1"

            radio_elem = wait.until(EC.presence_of_element_located((By.ID, radio_id)))
            driver.execute_script("arguments[0].click();", radio_elem)
            time.sleep(2)

            # 2. Seleccionar Filtros
            print(" --> 2. Aplicando filtros en los menús desplegables...")
            self._seleccionar_opcion_dropdown(driver, "entidad", self.estado, "Estado")
            self._seleccionar_opcion_dropdown(driver, "ciclo", self.ciclo, "Ciclo")
            self._seleccionar_opcion_dropdown(driver, "modalidad", self.modalidad, "Modalidad")
            self._seleccionar_opcion_dropdown(driver, "cultivo", self.cultivo, "Cultivo")

            # 3. Clic en Consultar
            print(" --> 3. Presionando botón 'Consultar'...")
            btn_consultar = wait.until(EC.presence_of_element_located((By.ID, "Consultar")))
            driver.execute_script("arguments[0].click();", btn_consultar)

            # 4. Esperar a que la tabla cargue
            print(" --> 4. Esperando la respuesta y datos de la tabla...")
            tabla_html = None
            for intento in range(30):
                time.sleep(1)
                html_pantalla = driver.page_source
                
                overlays = driver.find_elements(By.CLASS_NAME, "blockUI")
                esta_cargando = any(o.is_displayed() for o in overlays)
                
                if not esta_cargando and ("<table" in html_pantalla.lower()):
                    print(f" --> ¡Tabla procesada exitosamente al segundo {intento + 1}!")
                    tabla_html = html_pantalla
                    break

            driver.quit()
            return tabla_html

        except Exception as e:
            print(f" [!] Error en la navegación: {e}")
            try:
                driver.quit()
            except Exception:
                pass
            return None

    def _limpiar_texto(self, val):
        if val is None:
            return None
        val_str = str(val).strip()
        if not val_str or val_str.lower() == "nan":
            return None
        val_num = val_str.replace(",", "")
        try:
            return float(val_num) if "." in val_num else int(val_num)
        except ValueError:
            return val_str

    def parsear_html_a_json(self, html_content):
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            tablas = soup.find_all("table")

            if not tablas:
                return []

            tabla_target = max(tablas, key=lambda t: len(t.find_all("tr")))
            filas = tabla_target.find_all("tr")

            registros_limpios = []

            for fila in filas:
                celdas = fila.find_all(["td", "th"])
                
                if not celdas:
                    text_tr = str(fila)
                    if "<!--" in text_tr:
                        text_limpio = text_tr.replace("<!--", "").replace("-->", "")
                        soup_sub = BeautifulSoup(text_limpio, "html.parser")
                        celdas = soup_sub.find_all(["td", "th"])

                valores = [c.get_text(strip=True) for c in celdas]

                if not valores:
                    continue

                texto_fila = " ".join(valores).lower()

                if any(k in texto_fila for k in ["total", "fuente", "subsecretaría", "avance de siembras"]):
                    continue

                valores_procesados = [self._limpiar_texto(v) for v in valores if v != ""]
                
                if len(valores_procesados) >= 3:
                    item = {}
                    for i, val in enumerate(valores_procesados):
                        item[f"columna_{i}"] = val
                    registros_limpios.append(item)

            return registros_limpios

        except Exception as e:
            print(f" [!] Error al procesar el HTML: {e}")
            return []

    def ejecutar_extraccion(self):
        """
        Método principal optimizado para FastAPI y Hermes.
        Realiza el raspado, guarda en disco y RETORNA el diccionario estructurado.
        """
        html_pagina = self.obtener_tabla_html_directa()
        datos = []
        
        if html_pagina:
            datos = self.parsear_html_a_json(html_pagina)

        resultado = {
            "metadata": {
                "fuente": "SIAP - Avance Agrícola",
                "estado_consultado": self.estado,
                "tipo_consulta": self.tipo_consulta,
                "ciclo": self.ciclo,
                "modalidad": self.modalidad,
                "cultivo": self.cultivo,
                "metodo_extraccion": "HTML DOM Scraper Directo (Headless)",
                "fecha_extraccion": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_registros": len(datos)
            },
            "datos": datos
        }

        # Guardar en disco duro dentro de reports/suelo_y_socioeconomico/
        with open(self.archivo_json, "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)

        print(f"\n [✓] ÉXITO: Archivo respaldado en '{self.archivo_json}'")
        print(f"    Total de registros extraídos: {len(datos)}\n")

        return resultado


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scraper configurable del SIAP.")
    
    parser.add_argument("--estado", type=str, default="Michoacán de Ocampo", help="Nombre del estado.")
    parser.add_argument("--tipo", choices=["municipio", "entidad"], default="municipio", help="Tipo de consulta.")
    parser.add_argument("--ciclo", type=str, default="Ciclicos - Perennes", help="Ciclo agrícola.")
    parser.add_argument("--modalidad", type=str, default="Riego + Temporal", help="Modalidad.")
    parser.add_argument("--cultivo", type=str, default="Resumen cultivos", help="Nombre del cultivo.")
    
    args = parser.parse_args()

    extractor = ExtractorSIAPDirecto(
        estado=args.estado,
        tipo_consulta=args.tipo,
        ciclo=args.ciclo,
        modalidad=args.modalidad,
        cultivo=args.cultivo
    )
    
    extractor.ejecutar_extraccion()