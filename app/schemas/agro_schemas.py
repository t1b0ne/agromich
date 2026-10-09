from datetime import date
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

MAX_GEOJSON_POSITIONS = 5_000


def validar_geojson(value: Dict[str, Any], solo_poligono: bool = False) -> Dict[str, Any]:
    geometry = value.get("geometry") if value.get("type") == "Feature" else value
    allowed = {"Polygon"} if solo_poligono else {"Polygon", "MultiPolygon"}
    if not isinstance(geometry, dict) or geometry.get("type") not in allowed:
        raise ValueError("Se requiere un GeoJSON Polygon" + ("" if solo_poligono else " o MultiPolygon"))
    positions: list[tuple[float, float]] = []

    def visit(node: Any) -> None:
        if isinstance(node, (list, tuple)) and len(node) >= 2 and all(isinstance(x, (int, float)) for x in node[:2]):
            positions.append((float(node[0]), float(node[1])))
        elif isinstance(node, (list, tuple)):
            for child in node:
                visit(child)

    visit(geometry.get("coordinates"))
    if not 4 <= len(positions) <= MAX_GEOJSON_POSITIONS:
        raise ValueError(f"La geometria debe contener entre 4 y {MAX_GEOJSON_POSITIONS} posiciones")
    if any(not (-180 <= lon <= 180 and -90 <= lat <= 90) for lon, lat in positions):
        raise ValueError("La geometria contiene coordenadas fuera de rango WGS84")
    return value


class SolicitudSatelital(BaseModel):
    geometry: Dict[str, Any] = Field(..., description="GeoJSON Polygon, MultiPolygon o Feature")
    cultivo: str = Field(default="aguacate", min_length=2, max_length=80)
    fecha_inicio: date
    fecha_fin: date

    @model_validator(mode="after")
    def validar_rango_y_geometria(self):
        validar_geojson(self.geometry)
        if self.fecha_inicio > self.fecha_fin:
            raise ValueError("fecha_inicio debe ser menor o igual a fecha_fin")
        return self


class SolicitudSuelo(BaseModel):
    estado: str = Field(default="Michoacan", min_length=2, max_length=100)
    tipo_consulta: str = Field(default="municipio", pattern="^(municipio|entidad)$")
    ciclo: str = Field(default="Ciclicos - Perennes", max_length=100)
    modalidad: str = Field(default="Riego + Temporal", max_length=100)
    cultivo: str = Field(default="Resumen cultivos", max_length=100)


class SolicitudClima(BaseModel):
    estado: str = Field(default="Michoacan de Ocampo", max_length=100)
    municipio: Optional[str] = Field(default=None, max_length=100)
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    fecha_inicio: date = date(2024, 1, 1)
    fecha_fin: date = date(2024, 12, 31)
    temp_base_gdd: float = Field(default=10.0, ge=-20, le=50)

    @model_validator(mode="after")
    def validar_rango(self):
        if self.fecha_inicio > self.fecha_fin:
            raise ValueError("fecha_inicio debe ser menor o igual a fecha_fin")
        if (self.latitud is None) != (self.longitud is None) and not self.municipio:
            raise ValueError("latitud y longitud deben enviarse juntas")
        if self.latitud is not None and not (-90 <= self.latitud <= 90 and -180 <= self.longitud <= 180):
            raise ValueError("coordenadas fuera de rango")
        return self


class SolicitudSanidad(BaseModel):
    estado: str = Field(default="Michoacan de Ocampo", max_length=100)
    municipio: Optional[str] = Field(default=None, max_length=100)
    cultivo: Optional[str] = Field(default=None, max_length=100)


class SolicitudPredio(BaseModel):
    nombre_huerto: str = Field(..., min_length=2, max_length=120)
    productor: str = Field(..., min_length=2, max_length=120)
    cultivo: str = Field(..., min_length=2, max_length=80)
    municipio: str = Field(..., min_length=2, max_length=100)
    geojson: Dict[str, Any]
    fecha_inicio_auditoria: date = date(2018, 1, 1)
    fecha_fin_auditoria: date = date(2026, 1, 1)

    @field_validator("geojson")
    @classmethod
    def validar_geometria(cls, value):
        return validar_geojson(value)


class SolicitudImagenesHistoricas(BaseModel):
    geometry: Dict[str, Any]
    anios: list[int] = Field(..., min_length=1, max_length=20)
    cultivo: str = Field(..., min_length=2, max_length=80)
    visualizacion: str = Field(default="rgb", max_length=30)
    mes_inicio: int = Field(default=1, ge=1, le=12)
    mes_fin: int = Field(default=4, ge=1, le=12)

    @field_validator("geometry")
    @classmethod
    def validar_geometria(cls, value):
        return validar_geojson(value, solo_poligono=True)

    @model_validator(mode="after")
    def validar_meses_y_anios(self):
        if self.mes_inicio > self.mes_fin:
            raise ValueError("mes_inicio debe ser menor o igual a mes_fin")
        current_year = date.today().year
        if any(year < 1984 or year > current_year for year in self.anios):
            raise ValueError(f"Los anios deben estar entre 1984 y {current_year}")
        return self

