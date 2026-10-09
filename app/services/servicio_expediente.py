from datetime import datetime
from typing import Any, Dict, Iterable
from concurrent.futures import ThreadPoolExecutor
import ee
from app.core.gee import get_ee


class ServicioExpediente:
    """Genera una serie de imágenes históricas para un polígono en Earth Engine (Optimizado con Multihilos)."""

    def __init__(self, geometry: Dict[str, Any], mes_inicio: int, mes_fin: int):
        get_ee()
        if geometry.get("type") != "Polygon":
            raise ValueError("geometry debe ser un GeoJSON Polygon")
        if mes_inicio > mes_fin:
            raise ValueError("mes_inicio debe ser menor o igual que mes_fin")
        self.geometry_geojson = geometry
        self.geometry = ee.Geometry(geometry)
        self.mes_inicio = mes_inicio
        self.mes_fin = mes_fin

    @staticmethod
    def _mascara_sentinel(image):
        qa = image.select("QA60")
        mask = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
        return image.updateMask(mask).select(
            ["B4", "B3", "B2", "B8"], ["red", "green", "blue", "nir"]
        ).divide(10000)

    @staticmethod
    def _mascara_landsat(image, red_band: str, green_band: str, blue_band: str, nir_band: str):
        qa = image.select("QA_PIXEL")
        mask = qa.bitwiseAnd(1 << 1).eq(0).And(qa.bitwiseAnd(1 << 2).eq(0)) \
            .And(qa.bitwiseAnd(1 << 3).eq(0)).And(qa.bitwiseAnd(1 << 4).eq(0)) \
            .And(qa.bitwiseAnd(1 << 5).eq(0))
        return image.updateMask(mask).select(
            [red_band, green_band, blue_band, nir_band], ["red", "green", "blue", "nir"]
        ).multiply(0.0000275).add(-0.2)

    def _coleccion_sentinel(self, inicio: str, fin: str):
        return ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(self.geometry) \
            .filterDate(inicio, fin).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)) \
            .map(self._mascara_sentinel)

    def _coleccion_landsat(self, anio: int, inicio: str, fin: str):
        if anio < 2013:
            coleccion = ee.ImageCollection("LANDSAT/LE07/C02/T1_L2")
            bandas = ("B3", "B2", "B1", "B4")
            fuente = "Landsat 7"
        else:
            coleccion = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").merge(
                ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
            )
            bandas = ("B4", "B3", "B2", "B5")
            fuente = "Landsat 8"
        return coleccion.filterBounds(self.geometry).filterDate(inicio, fin) \
            .filter(ee.Filter.lt("CLOUD_COVER", 20)).map(
                lambda image: self._mascara_landsat(image, *bandas)
            ), fuente

    def _rango_anual(self, anio: int) -> tuple[str, str]:
        inicio = f"{anio:04d}-{self.mes_inicio:02d}-01"
        fin_anio = anio + (1 if self.mes_fin == 12 else 0)
        fin_mes = 1 if self.mes_fin == 12 else self.mes_fin + 1
        return inicio, f"{fin_anio:04d}-{fin_mes:02d}-01"

    @staticmethod
    def _bounds(geometry: Dict[str, Any]) -> list[float]:
        def pares(value: Any) -> Iterable[tuple[float, float]]:
            if isinstance(value, (list, tuple)) and len(value) >= 2 and all(
                isinstance(item, (int, float)) for item in value[:2]
            ):
                yield float(value[0]), float(value[1])
            elif isinstance(value, (list, tuple)):
                for item in value:
                    yield from pares(item)
        puntos = list(pares(geometry["coordinates"]))
        if not puntos:
            raise ValueError("geometry debe contener coordenadas válidas")
        return [min(p[0] for p in puntos), min(p[1] for p in puntos),
                max(p[0] for p in puntos), max(p[1] for p in puntos)]

    def _imagen_anual(self, anio: int) -> Dict[str, Any]:
        try:
            inicio, fin = self._rango_anual(anio)
            fuente = "Sentinel-2"
            coleccion = self._coleccion_sentinel(inicio, fin) if anio >= 2017 else None
            
            if coleccion is None or coleccion.size().getInfo() == 0:
                coleccion, fuente = self._coleccion_landsat(anio, inicio, fin)
            if coleccion.size().getInfo() == 0:
                return {"anio": anio, "disponible": False,
                        "motivo": "Sin escena con nubosidad menor al 20%"}

            propiedad_nubes = "CLOUDY_PIXEL_PERCENTAGE" if fuente == "Sentinel-2" else "CLOUD_COVER"
            escena = coleccion.sort(propiedad_nubes).first()
            propiedades = escena.toDictionary(["system:time_start", propiedad_nubes]).getInfo()
            compuesto = coleccion.median().clip(self.geometry)
            rgb = compuesto.visualize(bands=["red", "green", "blue"], min=0.02, max=0.35, gamma=1.1)
            mapa = rgb.getMapId()
            fecha_ms = propiedades.get("system:time_start")
            fecha = datetime.utcfromtimestamp(fecha_ms / 1000).strftime("%Y-%m-%d") if fecha_ms else None
            ndvi = compuesto.normalizedDifference(["nir", "red"]).rename("NDVI")
            promedio = ndvi.reduceRegion(ee.Reducer.mean(), self.geometry,
                                         scale=10 if fuente == "Sentinel-2" else 30,
                                         maxPixels=1e9).getInfo().get("NDVI")
            return {
                "anio": anio, "fuente": fuente, "fecha_escena": fecha,
                "nubosidad_porcentaje": propiedades.get(propiedad_nubes),
                "thumbnail_url": rgb.getThumbURL({"region": self.geometry, "dimensions": 512, "format": "png"}),
                "tile_url_template": mapa["tile_fetcher"].url_format,
                "bounds": self._bounds(self.geometry_geojson),
                "ndvi_promedio": round(float(promedio), 4) if promedio is not None else None,
            }
        except Exception as e:
            return {"anio": anio, "disponible": False, "motivo": f"Error procesando año: {str(e)}"}

    def generar(self, anios: list[int]) -> Dict[str, Any]:
        # 🚀 Procesamiento concurrente de los años en paralelo
        with ThreadPoolExecutor(max_workers=5) as executor:
            imagenes = list(executor.map(self._imagen_anual, anios))
            
        return {
            "status": "success", 
            "mensaje": "Serie histórica generada en paralelo",
            "geometry": self.geometry_geojson,
            "imagenes": imagenes
        }
