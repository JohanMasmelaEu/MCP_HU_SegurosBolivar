# Multi-Ecosystem Support — Tasks

## Fase 1: Modelos y State

- [x] Task 1: Crear modelos `WorkspaceInfo` y `ServerState` en `src/models/project.py`
- [x] Task 2: Crear `WorkspaceManager` en `src/engine/workspace_manager.py`
- [x] Task 3: Crear `EcosystemManager` en `src/engine/ecosystem_manager.py`

## Fase 2: Refactor Engines

- [x] Task 4: Modificar `MemoryEngine.__init__` para aceptar un path configurable (no singleton fijo)
- [x] Task 5: Modificar `EcosystemEngine.__init__` para aceptar un path configurable
- [x] Task 6: Implementar migracion legacy en `WorkspaceManager._migrate_legacy()`

## Fase 3: Nuevos Tools

- [x] Task 7: Crear `src/tools/workspace_tools.py` con handlers para list/switch/reset workspaces
- [x] Task 8: Crear `src/tools/ecosystem_mgmt_tools.py` con handlers para list/switch/reset ecosystems
- [x] Task 9: Actualizar `handle_init_project` para usar `WorkspaceManager`
- [x] Task 10: Actualizar `handle_init_ecosystem` para usar `EcosystemManager`

## Fase 4: Integracion

- [x] Task 11: Reemplazar `get_memory()` / `get_ecosystem()` en todos los tools por managers
- [x] Task 12: Registrar nuevos tools en `server.py`
- [x] Task 13: Actualizar `__init__.py` exports si necesario

## Fase 5: Validacion

- [ ] Task 14: Verificar que el servidor inicia correctamente
- [ ] Task 15: Actualizar changelog
