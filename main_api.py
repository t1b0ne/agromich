"""Punto de entrada compatible.

La aplicacion canonica vive en ``app.main``. Este modulo se conserva para no
romper comandos de despliegue existentes que usaban ``main_api:app``.
"""
from app.main import app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
