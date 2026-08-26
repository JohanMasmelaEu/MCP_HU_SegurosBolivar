# Changelog — MCP_HU_SegurosBolivar

## [No publicado]

### Corregido
- Se corrigió navegación directa a Constelación desde el spec visualizer y HU visualizer — al navegar a `/ecosystem#constellation` ahora se activa la vista de constelación automáticamente al cargar la página
- Se eliminó botón "Volver" del detalle de HU (story_detail_ui) que no funcionaba al abrir en pestaña nueva
- Se corrigió el tema claro en el HU visualizer — los nodos y edges del grafo Cytoscape ahora adaptan sus colores de texto y outline al cambiar a light mode

### Cambiado
- Se amplió el área de contenido principal del spec visualizer eliminando `max-width:1200px` y aumentando el padding lateral para aprovechar el espacio disponible en pantalla

### Agregado
- Se agregó filtro de búsqueda por ID o nombre en la sección de Historias de Usuario del spec visualizer
- Se agregó paginación tipo tabla en la sección de HU mostrando 4 elementos por página con controles de navegación
- Se creó motor de planificación Gantt (`gantt_engine.py`): scheduler dependency-aware con ruta crítica (CPM), calendario laboral Colombia, estimación por complejidad, detección automática de fases y dominios
- Se creó visualización interactiva del plan de trabajo (`gantt_ui.html`) estilo NLVS con barras por fase, marcadores de festivos/deadlines, tooltips, tarjetas resumen y tabla comparativa
- Se agregó persistencia de configuración del Gantt en `.hu-memory/gantt-config.json` con fases editables (nombre, task_ids, deadline por fase), overrides de días por tarea, y milestones
- Se agregaron días editables inline en la tabla Gantt con auto-guardado debounce y botón "💾 Guardar" para persistir toda la configuración
- Se agregó validación del plan ("🔍 Validar") que detecta deadlines excedidos, HUs sin estimación, dependencias rotas, ruta crítica sin margen y desbalanceo entre fases
- Se agregó función `get_work_plan_state()` como interfaz de transversalidad cross-tool para que las demás herramientas del MCP consulten el estado de salud del proyecto
- Se registraron herramientas MCP `get_work_plan`, `update_work_plan` y `validate_work_plan` en el servidor
- Se agregaron rutas `/gantt`, `/api/gantt`, `POST /api/gantt/config` y `GET /api/gantt/validate` en el visualizador
- Se agregó pestaña "Plan de Trabajo" en la navegación del visualizador de grafo y ecosistemas

## [2.0.0] — 2026-08-05

### Agregado
- Se agrego soporte de ecosistemas multi-app: modelos (`ContractDefinition`, `AppRegistration`, `SharedEntity`, `EcosystemRegistry`, `CrossAppConflict`), engine (`EcosystemEngine`), y 5 tools nuevos (`init_ecosystem`, `register_app`, `list_ecosystem`, `get_cross_app_context`, `sync_ecosystem`)
- Se extendio `detect_conflicts` para detectar conflictos cross-app (entidades divergentes, contratos rotos, flujos huerfanos entre apps)
- Se extendio `get_story_context` para incluir contexto transversal de otras apps del ecosistema
- Se agrego campo `ecosystem_id` y `app_id` opcionales a `ProjectConfig` para vincular proyectos a ecosistemas
- Se agrego helper `_ensure_str()` para normalizar parametros que pueden llegar como dict o string

### Corregido
- Se corrigio error de deserializacion en TODOS los tools que reciben JSON complejo: los parametros ahora usan tipo `Union[str, dict]` en lugar de `str`, eliminando el error "Input should be a valid string" que Pydantic/FastMCP generaba cuando Kiro enviaba parametros ya deserializados como dict
- Se corrigio error previo de deserializacion parcial en `init_project`, `add_story` y `register_completion` que solo aplicaba el fix en el handler pero no en la firma del tool

### Cambiado
- Se documento en el README la necesidad de usar `docker build --network=host` para evitar el error `Network is unreachable` durante `pip install` en la subred corporativa
- Version del servidor actualizada a 1.1.0
