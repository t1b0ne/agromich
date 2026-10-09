# Pruebas

- `unit/`: reglas de negocio e integraciones simuladas.
- `integration/`: rutas FastAPI y servicios externos en entornos controlados.

Las tareas pesadas de Earth Engine y Selenium deben probarse con mocks, no con
llamadas reales durante cada ejecucion de CI.
