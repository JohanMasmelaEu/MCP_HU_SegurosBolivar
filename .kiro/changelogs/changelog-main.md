# Changelog — main

## [No publicado]

### Agregado
- Se agregó soporte multi-workspace: N proyectos pueden coexistir en el servidor sin bloquearse mutuamente
- Se agregó soporte multi-ecosistema: N ecosistemas independientes con selección activa
- Se creó `WorkspaceManager` (`src/engine/workspace_manager.py`) para gestionar workspaces con create/list/switch/reset
- Se creó `EcosystemManager` (`src/engine/ecosystem_manager.py`) para gestionar ecosistemas con create/list/switch/reset
- Se creó `src/tools/workspace_tools.py` con handlers para los nuevos tools de gestión
- Se registraron 6 nuevos tools MCP: `list_workspaces`, `switch_workspace`, `reset_workspace`, `list_ecosystems`, `switch_ecosystem`, `reset_ecosystem`
- Se agregó persistencia de estado activo en `state.json` (sobrevive reinicios del contenedor)
- Se agregó modelo `ServerState` y `WorkspaceInfo` en `src/models/project.py`
- Se agregó migración automática de formato legacy (`.hu-memory/` y `.hu-ecosystem/` en raíz) al nuevo formato multi-workspace/ecosistema
- Se agregó selector de workspace y ecosistema en la UI del visualizador (puerto 9751)
- Se agregaron 4 endpoints HTTP al visualizador: `GET /api/workspaces`, `POST /api/workspaces/switch`, `GET /api/ecosystems`, `POST /api/ecosystems/switch`
- El grafo se recarga automáticamente al cambiar de workspace desde la UI
- Se documentó en README la configuración `--pull always` de Docker y el troubleshooting de versiones cacheadas

### Corregido
- Se corrigió bug en `MemoryEngine` donde `get_all_stories()`, `get_all_summaries()`, `save_story()` y `get_next_story_id()` usaban glob `HU-*.json` que ignoraba stories con IDs no prefijados con "HU-" (ej: `IMPL-001`, `GD905-336`). Ahora usa `*.json` para reconocer cualquier formato de ID
- Se corrigió panel lateral de detalle de HU en el visualizador que no se desplegaba al hacer click en un nodo story (causado por nodos implícitos sin atributo `type` creados por Cytoscape para edges huérfanos)
- Se corrigió que las conexiones entre HUs quedaban visibles sin nodos asociados en el grafo — ahora `_get_graph_data()` filtra edges cuyos endpoints no existen como nodos válidos, y el frontend también valida que ambos endpoints existan como nodos visibles
- Se corrigió selector de ecosistema en la UI del visualizador que no producía ningún efecto visible — ahora ejecuta `reloadGraph()` al cambiar de ecosistema

### Agregado (Visualizador)
- Se agregó botón "Relaciones" en la toolbar de capas para toggle de edges `depends_on`/`impacts` entre HUs — permite limpiar la vista ocultando las conexiones inter-HU
- Se agregó visualización de criterios de aceptación (Given/When/Then) en el panel lateral de detalle de HU
- Se rediseñó el panel lateral de detalle con mejor jerarquía visual: header con logo y botón cerrar, secciones separadas con bordes sutiles, narrativa en bloque estilizado, pills de estadísticas, y criterios de aceptación con labels coloreados

### Cambiado
- `MemoryEngine` ahora acepta `base_path` configurable en su constructor (antes hardcodeaba `/workspace/.hu-memory/`)
- `EcosystemEngine` ahora acepta `base_path` configurable en su constructor
- `get_memory()` y `get_ecosystem()` ahora delegan al manager activo cuando está disponible
- `handle_init_project` ya no bloquea si existe un proyecto — crea un nuevo workspace aislado
- `handle_init_ecosystem` ya no bloquea si existe un ecosistema — crea uno nuevo o sugiere `switch_ecosystem`/`reset_ecosystem`
- `server.py` version bumped a 2.0.0, inicializa managers al arranque
- Estructura en disco cambia de flat (`/workspace/.hu-memory/`) a multi (`/workspace/workspaces/<id>/.hu-memory/`)

### Eliminado
- Se eliminó el patrón singleton rígido que impedía tener más de un proyecto/ecosistema

### Agregado (Ecosystem Graph Visualizer)
- Se creó `src/engine/ecosystem_visualizer.py` con lógica backend para la vista de ecosistema: grafo macro (topología de acoplamiento), flujos micro (punto A → punto B), detalle de apps, e indicadores de salud
- Se creó `src/engine/ecosystem_visualizer_ui.html` con UI completa: vista macro (Cytoscape.js con compound nodes para clusters cohesivos, grosor de edges proporcional a fuerza de acoplamiento), vista micro (diagrama de flujos tipo secuencia en HTML/CSS), panel lateral de detalle, leyenda, filtros por tipo de integración
- Se agregaron 6 nuevas rutas HTTP al visualizador existente (puerto 9751): `GET /ecosystem`, `GET /api/eco/ecosystems`, `GET /api/eco/graph/{id}`, `GET /api/eco/flows/{id}/{app_a}/{app_b}`, `GET /api/eco/app/{id}/{app_id}`, `GET /api/eco/health/{id}`
- Se agregó selector de vista (tabs) en la UI existente: "Red Neuronal" ↔ "Ecosistema" para navegar entre las dos vistas desde el mismo puerto
- La vista macro muestra: apps como nodos con badge de salud (verde/amarillo/rojo), clusters cohesivos agrupados, fuerza de acoplamiento como grosor de línea, tipo de integración diferenciado (síncrona/asíncrona/mixta)
- La vista micro muestra: flujos concretos entre dos apps con HUs origen/destino, entidades en tránsito con indicador de divergencia, contratos que habilitan cada flujo
- Se agregó spec completa en `.kiro/specs/ecosystem-graph-visualizer/` (requirements, design, tasks)

### Corregido
- Se corrigió bug en `register_app` donde los contratos no poblaban `consumer_apps` porque el input usaba alias (`consumers`, `consumer_app`) que Pydantic ignoraba silenciosamente. Ahora se normalizan los alias `consumers` → `consumer_apps`, `consumer_app` → `consumer_apps`, y `entities` → `entities_involved` antes de construir el modelo
- Se corrigió que `add_contract` en `EcosystemEngine` no actualizaba las listas `exposes_contracts`/`consumes_contracts` de las apps involucradas. Ahora se auto-sincronizan al registrar un contrato

- Se corrigió bug intermitente en el toggle de capas (Flujos, Entidades, Relaciones) del visualizador de Red Neuronal: al activar/desactivar una capa, se destruía y recreaba todo el grafo Cytoscape.js, causando race conditions que impedían hacer click en HUs para ver su detalle. Ahora se usa `show()`/`hide()` sobre los elementos sin destruir la instancia
- Se corrigió memory leak: los intervalos del neural pulse (animación de edges) no se limpiaban al reconstruir el grafo, causando múltiples intervalos acumulados contra instancias destruidas

### Corregido (Ecosystem Visualizer — 2026-07-27)
- Se corrigió bug donde registrar un contrato con `role: "consumer"` creaba un contrato separado en vez de agregar la app al array `consumer_apps[]` del contrato provider existente. Ahora `handle_register_app` detecta `role="consumer"`, busca el contrato provider por `contract_id` o `provider_app`, y agrega la app como consumidor
- Se corrigió que `add_contract` en `EcosystemEngine` sobreescribía `consumer_apps` al actualizar un contrato existente. Ahora hace merge preservando consumidores previos
- Se corrigió tooltip de "Acoplamiento" que persistía visible sin hover en las vistas Micro/Macro y no desaparecía al cambiar de tab (Diagrama de Secuencia ↔ Diagrama de Proceso). Se agregó tracking de timer con `_clearTooltipTimer()` y llamadas a `hideTooltip()` en `switchDiagramType`, `backToMacro`, y `switchToMicro`
- Se corrigió leyenda que tapaba contenido del diagrama en pantallas de resolución normal. Ahora es colapsable con toggle show/hide via click en el header

### Agregado (Ecosystem Visualizer — 2026-07-27)
- Se agregaron flechas de REQUEST (consumer → provider) con método/path del `spec_reference` y flechas de RESPONSE (provider → consumer) con entidades retornadas en el Diagrama de Secuencia. Antes solo se mostraba una línea punteada con la palabra "response"
- Se agregó patrón de flujo conectado en el Diagrama de Proceso: para contratos síncronos muestra Request → Contract → Process → Response con flechas conectoras; para asíncronos muestra Publish → Contract → Consume. Se eliminaron los boxes sueltos sin conexión visual
- Se agregó modelo `EntityDefinition` (name + category) en `src/models/ecosystem.py` y campo `entities_grouped` en `ContractDefinition` para soportar agrupación jerárquica de entidades por categoría (request, pertinencia, calidad, etc.)
- Se agregaron funciones `renderEntitiesGrouped()` y `renderEntitiesByCategory()` en el frontend para renderizar entidades agrupadas por categoría en el panel de detalle y en los diagramas
- Se agregó función `_serialize_entities_grouped()` en el backend para exponer entidades agrupadas en las APIs de detalle de app
- Se agregó dirección de dependencia en la vista Macro: edges ahora muestran `direction_type` (directional=flecha unidireccional consumer→provider, bidirectional=flechas dobles, cohesive=línea sin flecha para BD compartida, implicit=línea punteada sin flecha). Source/target de edges se calculan según contratos consumer→provider
- Se actualizaron estilos Cytoscape.js con selectores por `direction_type` para diferenciación visual de la dirección de dependencia
- Se actualizó el tooltip de edges para mostrar información de dirección (Unidireccional, Bidireccional, Cohesivo, Implícito)
- Se actualizaron labels de edges en vista Macro para mostrar nombres de contratos en vez de conteos genéricos

### Cambiado (Ecosystem Visualizer — 2026-07-27)
- `_calculate_coupling_edges` ahora calcula `direction_type` y asigna source/target según la relación consumer→provider en vez de usar orden alfabético de app_ids
- El campo `entities` en contratos ahora acepta tanto strings planos como objetos `{name, category}` para backward compatibility
- Se rediseñó la leyenda del ecosistema para que sea menos intrusiva: inicia colapsada por defecto, tamaño reducido, opacidad 50% que sube a 100% solo al hover. Funciona como ayuda contextual sin robar protagonismo al diagrama
- Se rediseñó completamente el Diagrama de Proceso con estilo pipeline vertical: cada flujo muestra los pasos internos (Request → Pipeline interno → Response) con actores (consumer/provider) en cada paso, stages internos agrupados por categoría de entidades, y conectores verticales con flechas entre pasos. Los pipelines multi-stage como OCR ahora muestran cada etapa interna (pertinencia, calidad, extracción, etc.) como sub-pasos numerados y conectados
- Se mejoró la claridad visual de las relaciones de flujo en el Diagrama de Proceso: se agregó un rail vertical izquierdo que conecta todos los pasos con gradiente de color (azul→púrpura→verde), indicadores circulares en cada paso sobre el rail, labels de dirección en los conectores ("invoca", "publica", "retorna"), flechas con símbolo ▼ entre pasos, y hover state en cada step para interactividad. Los stages internos del pipeline ahora usan ▼ como conector visual entre etapas

### Corregido (Ecosystem Visualizer — Layout 2026-07-27)
- Se corrigió desbordamiento horizontal de entity pills en los diagramas de Secuencia y Proceso: se agregó `max-width`, `overflow: hidden`, y `text-overflow: ellipsis` a `.entity-pill`
- Se corrigió que los contenedores de entidades (`.seq-arrow-entities`, `.proc-pipeline-data`, `.proc-pipeline-stage-entities`) no contenían el overflow — ahora tienen `max-width: 100%` y `overflow: hidden` con `flex-wrap: wrap`
- Se corrigió la barra de participantes (`.seq-participants-bar`) que no tenía contención visual ni margen inferior: se agregó border-radius, borde sutil, backdrop-filter, y margin-bottom
- Se corrigió que las cajas de participantes (`.seq-p-box`) podían crecer sin límite: se agregó `max-width: 280px` y `flex-shrink: 0`
- Se corrigió que el área de mensajes del diagrama de secuencia (`.seq-msgs`) no restringía el overflow de su contenido: se agregó `min-width: 0` y `overflow: hidden`
- Se corrigió la falta de separación vertical entre bloques del diagrama de proceso: se cambió `gap: 0` a `gap: 24px` en `.proc-diagram`
- Se corrigió la poca visibilidad de los conectores entre pasos del pipeline: se aumentó el tamaño de los dots del rail (de 10px a 12px), se intensificaron los colores del gradiente del rail vertical, y se aumentó el tamaño de las flechas ▼ (de 8px a 10px)
- Se corrigió el espaciado interno de los pasos del pipeline (`.proc-pipeline-step`): se incrementó padding de 14px a 16px y se agregó `min-width: 0` para contener overflow
- Se corrigió la poca separación entre interacciones del diagrama de secuencia: se aumentó padding de `.seq-int` de 12px a 16px
- Se corrigió el texto de las flechas (`.seq-arrow-text`) que se desbordaba en endpoints largos: se agregó `text-overflow: ellipsis` y `white-space: nowrap`
