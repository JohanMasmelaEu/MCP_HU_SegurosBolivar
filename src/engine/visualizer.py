"""Graph Visualizer: servidor HTTP en background con UI interactiva Cytoscape.js.

Se levanta como thread en background al arrancar el MCP.
Sirve en localhost:9751 una UI web interactiva para explorar el grafo de HUs.
"""

import json
import logging
import threading
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from src.engine.memory import get_memory

logger = logging.getLogger("mcp_hu.engine.visualizer")

VISUALIZER_PORT = 9751
VISUALIZER_HOST = "0.0.0.0"


def _get_graph_data() -> dict:
    """Obtiene los datos del grafo para el frontend."""
    memory = get_memory()
    if not memory.is_initialized:
        return {"nodes": [], "edges": []}

    stories = memory.get_all_stories()
    entities = memory.get_entities()
    flows = memory.get_flows()

    nodes = []
    for story in stories:
        nodes.append({
            "data": {
                "id": story.id,
                "label": f"{story.id}\n{story.title[:30]}",
                "title": story.title,
                "status": story.status,
                "entities": story.entities_detected,
                "flows": story.flows_detected,
                "experts": [e.expert.value for e in story.expert_analysis],
                "gaps": story.total_gaps,
                "questions": story.total_questions,
                "complexity": story.complexity_tags,
                "type": "story",
            }
        })

    # Nodos de entidades (secundarios, mas pequenos)
    for entity in entities:
        nodes.append({
            "data": {
                "id": f"entity:{entity.name}",
                "label": entity.name,
                "type": "entity",
                "appears_in": entity.appears_in,
            }
        })

    # Nodos de flujos
    for flow in flows:
        nodes.append({
            "data": {
                "id": f"flow:{flow.name}",
                "label": flow.name,
                "type": "flow",
                "status": flow.status,
                "stories": flow.stories_involved,
            }
        })

    edges = []
    graph = memory.graph
    for src, tgt, attrs in graph.edges(data=True):
        edges.append({
            "data": {
                "source": src,
                "target": tgt,
                "relation": attrs.get("relation", "related_to"),
                "weight": attrs.get("weight", 1.0),
            }
        })

    # Edges de entidad a story
    for entity in entities:
        for story_id in entity.appears_in:
            edges.append({
                "data": {
                    "source": story_id,
                    "target": f"entity:{entity.name}",
                    "relation": "has_entity",
                    "weight": 0.5,
                }
            })

    # Edges de flow a story
    for flow in flows:
        for story_id in flow.stories_involved:
            edges.append({
                "data": {
                    "source": story_id,
                    "target": f"flow:{flow.name}",
                    "relation": "in_flow",
                    "weight": 0.5,
                }
            })

    return {"nodes": nodes, "edges": edges}


def _get_story_detail(story_id: str) -> dict:
    """Obtiene detalle completo de una HU."""
    memory = get_memory()
    story = memory.get_story(story_id)
    if not story:
        return {"error": f"HU '{story_id}' no encontrada"}
    return story.model_dump(mode="json")


def _get_neighbors(story_id: str) -> dict:
    """Obtiene vecinos directos de un nodo."""
    memory = get_memory()
    if not memory.graph.has_node(story_id):
        return {"node": story_id, "neighbors": []}

    neighbors = []
    # Vecinos salientes
    for _, tgt, attrs in memory.graph.out_edges(story_id, data=True):
        neighbors.append({"id": tgt, "direction": "out", "relation": attrs.get("relation", "related_to")})
    # Vecinos entrantes
    for src, _, attrs in memory.graph.in_edges(story_id, data=True):
        neighbors.append({"id": src, "direction": "in", "relation": attrs.get("relation", "related_to")})

    return {"node": story_id, "neighbors": neighbors}


# ─── ROUTES ──────────────────────────────────────────────────────────────────────


async def route_index(request):
    """Sirve la UI HTML principal."""
    return HTMLResponse(content=_get_html(), status_code=200)


async def route_graph(request):
    """API: datos completos del grafo."""
    return JSONResponse(_get_graph_data())


async def route_story(request):
    """API: detalle de una HU."""
    story_id = request.path_params["story_id"]
    return JSONResponse(_get_story_detail(story_id))


async def route_neighbors(request):
    """API: vecinos de un nodo."""
    story_id = request.path_params["story_id"]
    return JSONResponse(_get_neighbors(story_id))


app = Starlette(routes=[
    Route("/", route_index),
    Route("/api/graph", route_graph),
    Route("/api/story/{story_id}", route_story),
    Route("/api/neighbors/{story_id}", route_neighbors),
])


# ─── BACKGROUND THREAD ───────────────────────────────────────────────────────────


def start_visualizer() -> None:
    """Arranca el servidor de visualizacion en un thread en background."""
    def _run():
        logger.info("Graph Visualizer arrancando en http://localhost:%d", VISUALIZER_PORT)
        uvicorn.run(app, host=VISUALIZER_HOST, port=VISUALIZER_PORT, log_level="warning")

    thread = threading.Thread(target=_run, daemon=True, name="graph-visualizer")
    thread.start()
    logger.info("Graph Visualizer thread iniciado (puerto %d)", VISUALIZER_PORT)


# ─── HTML FRONTEND ───────────────────────────────────────────────────────────────


def _get_html() -> str:
    """Retorna el HTML completo de la UI con Cytoscape.js embebido."""
    return """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HU Graph Viewer - MCP_HU_SegurosBolivar</title>
    <script src="https://unpkg.com/cytoscape@3.30.4/dist/cytoscape.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; display: flex; height: 100vh; background: #1a1a2e; color: #eaeaea; }
        #cy { flex: 1; background: #16213e; }
        #panel { width: 380px; background: #0f3460; overflow-y: auto; padding: 16px; border-left: 1px solid #1a1a2e; display: none; }
        #panel.active { display: block; }
        #panel h2 { color: #e94560; margin-bottom: 8px; font-size: 14px; }
        #panel h3 { color: #00d2d3; margin: 12px 0 4px; font-size: 12px; text-transform: uppercase; }
        #panel p, #panel li { font-size: 12px; line-height: 1.5; color: #c8d6e5; }
        #panel ul { padding-left: 16px; }
        #panel .tag { display: inline-block; background: #e94560; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px; margin: 2px; }
        #panel .tag.entity { background: #00d2d3; color: #1a1a2e; }
        #panel .tag.flow { background: #feca57; color: #1a1a2e; }
        #toolbar { position: absolute; top: 12px; left: 12px; z-index: 10; display: flex; gap: 8px; }
        #toolbar button { background: #e94560; border: none; color: white; padding: 8px 14px; border-radius: 4px; cursor: pointer; font-size: 12px; }
        #toolbar button:hover { background: #c0392b; }
        #toolbar select { background: #0f3460; color: #eaeaea; border: 1px solid #e94560; padding: 6px; border-radius: 4px; font-size: 12px; }
        .status-badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: bold; }
        .status-analyzed { background: #feca57; color: #1a1a2e; }
        .status-refined { background: #00d2d3; color: #1a1a2e; }
        .status-completed { background: #2ecc71; color: #1a1a2e; }
        #legend { position: absolute; bottom: 12px; left: 12px; background: rgba(15,52,96,0.9); padding: 12px; border-radius: 6px; font-size: 11px; }
        #legend div { margin: 4px 0; display: flex; align-items: center; gap: 6px; }
        #legend span.dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
    </style>
</head>
<body>
    <div id="toolbar">
        <button onclick="resetGraph()">Reset</button>
        <button onclick="toggleEntities()">Entidades</button>
        <button onclick="toggleFlows()">Flujos</button>
        <select id="filterEntity" onchange="filterByEntity(this.value)">
            <option value="">Filtrar por entidad...</option>
        </select>
    </div>
    <div id="cy"></div>
    <div id="panel">
        <h2 id="panel-title"></h2>
        <div id="panel-content"></div>
    </div>
    <div id="legend">
        <div><span class="dot" style="background:#e94560"></span> HU (analyzed)</div>
        <div><span class="dot" style="background:#feca57"></span> HU (refined)</div>
        <div><span class="dot" style="background:#2ecc71"></span> HU (completed)</div>
        <div><span class="dot" style="background:#00d2d3"></span> Entidad</div>
        <div><span class="dot" style="background:#feca57"></span> Flujo</div>
        <div><span class="dot" style="background:#0f3460;border:2px solid #e94560"></span> depends_on</div>
        <div><span class="dot" style="background:#0f3460;border:2px solid #2ecc71"></span> impacts</div>
    </div>
    <script>
        let cy;
        let allElements = [];
        let showEntities = false;
        let showFlows = false;

        async function init() {
            const res = await fetch('/api/graph');
            const data = await res.json();
            allElements = [...data.nodes, ...data.edges];

            // Populate entity filter
            const entitySelect = document.getElementById('filterEntity');
            const entities = data.nodes.filter(n => n.data.type === 'entity');
            entities.forEach(e => {
                const opt = document.createElement('option');
                opt.value = e.data.id;
                opt.textContent = e.data.label;
                entitySelect.appendChild(opt);
            });

            renderGraph(allElements.filter(e => e.data.type !== 'entity' && e.data.type !== 'flow' && e.data.relation !== 'has_entity' && e.data.relation !== 'in_flow'));
        }

        function renderGraph(elements) {
            cy = cytoscape({
                container: document.getElementById('cy'),
                elements: elements,
                style: [
                    { selector: 'node[type="story"]', style: { 'label': 'data(label)', 'text-wrap': 'wrap', 'text-max-width': '100px', 'font-size': '10px', 'color': '#eaeaea', 'text-valign': 'bottom', 'text-margin-y': 5, 'background-color': (ele) => statusColor(ele.data('status')), 'width': 40, 'height': 40 }},
                    { selector: 'node[type="entity"]', style: { 'label': 'data(label)', 'font-size': '9px', 'color': '#00d2d3', 'background-color': '#00d2d3', 'width': 20, 'height': 20, 'shape': 'diamond' }},
                    { selector: 'node[type="flow"]', style: { 'label': 'data(label)', 'font-size': '9px', 'color': '#feca57', 'background-color': '#feca57', 'width': 20, 'height': 20, 'shape': 'rectangle' }},
                    { selector: 'edge[relation="depends_on"]', style: { 'line-color': '#e94560', 'target-arrow-color': '#e94560', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier', 'width': 2 }},
                    { selector: 'edge[relation="impacts"]', style: { 'line-color': '#2ecc71', 'target-arrow-color': '#2ecc71', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier', 'width': 2 }},
                    { selector: 'edge[relation="related_to"]', style: { 'line-color': '#576574', 'curve-style': 'bezier', 'width': 1, 'line-style': 'dashed' }},
                    { selector: 'edge[relation="has_entity"]', style: { 'line-color': '#00d2d3', 'curve-style': 'bezier', 'width': 1, 'opacity': 0.5 }},
                    { selector: 'edge[relation="in_flow"]', style: { 'line-color': '#feca57', 'curve-style': 'bezier', 'width': 1, 'opacity': 0.5 }},
                    { selector: ':selected', style: { 'border-width': 3, 'border-color': '#ffffff' }},
                    { selector: '.highlighted', style: { 'border-width': 3, 'border-color': '#e94560', 'opacity': 1 }},
                    { selector: '.faded', style: { 'opacity': 0.15 }}
                ],
                layout: { name: 'cose', nodeRepulsion: 8000, idealEdgeLength: 120, animate: true },
            });

            cy.on('tap', 'node[type="story"]', async function(evt) {
                const id = evt.target.data('id');
                highlightNeighbors(evt.target);
                await showStoryDetail(id);
            });

            cy.on('tap', function(evt) {
                if (evt.target === cy) { resetHighlight(); hidePanel(); }
            });
        }

        function statusColor(status) {
            if (status === 'completed') return '#2ecc71';
            if (status === 'refined') return '#00d2d3';
            return '#e94560';
        }

        function highlightNeighbors(node) {
            cy.elements().addClass('faded');
            node.removeClass('faded').addClass('highlighted');
            node.neighborhood().removeClass('faded');
        }

        function resetHighlight() {
            cy.elements().removeClass('faded').removeClass('highlighted');
        }

        async function showStoryDetail(id) {
            const res = await fetch(`/api/story/${id}`);
            const story = await res.json();
            if (story.error) return;

            const panel = document.getElementById('panel');
            const title = document.getElementById('panel-title');
            const content = document.getElementById('panel-content');

            title.textContent = `${story.id} - ${story.title}`;
            let html = `<span class="status-badge status-${story.status}">${story.status}</span>`;
            html += `<h3>Narrativa</h3><p><b>Como</b> ${story.narrative.as_a}<br><b>Quiero</b> ${story.narrative.i_want}<br><b>Para</b> ${story.narrative.so_that}</p>`;
            html += `<h3>Entidades</h3><div>${story.entities_detected.map(e => `<span class="tag entity">${e}</span>`).join('')}</div>`;
            html += `<h3>Flujos</h3><div>${story.flows_detected.map(f => `<span class="tag flow">${f}</span>`).join('')}</div>`;
            html += `<h3>Complejidad</h3><div>${story.complexity_tags.map(t => `<span class="tag">${t}</span>`).join('')}</div>`;
            if (story.dependencies.length) html += `<h3>Depende de</h3><ul>${story.dependencies.map(d => `<li>${d}</li>`).join('')}</ul>`;
            if (story.expert_analysis.length) {
                html += `<h3>Expertos</h3><ul>${story.expert_analysis.map(e => `<li><b>${e.expert}</b>: ${e.gaps.length} gaps, ${e.questions.length} preguntas</li>`).join('')}</ul>`;
            }
            html += `<h3>Gaps: ${story.total_gaps} | Preguntas: ${story.total_questions}</h3>`;
            content.innerHTML = html;
            panel.classList.add('active');
        }

        function hidePanel() { document.getElementById('panel').classList.remove('active'); }

        function resetGraph() {
            resetHighlight();
            hidePanel();
            const filtered = allElements.filter(e => {
                if (!showEntities && (e.data.type === 'entity' || e.data.relation === 'has_entity')) return false;
                if (!showFlows && (e.data.type === 'flow' || e.data.relation === 'in_flow')) return false;
                return true;
            });
            cy.elements().remove();
            cy.add(filtered);
            cy.layout({ name: 'cose', nodeRepulsion: 8000, idealEdgeLength: 120, animate: true }).run();
        }

        function toggleEntities() { showEntities = !showEntities; resetGraph(); }
        function toggleFlows() { showFlows = !showFlows; resetGraph(); }

        function filterByEntity(entityId) {
            if (!entityId) { resetGraph(); return; }
            resetHighlight();
            const node = cy.getElementById(entityId);
            if (node.length) { highlightNeighbors(node); }
        }

        init();
    </script>
</body>
</html>"""
