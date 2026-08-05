# Changelog — main

## [No publicado]

### Agregado
- Se agregó cache con invalidación por evento para grafos del ecosistema en `ecosystem_visualizer.py` (TTL 300s + invalidación explícita)
- Se agregó endpoint lightweight `/api/eco/status/{ecosystem_id}` para polling sin cómputo pesado
- Se agregó paginación con query params `limit` y `offset` en endpoints de grafo macro y constelación
- Se agregó `docker-compose.yml` con resource limits (CPU 1.0, RAM 512M) y restart policy
- Se agregó healthcheck al Dockerfile (`/api/eco/ecosystems` cada 30s)
- Se agregó descarga de Cytoscape.js y dependencias como archivos estáticos locales en el build de Docker
- Se agregó montaje de `/static` con `StaticFiles` de Starlette para servir vendor scripts
- Se agregó indicador de carga (spinner overlay) durante el cálculo de layout en Cytoscape
- Se agregó protección para grafos grandes con colapso de nodos poco conectados (máx 80 visibles)
- Se agregó lazy loading de la vista Constelación (solo carga cuando el tab se activa)

### Cambiado
- Se movió cómputo pesado de rutas API a `run_in_executor` con ThreadPoolExecutor(2) para no bloquear el event loop
- Se optimizó configuración de layout Cytoscape: `quality` de 'proof' a 'default', `animate` a 'end', `animationDuration` de 800 a 400ms
- Se reemplazaron CDN externos (unpkg.com, Google Fonts) por archivos locales bundleados en Docker
- Se modificó `switchEcosystem` para solo recargar la vista activa y resetear flag de constelación

### Seguridad
- Se agregó invalidación de cache desde `ecosystem_tools.py` al modificar datos (init, register_app, sync) para evitar respuestas stale
