# MCP_HU_SegurosBolivar

MCP Server para analisis inteligente de Historias de Usuario. Combina un panel de 10 expertos especializados, memoria contextual local y segmentacion inteligente de contexto para producir HUs completas, sin ambiguedades ni huecos funcionales.

Soporta **multiples workspaces y ecosistemas simultaneos** — cada proyecto vive aislado y puedes switchear entre ellos sin reiniciar.

---

## Requisitos

- **Docker Desktop** instalado y corriendo (unico requisito)
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
> Esto causa que el MCP siga usando una version vieja hasta que hagas `docker pull` manualmente.

### 2. Reiniciar sesion de Kiro

Docker descarga la imagen la primera vez (~80MB). El MCP queda disponible con los 26 tools.

### 3. Inicializar proyecto

Decirle a Kiro: "Inicializa un proyecto de HUs para [tu dominio]"

---

## Configuracion Docker — Notas Importantes

### Pull Policy (`--pull always`)

Docker no hace pull automatico cuando ya tiene una imagen con tag `latest` localmente.
Sin `--pull always`, puedes quedar usando una version vieja indefinidamente.

**Sintomas de version desactualizada:**
- El MCP rechaza crear un segundo ecosistema/proyecto con "ya existe"
- No aparecen tools como `list_workspaces` o `switch_ecosystem`
- El server reporta version `1.x` en lugar de `2.x`

**Solucion manual** (si ya tienes la config sin `--pull always`):
```bash
docker pull ghcr.io/johanmasmelaeu/mcp-hu-segurosbolivar:latest
```

Luego reconectar el MCP desde el panel de Kiro.

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

### Verificar version activa

```bash
docker run --rm --entrypoint python ghcr.io/johanmasmelaeu/mcp-hu-segurosbolivar:latest -c "from src.server import mcp; print(mcp.name, 'v' + mcp._mcp_server_options.get('version','?') if hasattr(mcp,'_mcp_server_options') else '')"
```

---

## Multi-Workspace y Multi-Ecosistema (v2.0)

A partir de v2.0, el MCP soporta **N workspaces y N ecosistemas** coexistiendo simultaneamente.

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

### Migracion automatica desde v1

Si ya tienes datos en el formato viejo (`/workspace/.hu-memory/` y `/workspace/.hu-ecosystem/`
directamente en la raiz), el servidor los migra automaticamente al nuevo formato:

```
/workspace/.hu-memory/     → /workspace/workspaces/default/.hu-memory/
/workspace/.hu-ecosystem/  → /workspace/ecosystems/<eco-id>/.hu-ecosystem/
```

No se pierde ningun dato. El workspace migrado se llama "default" y queda como activo.

### Estructura en disco (v2)

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

---

## Como funciona

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

La memoria vive dentro del volumen Docker. Portable via export/import.

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

### Estimacion Adaptativa (opcional)

Se calibra con cada HU completada. Rango optimista/probable/pesimista con nivel de confianza.

### Visualizador de Grafo Interactivo

Al arrancar el MCP, se levanta un servidor web en `http://localhost:9751` con UI interactiva:

- **Selector de Workspace** — cambia de proyecto desde el navegador
- **Selector de Ecosistema** — cambia de ecosistema desde el navegador
- **Click en nodo** → resalta relaciones y muestra panel con detalles
- **Boton Entidades** → muestra/oculta nodos de entidades del dominio
- **Boton Flujos** → muestra/oculta nodos de flujos de negocio
- **Filtro por entidad** → resalta solo HUs que involucran esa entidad
- **Colores:** naranja (analyzed), azul (refined), verde (completed)

Abrir en navegador: [http://localhost:9751](http://localhost:9751)

---

## Tools disponibles (26)

### Gestion de Workspaces y Ecosistemas
| Tool | Descripcion |
|------|-------------|
| `list_workspaces` | Lista todos los workspaces con metadata y cual es el activo |
| `switch_workspace` | Cambia el workspace activo (todas las operaciones van a este) |
| `reset_workspace` | Elimina un workspace permanentemente (requiere confirm=true) |
| `list_ecosystems` | Lista todos los ecosistemas con metadata y cual es el activo |
| `switch_ecosystem` | Cambia el ecosistema activo |
| `reset_ecosystem` | Elimina un ecosistema permanentemente (requiere confirm=true) |

### Gestion de proyecto
| Tool | Descripcion |
|------|-------------|
| `init_project` | Crea un workspace nuevo e inicializa su memoria |
| `get_project_summary` | Estado actual: entidades, flujos, HUs, gaps |
| `export_memory` | Exporta memoria como .zip portable |
| `import_memory` | Importa memoria desde export previo |

### Analisis de HUs
| Tool | Descripcion |
|------|-------------|
| `analyze_story` | Analisis multi-experto de una HU (input flexible → output estandarizado) |
| `add_story` | Persiste HU analizada en memoria y actualiza grafo |
| `get_story_context` | Contexto segmentado relevante para una HU |
| `get_expert_analysis` | Analisis profundo desde un experto especifico |
| `explain_for_stakeholder` | Reformula HU para un rol (dev, qa, po, ux) |

### Deteccion de problemas
| Tool | Descripcion |
|------|-------------|
| `detect_conflicts` | Detecta duplicaciones, contradicciones, flujos abiertos |
| `suggest_next_stories` | Sugiere HUs faltantes basado en gaps |

### Estimacion
| Tool | Descripcion |
|------|-------------|
| `estimate_story` | Estimacion con rango + confianza |
| `register_completion` | Registra tiempo real (calibra el motor) |
| `get_velocity` | Velocidad del equipo y tendencias |
| `calibrate_estimates` | Recalcula factores manualmente |

### Ecosistema (visibilidad transversal)
| Tool | Descripcion |
|------|-------------|
| `init_ecosystem` | Crea un ecosistema nuevo (aislado de los demas) |
| `register_app` | Registra app en el ecosistema activo |
| `list_ecosystem` | Estado completo del ecosistema activo (apps, contratos, entidades) |
| `get_cross_app_context` | Contexto transversal de otras apps relevante para una HU |
| `sync_ecosystem` | Re-sincroniza snapshots de apps desde sus memorias |

---

## Troubleshooting

### "El proyecto ya esta inicializado"

**Causa:** Estas usando la version v1 del MCP (no tiene multi-workspace).

**Solucion:**
1. Verificar que la imagen sea la ultima: `docker pull ghcr.io/johanmasmelaeu/mcp-hu-segurosbolivar:latest`
2. Agregar `"--pull", "always"` en la config de Kiro
3. Reconectar el MCP desde el panel de Kiro

### "El ecosistema ya esta inicializado"

**Causa v1:** Misma que arriba — actualizar imagen.
**Causa v2:** Ese `ecosystem_id` ya existe. Usar `switch_ecosystem` para activarlo o `reset_ecosystem` para eliminarlo y recrear.

### Tools nuevos no aparecen

El agente solo ve los tools que el MCP server expone. Si no ves `list_workspaces`, `switch_ecosystem`, etc.:
1. La imagen es vieja → `docker pull` + reconectar
2. El MCP no se reconecto → Panel de Kiro → MCP Servers → Reconnect

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

---

## Build local (solo contribuidores)

> **Importante:** El build requiere pasar los argumentos de proxy corporativo para que
> `pip install` pueda resolver PyPI desde la subred de Seguros Bolivar.

```bash
git clone https://github.com/JohanMasmelaEu/MCP_HU_SegurosBolivar.git
cd MCP_HU_SegurosBolivar
docker build --build-arg HTTP_PROXY=%HTTP_PROXY% --build-arg HTTPS_PROXY=%HTTPS_PROXY% -t ghcr.io/johanmasmelaeu/mcp-hu-segurosbolivar:latest .
```

> En PowerShell usar `$env:HTTP_PROXY` y `$env:HTTPS_PROXY` en lugar de `%...%`.

---

## Publicar imagen (maintainers)

Push a `main` publica automaticamente en ghcr.io via GitHub Actions.

```bash
git tag v2.0.0 && git push origin v2.0.0
```

Hacer paquete publico: GitHub → Package settings → Danger Zone → Public.

---

## Licencia

Uso interno Seguros Bolivar.
