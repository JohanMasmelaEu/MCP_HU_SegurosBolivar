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
