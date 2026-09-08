from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr

class SolicitudSatelital(BaseModel):
    estado: str = Field(..., description="Estado, ej. Michoacán")
    municipio: str = Field(..., description="Municipio, ej. Uruapan")
    fecha_inicio: str = Field(..., description="Fecha inicial formato YYYY-MM-DD")
    fecha_fin: str = Field(..., description="Fecha final formato YYYY-MM-DD")

class SolicitudSuelo(BaseModel):
    estado: str = Field(default="Michoacán", description="Nombre del estado (ej. Michoacán, Jalisco)")
    tipo_consulta: str = Field(default="municipio", description="municipio o entidad")
    ciclo: str = Field(default="Ciclicos - Perennes")
    modalidad: str = Field(default="Riego + Temporal")
    cultivo: str = Field(default="Resumen cultivos")

class SolicitudClima(BaseModel):
    estado: str = Field(default="Michoacán de Ocampo")
    municipio: Optional[str] = Field(default=None)
    latitud: Optional[float] = Field(default=None)
    longitud: Optional[float] = Field(default=None)
    fecha_inicio: str = Field(default="2024-01-01")
    fecha_fin: str = Field(default="2024-12-31")
    temp_base_gdd: float = Field(default=10.0)

class SolicitudSanidad(BaseModel):
    estado: str = Field(default="Michoacán de Ocampo")
    municipio: Optional[str] = Field(default=None)
    cultivo: Optional[str] = Field(default=None)

class SolicitudPredio(BaseModel):
    nombre_huerto: str = Field(..., description="Nombre del predio o huerto")
    productor: str = Field(..., description="Nombre del productor o propietario")
    cultivo: str = Field(..., description="Ej. Aguacate, Zarzamora, Fresa, Arándano")
    municipio: str = Field(..., description="Municipio de Michoacán")
    geojson: Dict[str, Any] = Field(..., description="Objeto GeoJSON del terreno (Polygon o Feature)")
    fecha_inicio_auditoria: Optional[str] = Field("2018-01-01", description="Fecha histórica para comparar")
    fecha_fin_auditoria: Optional[str] = Field("2026-01-01", description="Fecha actual de análisis")


class SolicitudImagenesHistoricas(BaseModel):
    geometry: Dict[str, Any] = Field(..., description="Geometría GeoJSON del polígono")
    anios: list[int] = Field(..., min_length=1, max_length=20, description="Años a consultar")
    cultivo: str = Field(..., description="Cultivo del predio")
    visualizacion: str = Field(default="rgb", description="Tipo de visualización")
    mes_inicio: int = Field(default=1, ge=1, le=12)
    mes_fin: int = Field(default=4, ge=1, le=12)

class EmailSchema(BaseModel):
    email: EmailStr
    name: str
    subject: str
    html_content: str
