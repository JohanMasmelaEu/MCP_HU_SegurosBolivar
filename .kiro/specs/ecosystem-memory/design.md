# Design: Ecosystem Memory

## Arquitectura General

```
┌─────────────────────────────────────────────────────────┐
│  .hu-ecosystem/   (ruta configurable)                   │
│  ├── ecosystem.json     (registry central)              │
│  ├── apps/                                              │
│  │   ├── app-cotizador.json   (snapshot de entidades)   │
│  │   ├── app-siniestros.json                            │
│  │   └── app-motor-riesgo.json                          │
│  └── contracts/                                         │
│      ├── contract-001.json                              │
│      └── contract-002.json                              │
└─────────────────────────────────────────────────────────┘

┌──────────────────────┐     ┌──────────────────────┐
│  Proyecto A          │     │  Proyecto B          │
│  .hu-memory/         │     │  .hu-memory/         │
│  index.json          │     │  index.json          │
│    ecosystem_id: "X" │     │    ecosystem_id: "X" │
└──────────────────────┘     └──────────────────────┘
```

## Modelos de Datos

### src/models/ecosystem.py

```python
class ContractDefinition(BaseModel):
    contract_id: str               # "contract-001"
    name: str                      # "API Cotización"
    type: Literal["rest_api", "graphql", "async_event", "shared_lib"]
    provider_app: str              # app_id que lo expone
    consumer_apps: list[str]       # app_ids que lo consumen
    spec_reference: str            # path o URL al OpenAPI/AsyncAPI/schema
    version: str
    entities_involved: list[str]   # entidades que cruzan por este contrato

class AppRegistration(BaseModel):
    app_id: str                    # "app-cotizador"
    name: str                      # "Cotizador Web"
    memory_path: str               # ruta absoluta o relativa a .hu-memory/
    coupling_type: Literal["cohesive", "decoupled"]
    description: str
    team: str                      # equipo dueño
    exposes_contracts: list[str]   # contract_ids
    consumes_contracts: list[str]  # contract_ids
    entities_snapshot: list[str]   # entidades indexadas del .hu-memory/
    registered_at: str

class SharedEntity(BaseModel):
    entity_name: str
    defined_in_apps: list[str]     # app_ids donde aparece
    fields_by_app: dict[str, list[str]]  # {app_id: [campos]}
    is_consistent: bool            # True si todos definen igual
    divergence_notes: str          # descripción de la inconsistencia

class EcosystemRegistry(BaseModel):
    ecosystem_id: str
    name: str
    description: str
    apps: list[AppRegistration]
    contracts: list[ContractDefinition]
    shared_entities: list[SharedEntity]
    created_at: str
    updated_at: str
```

### Extensión a ProjectConfig (src/models/project.py)

```python
class ProjectConfig(BaseModel):
    # ... campos existentes ...
    ecosystem_id: Optional[str] = None  # ID del ecosistema al que pertenece
    app_id: Optional[str] = None        # ID de esta app dentro del ecosistema
```

## Motor de Ecosistema (src/engine/ecosystem.py)

Clase `EcosystemEngine`:
- `__init__()` — detecta si existe `.hu-ecosystem/` en `MCP_ECOSYSTEM_PATH`
- `init_ecosystem(config)` — crea directorio y registry
- `register_app(app)` — registra una app, lee su `.hu-memory/index.json` para snapshot de entidades
- `sync_app(app_id)` — re-lee entidades/flujos de una app (refresh)
- `get_apps()` — lista todas las apps
- `get_shared_entities()` — entidades que aparecen en 2+ apps
- `get_cross_app_context(entity_names, flow_names)` — contexto relevante de otras apps
- `get_app_dependencies(app_id)` — quién depende de esta app y de quién depende
- `detect_cross_app_conflicts()` — inconsistencias, contratos rotos, flujos huérfanos

**Principio**: read-only sobre otras apps. Solo escribe en `.hu-ecosystem/`.

## Tools Nuevos

| Tool | Parámetros | Descripción |
|------|-----------|-------------|
| `init_ecosystem` | config JSON | Crea el registro de ecosistema |
| `register_app` | app JSON | Registra una app en el ecosistema |
| `list_ecosystem` | — | Devuelve apps, contratos, entidades compartidas |
| `get_cross_app_context` | story_id | Contexto cross-app relevante para una HU |
| `sync_ecosystem` | app_id (opcional) | Re-sincroniza entidades desde las apps |

## Integración con Tools Existentes

### `analyze_story` / `get_story_context`
- Si el proyecto pertenece a un ecosistema, se agrega una sección `cross_app_context` al resultado
- Filtra solo entidades/contratos relevantes a la HU

### `detect_conflicts`
- Si hay ecosistema, agrega conflictos cross-app al reporte existente
- Nuevos tipos: `cross_app_entity_divergence`, `missing_contract_provider`, `dead_contract`, `cross_app_flow_gap`

## Persistencia

- `MCP_ECOSYSTEM_PATH` env var (default: mismo directorio que `MCP_WORKSPACE_PATH`)
- Estructura de archivos JSON (sin DB, sin red)
- Cada app se snapshottea al registrarse; sync manual con `sync_ecosystem`

## Backward Compatibility

- Si `ecosystem_id` es None en el proyecto → todo funciona igual que antes
- Si `MCP_ECOSYSTEM_PATH` no existe o no tiene `ecosystem.json` → graceful degradation
- Ningún tool existente cambia su firma ni su output default
