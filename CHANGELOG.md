# Changelog — MCP_HU_SegurosBolivar

## [No publicado]

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
