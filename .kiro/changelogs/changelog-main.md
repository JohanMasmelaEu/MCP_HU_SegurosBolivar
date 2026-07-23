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
