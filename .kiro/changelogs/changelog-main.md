# Changelog — main

## [No publicado]

### Agregado
- Se creó pantalla dedicada de visualización de SDD/Spec (`/spec`) con UI profesional e interactiva:
  - Navegación lateral por capas con barra de progreso de completitud por capa.
  - Cards colapsables con animación para decisiones/restricciones/artefactos.
  - Campo `details` expandido bajo cada item al hacer click.
  - Filtro por rol/perspectiva (dev_backend, qa, po, etc.) con hint contextual que explica qué ve cada stakeholder.
  - **Modo edición** (toggle en topbar): edición inline de summary, título y detalle de cada item, agregar y eliminar items.
  - **Panel de formalización**: al agregar un item, se abre un overlay donde el stakeholder escribe en lenguaje natural y el sistema genera una entrada tipificada (ID + título + detalle estructurado con justificación/impacto/origen). Vista previa editable antes de aceptar.
  - Botón "Formalizar" en cada item existente para re-tipificar entradas ya guardadas.
  - Operaciones PUT vía `/api/spec/{spec_id}/layer/{layer}` para persistir cambios desde la UI.
  - Endpoint POST `/api/spec/{spec_id}/refine` que toma input crudo y retorna la versión formalizada con ID auto-generado, título conciso y detalle con plantilla estructurada por tipo (decisión/restricción/artefacto).
  - **Panel de confirmación con análisis de impacto cross-layer**: ningún cambio se indexa automáticamente. Toda operación muestra primero una propuesta con diff visual (antes/después) + análisis de impacto que muestra qué otras capas del SDD se ven afectadas por el cambio (con nivel: alto/medio/bajo, razón, y sugerencia de acción). El usuario debe confirmar explícitamente con "Confirmar e indexar" o descartar.
  - Endpoint POST `/api/spec/{spec_id}/impact` que analiza el impacto cross-layer de un cambio usando la matriz `LAYER_IMPACT_MATRIX` (8 capas × relaciones tipificadas con nivel, razón y sugerencia contextual por tipo de cambio).
  - Metadata panel (aprobadores, fechas, app vinculada, conteos).
  - Diseño responsive con glass-morphism y dark theme consistente con el ecosistema.
- Se creó route handler `spec_visualizer.py` con endpoints: `/spec` (UI), `/api/specs` (listado), `/api/spec/{spec_id}?role=` (detalle), `PUT /api/spec/{spec_id}/layer/{layer}` (actualización), `POST /api/spec/{spec_id}/refine` (formalización de input).
- Se registraron las nuevas rutas en el servidor Starlette (`visualizer.py`).
- Se agregó campo `details: dict[str, str]` al modelo `LayerContent` (`src/models/sdd.py`) para almacenar contenido expandido por ID de decisión/constraint/artifact. Backward compatible: specs existentes sin este campo cargan con `{}` por default.
- Se agregó función `_render_spec_to_markdown` que genera markdown estructurado con detalle completo por capa.
- Se agregó función `_try_write_output` con manejo de errores (PermissionError, OSError) y verificación post-escritura.
- Se agregó función `_find_detail_for_item` con matching por ID exacto, prefijo ID regex, y match parcial.

### Corregido
- Se corrigió bug en `export_spec_markdown` donde `output_path` reportaba éxito sin escribir el archivo en disco. Ahora siempre retorna el campo `markdown` en la respuesta (independientemente de si `output_path` se proporciona o no), y maneja errores de escritura con `_try_write_output` que valida permisos y accesibilidad. Si el MCP corre en Docker y el path del host no es accesible, retorna warning explícito en lugar de fallo silencioso.

### Cambiado
- Se reemplazó el panel superficial de detalle de spec en la Constelación por redirección a la pantalla dedicada `/spec?spec_id=...`. Al hacer click en una spec del árbol radial, ahora abre la vista completa.
- Se mejoró la generación de markdown del SDD: el export ahora produce un documento profesional con headers `####` por sección (Decisiones, Restricciones, Artefactos), items en **bold**, y contenido expandido indentado debajo de cada item cuando existe detalle en el campo `details`.
- Se actualizó docstring de `update_spec_layer` y `export_spec_markdown` en `server.py` para documentar el campo `details` y el nuevo comportamiento de retorno.

### Cambiado
- Se rediseñó la UI del SDD Spec Viewer (`spec_visualizer_ui.html`):
  - Se implementó navegación por **tabs** (Decisiones / Restricciones / Artefactos) dentro de cada capa, reemplazando el listado secuencial. Cada tab muestra el conteo de items y cambia de color según el tipo.
  - Se corrigieron los **selects invisibles en dark mode**: fondo diferenciado (`--select-bg`), bordes más visibles (`--select-border`), flecha custom SVG, y focus state con box-shadow azul.
  - Se mejoró el **contraste general del sidebar**: section titles y layer-nav items ahora usan `--text-primary`/`--text-secondary` en lugar de `--text-tertiary`.
  - Se mejoró el diseño de **item-cards**: borde izquierdo de color por tipo (azul=decisiones, naranja=restricciones, púrpura=artefactos), preview del detalle visible sin expandir, y `data-type` para estilizado contextual.
  - Se agregó **tema claro funcional** con toggle en el topnav (botón luna/sol). Variables CSS completas para light mode, persistencia en `localStorage`, y estilos específicos para selects y scrollbars en light.

### Cambiado
- Se rediseñó la UI del detalle de Spec (`spec_visualizer_ui.html`) con nuevo layout master-detail:
  - **Panel de Elementos Asociados (HU)**: zona superior a nivel general del spec (no por capa) que muestra el listado de Historias de Usuario vinculadas. Cada HU es clickeable y abre su detalle en nueva pestaña (`target="_blank"`).
  - **Layout Master-Detail para contenido de tabs**: la zona de Decisiones/Restricciones/Artefactos ahora se divide en un listado a la izquierda (master) y un panel de detalle a la derecha (detail). Al seleccionar un elemento de la lista, su detalle se muestra en el panel derecho.
  - **Formulario de nuevo elemento en zona de detalle**: al presionar "+ Agregar", el panel derecho (detail) se convierte en el formulario para capturar título y detalle del nuevo item, manteniendo la consistencia visual.
  - Se eliminó el patrón de cards colapsables (accordion) reemplazándolo por el patrón click-to-select en master-detail.

### Agregado
- Se creó endpoint `GET /api/spec/{spec_id}/stories` que retorna la lista de HUs almacenadas en la memoria del workspace activo (id, título, status, narrativa, complexity_tags, gaps, questions).
- Se registró la nueva ruta en `visualizer.py` para servir las stories asociadas.
