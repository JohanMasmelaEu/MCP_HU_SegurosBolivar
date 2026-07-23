# Multi-Ecosystem Support — Design

## Arquitectura de Almacenamiento

### Estructura de Directorios (Nueva)

```
<BASE_PATH>/                          # MCP_WORKSPACE_PATH (default: /workspace)
  state.json                          # Workspace/ecosistema activos
  workspaces/
    <workspace_id>/
      .hu-memory/
        index.json
        stories/
        estimations/
        graph.json
    <otro-workspace>/
      .hu-memory/
        ...
  ecosystems/
    <ecosystem_id>/
      .hu-ecosystem/
        ecosystem.json
        apps/
        contracts/
    <otro-ecosystem>/
      .hu-ecosystem/
        ...
```

### state.json

```json
{
  "active_workspace": "ocr-cuc",
  "active_ecosystem": "eco-cuc-ocr",
  "version": "2.0"
}
```

## Modelo de Datos

### WorkspaceInfo (nuevo modelo)

```python
class WorkspaceInfo(BaseModel):
    workspace_id: str
    project_name: str
    domain: str
    description: str = ""
    ecosystem_id: Optional[str] = None
    app_id: Optional[str] = None
    story_count: int = 0
    created_at: str
```

### ServerState (nuevo modelo)

```python
class ServerState(BaseModel):
    active_workspace: Optional[str] = None
    active_ecosystem: Optional[str] = None
    version: str = "2.0"
```

## Cambios en MemoryEngine

1. El constructor recibe `workspace_id` y calcula su path como `BASE_PATH/workspaces/<workspace_id>/.hu-memory/`.
2. Se elimina el singleton global. Se reemplaza por un `WorkspaceManager` que:
   - Mantiene la instancia activa.
   - Permite crear, listar, switchear, y eliminar workspaces.
   - Persiste el estado en `state.json`.

### WorkspaceManager

```python
class WorkspaceManager:
    def __init__(self, base_path: Path):
        self._base_path = base_path
        self._workspaces_path = base_path / "workspaces"
        self._state_path = base_path / "state.json"
        self._active_memory: Optional[MemoryEngine] = None
        self._state: ServerState = self._load_state()
        self._migrate_legacy()
        self._restore_active()

    def list_workspaces(self) -> list[WorkspaceInfo]: ...
    def create_workspace(self, workspace_id: str, config: ProjectConfig) -> MemoryEngine: ...
    def switch_workspace(self, workspace_id: str) -> MemoryEngine: ...
    def reset_workspace(self, workspace_id: str, confirm: bool) -> bool: ...
    def get_active(self) -> Optional[MemoryEngine]: ...
```

## Cambios en EcosystemEngine

1. El constructor recibe `ecosystem_id` y calcula su path como `BASE_PATH/ecosystems/<ecosystem_id>/.hu-ecosystem/`.
2. Se reemplaza el singleton por un `EcosystemManager`:

### EcosystemManager

```python
class EcosystemManager:
    def __init__(self, base_path: Path):
        self._base_path = base_path
        self._ecosystems_path = base_path / "ecosystems"
        self._active_ecosystem: Optional[EcosystemEngine] = None
        # Usa el mismo state.json via referencia compartida

    def list_ecosystems(self) -> list[dict]: ...
    def create_ecosystem(self, ecosystem_id: str, name: str, description: str) -> EcosystemEngine: ...
    def switch_ecosystem(self, ecosystem_id: str) -> EcosystemEngine: ...
    def reset_ecosystem(self, ecosystem_id: str, confirm: bool) -> bool: ...
    def get_active(self) -> Optional[EcosystemEngine]: ...
```

## Migracion Legacy

Al inicio del servidor:
1. Si existe `<BASE_PATH>/.hu-memory/` (formato v1), mover a `<BASE_PATH>/workspaces/default/.hu-memory/`.
2. Si existe `<BASE_PATH>/.hu-ecosystem/`, leer su `ecosystem_id` del registro y mover a `<BASE_PATH>/ecosystems/<ecosystem_id>/.hu-ecosystem/`.
3. Crear `state.json` con `active_workspace: "default"` y `active_ecosystem: <ecosystem_id>`.

## Nuevos Tools MCP

| Tool | Descripcion |
|------|-------------|
| `list_workspaces` | Lista workspaces con metadata |
| `switch_workspace` | Cambia workspace activo |
| `reset_workspace` | Elimina un workspace (con confirm) |
| `list_ecosystems` | Lista ecosistemas registrados |
| `switch_ecosystem` | Cambia ecosistema activo |
| `reset_ecosystem` | Elimina un ecosistema (con confirm) |

## Impacto en Tools Existentes

### init_project
- Ya NO falla si un proyecto existe. En su lugar, crea un nuevo workspace con `workspace_id` derivado del nombre del proyecto (slugified).
- Si el workspace ya existe, retorna error indicando usar `switch_workspace` o `reset_workspace`.

### init_ecosystem
- Ya NO falla si un ecosistema existe. Crea uno nuevo con su propio ID.
- Si el `ecosystem_id` ya existe, retorna error indicando usar `switch_ecosystem` o `reset_ecosystem`.

### Todos los demas tools (analyze_story, add_story, etc.)
- Obtienen la memoria via `workspace_manager.get_active()`.
- Si no hay workspace activo, retornan error: "No hay workspace activo. Usar list_workspaces y switch_workspace."

## Diagrama de Flujo — init_project

```
init_project(config)
  |
  v
workspace_id = slugify(project_name) OR config.workspace_id
  |
  v
workspace_exists(workspace_id)?
  |--- SI --> Error: "Workspace ya existe. Usar switch_workspace o reset_workspace."
  |--- NO --> create_workspace(workspace_id, config)
                |
                v
              set_active(workspace_id)
                |
                v
              Si config.ecosystem_id: link_to_ecosystem()
                |
                v
              return success
```

## Diagrama de Flujo — switch_workspace

```
switch_workspace(workspace_id)
  |
  v
workspace_exists(workspace_id)?
  |--- NO --> Error: "Workspace no encontrado."
  |--- SI --> load MemoryEngine(workspace_path)
                |
                v
              update state.json
                |
                v
              return success + project_summary
```
