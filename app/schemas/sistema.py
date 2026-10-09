from typing import Literal

from pydantic import BaseModel


class EstadoServicio(BaseModel):
    nombre: str
    disponible: bool
    detalle: str | None = None


class EstadoSistema(BaseModel):
    estado: Literal["ok", "degradado"]
    version: str
    servicios: list[EstadoServicio]
