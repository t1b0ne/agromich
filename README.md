# AgroMich API

API REST para análisis agrícola, climático y geoespacial de predios. Integra Google Earth Engine, NASA POWER, SIAP y catálogos de sanidad/programas. Genera reportes descargables en HTML o PDF.

## Capacidades

- Análisis satelital: NDVI, EVI, topografía, evapotranspiración y señales de cambio de cobertura.
- Auditoría de predios y clasificación preliminar de cultivos.
- Clima agronómico: precipitación, evapotranspiración, GDD y riesgos climáticos.
- Consulta SIAP mediante navegador automatizado.
- Alertas fitosanitarias y programas agrícolas disponibles.
- Expedientes ambientales e imágenes históricas.
- Reportes consolidados y descarga manual en HTML/PDF.

> Los resultados geoespaciales son indicadores técnicos. No sustituyen validación en campo ni un dictamen legal o ambiental oficial.

## Requisitos

- Python 3.10 o superior.
- Google Chrome y ChromeDriver compatibles para el endpoint SIAP (`/api/v1/suelo/analisis`).
- Una cuenta/proyecto con acceso a Google Earth Engine para satélite, cultivos, predios y expediente.
- Acceso a internet para NASA POWER, SIAP y Google Earth Engine.

## Instalación y arranque

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

La API queda disponible en `http://localhost:8000`.

- Swagger/OpenAPI interactivo: `http://localhost:8000/docs`
- Esquema OpenAPI: `http://localhost:8000/openapi.json`

## Configuración

Cree un archivo `.env` en la raíz del proyecto. No lo suba a Git.

```env
# Recomendado en cualquier entorno que no sea local.
AGROMICH_API_KEY=una-clave-larga-y-secreta

# Proyecto de Google Earth Engine.
EARTHENGINE_PROJECT=agromich-507422

# Opcional: JSON de credenciales OAuth serializado en una sola línea.
EARTHENGINE_CREDENTIALS={"refresh_token":"...","client_id":"...","client_secret":"...","token_uri":"https://oauth2.googleapis.com/token","project":"agromich-507422"}

# Orígenes permitidos para frontend separados por coma.
GEOVIGIA_ORIGINS=http://localhost:5173,https://tu-dominio.com
```

### Autenticación

Las operaciones que consumen recursos externos o acceden a reportes requieren el encabezado `X-API-Key` **si** se configuró `AGROMICH_API_KEY`. Si la variable no existe, la protección queda desactivada solo para desarrollo local.

```bash
curl -X POST http://localhost:8000/api/v1/clima/analisis \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu-clave" \
  -d "{...}"
```

## Convenciones generales

- Todas las rutas de negocio están bajo `/api/v1`.
- Los cuerpos se envían como JSON con `Content-Type: application/json`.
- Fechas: `YYYY-MM-DD`.
- GeoJSON usa coordenadas WGS84 en orden `[longitud, latitud]`.
- Se aceptan `Polygon` y, cuando se indique, `MultiPolygon` o `Feature`.
- Máximo: 5,000 posiciones GeoJSON por solicitud.
- Errores comunes: `401`/`403` API key, `422` cuerpo inválido, `502` fallo de proveedor externo y `503` servicio no disponible.

Ejemplo de polígono pequeño reutilizable:

```json
{
  "type": "Polygon",
  "coordinates": [[
    [-102.065, 19.412], [-102.055, 19.412],
    [-102.055, 19.422], [-102.065, 19.422],
    [-102.065, 19.412]
  ]]
}
```

## Endpoints

### Sistema

| Método | Ruta | API key | Descripción |
| --- | --- | --- | --- |
| `GET` | `/` | No | Información básica y enlaces de la API. |
| `GET` | `/api/v1/sistema/salud` | No | *Liveness probe*: confirma que FastAPI está activo, sin llamadas externas. |
| `GET` | `/api/v1/sistema/preparacion` | No | Comprueba que Selenium, ReportLab y el proyecto GEE estén configurados localmente. |

Ejemplo:

```bash
curl http://localhost:8000/api/v1/sistema/preparacion
```

### Clima agronómico

`POST /api/v1/clima/analisis`

Obtiene información diaria de NASA POWER y calcula precipitación acumulada, evapotranspiración, balance hídrico, GDD, heladas, estrés térmico y días aptos para fumigación. Se puede indicar un municipio o coordenadas.

```json
{
  "estado": "Michoacan de Ocampo",
  "municipio": "Uruapan",
  "fecha_inicio": "2025-01-01",
  "fecha_fin": "2025-12-31",
  "temp_base_gdd": 10
}
```

Para coordenadas directas use `latitud` y `longitud` juntos:

```json
{
  "latitud": 19.421,
  "longitud": -102.062,
  "fecha_inicio": "2025-01-01",
  "fecha_fin": "2025-03-31"
}
```

Los campos tienen valores por defecto para estado, fechas y GDD. `temp_base_gdd` debe estar entre `-20` y `50`.

### Suelo y datos SIAP

`POST /api/v1/suelo/analisis`

Ejecuta el extractor SIAP y guarda un JSON en `reports/suelo_y_socioeconomico/`. Es una operación lenta porque inicia Chrome headless.

```json
{
  "estado": "Michoacan de Ocampo",
  "tipo_consulta": "municipio",
  "ciclo": "Ciclicos - Perennes",
  "modalidad": "Riego + Temporal",
  "cultivo": "Resumen cultivos"
}
```

`tipo_consulta` solo acepta `municipio` o `entidad`. Los demás campos son opcionales y tienen valores por defecto.

### Sanidad y programas

`POST /api/v1/sanidad/consulta`

Consulta el catálogo de alertas fitosanitarias y programas disponibles, y guarda una copia en `reports/sanidad_y_programas/`.

```json
{
  "estado": "Michoacan de Ocampo",
  "municipio": "Uruapan",
  "cultivo": "Aguacate"
}
```

`municipio` y `cultivo` son opcionales. Si se omiten, la consulta es estatal/general.

### Análisis satelital

`POST /api/v1/satelite/analisis`

Analiza una geometría con Sentinel-2, Hansen, NASADEM y MODIS. Devuelve métricas de vegetación, topografía, evapotranspiración y alertas preliminares.

```json
{
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[-102.065, 19.412], [-102.055, 19.412], [-102.055, 19.422], [-102.065, 19.422], [-102.065, 19.412]]]
  },
  "cultivo": "aguacate",
  "fecha_inicio": "2020-01-01",
  "fecha_fin": "2025-12-31"
}
```

`geometry`, `fecha_inicio` y `fecha_fin` son obligatorios. `cultivo` tiene el valor predeterminado `aguacate`.

### Clasificación de cultivos

`POST /api/v1/cultivos/clasificar-y-verificar`

Clasificación preliminar basada en firma espectral y textura para contrastar el cultivo declarado.

```json
{
  "geometry": { "type": "Polygon", "coordinates": [[[-102.065, 19.412], [-102.055, 19.412], [-102.055, 19.422], [-102.065, 19.422], [-102.065, 19.412]]] },
  "cultivo": "aguacate",
  "anio": 2025
}
```

`anio` debe estar entre 2017 y el año actual.

### Predios y auditorías

`POST /api/v1/predios/auditar`

Audita un predio con información declarada y análisis satelital comparativo.

```json
{
  "nombre_huerto": "Huerta San Jose",
  "productor": "Productor Ejemplo",
  "cultivo": "aguacate",
  "municipio": "Uruapan",
  "geojson": { "type": "Polygon", "coordinates": [[[-102.065, 19.412], [-102.055, 19.412], [-102.055, 19.422], [-102.065, 19.422], [-102.065, 19.412]]] },
  "fecha_inicio_auditoria": "2018-01-01",
  "fecha_fin_auditoria": "2025-12-31"
}
```

Los dos campos de fecha de auditoría son opcionales.

### Expedientes ambientales

`POST /api/v1/expediente/generar-completo`

Genera un expediente con serie NDVI, verificación preliminar de uso de suelo, incendios y alertas de deforestación.

```json
{
  "nombre_huerto": "Huerta San Jose",
  "productor": "Productor Ejemplo",
  "municipio": "Uruapan",
  "cultivo": "aguacate",
  "geometry": { "type": "Polygon", "coordinates": [[[-102.065, 19.412], [-102.055, 19.412], [-102.055, 19.422], [-102.065, 19.422], [-102.065, 19.412]]] },
  "anio_inicio": 2018,
  "anio_fin": 2025
}
```

`nombre_huerto`, `productor` y `geometry` son obligatorios. Los años están limitados desde 1984 hasta el año actual.

`POST /api/v1/expediente/imagenes-historicas`

Devuelve metadatos, miniaturas y URLs de mosaicos para los años solicitados.

```json
{
  "geometry": { "type": "Polygon", "coordinates": [[[-102.065, 19.412], [-102.055, 19.412], [-102.055, 19.422], [-102.065, 19.422], [-102.065, 19.412]]] },
  "anios": [2018, 2020, 2022, 2025],
  "cultivo": "aguacate",
  "visualizacion": "rgb",
  "mes_inicio": 1,
  "mes_fin": 4
}
```

Acepta únicamente `Polygon`; `anios` acepta de 1 a 20 valores, entre 1984 y el año actual. `mes_inicio` no puede ser mayor que `mes_fin`.

### Reportes y descargas

`POST /api/v1/reportes/generar`

Consolida los JSON disponibles de clima, suelo, sanidad y procesados, filtrados por estado y municipio. Devuelve el archivo inmediatamente como descarga y además lo almacena en `reports/generados/`.

```json
{
  "titulo": "Reporte integral Uruapan",
  "estado": "Michoacan de Ocampo",
  "municipio": "Uruapan",
  "servicios": ["clima", "suelo", "sanidad"],
  "incluir_historial": false,
  "formato": "pdf",
  "datos_adicionales": {
    "folio": "AGM-2025-001",
    "responsable": "Equipo tecnico"
  }
}
```

Valores permitidos para `servicios`: `clima`, `suelo`, `sanidad`, `procesados`. Si se omite, se incluyen todos. `formato` acepta `html` o `pdf`.

```bash
curl -X POST http://localhost:8000/api/v1/reportes/generar \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu-clave" \
  -d @reporte.json \
  --output reporte-uruapan.pdf
```

`GET /api/v1/reportes` lista archivos generados:

```bash
curl -H "X-API-Key: tu-clave" http://localhost:8000/api/v1/reportes
```

`GET /api/v1/reportes/{archivo}/descarga` descarga uno de los nombres devueltos por el catálogo:

```bash
curl -H "X-API-Key: tu-clave" \
  "http://localhost:8000/api/v1/reportes/reporte-integral-uruapan_uruapan_20251008_101500.pdf/descarga" \
  --output reporte.pdf
```

## Estructura relevante

```text
app/
├── main.py                    # Aplicación FastAPI y registro de routers
├── routers/                   # Implementación HTTP por dominio
├── schemas/                   # Validación Pydantic de solicitudes/respuestas
├── services/                  # Lógica de clima, GEE, SIAP, expedientes y reportes
├── integrations/              # Clientes de servicios externos (NASA POWER, GEE)
├── repositories/              # Lectura/escritura segura de reports/
├── core/                      # Configuración, seguridad e inicialización GEE
└── api/v1/routers/            # Adaptadores para la API versionada
reports/
├── clima_avanzado/            # Salidas de clima
├── suelo_y_socioeconomico/    # Resultados SIAP
├── sanidad_y_programas/       # Consultas fitosanitarias
└── generados/                 # HTML/PDF descargables
```

## Operación y límites

- Mantenga `reports/` fuera de Git en producción si contiene información de productores o predios.
- Las tareas SIAP y GEE pueden tardar; no las use desde una interfaz sin indicador de carga o límite de tiempo.
- Para despliegue productivo, configure `AGROMICH_API_KEY`, CORS específico y un mecanismo de rate limiting.
- Consulte `/docs` para el contrato OpenAPI actualizado, que es la fuente de verdad cuando cambien los modelos.
