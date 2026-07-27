# Ecosystem Graph Visualizer — Tasks

## Fase 1: Backend — API para Vista Macro

- [ ] Task 1: Crear `src/engine/ecosystem_visualizer.py` — estructura base
  - Handler `route_ecosystem_index`: sirve el HTML.
  - Handler `route_eco_ecosystems`: lista ecosistemas.
  - Logging consistente con el resto del proyecto.

- [ ] Task 2: Implementar `GET /api/eco/graph/{ecosystem_id}` — Grafo Macro
  - Funcion `_build_macro_graph(ecosystem_id)`.
  - Generar nodos tipo `app` con metadata (team, story_count, coupling_type, health).
  - Generar compound nodes `cluster` agrupando apps cohesivas.
  - Funcion `_calculate_coupling_edges()`: calcula fuerza de acoplamiento (contratos + entidades compartidas) entre cada par de apps.
  - Generar edges con `coupling_strength`, `sync_type`, label.

- [ ] Task 3: Implementar `_calculate_health(app_id, conflicts, shared_entities)`
  - Ejecuta `detect_cross_app_conflicts()`.
  - Retorna semaforo por app (green/yellow/red).

- [ ] Task 4: Implementar `GET /api/eco/app/{ecosystem_id}/{app_id}` — Detalle App
  - Retorna: entidades, flujos, contratos expuestos/consumidos, dependencias, story_count.

## Fase 2: Backend — API para Vista Micro

- [ ] Task 5: Implementar `GET /api/eco/flows/{ecosystem_id}/{app_a}/{app_b}` — Flujos Micro
  - Funcion `_build_flows_between_apps(ecosystem, app_a, app_b)`.
  - Cruzar contratos (provider/consumer) entre las dos apps.
  - Para cada contrato: identificar entidades en transito y su consistencia.
  - Vincular con HUs de cada app que mencionan esas entidades (origen/destino del flujo).
  - Retornar lista de flujos con direction, origin story, target story, contract, entities_in_transit.

- [ ] Task 6: Implementar `GET /api/eco/health/{ecosystem_id}` — Salud Global
  - Retorna indicadores de salud para todas las apps del ecosistema.

## Fase 3: Frontend — Vista Macro (Cytoscape.js)

- [ ] Task 7: Crear `src/engine/ecosystem_visualizer_ui.html` — estructura HTML base
  - Layout: nav selector de vista, toolbar (ecosistema dropdown, toggle macro/micro, filtros), canvas, panel, leyenda.
  - Importar Cytoscape.js + cose-bilkent via CDN.
  - CSS embebido: mismo lenguaje visual que `visualizer_ui.html` (glass panels, fondo negro, ambient mesh).

- [ ] Task 8: Implementar renderizado del grafo macro
  - Inicializar Cytoscape con compound nodes (clusters cohesivos).
  - Estilos: apps como rectangulos, border-color por health, edges con grosor proporcional.
  - Layout cose-bilkent configurado para compound nodes.
  - Fetch a `/api/eco/graph/{id}` al cargar.

- [ ] Task 9: Implementar tooltips y panel de detalle (macro)
  - Hover en app: tooltip con resumen (nombre, team, HUs, health).
  - Hover en edge: tooltip con coupling summary.
  - Click en app: panel lateral con detalle (fetch a `/api/eco/app/`).
  - Click en edge: transicion a vista micro.

- [ ] Task 10: Implementar filtros (macro)
  - Checkboxes: tipo de integracion (REST, GraphQL, async, shared_lib).
  - Toggle "Solo apps con conflictos" (aplica .faded a apps green).
  - Los filtros ocultan/muestran edges sin recargar.

## Fase 4: Frontend — Vista Micro (Diagrama de Flujos HTML)

- [ ] Task 11: Implementar vista micro — diagrama de secuencia
  - Layout HTML/CSS: dos columnas (App A, App B) con lifeline vertical.
  - Flujos como cards horizontales entre las columnas.
  - Cada card muestra: nombre flujo, direccion (flecha), HU origen/destino, entidades en transito, contrato.
  - Entidades divergentes con estilo de alerta (pill roja + pulse).

- [ ] Task 12: Implementar transicion macro ↔ micro
  - Click en edge del macro → fade out macro, fetch flujos, render micro, fade in.
  - Boton "← Volver a Macro" → reverse transition.
  - Toggle en toolbar sincronizado con el estado de la vista.

- [ ] Task 13: Implementar interaccion en micro — panel de detalle y navegacion
  - Click en flow card: panel lateral con detalle completo del flujo.
  - Click en HU o "Ver en [app]": switch workspace + navegar a `/` con highlight.
  - Entidades con divergencia: al click, panel muestra comparacion de campos entre apps.

## Fase 5: Frontend — Leyenda y Acabado Visual

- [ ] Task 14: Implementar leyenda
  - Vista macro: grosor = acoplamiento, estilos de linea = sync/async/mixed, colores de health.
  - Vista micro: flechas = direccion, pills = entidades, alertas = divergencias.
  - Siempre visible en footer.

- [ ] Task 15: Implementar selector de ecosistema
  - Dropdown que lista ecosistemas via `/api/eco/ecosystems`.
  - Al cambiar, recarga el grafo macro.
  - Si solo hay uno, mostrarlo como label.

## Fase 6: Integracion

- [ ] Task 16: Registrar rutas en `visualizer.py`
  - Importar handlers desde `ecosystem_visualizer.py`.
  - Agregar rutas: `/ecosystem`, `/api/eco/ecosystems`, `/api/eco/graph/{id}`, `/api/eco/flows/{id}/{a}/{b}`, `/api/eco/app/{id}/{app}`, `/api/eco/health/{id}`.

- [ ] Task 17: Agregar nav tab en `visualizer_ui.html`
  - Agregar `<nav class="view-selector">` con tab "Ecosistema" enlazando a `/ecosystem`.
  - Cambio minimo: solo el nav, sin tocar logica del grafo existente.

## Fase 7: Validacion

- [ ] Task 18: Verificar coexistencia de ambas vistas
  - `/` muestra Red Neuronal sin regresiones.
  - `/ecosystem` muestra vista macro del ecosistema.
  - Navegacion entre vistas funciona correctamente.

- [ ] Task 19: Test manual — ecosistema con 3+ apps y flujos cruzados
  - Macro: apps visibles, clusters cohesivos agrupados, grosor de edges correcto.
  - Click en edge → micro: flujos visibles con HUs, entidades, contratos.
  - Entidad divergente muestra alerta en micro.
  - "Ver en app" navega correctamente al workspace.
  - Filtros funcionan.

- [ ] Task 20: Actualizar changelog
