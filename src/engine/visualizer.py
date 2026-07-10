"""Graph Visualizer: servidor HTTP en background con UI interactiva Cytoscape.js.

Se levanta como thread en background al arrancar el MCP.
Sirve en localhost:9751 una UI web interactiva para explorar el grafo de HUs.
Layout jerarquico con entidades en periferia y spacing equidistante.
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
HTML_PATH = Path(__file__).parent / "visualizer_ui.html"


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
                "label": story.id,
                "title": story.title,
                "status": story.status,
                "entities": story.entities_detected,
                "flows": story.flows_detected,
                "experts": [e.expert.value for e in story.expert_analysis],
                "gaps": story.total_gaps,
                "questions": story.total_questions,
                "complexity": story.complexity_tags,
                "type": "story",
                "dependencies": story.dependencies,
            }
        })

    for entity in entities:
        nodes.append({
            "data": {
                "id": f"entity:{entity.name}",
                "label": entity.name,
                "type": "entity",
                "appears_in": entity.appears_in,
            }
        })

    for flow in flows:
        nodes.append({
            "data": {
                "id": f"flow:{flow.name}",
                "label": flow.name.replace("_", " "),
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

    for entity in entities:
        for story_id in entity.appears_in:
            edges.append({
                "data": {
                    "source": story_id,
                    "target": f"entity:{entity.name}",
                    "relation": "has_entity",
                    "weight": 0.3,
                }
            })

    for flow in flows:
        for story_id in flow.stories_involved:
            edges.append({
                "data": {
                    "source": story_id,
                    "target": f"flow:{flow.name}",
                    "relation": "in_flow",
                    "weight": 0.3,
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
    for _, tgt, attrs in memory.graph.out_edges(story_id, data=True):
        neighbors.append({"id": tgt, "direction": "out", "relation": attrs.get("relation", "related_to")})
    for src, _, attrs in memory.graph.in_edges(story_id, data=True):
        neighbors.append({"id": src, "direction": "in", "relation": attrs.get("relation", "related_to")})

    return {"node": story_id, "neighbors": neighbors}


async def route_index(request):
    """Sirve la UI HTML principal."""
    html = HTML_PATH.read_text(encoding="utf-8")
    return HTMLResponse(content=html, status_code=200)


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


def start_visualizer() -> None:
    """Arranca el servidor de visualizacion en un thread en background."""
    def _run():
        logger.info("Graph Visualizer arrancando en http://localhost:%d", VISUALIZER_PORT)
        uvicorn.run(app, host=VISUALIZER_HOST, port=VISUALIZER_PORT, log_level="warning")

    thread = threading.Thread(target=_run, daemon=True, name="graph-visualizer")
    thread.start()
    logger.info("Graph Visualizer thread iniciado (puerto %d)", VISUALIZER_PORT)
