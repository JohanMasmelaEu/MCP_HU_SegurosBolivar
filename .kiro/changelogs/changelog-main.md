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
- Se reemplazó el botón global "Editar" del top nav por botones de edición contextuales: uno junto a la descripción/resumen de cada capa y otro en el panel de detalle de cada elemento seleccionado
- Se hizo visible permanentemente el botón "+ Agregar" en los paneles master (antes solo aparecía en modo edición global)
- Se actualizó el texto placeholder de "Sin detalle expandido" para reflejar el nuevo flujo contextual
