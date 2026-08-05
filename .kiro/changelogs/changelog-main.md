# Changelog — main

## [No publicado]

### Corregido
- Se corrigió que el campo `border_style` (maturity) no tenía efecto visual en Cytoscape — se agregaron selectores para solid/dashed/dotted
- Se corrigió `route_eco_app_detail` para incluir `maturity` de la app y `status` de cada contrato en la respuesta JSON
- Se implementó `_find_stories_for_entities` que antes retornaba lista vacía — ahora lee el index.json del .hu-memory/ con cache en memoria
- Se corrigió tooltip del edge que mostraba "Fuerza: X/10" engañosamente — se eliminó el denominador "/10"
- Se corrigió categorización de `shared_lib` que caía como "mixed" en filtro de integración micro — ahora se clasifica como "sync"
- Se corrigió tooltip que se desbordaba del viewport sin reposicionamiento — ahora se ajusta si excede bordes derecho o inferior

### Agregado
- Se agregó fila "Madurez" al panel lateral con color según estado (formalized/draft/reference)
- Se agregaron badges de status (active/draft/deprecated) a cada contrato en el panel lateral
- Se agregaron 3 entradas a la leyenda para estilos de madurez (solid=Formalized, dashed=Draft, dotted=Reference)
- Se agregó fallback cuando Cytoscape CDN no carga (entorno sin internet) — muestra mensaje de error claro
- Se expandió filtro "Solo conflictos" en vista micro para incluir conflictos de salud (dead_contract, missing_contract_provider), no solo divergencias de entidades
- Se agregó filtro por madurez (Formalized/Draft/Reference) al toolbar de la vista macro
- Se agregaron campos `version` y `approved_by` al listado de ecosistemas en `list_ecosystems()`
- Se agregó visualización de versión del ecosistema y badge de aprobación ("Aprobado"/"Sin aprobar") en el toolbar

### Cambiado
- Se actualizó `ecosystem_manager.list_ecosystems()` para incluir `version` y `approved_by` en la respuesta
- Se refactorizó `applyFilters()` para manejar filtros de madurez junto con filtros de integración y conflictos

### Eliminado
- Se eliminó el fallback legacy de `handle_init_ecosystem` en `ecosystem_tools.py` — ahora retorna error si EcosystemManager no está disponible
- Se eliminó la función `_legacy_init_project()` y su llamada fallback en `project_tools.py`
- Se eliminó el patrón singleton (`_memory_instance`) de `memory.py` — `get_memory()` ahora delega exclusivamente al WorkspaceManager
- Se eliminó `_migrate_legacy()` de `ecosystem_manager.py` y `workspace_manager.py`
- Se eliminó la property `migrated_ecosystem_id` de `EcosystemManager`
- Se eliminó la referencia a `_eco_manager.migrated_ecosystem_id` en `server.py`

### Agregado
- Se creó `src/models/sdd.py` con modelos SDD: `SDDLayer` (enum 8 capas), `SDD_LAYER_META`, `TransversalRule`, `RoleDepthMatrix`, `DepthLevel`, `LayerContent`, `SpecDependency`, `ProjectSpec`, `DEFAULT_ROLE_DEPTH` (11 roles × 8 capas)
- Se migró `EXPERT_SDD_LAYER_MAP` de `story.py` a `sdd.py` usando valores del enum `SDDLayer`
- Se creó `src/engine/rules_catalog.py` — `RulesCatalogEngine` con CRUD, `get_rules_for_layer()`, `get_rules_for_spec()`
- Se creó `src/engine/spec_engine.py` — `SpecEngine` con create/update/approve/get/list, `apply_catalog_rules()`, `get_spec_for_role()` con filtrado por profundidad
- Se conectó `SpecEngine` a `handle_analyze_story` — agrega `spec_context` con constraints de la spec vinculada
- Se creó `src/tools/sdd_tools.py` con handlers: `manage_rules_catalog`, `create_spec`, `update_spec_layer`, `approve_spec`, `get_spec`, `list_specs`
- Se registraron 6 tools SDD iniciales en `server.py` con `init_rules_catalog()` e `init_spec_engine()`
- Se actualizó `handle_explain_for_stakeholder` para usar `RoleDepthMatrix` — filtra spec por rol y agrega `spec_context_for_role`
- Se agregó campo `spec_id` a `AppRegistration` en `models/ecosystem.py`
- Se agregó campo `specs` a `EcosystemRegistry` en `models/ecosystem.py`
- Se agregó método `link_app_to_spec()` a `EcosystemEngine`
- Se creó `src/engine/constellation.py` — `ConstellationEngine` con `build_constellation()` (Cytoscape.js), `detect_gaps()`, `infer_dependencies_from_contracts()`
- Se agregaron handlers de constelación a `sdd_tools.py`: `handle_get_constellation`, `handle_add_spec_dependency`, `handle_detect_constellation_gaps`
- Se registraron 3 tools de constelación en `server.py`: `get_constellation`, `add_spec_dependency`, `detect_constellation_gaps`
- Se agregó tab "Constelación" al visualizador `ecosystem_visualizer_ui.html` con renderizado Cytoscape (nodos por status, edges por tipo/maturity, panel de detalle)
- Se crearon 3 rutas API de constelación en `ecosystem_visualizer.py`: `/api/constellation/{id}`, `/api/constellation/{id}/spec/{spec_id}`, `/api/constellation/{id}/gaps`
- Se registraron rutas de constelación en `visualizer.py`
- Se creó handler `handle_export_spec_markdown` — exporta spec como Markdown estructurado
- Se creó handler `handle_import_spec` — importa specs desde Markdown con detección de capas y dependencias
- Se registraron tools `export_spec_markdown` e `import_spec` en `server.py`
