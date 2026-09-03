from typing import Optional
from pydantic import BaseModel, Field

class SolicitudSatelital(BaseModel):
    estado: str = Field(default="Michoacán de Ocampo")
    municipio: Optional[str] = Field(default=None)
    fecha_inicio: str = Field(default="2025-01-01")
    fecha_fin: str = Field(default="2025-12-31")

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