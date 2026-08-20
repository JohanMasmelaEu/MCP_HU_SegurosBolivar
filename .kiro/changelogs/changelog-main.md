# Changelog — main

## [No publicado]

### Agregado
- Se creó endpoint `/story` con página de detalle completo de Historia de Usuario (HU) accesible desde el panel de HUs del Spec Visualizer
- Se creó `src/engine/story_detail_ui.html` con renderizado de narrativa, criterios de aceptación, entidades, flujos, complejidad, dependencias, impactos y panel de expertos
- Se agregó handler `route_story_index` en `src/engine/spec_visualizer.py`
- Se registró ruta `/story` en la app Starlette de `src/engine/visualizer.py`
- Se agregó botón de toggle de tema (claro/oscuro) en el visualizador de grafo principal (`visualizer_ui.html`)
- Se agregó botón de toggle de tema en el visualizador de ecosistemas (`ecosystem_visualizer_ui.html`)
- Se agregó soporte de clase `html.light` con localStorage en todas las vistas del MCP para toggle manual de tema

### Cambiado
- Se rediseñó el panel de "Elementos Asociados (HU)" en la vista de Spec para una presentación más sutil e integrada: sin borde rosa, colores neutros, tipografía más compacta
- Se rediseñó el modal de formalización (Refine overlay): más ancho (900px), layout de dos columnas cuando aparece la vista previa (input a la izquierda, resultado a la derecha), textareas expandibles y sin necesidad de scroll
- Se rediseñó el panel de detalle de elementos en modo edición: layout de dos columnas (izquierda: contenido actual como texto plano sin card, derecha: formulario de edición con título y detalle expandido), ocupa todo el ancho disponible sin necesidad de scroll

### Corregido
- Se corrigió error "not found" al acceder al detalle de una HU desde la vista de Spec (el endpoint `/story` no existía)

### Cambiado
- Se reemplazó el botón global "Editar" del top nav por botones de edición contextuales: uno en la esquina superior derecha de la descripción de cada capa y otro en la esquina superior derecha del panel de detalle de cada elemento seleccionado
- Se agregó botón "Cancelar" tanto en la edición de la descripción de la capa como en la edición del detalle de un elemento, para poder salir del modo edición sin guardar
- Se hizo visible permanentemente el botón "+ Agregar" en los paneles master (antes solo aparecía en modo edición global)
- Se actualizó el texto placeholder de "Sin detalle expandido" para reflejar el nuevo flujo contextual

### Agregado
- Se agregó campo `associations: dict[str, list[str]]` al modelo `LayerContent` en `src/models/sdd.py` para vincular HUs a items individuales (decisiones, restricciones, artefactos) de cada capa del SDD
- Se creó endpoint `POST/GET /api/spec/{spec_id}/associations` en `src/engine/spec_visualizer.py` para gestionar asociaciones HU↔item (acciones: add, remove)
- Se registró ruta `/api/spec/{spec_id}/associations` en `src/engine/visualizer.py`
- Se implementó drag-and-drop en el panel de HUs del Spec Visualizer: los items de HU son arrastrables (`draggable`) hacia la zona de drop en el detalle de cada elemento
- Se agregó zona de drop ("HUs Asociadas") en el panel de detalle de cada item (tanto en modo lectura como edición) que muestra chips con las HUs vinculadas y permite eliminar asociaciones
- Se exponen nodos `sdd_item` y aristas `implements` (HU→item) en el grafo del workspace (`_get_graph_data()` en `visualizer.py`) para que la red neuronal muestre qué HUs implementan qué items del SDD
- Se exponen nodos `story` y aristas `implements` (HU→spec) en el grafo de constelación (`build_constellation()` en `constellation.py`) para visualizar la relación HU↔Spec en la vista de constelación

### Cambiado
- Se modificó el panel de HUs en el Spec Visualizer: los items ahora son `<div>` arrastrables en lugar de `<a>` links, con un link externo independiente para abrir el detalle de la HU
- Se agregó hint visual en el header del panel de HUs indicando que se pueden arrastrar para asociar
