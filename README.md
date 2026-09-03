# 🌱 AgroMich v2.0 - Inteligencia Territorial, Agronómica y Edáfica

Sistema modular de alta precisión diseñado para la gestión, análisis de datos climáticos, edáficos, satelitales y de sanidad agrícola en el estado de Michoacán. Operado de forma autónoma por los agentes **Hermes & Eve**.

---

## 📂 Arquitectura del Proyecto

El proyecto ha sido refactorizado hacia una arquitectura modular, moderna y orientada a microservicios con FastAPI y una interfaz de terminal interactiva (TUI):

```text
Datos/
│
├── app/                      # Núcleo modular de la API
│   ├── routers/              # Endpoints divididos por dominios (clima, suelo, satelite, sanidad)
│   ├── schemas/              # Modelos de datos estandarizados con Pydantic
│   ├── services/             # Lógica de negocio, scrapers y conectores de GEE
│   ├── __init__.py
│   └── main.py               # Punto de entrada principal de FastAPI
│
├── reports/                  # Almacenamiento centralizado de respaldos JSON y CSV
├── venv/                     # Entorno virtual de Python
├── menu_app.py               # Consola TUI interactiva con Rich y panel de logs dinámicos
├── main_api.py               # (Legado / Respaldo de arranque alternativo)
└── requirements.txt          # Dependencias del proyecto