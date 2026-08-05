# MCP_HU_SegurosBolivar

MCP Server para analisis inteligente de Historias de Usuario. Combina un panel de 10 expertos especializados, memoria contextual local, segmentacion inteligente de contexto, motor de estimacion adaptativa, gestion de specs SDD y integracion con Jira/Confluence/Clockwork Pro.

Soporta **multiples workspaces y ecosistemas simultaneos** — cada proyecto vive aislado y puedes switchear entre ellos sin reiniciar.

---

## Requisitos

- **Docker Desktop** instalado y corriendo (unico requisito para uso normal)
- **Kiro IDE** (o cualquier cliente MCP compatible con stdio)

> No se necesita Python ni ningun runtime en la maquina. Todo corre dentro de Docker.

---

## Inicio Rapido

### 1. Configurar MCP en Kiro

Crear `~/.kiro/settings/mcp.json` (global) o `<workspace>/.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "MCP_HU_SegurosBolivar": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--pull", "always",
        "-v", "mcp-hu-memory:/workspace",
        "-p", "9751:9751",
        "ghcr.io/johanmasmelaeu/mcp-hu-segurosbolivar:latest"
      ],
      "disabled": false
    }
  }
}
```

> **IMPORTANTE: `--pull always`** — Sin este flag, Docker usa la imagen cacheada
> localmente y NO descarga actualizaciones aunque exista una version nueva en el registry.

### 2. Reiniciar sesion de Kiro

Docker descarga la imagen la primera vez (~80MB). El MCP queda disponible con los 58 tools.

### 3. Inicializar proyecto

Decirle a Kiro: "Inicializa un proyecto de HUs para [tu dominio]"

---

## Configuracion Docker — Notas Importantes

### Pull Policy (`--pull always`)

Docker no hace pull automatico cuando ya tiene una imagen con tag `latest` localmente.
Sin `--pull always`, puedes quedar usando una version vieja indefinidamente.

**Sintomas de version desactualizada:**
- El MCP rechaza crear un segundo ecosistema/proyecto con "ya existe"
- No aparecen tools nuevos (SDD, Jira, Confluence, Clockwork)
- El server reporta version anterior

**Solucion manual** (si ya tienes la config sin `--pull always`):
```bash
docker pull ghcr.io/johanmasmelaeu/mcp-hu-segurosbolivar:latest
```

### Persistencia con Named Volumes

La config usa un **named volume** (`mcp-hu-memory:/workspace`) para que la memoria
sobreviva entre sesiones. Si necesitas empezar limpio:

```bash
# Eliminar toda la memoria (irreversible)
docker volume rm mcp-hu-memory

# O eliminar solo un workspace/ecosistema usando los tools del MCP:
# reset_workspace(workspace_id, confirm=true)
# reset_ecosystem(ecosystem_id, confirm=true)
```

---

## Arquitectura del MCP

### Panel de Expertos (10)

| Experto | Analiza |
|---------|---------|
| Negocio/Dominio | Reglas, edge cases, flujos alternativos (siempre activo) |
| UX/UI | Flujos de usuario, estados, accesibilidad, feedback visual |
| Backend/API | Contratos, validaciones, idempotencia, performance |
| Datos/Persistencia | Modelo de datos, relaciones, migraciones, consistencia |
| Seguridad | Auth, permisos, OWASP, PII, auditoria |
| QA/Testing | Criterios de aceptacion, escenarios negativos (siempre activo) |
| Integracion | Sistemas externos, timeouts, retry, fallback |
| Observabilidad | Metricas, alertas, logs, trazabilidad |
| DevOps/Infra | Escalabilidad, feature flags, jobs batch |
| Legal/Compliance | Retencion de datos, consentimiento, regulacion |

Los expertos se activan automaticamente segun el contenido de la HU.

### Memoria Contextual Local

```
.hu-memory/
├── index.json          # Metadata del proyecto
├── graph.json          # Relaciones entre HUs
├── stories/            # HUs analizadas (JSON)
└── estimations/        # Historico de estimaciones
```

### Segmentacion Inteligente de Contexto

No carga todas las HUs al contexto — solo las relevantes:

```
relevance(HU_new, HU_existing) =
    0.4 x entity_overlap +
    0.3 x flow_overlap +
    0.2 x keyword_similarity +
    0.1 x dependency_distance
```

Solo HUs con score > 0.5 entran al contexto. Ahorro tipico: 80-90% de tokens.

### Estimacion Adaptativa

Se calibra con cada HU completada. Rango optimista/probable/pesimista con nivel de confianza.

### Specs SDD (Spec-Driven Development)

Modelo de especificacion por capas:
- **Negocio** — reglas, procesos, restricciones
- **Arquitectura** — decisiones tecnicas, patrones
- **Seguridad** — controles, autenticacion, cifrado
- **Gobierno de Informacion** — clasificacion, retencion
- **Acceso a Datos** — permisos, roles, auditorias
- **Datos** — modelo, migraciones, indices
- **Desarrollo** — convenciones, patrones, librerias
- **QA** — estrategia de testing, cobertura

Las specs se organizan en una **constelacion** con dependencias tipificadas entre ellas (process, data, functional).

### Integracion Jira / Confluence / Clockwork Pro

Operaciones con **doble confirmacion** (el agente prepara, el usuario confirma):
- Consultar/crear subtareas en Jira
- Registrar worklogs retroactivos
- Mover issues entre columnas
- Leer/crear/actualizar paginas Confluence
- Iniciar/detener timers en Clockwork Pro

### Visualizador de Grafo Interactivo

Al arrancar el MCP se levanta un servidor web en `http://localhost:9751`:

- **Red Neuronal** — grafo de HUs con layout jerarquico/concentrico
- **Ecosistema** — grafo de apps con contratos y health
- **Selector de Workspace/Ecosistema** — cambia de proyecto desde el navegador
- **Click en nodo** → resalta relaciones y muestra panel con detalles
- **Capas** → entidades, flujos, relaciones (toggle individual)
- **Filtro por entidad** → resalta solo HUs que involucran esa entidad

---

## Multi-Workspace y Multi-Ecosistema

### Conceptos

| Concepto | Que es | Ejemplo |
|----------|--------|---------|
| **Workspace** | Un proyecto aislado con su propia memoria de HUs | "OCR Processing", "Cotizador Autos" |
| **Ecosistema** | Agrupacion de apps con visibilidad transversal | "CUC Platform", "Seguros Core" |

### Flujo tipico multi-proyecto

```
1. init_project("OCR Processing", domain="ocr/docs")     → crea workspace "ocr-processing"
2. init_project("Cotizador Web", domain="seguros/autos")  → crea workspace "cotizador-web"
3. list_workspaces()                                       → muestra ambos, indica activo
4. switch_workspace("ocr-processing")                      → cambia al primer proyecto
5. analyze_story("Como usuario quiero...")                  → opera sobre "ocr-processing"
```

### Flujo tipico multi-ecosistema

```
1. init_ecosystem(ecosystem_id="eco-cuc", name="CUC Platform")
2. init_ecosystem(ecosystem_id="eco-seguros", name="Seguros Core")
3. list_ecosystems()                               → muestra ambos
4. switch_ecosystem("eco-cuc")                     → activa CUC
5. register_app(app_id="app-ocr", ...)             → registra en CUC
```

### Estructura en disco

```
/workspace/                        # Volumen Docker montado
  state.json                       # Workspace y ecosistema activos
  workspaces/
    ocr-processing/
      .hu-memory/
        index.json, stories/, graph.json, ...
    cotizador-web/
      .hu-memory/
        ...
  ecosystems/
    eco-cuc/
      .hu-ecosystem/
        ecosystem.json, apps/, contracts/
    eco-seguros/
      .hu-ecosystem/
        ...
```

### Migracion automatica desde v1

Si ya tienes datos en el formato viejo (`/workspace/.hu-memory/` directamente en la raiz), el servidor los migra automaticamente al nuevo formato multi-workspace/ecosistema. No se pierde ningun dato.

---

## Tools disponibles (58)

### Gestion de Workspaces y Ecosistemas (6)
| Tool | Descripcion |
|------|-------------|
| `list_workspaces` | Lista todos los workspaces con metadata y cual es el activo |
| `switch_workspace` | Cambia el workspace activo |
| `reset_workspace` | Elimina un workspace permanentemente (requiere confirm=true) |
| `list_ecosystems` | Lista todos los ecosistemas con metadata y cual es el activo |
| `switch_ecosystem` | Cambia el ecosistema activo |
| `reset_ecosystem` | Elimina un ecosistema permanentemente (requiere confirm=true) |

### Gestion de Proyecto (4)
| Tool | Descripcion |
|------|-------------|
| `init_project` | Crea un workspace nuevo e inicializa su memoria |
| `get_project_summary` | Estado actual: entidades, flujos, HUs, gaps |
| `export_memory` | Exporta memoria como .zip portable |
| `import_memory` | Importa memoria desde export previo |

### Analisis de HUs (5)
| Tool | Descripcion |
|------|-------------|
| `analyze_story` | Analisis multi-experto de una HU (input flexible → output estandarizado) |
| `add_story` | Persiste HU analizada en memoria y actualiza grafo |
| `get_story_context` | Contexto segmentado relevante para una HU |
| `get_expert_analysis` | Analisis profundo desde un experto especifico |
| `explain_for_stakeholder` | Reformula HU para un rol (dev, qa, po, ux) |

### Deteccion de Problemas (2)
| Tool | Descripcion |
|------|-------------|
| `detect_conflicts` | Detecta duplicaciones, contradicciones, flujos abiertos |
| `suggest_next_stories` | Sugiere HUs faltantes basado en gaps |

### Estimacion (4)
| Tool | Descripcion |
|------|-------------|
| `estimate_story` | Estimacion con rango optimista/probable/pesimista + confianza |
| `register_completion` | Registra tiempo real (calibra el motor) |
| `get_velocity` | Velocidad del equipo y tendencias |
| `calibrate_estimates` | Recalcula factores manualmente |

### Ecosistema (5)
| Tool | Descripcion |
|------|-------------|
| `init_ecosystem` | Crea un ecosistema nuevo |
| `register_app` | Registra app en el ecosistema activo |
| `list_ecosystem` | Estado completo del ecosistema (apps, contratos, entidades) |
| `get_cross_app_context` | Contexto transversal de otras apps relevante para una HU |
| `sync_ecosystem` | Re-sincroniza snapshots de apps desde sus memorias |

### SDD — Reglas y Specs (11)
| Tool | Descripcion |
|------|-------------|
| `manage_rules_catalog` | CRUD de reglas transversales corporativas |
| `create_spec` | Crea una nueva spec SDD (inicializa capas vacias) |
| `update_spec_layer` | Actualiza el contenido de una capa SDD |
| `approve_spec` | Aprueba una spec (cambia status a approved) |
| `get_spec` | Obtiene spec completa o filtrada por rol |
| `list_specs` | Lista resumenes de todas las specs |
| `get_constellation` | Grafo de specs con dependencias (formato Cytoscape.js) |
| `add_spec_dependency` | Agrega dependencia entre specs |
| `detect_constellation_gaps` | Detecta specs huerfanas, ciclos, referencias rotas |
| `export_spec_markdown` | Exporta spec como Markdown estructurado |
| `import_spec` | Importa specs desde Markdown |

### Documentacion y Bitacoras (2)
| Tool | Descripcion |
|------|-------------|
| `generate_bitacora` | Bitacora completa del proyecto (Markdown + HTML Confluence) |
| `generate_daily_bitacora` | Bitacora diaria con validacion de 8 horas |

### Jira (7)
| Tool | Descripcion |
|------|-------------|
| `jira_query_issue` | Consulta detallada de un issue |
| `jira_search` | Busqueda por JQL |
| `jira_add_comment` | Agregar comentario a un issue |
| `jira_add_worklog` | Registrar worklog retroactivo |
| `jira_get_worklogs` | Consultar worklogs de un issue |
| `jira_delete_worklog` | Eliminar worklog propio |
| `jira_create_subtask` | Crear subtarea en un issue existente |
| `jira_transition_issue` | Mover issue entre columnas del flujo |

### Confluence (3)
| Tool | Descripcion |
|------|-------------|
| `confluence_read_page` | Leer pagina completa |
| `confluence_create_page` | Crear pagina nueva |
| `confluence_update_page` | Actualizar pagina existente |

### Clockwork Pro (4)
| Tool | Descripcion |
|------|-------------|
| `clockwork_get_assignments` | Asignaciones del usuario en sprint activo |
| `clockwork_get_activity_types` | Tipos de tarea disponibles |
| `clockwork_start_timer` | Iniciar timer en subtarea |
| `clockwork_stop_timer` | Detener timer en subtarea |

### Control de Acciones (3)
| Tool | Descripcion |
|------|-------------|
| `confirm_action` | Ejecuta accion previamente confirmada por el usuario |
| `reject_action` | Rechaza/cancela accion pendiente |
| `list_pending_actions` | Lista acciones pendientes de confirmacion |

### Credenciales (1)
| Tool | Descripcion |
|------|-------------|
| `check_credentials_status` | Verifica que credenciales estan configuradas (no expone valores) |

---

## Integracion Jira / Confluence / Clockwork Pro

### Configuracion de credenciales

Las credenciales se pasan como variables de entorno al container:

```json
{
  "mcpServers": {
    "MCP_HU_SegurosBolivar": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm", "--pull", "always",
        "-v", "mcp-hu-memory:/workspace",
        "-p", "9751:9751",
        "-e", "JIRA_BASE_URL=https://tu-instancia.atlassian.net",
        "-e", "JIRA_EMAIL=tu@email.com",
        "-e", "JIRA_API_TOKEN=tu-api-token",
        "-e", "CONFLUENCE_BASE_URL=https://tu-instancia.atlassian.net/wiki",
        "-e", "CONFLUENCE_EMAIL=tu@email.com",
        "-e", "CONFLUENCE_API_TOKEN=tu-api-token",
        "-e", "CLOCKWORK_BASE_URL=https://api.clockwork.report",
        "-e", "CLOCKWORK_API_TOKEN=tu-clockwork-token",
        "ghcr.io/johanmasmelaeu/mcp-hu-segurosbolivar:latest"
      ],
      "disabled": false
    }
  }
}
```

Usa `check_credentials_status` para verificar que todo esta configurado.

### Modelo de seguridad

Todas las operaciones contra servicios externos siguen un flujo de **doble confirmacion**:

1. El agente **prepara** la accion (retorna preview con `action_id`)
2. El usuario **revisa** y confirma o rechaza
3. Solo `confirm_action` ejecuta realmente la llamada

No existe path de codigo que ejecute operaciones sin confirmacion explicita.

---

## Build local (solo contribuidores)

> **Importante:** El build requiere acceso a PyPI y unpkg.com.
> En redes corporativas que bloquean tráfico directo, usar el override de Docker Compose.

### Red con acceso directo a internet

```bash
git clone https://github.com/JohanMasmelaEu/MCP_HU_SegurosBolivar.git
cd MCP_HU_SegurosBolivar
docker compose build --no-cache
docker compose up -d
```

### Red corporativa (sin acceso directo a PyPI)

Crear un archivo `docker-compose.override.yml` en la raíz del proyecto (ya está en `.gitignore`, no se commitea):

```yaml
version: "3.8"
services:
  mcp-hu:
    build:
      context: .
      network: host
```

Esto le indica a Docker que use la red del host durante el build, permitiendo resolver PyPI a través de la misma ruta que usa tu máquina.

```bash
docker compose build --no-cache
docker compose up -d
```

### Alternativa sin Docker (desarrollo rápido)

Si el build con Docker sigue fallando, puedes correr el servidor directamente con Python:

```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
python -m src.server
```

El visualizador queda disponible en `http://localhost:9751`.

> **Tip:** Para no repetir los `--trusted-host` cada vez, crear `%APPDATA%\pip\pip.ini`:
> ```ini
> [global]
> trusted-host = pypi.org
>                pypi.python.org
>                files.pythonhosted.org
> ```

---

## Publicar imagen (maintainers)

Push a `main` publica automaticamente en ghcr.io via GitHub Actions.

```bash
git tag v2.0.0 && git push origin v2.0.0
```

Hacer paquete publico: GitHub → Package settings → Danger Zone → Public.

---

## Troubleshooting

### Tools nuevos no aparecen

El agente solo ve los tools que el MCP server expone. Si no ves tools recientes:
1. La imagen es vieja → `docker pull ghcr.io/johanmasmelaeu/mcp-hu-segurosbolivar:latest` + reconectar
2. Agregar `--pull always` a la config
3. Panel de Kiro → MCP Servers → Reconnect

### Docker no descarga la version nueva

Docker cachea imagenes `latest` localmente. Agregar `--pull always` a la config:
```json
"args": ["run", "-i", "--rm", "--pull", "always", "-v", "mcp-hu-memory:/workspace", ...]
```

### Quiero empezar de cero

```bash
# Opcion 1: Eliminar solo un workspace
# Usar tool: reset_workspace("nombre-workspace", confirm=true)

# Opcion 2: Eliminar todo el volumen
docker volume rm mcp-hu-memory
```

### Credenciales de Jira/Confluence no funcionan

1. Verificar con `check_credentials_status`
2. Los tokens de Atlassian se crean en: https://id.atlassian.com/manage-profile/security/api-tokens
3. Usar el email de la cuenta Atlassian, no el usuario

---

## Stack Tecnico

| Componente | Tecnologia |
|-----------|------------|
| Runtime | Python 3.12 |
| MCP SDK | mcp 1.9.2 |
| Validacion | Pydantic 2.11.3 |
| Grafos | NetworkX 3.4.2 |
| HTTP Server (visualizador) | Starlette 0.46.2 + Uvicorn 0.34.3 |
| HTTP Client (integraciones) | httpx 0.28.1 |
| Frontend (visualizador) | Cytoscape.js 3.30.4 |
| Container | Docker (python:3.12-slim) |
| CI/CD | GitHub Actions → ghcr.io |
| Transport | stdio (Docker) |

---

## Licencia

Uso interno Seguros Bolivar.
