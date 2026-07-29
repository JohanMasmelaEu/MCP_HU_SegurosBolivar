# Design: Documentation Integration — Jira, Confluence y Clockwork Pro

## Arquitectura General

```
┌─────────────────────────────────────────────────────────────────────────┐
│  MCP Server (src/server.py)                                             │
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────────────┐  │
│  │ Tools Existentes │  │  Documentation  │  │  External API Clients  │  │
│  │ (sin cambios)    │  │  Tools (nuevos) │  │  (con confirmación)    │  │
│  └─────────────────┘  └────────┬────────┘  └───────────┬────────────┘  │
│                                 │                        │               │
│                        ┌────────▼────────┐     ┌────────▼────────┐      │
│                        │  Bitacora Engine │     │ Confirmation    │      │
│                        │  (offline/local) │     │ Gate (guardian) │      │
│                        └─────────────────┘     └────────┬────────┘      │
│                                                          │               │
│                                              ┌───────────▼───────────┐   │
│                                              │  Allowlisted Clients  │   │
│                                              │  ┌─────┐ ┌─────────┐ │   │
│                                              │  │Jira │ │Confluence│ │   │
│                                              │  └─────┘ └─────────┘ │   │
│                                              │  ┌──────────────┐    │   │
│                                              │  │Clockwork Pro │    │   │
│                                              │  └──────────────┘    │   │
│                                              └───────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘

                              │
                    Variables de Entorno
                              │
                              ▼
          ┌───────────────────────────────────────────────┐
          │  ATLASSIAN_EMAIL                              │
          │  ATLASSIAN_API_TOKEN                          │
          │  ATLASSIAN_DOMAIN = jirasegurosbolivar.at...  │
          │  CLOCKWORK_API_TOKEN                          │
          └───────────────────────────────────────────────┘
```

## Modelo de Seguridad — Confirmation Gate

### Principio: Separación Preparar vs Ejecutar

Toda operación contra APIs externas se divide en dos fases:

```
┌──────────────┐         ┌───────────────────┐         ┌──────────────┐
│  PREPARE     │────────▶│  PREVIEW (output)  │────────▶│  EXECUTE     │
│  (siempre)   │         │  (al usuario)      │         │  (solo con   │
│              │         │                    │         │  confirmación)│
└──────────────┘         └───────────────────┘         └──────────────┘
```

Cada tool que toca APIs externas retorna SIEMPRE un objeto `PendingAction` que describe qué va a hacer. El agente presenta esto al usuario. Solo con `confirm_action(action_id)` se ejecuta.

### Allowlist — frozenset inmutable

```python
# src/clients/allowlist.py — ÚNICA fuente de verdad

ALLOWED_OPERATIONS: frozenset[str] = frozenset([
    # ─── JIRA (READ) ───
    "jira.get_issue",
    "jira.search_issues",
    "jira.get_transitions",
    "jira.get_subtasks",

    # ─── JIRA (WRITE) ───
    "jira.add_comment",
    "jira.create_subtask",
    "jira.transition_issue",

    # ─── CONFLUENCE (READ) ───
    "confluence.get_page",
    "confluence.get_page_by_title",

    # ─── CONFLUENCE (WRITE) ───
    "confluence.create_page",
    "confluence.update_page",

    # ─── CLOCKWORK PRO (READ) ───
    "clockwork.get_worklogs",
    "clockwork.get_activity_types",

    # ─── CLOCKWORK PRO (WRITE) ───
    "clockwork.start_timer",
    "clockwork.stop_timer",
])

# OPERACIONES EXPLÍCITAMENTE PROHIBIDAS (para documentación y claridad)
FORBIDDEN_OPERATIONS: frozenset[str] = frozenset([
    "confluence.delete_page",           # NUNCA — ir a Confluence directamente
    "jira.delete_issue",                # NUNCA
    "jira.update_workflow",             # NUNCA — paramétrico/estructural
    "jira.update_field_configuration",  # NUNCA
    "jira.create_issue_top_level",      # NUNCA — solo subtareas
    "clockwork.delete_worklog",         # NUNCA
    "clockwork.modify_others_worklog",  # NUNCA
])
```

---

## Modelos de Datos

### src/models/documentation.py

```python
from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ActionStatus(str, Enum):
    """Estado de una acción pendiente."""
    PENDING = "pending"       # preparada, esperando confirmación
    CONFIRMED = "confirmed"   # usuario confirmó
    EXECUTED = "executed"     # ejecutada exitosamente
    REJECTED = "rejected"     # usuario rechazó
    FAILED = "failed"         # ejecutada pero falló


class ExternalService(str, Enum):
    """Servicios externos soportados."""
    JIRA = "jira"
    CONFLUENCE = "confluence"
    CLOCKWORK = "clockwork"


class PendingAction(BaseModel):
    """Acción preparada pendiente de confirmación del usuario."""
    action_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    service: ExternalService
    operation: str                    # ej: "confluence.create_page"
    method: str                       # HTTP method: GET, POST, PUT
    endpoint: str                     # URL completa (sin token)
    payload_preview: Optional[dict] = None   # body resumido para preview
    description: str                  # descripción humana de qué hace
    impact: str                       # qué efecto tendrá
    reversible: bool = False          # si se puede deshacer
    status: ActionStatus = ActionStatus.PENDING
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    executed_at: Optional[str] = None
    result: Optional[dict] = None


class AuditEntry(BaseModel):
    """Registro de auditoría de operaciones ejecutadas."""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    action_id: str
    service: ExternalService
    operation: str
    status: ActionStatus
    user_confirmed: bool
    response_code: Optional[int] = None
    error_message: Optional[str] = None


class BitacoraEntry(BaseModel):
    """Entrada de bitácora diaria."""
    date: str
    subtask_key: str
    subtask_summary: str
    parent_key: str
    activity_type: Optional[str] = None
    description: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    hours: float
    is_overtime: bool = False
    overtime_reason: Optional[str] = None


class DailyBitacora(BaseModel):
    """Bitácora completa de un día."""
    date: str
    user_email: str
    entries: list[BitacoraEntry] = Field(default_factory=list)
    total_hours: float = 0.0
    regular_hours: float = 0.0
    overtime_hours: float = 0.0
    overtime_approved: bool = False
    overtime_reason: Optional[str] = None
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class WorkHoursConfig(BaseModel):
    """Configuración de horas laborales (invariante)."""
    daily_hours: float = 8.0
    includes_lunch: bool = False  # las 8h NO incluyen almuerzo
    overtime_requires_approval: bool = True
    overtime_requires_reason: bool = True
    default_to_regular_on_ignore: bool = True  # si no confirma, solo 8h
```

---

## Clientes de API — src/clients/

### src/clients/base_client.py

```python
class BaseExternalClient:
    """Cliente base con Confirmation Gate integrado."""

    def __init__(self, service: ExternalService):
        self.service = service
        self._pending_actions: dict[str, PendingAction] = {}

    def prepare_action(self, operation: str, method: str,
                       endpoint: str, payload: dict | None,
                       description: str, impact: str,
                       reversible: bool = False) -> PendingAction:
        """Prepara una acción SIN ejecutarla. Retorna PendingAction para preview."""
        if operation not in ALLOWED_OPERATIONS:
            raise OperationNotAllowedError(operation)

        action = PendingAction(
            service=self.service,
            operation=operation,
            method=method,
            endpoint=endpoint,
            payload_preview=payload,
            description=description,
            impact=impact,
            reversible=reversible,
        )
        self._pending_actions[action.action_id] = action
        return action

    def execute_confirmed(self, action_id: str) -> dict:
        """Ejecuta una acción previamente confirmada por el usuario."""
        action = self._pending_actions.get(action_id)
        if not action:
            raise ActionNotFoundError(action_id)
        if action.status != ActionStatus.CONFIRMED:
            raise ActionNotConfirmedError(action_id)

        # Ejecutar HTTP request real
        result = self._do_request(action)
        action.status = ActionStatus.EXECUTED
        action.executed_at = datetime.now().isoformat()
        action.result = result

        # Registrar en audit log
        self._audit(action)
        return result
```

### src/clients/jira_client.py

```python
class JiraClient(BaseExternalClient):
    """Cliente Jira con operaciones allowlisted."""

    BASE_URL = f"https://{ATLASSIAN_DOMAIN}/rest/api/3"

    def prepare_get_issue(self, issue_key: str) -> PendingAction:
        """Prepara consulta de un issue."""
        return self.prepare_action(
            operation="jira.get_issue",
            method="GET",
            endpoint=f"{self.BASE_URL}/issue/{issue_key}",
            payload=None,
            description=f"Consultar detalle del issue {issue_key}",
            impact="Solo lectura. No modifica nada.",
        )

    def prepare_add_comment(self, issue_key: str, body: str) -> PendingAction:
        """Prepara agregar un comentario."""
        return self.prepare_action(
            operation="jira.add_comment",
            method="POST",
            endpoint=f"{self.BASE_URL}/issue/{issue_key}/comment",
            payload={"body": {"type": "doc", "version": 1, "content": [...]}},
            description=f"Agregar comentario en {issue_key}",
            impact="Se publicará un comentario visible para todo el equipo.",
        )

    def prepare_create_subtask(self, parent_key: str, summary: str,
                                description: str) -> PendingAction:
        """Prepara crear una subtarea."""
        return self.prepare_action(
            operation="jira.create_subtask",
            method="POST",
            endpoint=f"{self.BASE_URL}/issue",
            payload={
                "fields": {
                    "parent": {"key": parent_key},
                    "summary": summary,
                    "issuetype": {"name": "Sub-task"},
                    "description": {...},
                }
            },
            description=f"Crear subtarea '{summary}' bajo {parent_key}",
            impact="Se creará una nueva subtarea en Jira.",
        )

    def prepare_transition(self, issue_key: str, transition_id: str,
                           transition_name: str) -> PendingAction:
        """Prepara mover un issue a otra columna."""
        return self.prepare_action(
            operation="jira.transition_issue",
            method="POST",
            endpoint=f"{self.BASE_URL}/issue/{issue_key}/transitions",
            payload={"transition": {"id": transition_id}},
            description=f"Mover {issue_key} a columna '{transition_name}'",
            impact=f"El issue cambiará de estado a '{transition_name}'.",
        )

    # NO existen métodos para: delete, update_workflow, create_issue_top_level
```

### src/clients/confluence_client.py

```python
class ConfluenceClient(BaseExternalClient):
    """Cliente Confluence con operaciones allowlisted. SIN DELETE."""

    BASE_URL = f"https://{ATLASSIAN_DOMAIN}/wiki/rest/api"

    def prepare_get_page(self, page_id: str) -> PendingAction:
        """Prepara lectura de una página."""
        return self.prepare_action(
            operation="confluence.get_page",
            method="GET",
            endpoint=f"{self.BASE_URL}/content/{page_id}?expand=body.storage,version,ancestors",
            payload=None,
            description=f"Leer página Confluence (ID: {page_id})",
            impact="Solo lectura. No modifica nada.",
        )

    def prepare_create_page(self, space_key: str, title: str,
                            body_html: str, ancestor_id: str) -> PendingAction:
        """Prepara crear una página nueva."""
        return self.prepare_action(
            operation="confluence.create_page",
            method="POST",
            endpoint=f"{self.BASE_URL}/content",
            payload={
                "type": "page",
                "title": title,
                "space": {"key": space_key},
                "ancestors": [{"id": ancestor_id}],
                "body": {"storage": {"value": body_html, "representation": "storage"}},
            },
            description=f"Crear página '{title}' en espacio {space_key}",
            impact="Se creará una nueva página en Confluence visible para el equipo.",
        )

    def prepare_update_page(self, page_id: str, title: str,
                            body_html: str, version_number: int,
                            is_own_page: bool, author_name: str) -> PendingAction:
        """Prepara actualizar una página existente.

        Si no es página propia, la descripción incluye advertencia enfática.
        """
        impact = "Se actualizará el contenido de la página."
        if not is_own_page:
            impact = (
                f"⚠️ ADVERTENCIA: Esta página fue creada por {author_name}. "
                f"Estás a punto de modificar trabajo AJENO. "
                f"¿Estás SEGURO de que quieres editarla?"
            )

        return self.prepare_action(
            operation="confluence.update_page",
            method="PUT",
            endpoint=f"{self.BASE_URL}/content/{page_id}",
            payload={
                "version": {"number": version_number + 1},
                "title": title,
                "type": "page",
                "body": {"storage": {"value": body_html, "representation": "storage"}},
            },
            description=f"Actualizar página '{title}' (v{version_number} → v{version_number + 1})",
            impact=impact,
        )

    # ┌──────────────────────────────────────────────────────────────────┐
    # │  NO EXISTE delete_page — NUNCA SE IMPLEMENTARÁ                   │
    # │  Para eliminar páginas, el usuario va directamente a Confluence  │
    # └──────────────────────────────────────────────────────────────────┘
```

### src/clients/clockwork_client.py

```python
class ClockworkClient(BaseExternalClient):
    """Cliente Clockwork Pro con operaciones allowlisted."""

    BASE_URL = "https://api.clockwork.report/v1"

    def prepare_get_worklogs(self, starting_at: str, ending_at: str,
                             account_id: str, project_keys: list[str]) -> PendingAction:
        """Prepara consulta de worklogs del usuario en la iteración activa."""
        params = {
            "starting_at": starting_at,
            "ending_at": ending_at,
            "account_id": account_id,
            "project_keys[]": project_keys,
            "expand": "issues,worklogs",
        }
        return self.prepare_action(
            operation="clockwork.get_worklogs",
            method="GET",
            endpoint=f"{self.BASE_URL}/worklogs",
            payload=params,
            description=f"Consultar worklogs del {starting_at} al {ending_at}",
            impact="Solo lectura. No modifica nada.",
        )

    def prepare_start_timer(self, issue_key: str) -> PendingAction:
        """Prepara inicio de timer en una subtarea."""
        return self.prepare_action(
            operation="clockwork.start_timer",
            method="POST",
            endpoint=f"{self.BASE_URL}/start_timer",
            payload={"issue_key": issue_key},
            description=f"Iniciar timer en {issue_key}",
            impact=f"Se iniciará el conteo de tiempo en {issue_key}.",
        )

    def prepare_stop_timer(self, issue_key: str) -> PendingAction:
        """Prepara detener timer en una subtarea."""
        return self.prepare_action(
            operation="clockwork.stop_timer",
            method="POST",
            endpoint=f"{self.BASE_URL}/stop_timer",
            payload={"issue_key": issue_key},
            description=f"Detener timer en {issue_key}",
            impact="Se detendrá el timer y se registrará el tiempo transcurrido.",
        )

    # Los Activity Types se obtienen via Jira custom fields + Clockwork attributes
    # No se hardcodean — se consultan dinámicamente
```

---

## Bitácora Engine — src/engine/bitacora.py

### Responsabilidades

1. **Generar bitácora offline** (sin API) → Markdown + Confluence Storage Format
2. **Compilar bitácora diaria** → recopilar subtareas, tiempos, avances
3. **Aplicar regla de 8 horas** → validar overtime con el usuario
4. **Formatear para Clockwork** → preparar datos en el formato que entiende la API

### Flujo de bitácora diaria

```
┌───────────────────┐
│ Usuario pide      │
│ "genera bitácora" │
└────────┬──────────┘
         │
         ▼
┌───────────────────────────────────────────────────────┐
│ 1. Obtener subtareas asignadas (sprint activo)        │
│    → prepare_action → confirmación → execute          │
└────────┬──────────────────────────────────────────────┘
         │
         ▼
┌───────────────────────────────────────────────────────┐
│ 2. Obtener tipos de tarea de Clockwork (dinámico)     │
│    → prepare_action → confirmación → execute          │
└────────┬──────────────────────────────────────────────┘
         │
         ▼
┌───────────────────────────────────────────────────────┐
│ 3. Verificar integración Google Calendar              │
│    Si existe → traer reuniones del día                │
│    Si no → continuar sin ese dato                     │
└────────┬──────────────────────────────────────────────┘
         │
         ▼
┌───────────────────────────────────────────────────────┐
│ 4. Presentar opciones al usuario:                     │
│    - Subtareas disponibles (solo del usuario/sprint)  │
│    - Tipos de tarea (del API)                         │
│    - Pedir: subtarea, tipo, descripción, día,         │
│             hora inicio, hora fin                     │
└────────┬──────────────────────────────────────────────┘
         │
         ▼
┌───────────────────────────────────────────────────────┐
│ 5. Validar regla de 8 horas:                          │
│    total > 8h? →                                      │
│      SI: "Se exceden las 8h normativas.               │
│           ¿Registrar solo 8h o confirmar horas extra  │
│           con justificación?"                         │
│      NO confirma/ignora → solo 8h                     │
│      SÍ confirma + motivo → registrar extra           │
└────────┬──────────────────────────────────────────────┘
         │
         ▼
┌───────────────────────────────────────────────────────┐
│ 6. Generar preview completo de la bitácora            │
│    → mostrar al usuario para validación final         │
└────────┬──────────────────────────────────────────────┘
         │
         ▼
┌───────────────────────────────────────────────────────┐
│ 7. Si confirma → registrar en Clockwork (con confirm) │
│    Si no → guardar solo localmente                    │
└───────────────────────────────────────────────────────┘
```

---

## Tools Nuevos — src/tools/documentation_tools.py

| Tool | Tipo | Descripción |
|------|------|-------------|
| `generate_bitacora` | Offline | Genera bitácora en formato Confluence Storage Format + Markdown local |
| `generate_daily_bitacora` | Offline + API | Compila bitácora diaria con subtareas y tiempos |
| `prepare_confluence_page` | API (prepare) | Prepara creación/actualización de página — retorna preview |
| `prepare_jira_query` | API (prepare) | Prepara consulta a Jira — retorna preview |
| `prepare_jira_comment` | API (prepare) | Prepara comentario en issue — retorna preview |
| `prepare_jira_subtask` | API (prepare) | Prepara crear subtarea — retorna preview |
| `prepare_jira_transition` | API (prepare) | Prepara mover issue — retorna preview |
| `prepare_clockwork_register` | API (prepare) | Prepara registro de tiempo — retorna preview |
| `confirm_action` | API (execute) | Ejecuta una acción previamente preparada y confirmada |
| `list_pending_actions` | Utility | Lista acciones pendientes de confirmación |
| `reject_action` | Utility | Rechaza/cancela una acción pendiente |

---

## Formato de Tiempo — Clockwork Pro

Según la API de Clockwork Pro, los worklogs usan formato ISO 8601:

```
started: "2026-07-28T09:00:00-05:00"   (con timezone Colombia)
timeSpentSeconds: 3600                   (1 hora = 3600 segundos)
```

Para el registro, el agente pide al usuario:
- Día: `YYYY-MM-DD`
- Hora inicio: `HH:MM` (24h)
- Hora fin: `HH:MM` (24h)

Y calcula internamente el `timeSpentSeconds` y el `started` en formato Clockwork.

---

## APIs Externas — Endpoints Utilizados

### Jira Cloud REST API v3

| Operación | Método | Endpoint |
|-----------|--------|----------|
| Get issue | GET | `/rest/api/3/issue/{issueIdOrKey}` |
| Search (JQL) | POST | `/rest/api/3/search` |
| Get transitions | GET | `/rest/api/3/issue/{issueIdOrKey}/transitions` |
| Add comment | POST | `/rest/api/3/issue/{issueIdOrKey}/comment` |
| Create subtask | POST | `/rest/api/3/issue` |
| Do transition | POST | `/rest/api/3/issue/{issueIdOrKey}/transitions` |

Auth: Basic Auth (`email:api_token` en Base64)

### Confluence Cloud REST API

| Operación | Método | Endpoint |
|-----------|--------|----------|
| Get page | GET | `/wiki/rest/api/content/{id}?expand=body.storage,version` |
| Search by title | GET | `/wiki/rest/api/content?title={title}&spaceKey={key}` |
| Create page | POST | `/wiki/rest/api/content` |
| Update page | PUT | `/wiki/rest/api/content/{id}` |

Auth: Basic Auth (mismo token que Jira — `email:api_token` en Base64)

### Clockwork Pro API

| Operación | Método | Endpoint |
|-----------|--------|----------|
| Get worklogs | GET | `https://api.clockwork.report/v1/worklogs` |
| Start timer | POST | `https://api.clockwork.report/v1/start_timer` |
| Stop timer | POST | `https://api.clockwork.report/v1/stop_timer` |

Auth: `Authorization: Token {clockwork_token}`

Filtros relevantes para worklogs:
- `starting_at` / `ending_at`: rango de fechas (YYYY-MM-DD)
- `account_id`: filtrar por usuario
- `project_keys[]`: filtrar por proyecto
- `expand=issues,worklogs,authors`: expandir detalles
- `tz`: timezone (ej: `America/Bogota`)

---

## Estructura de Archivos (nuevos)

```
src/
  clients/
    __init__.py
    allowlist.py              # frozenset ALLOWED_OPERATIONS + FORBIDDEN_OPERATIONS
    base_client.py            # BaseExternalClient con Confirmation Gate
    jira_client.py            # JiraClient (allowlisted)
    confluence_client.py      # ConfluenceClient (allowlisted, SIN DELETE)
    clockwork_client.py       # ClockworkClient (allowlisted)
  engine/
    bitacora.py               # BitacoraEngine (offline + compilación diaria)
  models/
    documentation.py          # PendingAction, AuditEntry, BitacoraEntry, DailyBitacora
  tools/
    documentation_tools.py    # Handlers de los nuevos tools
```

---

## Auditoría Local

Archivo: `.hu-memory/audit-log.jsonl` (JSON Lines, append-only)

```json
{"timestamp": "2026-07-28T14:32:00", "action_id": "a3f2b1c9", "service": "jira", "operation": "jira.get_issue", "status": "executed", "user_confirmed": true, "response_code": 200}
{"timestamp": "2026-07-28T14:33:15", "action_id": "d7e4f2a1", "service": "confluence", "operation": "confluence.create_page", "status": "executed", "user_confirmed": true, "response_code": 200}
```

Nunca incluye tokens, payloads con datos sensibles, ni contenido completo de respuestas.

---

## Hook de Protección (PreToolUse)

Se creará un hook que intercepte las tools de documentación para reforzar la confirmación:

```json
{
  "version": "v1",
  "hooks": [{
    "name": "Confirm External API Actions",
    "trigger": "PreToolUse",
    "matcher": "confirm_action",
    "action": {
      "type": "agent",
      "prompt": "ANTES de ejecutar confirm_action, verifica que el usuario ha dado confirmación EXPLÍCITA en este mismo turno de conversación. Si no hay confirmación clara del usuario, NO procedas."
    }
  }]
}
```

---

## Degradación Graceful

| Escenario | Comportamiento |
|-----------|---------------|
| Sin `ATLASSIAN_API_TOKEN` | Tools de API no disponibles, `generate_bitacora` offline funciona |
| Sin `CLOCKWORK_API_TOKEN` | Tools de Clockwork no disponibles, bitácora sin tiempos reales |
| API responde 401/403 | Informar al usuario, no reintentar sin permiso |
| API responde 429 (rate limit) | Informar al usuario, sugerir reintentar más tarde |
| API responde 5xx | Informar error, guardar bitácora localmente |
| Sin Google Calendar en Clockwork | Funcionar sin reuniones, pedir datos manualmente |

---

## Backward Compatibility

- Los tools existentes (analyze_story, estimate_story, etc.) NO cambian.
- Los nuevos tools son 100% aditivos.
- Si no se configuran variables de entorno, el MCP funciona exactamente igual que antes.
- La integración es opt-in: solo se activa si los tokens están presentes Y el usuario invoca los tools.
