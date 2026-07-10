# MCP_HU_SegurosBolivar

MCP Server para analisis inteligente de Historias de Usuario. Combina un panel de 10 expertos especializados, memoria contextual local y segmentacion inteligente de contexto para producir HUs completas, sin ambiguedades ni huecos funcionales.

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
        "-v", ".:/workspace",
        "-p", "9751:9751",
        "ghcr.io/johanmasmelaeu/mcp-hu-segurosbolivar:latest"
      ],
      "disabled": false
    }
  }
}
```

### 2. Reiniciar sesion de Kiro

Docker descarga la imagen la primera vez (~80MB). El MCP queda disponible.

### 3. Inicializar proyecto

Decirle a Kiro: "Inicializa un proyecto de HUs para [tu dominio]"

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
├── entities.json       # Entidades del dominio
├── flows.json          # Flujos de negocio
├── decisions.json      # Decisiones tomadas
├── estimations/        # Historico de estimaciones
└── stories/            # HUs analizadas (JSON)
```

La memoria vive en tu workspace. Portable via export/import.

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

Al arrancar el MCP, se levanta automaticamente un servidor web en `http://localhost:9751` con una UI interactiva para explorar el grafo de HUs:

- **Click en un nodo** → resalta sus relaciones y muestra panel lateral con detalles
- **Click en fondo** → vuelve al estado original (reset)
- **Boton Reset** → restaura vista completa
- **Boton Entidades** → muestra/oculta nodos de entidades del dominio
- **Boton Flujos** → muestra/oculta nodos de flujos de negocio
- **Filtro por entidad** → resalta solo HUs que involucran esa entidad
- **Colores:** rojo (analyzed), cyan (refined), verde (completed)
- **Bordes:** rojo (depends_on), verde (impacts), gris (related_to)

Abrir en navegador: [http://localhost:9751](http://localhost:9751)

---

## Tools disponibles (15)

### Gestion de proyecto
| Tool | Descripcion |
|------|-------------|
| `init_project` | Inicializa proyecto y memoria local |
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

---

## Build local (solo contribuidores)

```bash
git clone https://github.com/JohanMasmelaEu/MCP_HU_SegurosBolivar.git
cd MCP_HU_SegurosBolivar
docker build --network=host -t mcp-hu-segurosbolivar:latest .
```

Usar imagen local:
```json
"args": ["run", "-i", "--rm", "-v", ".:/workspace", "-p", "9751:9751", "mcp-hu-segurosbolivar:latest"]
```

---

## Publicar imagen (maintainers)

Push a `main` publica automaticamente en ghcr.io via GitHub Actions.

```bash
git tag v1.0.0 && git push origin v1.0.0
```

Hacer paquete publico: GitHub → Package settings → Danger Zone → Public.

---

## Licencia

Uso interno Seguros Bolivar.
