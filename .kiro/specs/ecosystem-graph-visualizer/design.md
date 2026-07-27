# Ecosystem Graph Visualizer — Design

## Arquitectura General

La solucion extiende el **servidor HTTP existente** (puerto 9751) agregando nuevas rutas para la vista de ecosistema. Ambas vistas coexisten en la misma app con un selector/tab que permite navegar entre ellas.

```
┌──────────────────────────────────────────────────────────────────┐
│  MCP Server (stdio)                                              │
│    ├── MemoryEngine (workspace activo)                           │
│    ├── EcosystemManager (ecosistemas)                            │
│    └── Visualizer (Starlette) → :9751                            │
│          ├── /              → Red Neuronal (workspace view)      │
│          ├── /ecosystem     → Ecosistema: Macro ↔ Micro (nuevo)  │
│          ├── /api/graph     → API workspace graph (existente)    │
│          └── /api/eco/*     → API ecosystem graph (nuevo)        │
└──────────────────────────────────────────────────────────────────┘
```

## Componentes Nuevos

| Archivo | Responsabilidad |
|---------|----------------|
| `src/engine/ecosystem_visualizer.py` | Logica backend: construir grafo macro, calcular flujos micro entre apps, calcular salud, handlers de rutas API. |
| `src/engine/ecosystem_visualizer_ui.html` | UI completa: vista Macro (Cytoscape.js con compound nodes), vista Micro (diagrama de flujos), panel de detalle, filtros, leyenda. Single-file HTML con transicion interna entre vistas. |

## Cambios Minimos a Archivos Existentes

| Archivo | Cambio |
|---------|--------|
| `src/engine/visualizer.py` | Agregar rutas `/ecosystem` y `/api/eco/*`. Importar handlers del nuevo modulo. |
| `src/engine/visualizer_ui.html` | Agregar un `<nav>` con tab "Ecosistema" que enlaza a `/ecosystem`. |

## Flujo de Datos

```
Browser (localhost:9751)
    │
    ├── GET /                                         → HTML Red Neuronal (existente)
    ├── GET /ecosystem                                → HTML Ecosistema Macro/Micro (nuevo)
    ├── GET /api/eco/ecosystems                       → Lista ecosistemas disponibles
    ├── GET /api/eco/graph/{eco_id}                   → Grafo macro (apps + acoplamiento)
    ├── GET /api/eco/flows/{eco_id}/{app_a}/{app_b}   → Flujos micro entre 2 apps
    ├── GET /api/eco/app/{eco_id}/{app_id}            → Detalle de una app
    └── GET /api/eco/health/{eco_id}                  → Indicadores de salud por app
```

---

## Vista Macro — Modelo de Datos del Grafo

### GET /api/eco/graph/{ecosystem_id}

Retorna la topologia de acoplamiento para Cytoscape.js:

```json
{
  "ecosystem_id": "eco-seguros",
  "ecosystem_name": "Plataforma Seguros",
  "nodes": [
    {
      "data": {
        "id": "cluster:auth-gateway",
        "label": "Cluster Auth + Gateway",
        "type": "cluster"
      }
    },
    {
      "data": {
        "id": "app:app-cotizador",
        "label": "Cotizador Web",
        "type": "app",
        "team": "Equipo Frontend",
        "story_count": 12,
        "coupling_type": "decoupled",
        "entities_count": 8,
        "flows_count": 5,
        "health": "green",
        "conflicts": 0,
        "divergent_entities": 0
      }
    },
    {
      "data": {
        "id": "app:auth-service",
        "parent": "cluster:auth-gateway",
        "label": "Auth Service",
        "type": "app",
        "coupling_type": "cohesive",
        "story_count": 3,
        "health": "green"
      }
    }
  ],
  "edges": [
    {
      "data": {
        "id": "coupling:cotizador-emision",
        "source": "app:app-cotizador",
        "target": "app:app-emision",
        "type": "coupling",
        "coupling_strength": 7,
        "contracts_count": 3,
        "shared_entities_count": 4,
        "sync_type": "mixed",
        "label": "3 contratos · 4 entidades"
      }
    }
  ]
}
```

### Nodos

| Tipo | Representacion | Comportamiento |
|------|---------------|----------------|
| `cluster` | Compound node (borde punteado, agrupa apps cohesivas) | No interactivo directamente, solo visual |
| `app` | Rectangulo con info, badge de salud | Click → panel detalle. Doble-click → navegar a workspace |

### Edges (Macro)

| Propiedad | Representacion Visual |
|-----------|-----------------------|
| `coupling_strength` | Grosor de la linea (mapData 1-10 → 2px-8px) |
| `sync_type: "sync"` | Linea solida azul |
| `sync_type: "async"` | Linea punteada naranja |
| `sync_type: "mixed"` | Linea solida con segmento punteado (bicolor) |
| `label` | Texto sobre la linea: "N contratos · M entidades" |

---

## Vista Micro — Flujos Punto A → Punto B

### GET /api/eco/flows/{ecosystem_id}/{app_a}/{app_b}

Retorna los flujos concretos entre dos apps:

```json
{
  "app_a": { "app_id": "app-cotizador", "name": "Cotizador Web" },
  "app_b": { "app_id": "app-emision", "name": "Emision Backend" },
  "coupling_summary": {
    "contracts_count": 3,
    "shared_entities_count": 4,
    "coupling_strength": 7
  },
  "flows": [
    {
      "flow_id": "flow-001",
      "flow_name": "Solicitar Cotizacion",
      "direction": "a_to_b",
      "origin": {
        "story_id": "HU-003",
        "story_title": "Crear cotizacion online",
        "app_id": "app-cotizador"
      },
      "target": {
        "story_id": "HU-012",
        "story_title": "Procesar solicitud de cotizacion",
        "app_id": "app-emision"
      },
      "contract": {
        "contract_id": "contract-001",
        "name": "API Cotizacion",
        "type": "rest_api",
        "version": "1.2.0",
        "spec_reference": "/api/v1/cotizaciones"
      },
      "entities_in_transit": [
        {
          "name": "Cotizacion",
          "direction": "request",
          "is_consistent": true
        },
        {
          "name": "Poliza",
          "direction": "response",
          "is_consistent": false,
          "divergence": "Cotizador define 8 campos, Emision define 12 campos"
        }
      ]
    },
    {
      "flow_id": "flow-002",
      "flow_name": "Notificar Pago Procesado",
      "direction": "b_to_a",
      "origin": {
        "story_id": "HU-016",
        "story_title": "Emitir evento de pago confirmado",
        "app_id": "app-emision"
      },
      "target": {
        "story_id": "HU-007",
        "story_title": "Recibir confirmacion de pago",
        "app_id": "app-cotizador"
      },
      "contract": {
        "contract_id": "contract-003",
        "name": "Evt Pago Procesado",
        "type": "async_event",
        "version": "1.0.0"
      },
      "entities_in_transit": [
        { "name": "Pago", "direction": "event_payload", "is_consistent": true }
      ]
    }
  ]
}
```

### Construccion de la Vista Micro

La vista micro NO usa Cytoscape.js para el layout principal. Usa un **diagrama tipo swim-lane renderizado con HTML/CSS** (mas legible para flujos secuenciales):

```
┌──────────────┐                              ┌──────────────┐
│  COTIZADOR   │                              │   EMISION    │
│     WEB      │                              │   BACKEND    │
└──────┬───────┘                              └──────┬───────┘
       │                                             │
       │  ══════ Solicitar Cotizacion ═══════▶       │
       │  HU-003                          HU-012     │
       │  ◆ Cotizacion →                             │
       │                           ← ◆ Poliza ⚠     │
       │  Contrato: API Cotizacion (REST v1.2.0)     │
       │                                             │
       │       ◀┄┄┄ Notificar Pago ┄┄┄┄┄┄┄┄┄       │
       │  HU-007                          HU-016     │
       │                  ◆ Pago (evento) →          │
       │  Contrato: Evt Pago (async v1.0.0)          │
       │                                             │
```

Esto se renderiza con elementos HTML estilizados (divs con flex), no con canvas. Las ventajas:
- Mas legible que un grafo para flujos lineales.
- Facilita la interaccion (hover, click en cada elemento).
- Escala bien verticalmente (scroll).
- Se parece a un diagrama de secuencia — familiar para cualquier desarrollador.

---

## Calculo de la Fuerza de Acoplamiento (Backend)

```python
def _calculate_coupling_edges(apps: list, contracts: list, shared_entities: list) -> list[dict]:
    """Calcula la fuerza de acoplamiento entre cada par de apps.

    La fuerza es: num_contratos_entre_ellas + num_entidades_compartidas.
    Solo genera edges para pares con coupling_strength > 0.

    Returns:
        Lista de edges con coupling_strength, contracts_count,
        shared_entities_count, y sync_type.
    """
    edges = []
    app_ids = [a.app_id for a in apps]

    for i, app_a in enumerate(app_ids):
        for app_b in app_ids[i+1:]:
            # Contratos entre app_a y app_b
            pair_contracts = [
                c for c in contracts
                if (c.provider_app == app_a and app_b in c.consumer_apps)
                or (c.provider_app == app_b and app_a in c.consumer_apps)
            ]
            # Entidades compartidas entre ambas
            pair_entities = [
                e for e in shared_entities
                if app_a in e.defined_in_apps and app_b in e.defined_in_apps
            ]

            strength = len(pair_contracts) + len(pair_entities)
            if strength == 0:
                continue

            # Determinar sync_type
            types = set(c.type for c in pair_contracts)
            sync = "async" if types <= {"async_event"} else "sync" if "async_event" not in types else "mixed"

            edges.append({
                "source": f"app:{app_a}",
                "target": f"app:{app_b}",
                "type": "coupling",
                "coupling_strength": strength,
                "contracts_count": len(pair_contracts),
                "shared_entities_count": len(pair_entities),
                "sync_type": sync,
                "label": f"{len(pair_contracts)} contratos · {len(pair_entities)} entidades",
            })

    return edges
```

## Construccion de Flujos Micro (Backend)

```python
def _build_flows_between_apps(ecosystem, app_a_id: str, app_b_id: str) -> list[dict]:
    """Construye los flujos concretos entre dos apps.

    Cruza contratos (quien provee, quien consume) con las HUs de cada app
    para identificar los flujos punto A → punto B.

    Para cada contrato entre las apps:
    1. Identifica la HU del provider que "genera" el flujo.
    2. Identifica la HU del consumer que "recibe" el flujo.
    3. Identifica las entidades que viajan en ese contrato.
    4. Marca divergencias en entidades compartidas.

    Returns:
        Lista de flujos con origin, target, contract, entities_in_transit.
    """
```

La logica cruza:
- `contracts` donde `provider_app` es una de las dos apps y la otra esta en `consumer_apps`.
- `entities_involved` del contrato con `shared_entities` para detectar divergencias.
- Las HUs de cada app (via su `.hu-memory/`) que mencionan las entidades del contrato, para vincular HU origen/destino.

## Calculo de Salud

```python
def _calculate_health(app_id: str, conflicts: list, shared_entities: list) -> str:
    """Calcula el indicador de salud de una app.

    Returns:
        'green', 'yellow', o 'red'.
    """
    app_conflicts = [c for c in conflicts if app_id in c.apps_involved]
    app_divergences = [
        e for e in shared_entities
        if app_id in e.defined_in_apps and not e.is_consistent
    ]

    critical = [c for c in app_conflicts if c.severity == "high"]
    if critical:
        return "red"
    if app_conflicts or app_divergences:
        return "yellow"
    return "green"
```

---

## Diseno de la UI — Layout

### Estructura General del HTML

```html
<body>
  <!-- Nav: selector de vista -->
  <nav class="view-selector">
    <a href="/" class="view-tab">Red Neuronal</a>
    <a href="/ecosystem" class="view-tab active">Ecosistema</a>
  </nav>

  <!-- Toolbar: ecosistema selector + vista macro/micro + filtros -->
  <div id="toolbar">
    <select id="selectorEcosystem">...</select>
    <div class="toggle-group">
      <button id="btn-macro" class="active">Macro</button>
      <button id="btn-micro">Micro</button>
    </div>
    <!-- Filtros (solo en macro) -->
    <button class="filter-btn active">REST</button>
    <button class="filter-btn active">GraphQL</button>
    <button class="filter-btn active">Async</button>
    <button class="filter-btn">Solo conflictos</button>
  </div>

  <!-- Vista Macro: Cytoscape.js canvas -->
  <div id="view-macro">
    <div id="cy-ecosystem"></div>
  </div>

  <!-- Vista Micro: diagrama de flujos HTML -->
  <div id="view-micro" style="display:none">
    <div id="micro-header">...</div>
    <div id="micro-flows">...</div>
  </div>

  <!-- Panel lateral de detalle -->
  <div id="panel">...</div>

  <!-- Leyenda -->
  <div id="legend">...</div>
</body>
```

### Vista Macro — Cytoscape.js Config

```javascript
// Layout: cose-bilkent para compound nodes (clusters cohesivos)
const macroLayout = {
  name: 'cose-bilkent',
  quality: 'proof',
  animate: true,
  animationDuration: 800,
  nodeDimensionsIncludeLabels: true,
  idealEdgeLength: 250,
  nodeRepulsion: 10000,
  edgeElasticity: 0.3,
  nestingFactor: 0.15,
  gravity: 0.2,
  tile: true,
  tilingPaddingVertical: 40,
  tilingPaddingHorizontal: 40,
};

// Estilos principales
const macroStyles = [
  // Cluster (compound node — apps cohesivas)
  { selector: 'node[type="cluster"]', style: {
    'background-color': 'rgba(255,255,255,0.02)',
    'border-width': 1, 'border-style': 'dashed',
    'border-color': 'rgba(255,255,255,0.15)',
    'border-radius': 20,
    'label': 'data(label)', 'font-size': 10,
    'text-valign': 'top', 'text-halign': 'center',
    'color': 'rgba(255,255,255,0.35)',
    'padding': 30,
  }},
  // App node
  { selector: 'node[type="app"]', style: {
    'shape': 'round-rectangle',
    'width': 180, 'height': 90,
    'background-color': 'rgba(10,132,255,0.15)',
    'border-width': 2, 'border-color': '#0a84ff',
    'label': 'data(label)', 'font-size': 13, 'font-weight': 500,
    'text-valign': 'center', 'text-halign': 'center',
    'color': 'rgba(255,255,255,0.9)',
    'shadow-blur': 20, 'shadow-color': '#0a84ff', 'shadow-opacity': 0.3,
  }},
  // Health badges via border-color override
  { selector: 'node[health="green"]', style: { 'border-color': '#30d158' }},
  { selector: 'node[health="yellow"]', style: { 'border-color': '#ff9f0a' }},
  { selector: 'node[health="red"]', style: { 'border-color': '#ff453a' }},
  // Coupling edges — grosor proporcional
  { selector: 'edge[type="coupling"]', style: {
    'width': 'mapData(coupling_strength, 1, 10, 2, 8)',
    'curve-style': 'bezier',
    'label': 'data(label)', 'font-size': 9,
    'text-rotation': 'autorotate',
    'color': 'rgba(255,255,255,0.5)',
    'text-outline-color': 'rgba(0,0,0,0.8)', 'text-outline-width': 2,
  }},
  // Sync type coloring
  { selector: 'edge[sync_type="sync"]', style: {
    'line-color': 'rgba(10,132,255,0.6)',
    'target-arrow-color': '#0a84ff', 'target-arrow-shape': 'triangle',
  }},
  { selector: 'edge[sync_type="async"]', style: {
    'line-color': 'rgba(255,159,10,0.6)', 'line-style': 'dotted',
    'target-arrow-color': '#ff9f0a', 'target-arrow-shape': 'triangle',
  }},
  { selector: 'edge[sync_type="mixed"]', style: {
    'line-color': 'rgba(191,90,242,0.6)',
    'target-arrow-color': '#bf5af2', 'target-arrow-shape': 'triangle',
  }},
];
```

### Vista Micro — Diagrama de Flujos (HTML/CSS)

La vista micro es un **diagrama de secuencia** renderizado con HTML, no con Cytoscape.js. Es mas legible para flujos lineales y se parece a la convencion que cualquier desarrollador conoce.

```css
/* Layout: dos columnas (apps) con flujos entre ellas */
.micro-container {
  display: flex;
  gap: 0;
  height: 100%;
}
.micro-column {
  width: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.micro-column .app-header {
  /* Bloque de la app: nombre, equipo, HUs */
  padding: 16px;
  border-radius: 12px;
  background: rgba(10,132,255,0.12);
  border: 1px solid rgba(10,132,255,0.3);
}
.micro-column .lifeline {
  /* Linea vertical tipo diagrama de secuencia */
  width: 2px;
  flex: 1;
  background: rgba(255,255,255,0.1);
}
.micro-flows {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 40px 20px;
  overflow-y: auto;
}
.flow-card {
  /* Cada flujo como una card horizontal */
  padding: 16px;
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  cursor: pointer;
  transition: border-color 0.2s;
}
.flow-card:hover {
  border-color: rgba(10,132,255,0.4);
}
.flow-arrow {
  /* Flecha direccional: → o ← */
  display: flex;
  align-items: center;
  gap: 8px;
}
.flow-arrow.a-to-b { flex-direction: row; }
.flow-arrow.b-to-a { flex-direction: row-reverse; }
.entity-pill {
  display: inline-flex;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 11px;
}
.entity-pill.consistent {
  background: rgba(48,209,88,0.1);
  border: 1px solid rgba(48,209,88,0.2);
  color: #30d158;
}
.entity-pill.divergent {
  background: rgba(255,69,58,0.1);
  border: 1px solid rgba(255,69,58,0.3);
  color: #ff453a;
  animation: pulse 2s infinite;
}
```

### Transicion Macro ↔ Micro

```javascript
// Click en edge del macro → transicion a micro
cy.on('tap', 'edge[type="coupling"]', async function(evt) {
  const appA = evt.target.data('source').replace('app:', '');
  const appB = evt.target.data('target').replace('app:', '');
  await switchToMicro(appA, appB);
});

async function switchToMicro(appA, appB) {
  // Fade out macro
  document.getElementById('view-macro').style.opacity = '0';
  
  // Fetch flujos
  const res = await fetch(`/api/eco/flows/${ecoId}/${appA}/${appB}`);
  const data = await res.json();
  
  // Render micro
  renderMicroView(data);
  
  // Swap views
  setTimeout(() => {
    document.getElementById('view-macro').style.display = 'none';
    document.getElementById('view-micro').style.display = 'flex';
    document.getElementById('view-micro').style.opacity = '1';
  }, 300);
}

function backToMacro() {
  // Reverse transition
  document.getElementById('view-micro').style.opacity = '0';
  setTimeout(() => {
    document.getElementById('view-micro').style.display = 'none';
    document.getElementById('view-macro').style.display = 'block';
    document.getElementById('view-macro').style.opacity = '1';
  }, 300);
}
```

### Navegacion al Detalle (Workspace)

```javascript
// Desde micro, click en "Ver en [App]" o en una HU
async function navigateToWorkspace(appId, storyId) {
  // 1. Activar el workspace de esa app
  await fetch('/api/workspaces/switch', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ workspace_id: appId })
  });
  
  // 2. Navegar a la red neuronal con parametro de highlight
  window.location.href = `/?highlight=${storyId}`;
}
```

---

## Navegacion entre Vistas

Ambos HTMLs incluyen el selector de vista:

```html
<nav class="view-selector">
  <a href="/" class="view-tab" id="tab-neural">Red Neuronal</a>
  <a href="/ecosystem" class="view-tab" id="tab-ecosystem">Ecosistema</a>
</nav>
```

Estilo: toggle-group con el tab activo resaltado. Navegacion por page-load (no SPA).

---

## Dependencias

No se agregan dependencias nuevas:
- `starlette` (ya en requirements.txt).
- `uvicorn` (ya en requirements.txt).
- Cytoscape.js via CDN (ya usado).
- Extension `cytoscape-cose-bilkent` via CDN (para compound nodes y layout del macro).

## Consideraciones de Seguridad

- Servidor escucha en localhost. En Docker se expone via port mapping.
- No hay autenticacion (herramienta de desarrollo local).
- No se exponen secrets — solo metadata de estructura.
- Inputs validados: `ecosystem_id`, `app_id` se validan contra el registro.
