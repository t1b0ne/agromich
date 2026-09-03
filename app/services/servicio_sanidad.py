import argparse
import os
import json
import unicodedata
from datetime import datetime

def normalizar_texto(texto):
    """Elimina tildes, caracteres especiales y convierte a minúsculas para comparaciones limpias."""
    if not texto:
        return ""
    texto_norm = unicodedata.normalize('NFD', texto)
    return ''.join(c for c in texto_norm if unicodedata.category(c) != 'Mn').strip().lower()

class ServicioSanidadYProgramasEstatales:
    def __init__(self, estado="Michoacán de Ocampo", municipio=None, cultivo=None, project="agromich-507422"):
        self.estado = estado
        self.municipio = municipio
        self.cultivo = cultivo.capitalize() if cultivo else None
        self.project = project
        self.carpeta_salida = os.path.abspath(os.path.join("reports", "sanidad_y_programas"))
        os.makedirs(self.carpeta_salida, exist_ok=True)

        # Base de Datos de Alertas y Estatus Fitosanitario (CESAVEMICH)
        self.base_cesavemich = [
            {
                "cultivo": "Aguacate",
                "plaga_enfermedad": "Barrenador de hueso (Conotrachelus spp. y Heilipus lauri)",
                "estatus": "Baja Prevalencia / Zona Bajo Control Oficial",
                "nivel_alerta": "Media",
                "recomendacion_fitosanitaria": "Muestreo continuo de frutos, podas sanitarias y destrucción de frutos caídos.",
                "zonas_criticas": ["Uruapan", "Tancítaro", "Ario", "Tacámbaro"]
            },
            {
                "cultivo": "Aguacate",
                "plaga_enfermedad": "Trips (Frankliniella spp.)",
                "estatus": "Endémica / Control en época de floración",
                "nivel_alerta": "Alta",
                "recomendacion_fitosanitaria": "Monitoreo con trampas amarillas y control biológico/físico en floración.",
                "zonas_criticas": ["Peribán", "Los Reyes", "Salvador Escalante"]
            },
            {
                "cultivo": "Berries",
                "plaga_enfermedad": "Trips y Araña Roja (Tetranychus urticae)",
                "estatus": "Alerta Activa en temporada seca",
                "nivel_alerta": "Alta",
                "recomendacion_fitosanitaria": "Uso de ácaros depredadores (Phytoseiulus), regulación de microclima y humedad relativa.",
                "zonas_criticas": ["Zamora", "Jacona", "Tangancícuaro", "Maravatío"]
            },
            {
                "cultivo": "Berries",
                "plaga_enfermedad": "Mosca de alas manchadas (Drosophila suzukii)",
                "estatus": "Vigilancia Epidemiológica Permanente",
                "nivel_alerta": "Alta",
                "recomendacion_fitosanitaria": "Colocación de trampas de monitoreo con vinagre de manzana, recolección oportuna.",
                "zonas_criticas": ["Maravatío", "Zitácuaro", "Zamora"]
            },
            {
                "cultivo": "Cítricos",
                "plaga_enfermedad": "HLB / Dragón Amarillo (Candidatus Liberibacter)",
                "estatus": "Cuarentenaria bajo Control Oficial",
                "nivel_alerta": "Crítica",
                "recomendacion_fitosanitaria": "Control de psílido asiático (Diaphorina citri) y eliminación de árboles con síntomas.",
                "zonas_criticas": ["Apatzingán", "Buenavista", "Tepalcatepec", "Múgica"]
            },
            {
                "cultivo": "Maíz",
                "plaga_enfermedad": "Gusano Cogollero (Spodoptera frugiperda)",
                "estatus": "Frecuente / Estacional",
                "nivel_alerta": "Media",
                "recomendacion_fitosanitaria": "Liberación de Trichogramma, aplicación de Bacillus thuringiensis en primeras etapas.",
                "zonas_criticas": ["Maravatío", "Penjamillo", "Ecuandureo", "Venustiano Carranza"]
            }
        ]

        # Base de Datos de Programas y Apoyos Estatales (SADER Michoacán)
        self.base_sader_michoacan = [
            {
                "programa": "AgroSano Michoacán",
                "descripcion": "Fomento a la transición agroecológica, bioinsumos y asistencia técnica gratuita en territorio.",
                "beneficiarios": "Pequeños y medianos productores de granos, hortalizas y frutales.",
                "requisitos_clave": "CURP, Identificación Oficial, Comprobante de legal posesión del predio.",
                "cobertura": "Estatal (113 municipios)"
            },
            {
                "programa": "Programa de Maíz e Insumos Agrícolas",
                "descripcion": "Subsidiario para la adquisición de semilla certificada y fertilizantes / acondicionadores de suelo.",
                "beneficiarios": "Productores de temporal y riego de maíz y trigo.",
                "requisitos_clave": "Estar dentro del Padrón Único de Productores de SADER y georreferenciación de parcela.",
                "cobertura": "Bajío Michoacano, Valle de Maravatío, Meseta Purépecha"
            },
            {
                "programa": "Certificación y Fitosanidad Agropecuaria",
                "descripcion": "Apoyos directos para la integración de campañas fitosanitarias de CESAVEMICH e inocuidad.",
                "beneficiarios": "Unidades de Producción de Aguacate, Berries y Cítricos.",
                "requisitos_clave": "Registro de Huerto en SADER-CESAVEMICH y bitácora de manejo de plaguicidas.",
                "cobertura": "Zonas de Exportación Fitosanitaria"
            }
        ]

    def consultar_cesavemich(self):
        """Filtra alertas epidemiológicas de CESAVEMICH por cultivo y/o municipio."""
        print("\n" + "="*70)
        print(" [CESAVEMICH] CONSULTA DE ALERTAS Y ESTATUS FITOSANITARIO")
        print("="*70)

        alertas_filtradas = []
        cultivo_buscado = normalizar_texto(self.cultivo) if self.cultivo else None
        municipio_buscado = normalizar_texto(self.municipio) if self.municipio else None

        for alerta in self.base_cesavemich:
            cumple_cultivo = not cultivo_buscado or cultivo_buscado in normalizar_texto(alerta["cultivo"])
            cumple_mun = not municipio_buscado or any(municipio_buscado in normalizar_texto(z) for z in alerta["zonas_criticas"])

            if cumple_cultivo or cumple_mun:
                alertas_filtradas.append(alerta)

        print(f" --> Registros epidemiológicos encontrados: {len(alertas_filtradas)}")
        return alertas_filtradas

    def consultar_sader(self):
        """Obtiene programas de apoyo y zonificación estatal de SADER Michoacán."""
        print("\n" + "="*70)
        print(" [SADER MICHOACÁN] PROGRAMAS DE APOYO Y ZONIFICACIÓN")
        print("="*70)

        programas_aplicables = self.base_sader_michoacan
        print(f" --> Programas estatales activos disponibles: {len(programas_aplicables)}")
        return programas_aplicables

    def generar_reporte(self):
        """
        Método principal optimizado para FastAPI / Hermes.
        Genera el informe de sanidad y apoyos, guarda respaldo en disco y RETORNA el diccionario.
        """
        alertas = self.consultar_cesavemich()
        programas = self.consultar_sader()

        resumen = {
            "fecha_consulta": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "parametros_busqueda": {
                "estado": self.estado,
                "municipio": self.municipio if self.municipio else "Todo el Estado",
                "cultivo": self.cultivo if self.cultivo else "Todos los Cultivos"
            },
            "cesavemich_sanidad_vegetal": {
                "total_alertas": len(alertas),
                "alertas_y_estatus": alertas
            },
            "sader_michoacan_programas": {
                "total_programas": len(programas),
                "programas_activos": programas
            }
        }

        # Generar archivos de respaldo
        mun_str = normalizar_texto(self.municipio).replace(" ", "_") if self.municipio else "estatal"
        cul_str = normalizar_texto(self.cultivo).replace(" ", "_") if self.cultivo else "general"
        identificador = f"{mun_str}_{cul_str}"
        
        ruta_json = os.path.join(self.carpeta_salida, f"sanidad_y_sader_{identificador}.json")

        with open(ruta_json, 'w', encoding='utf-8') as f:
            json.dump(resumen, f, ensure_ascii=False, indent=4)

        print("\n" + "="*70)
        print(" [✓] INFORME DE SANIDAD VEGETAL Y APOYOS ESTATALES GENERADO")
        print(f"  -> Archivo JSON guardado en: '{ruta_json}'")
        print("="*70)

        return resumen

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Módulo de Sanidad Vegetal (CESAVEMICH) y Programas Estatales (SADER Michoacán).")
    parser.add_argument("--estado", type=str, default="Michoacán de Ocampo")
    parser.add_argument("--municipio", type=str, default=None, help="Ej. Maravatío, Uruapan, Zamora, Apatzingán")
    parser.add_argument("--cultivo", type=str, default=None, help="Ej. Aguacate, Berries, Cítricos, Maíz")
    parser.add_argument("--project", type=str, default="agromich-507422")

    args = parser.parse_args()

    servicio = ServicioSanidadYProgramasEstatales(
        estado=args.estado,
        municipio=args.municipio,
        cultivo=args.cultivo,
        project=args.project
    )
    servicio.generar_reporte()