"""Graph Visualizer: servidor HTTP en background con UI interactiva Cytoscape.js.

Se levanta como thread en background al arrancar el MCP.
Sirve en localhost:9751 una UI web interactiva para explorar el grafo de HUs.
Layout jerarquico con entidades en periferia y spacing equidistante.
Incluye selector de workspaces y ecosistemas.
"""

import json
import logging
import threading
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles

from src.engine.memory import get_memory
from src.engine.spec_engine import get_spec_engine
from src.engine.workspace_manager import get_workspace_manager
from src.engine.ecosystem_manager import get_ecosystem_manager
from src.engine.ecosystem_visualizer import (
    route_ecosystem_index,
    route_eco_ecosystems,
    route_eco_graph,
    route_eco_flows,
    route_eco_app_detail,
    route_eco_health,
    route_eco_status,
    route_constellation_graph,
    route_constellation_spec_detail,
    route_constellation_gaps,
)
from src.engine.spec_visualizer import (
    route_spec_index,
    route_story_index,
    route_api_specs,
    route_api_spec_detail,
    route_api_spec_update_layer,
    route_api_spec_refine,
    route_api_spec_impact,
    route_api_spec_stories,
    route_api_spec_associations,
)

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
    # Collect valid node IDs to filter orphan edges
    valid_node_ids = {n["data"]["id"] for n in nodes}

    graph = memory.graph
    for src, tgt, attrs in graph.edges(data=True):
        if src in valid_node_ids and tgt in valid_node_ids:
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
            if story_id in valid_node_ids:
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
            if story_id in valid_node_ids:
                edges.append({
                    "data": {
                        "source": story_id,
                        "target": f"flow:{flow.name}",
                        "relation": "in_flow",
                        "weight": 0.3,
                }
            })

    # ─── SDD Spec Item nodes + HU→Item edges (associations) ──────────────────
    spec_engine = get_spec_engine()
    if spec_engine:
        for spec_summary in spec_engine.list_specs():
            spec = spec_engine.get_spec(spec_summary["spec_id"])
            if not spec:
                continue
            for layer_name, layer_content in spec.layers.items():
                if not layer_content.associations:
                    continue
                for item_id, hu_ids in layer_content.associations.items():
                    if not hu_ids:
                        continue
                    # Create a node for the SDD item
                    node_id = f"sdd:{spec.spec_id}:{layer_name}:{item_id}"
                    nodes.append({
                        "data": {
                            "id": node_id,
                            "label": item_id,
                            "type": "sdd_item",
                            "spec_id": spec.spec_id,
                            "spec_name": spec.project_name,
                            "layer": layer_name,
                            "item_id": item_id,
                        }
                    })
                    valid_node_ids.add(node_id)
                    # Create edges from each associated HU to this item
                    for hu_id in hu_ids:
                        if hu_id in valid_node_ids:
                            edges.append({
                                "data": {
                                    "source": hu_id,
                                    "target": node_id,
                                    "relation": "implements",
                                    "weight": 0.6,
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


async def route_story_feedback(request: Request):
    """API: agrega una pregunta o gap a una HU.

    POST /api/story/{story_id}/feedback
    Body JSON:
    {
        "type": "question" | "gap",
        "text": "Texto de la pregunta o gap",
        "ac_reference": "Given/When/Then text (opcional)"
    }

    Persiste la pregunta o gap en el expert 'negocio' de la HU
    y actualiza los contadores total_gaps / total_questions.
    """
    story_id = request.path_params["story_id"]
    memory = get_memory()
    story = memory.get_story(story_id)
    if not story:
        return JSONResponse({"error": f"HU '{story_id}' no encontrada"}, status_code=404)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Body JSON inválido."}, status_code=400)

    feedback_type = body.get("type", "")
    text = body.get("text", "").strip()
    ac_ref = body.get("ac_reference", "").strip()

    if feedback_type not in ("question", "gap"):
        return JSONResponse({"error": "type debe ser 'question' o 'gap'."}, status_code=400)
    if not text:
        return JSONResponse({"error": "text es requerido."}, status_code=400)

    # Build full text with AC reference if provided
    full_text = text
    if ac_ref:
        full_text = f"[Ref AC: {ac_ref}] {text}"

    # Find or create a 'negocio' expert section to add the feedback
    from src.models.story import ExpertType
    target_expert = None
    for expert_section in story.expert_analysis:
        if expert_section.expert == ExpertType.NEGOCIO:
            target_expert = expert_section
            break

    if not target_expert:
        from src.models.story import ExpertSection
        target_expert = ExpertSection(expert=ExpertType.NEGOCIO)
        story.expert_analysis.append(target_expert)

    if feedback_type == "question":
        target_expert.questions.append(full_text)
        story.total_questions += 1
        # Crear Question estructurada
        from src.models.story import Question
        question = Question(
            text=text,
            expert=target_expert.expert.value,
            ac_reference=ac_ref,
            created_by=body.get("created_by", "user"),
        )
        story.structured_questions.append(question)
    else:
        target_expert.gaps.append(full_text)
        story.total_gaps += 1

    from datetime import datetime
    story.updated_at = datetime.now().isoformat()
    memory.save_story(story)

    return JSONResponse({
        "status": "success",
        "story_id": story_id,
        "type": feedback_type,
        "text": full_text,
        "total_gaps": story.total_gaps,
        "total_questions": story.total_questions,
        "question_id": question.id if feedback_type == "question" else None,
    })


async def route_resolve_question(request: Request):
    """API: resuelve una pregunta de una HU.

    POST /api/story/{story_id}/question/{question_id}/resolve
    Body JSON:
    {
        "resolved_by": "nombre de quien resuelve",
        "note": "respuesta o nota de resolucion"
    }
    """
    story_id = request.path_params["story_id"]
    question_id = request.path_params["question_id"]
    memory = get_memory()
    story = memory.get_story(story_id)
    if not story:
        return JSONResponse({"error": f"HU '{story_id}' no encontrada"}, status_code=404)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Body JSON invalido."}, status_code=400)

    resolved_by = body.get("resolved_by", "").strip()
    note = body.get("note", "").strip()

    if not resolved_by:
        return JSONResponse({"error": "resolved_by es requerido."}, status_code=400)

    # Buscar la pregunta en structured_questions
    target_question = None
    for q in story.structured_questions:
        if q.id == question_id:
            target_question = q
            break

    if not target_question:
        return JSONResponse({"error": f"Pregunta '{question_id}' no encontrada."}, status_code=404)

    if target_question.status.value == "resolved":
        return JSONResponse({"error": "La pregunta ya esta resuelta."}, status_code=400)

    # Resolver
    from src.models.story import QuestionResolution, QuestionStatus
    target_question.status = QuestionStatus.RESOLVED
    target_question.resolution = QuestionResolution(
        resolved_by=resolved_by,
        note=note,
    )

    from datetime import datetime
    story.updated_at = datetime.now().isoformat()
    memory.save_story(story)

    return JSONResponse({
        "status": "success",
        "story_id": story_id,
        "question_id": question_id,
        "resolved_by": resolved_by,
        "resolved_at": target_question.resolution.resolved_at,
        "note": note,
    })


async def route_neighbors(request):
    """API: vecinos de un nodo."""
    story_id = request.path_params["story_id"]
    return JSONResponse(_get_neighbors(story_id))


# ─── WORKSPACE & ECOSYSTEM MANAGEMENT API ────────────────────────────────────────


async def route_workspaces(request: Request):
    """API: lista workspaces disponibles y activo."""
    manager = get_workspace_manager()
    if not manager:
        return JSONResponse({"workspaces": [], "active": None})

    workspaces = manager.list_workspaces()
    return JSONResponse({
        "workspaces": [w.model_dump(mode="json") for w in workspaces],
        "active": manager.active_workspace_id,
    })


async def route_switch_workspace(request: Request):
    """API: cambia el workspace activo.

    POST /api/workspaces/switch con body {"workspace_id": "..."}
    """
    manager = get_workspace_manager()
    if not manager:
        return JSONResponse({"error": "WorkspaceManager no disponible"}, status_code=500)

    body = await request.json()
    workspace_id = body.get("workspace_id", "")

    if not workspace_id:
        return JSONResponse({"error": "workspace_id requerido"}, status_code=400)

    try:
        manager.switch_workspace(workspace_id)
        return JSONResponse({"status": "ok", "active": workspace_id})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)


async def route_ecosystems(request: Request):
    """API: lista ecosistemas disponibles y activo."""
    eco_manager = get_ecosystem_manager()
    ws_manager = get_workspace_manager()

    if not eco_manager:
        return JSONResponse({"ecosystems": [], "active": None})

    ecosystems = eco_manager.list_ecosystems()
    active_id = ws_manager.active_ecosystem_id if ws_manager else None

    return JSONResponse({
        "ecosystems": ecosystems,
        "active": active_id,
    })


async def route_switch_ecosystem(request: Request):
    """API: cambia el ecosistema activo.

    POST /api/ecosystems/switch con body {"ecosystem_id": "..."}
    """
    eco_manager = get_ecosystem_manager()
    ws_manager = get_workspace_manager()

    if not eco_manager:
        return JSONResponse({"error": "EcosystemManager no disponible"}, status_code=500)

    body = await request.json()
    ecosystem_id = body.get("ecosystem_id", "")

    if not ecosystem_id:
        return JSONResponse({"error": "ecosystem_id requerido"}, status_code=400)

    try:
        eco_manager.switch_ecosystem(ecosystem_id)
        if ws_manager:
            ws_manager.set_active_ecosystem(ecosystem_id)
        return JSONResponse({"status": "ok", "active": ecosystem_id})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)


app = Starlette(routes=[
    Route("/", route_index),
    Route("/api/graph", route_graph),
    Route("/api/story/{story_id}", route_story),
    Route("/api/story/{story_id}/feedback", route_story_feedback, methods=["POST"]),
    Route("/api/story/{story_id}/question/{question_id}/resolve", route_resolve_question, methods=["POST"]),
    Route("/api/neighbors/{story_id}", route_neighbors),
    Route("/api/workspaces", route_workspaces),
    Route("/api/workspaces/switch", route_switch_workspace, methods=["POST"]),
    Route("/api/ecosystems", route_ecosystems),
    Route("/api/ecosystems/switch", route_switch_ecosystem, methods=["POST"]),
    # ─── Ecosystem Graph Visualizer ───────────────────────────────────────────
    Route("/ecosystem", route_ecosystem_index),
    Route("/api/eco/ecosystems", route_eco_ecosystems),
    Route("/api/eco/graph/{ecosystem_id}", route_eco_graph),
    Route("/api/eco/flows/{ecosystem_id}/{app_a}/{app_b}", route_eco_flows),
    Route("/api/eco/app/{ecosystem_id}/{app_id}", route_eco_app_detail),
    Route("/api/eco/health/{ecosystem_id}", route_eco_health),
    Route("/api/eco/status/{ecosystem_id}", route_eco_status),
    # ─── Constellation Visualizer ─────────────────────────────────────────────
    Route("/api/constellation/{ecosystem_id}", route_constellation_graph),
    Route("/api/constellation/{ecosystem_id}/spec/{spec_id}", route_constellation_spec_detail),
    Route("/api/constellation/{ecosystem_id}/gaps", route_constellation_gaps),
    # ─── Spec SDD Visualizer (pantalla dedicada) ──────────────────────────────
    Route("/spec", route_spec_index),
    Route("/story", route_story_index),
    Route("/api/specs", route_api_specs),
    Route("/api/spec/{spec_id}", route_api_spec_detail),
    Route("/api/spec/{spec_id}/layer/{layer}", route_api_spec_update_layer, methods=["PUT"]),
    Route("/api/spec/{spec_id}/refine", route_api_spec_refine, methods=["POST"]),
    Route("/api/spec/{spec_id}/impact", route_api_spec_impact, methods=["POST"]),
    Route("/api/spec/{spec_id}/stories", route_api_spec_stories),
    Route("/api/spec/{spec_id}/associations", route_api_spec_associations, methods=["GET", "POST"]),
])

# Montar archivos estáticos (vendor scripts bundleados en Docker)
_static_path = Path(__file__).parent.parent.parent / "static"
if _static_path.exists():
    app.mount("/static", StaticFiles(directory=str(_static_path)), name="static")


def start_visualizer() -> None:
    """Arranca el servidor de visualizacion en un thread en background."""
    def _run():
        logger.info("Graph Visualizer arrancando en http://localhost:%d", VISUALIZER_PORT)
        uvicorn.run(app, host=VISUALIZER_HOST, port=VISUALIZER_PORT, log_level="warning")

    thread = threading.Thread(target=_run, daemon=True, name="graph-visualizer")
    thread.start()
    logger.info("Graph Visualizer thread iniciado (puerto %d)", VISUALIZER_PORT)
