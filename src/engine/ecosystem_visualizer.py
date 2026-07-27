"""Ecosystem Graph Visualizer: logica backend para la vista de ecosistema.

Provee handlers de rutas API para:
- Grafo macro (topologia de acoplamiento entre apps).
- Flujos micro (punto A → punto B entre dos apps).
- Detalle de apps y salud del ecosistema.

Se integra con el servidor Starlette existente en visualizer.py (puerto 9751).
"""

import logging
from pathlib import Path
from typing import Optional

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from src.engine.ecosystem_manager import get_ecosystem_manager
from src.engine.ecosystem import EcosystemEngine
from src.models.ecosystem import (
    AppRegistration,
    ContractDefinition,
    CrossAppConflict,
    SharedEntity,
)

logger = logging.getLogger("mcp_hu.engine.ecosystem_visualizer")

HTML_PATH = Path(__file__).parent / "ecosystem_visualizer_ui.html"


# ─── ROUTE HANDLERS ─────────────────────────────────────────────────────────────


async def route_ecosystem_index(request: Request) -> HTMLResponse:
    """Sirve la UI HTML de la vista de ecosistema."""
    try:
        html = HTML_PATH.read_text(encoding="utf-8")
        return HTMLResponse(content=html, status_code=200)
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Ecosystem Visualizer UI not found</h1>",
            status_code=500,
        )


async def route_eco_ecosystems(request: Request) -> JSONResponse:
    """API: lista ecosistemas disponibles con metadata."""
    manager = get_ecosystem_manager()
    if not manager:
        return JSONResponse({"ecosystems": [], "active": None})

    ecosystems = manager.list_ecosystems()

    # Determinar el activo
    active_id = None
    active_engine = manager.get_active()
    if active_engine and active_engine.registry:
        active_id = active_engine.registry.ecosystem_id

    return JSONResponse({
        "ecosystems": ecosystems,
        "active": active_id,
    })


async def route_eco_graph(request: Request) -> JSONResponse:
    """API: grafo macro del ecosistema (apps + acoplamiento).

    Retorna nodos (apps, clusters) y edges (fuerza de acoplamiento)
    listos para renderizar en Cytoscape.js.
    """
    ecosystem_id = request.path_params.get("ecosystem_id", "")
    engine = _get_ecosystem_engine(ecosystem_id)

    if not engine:
        return JSONResponse(
            {"error": f"Ecosistema '{ecosystem_id}' no encontrado o no inicializado."},
            status_code=404,
        )

    graph_data = _build_macro_graph(engine)
    return JSONResponse(graph_data)


async def route_eco_flows(request: Request) -> JSONResponse:
    """API: flujos micro entre dos apps (punto A → punto B).

    Retorna los flujos concretos entre un par de apps, incluyendo
    HUs origen/destino, entidades en transito, y contratos.
    """
    ecosystem_id = request.path_params.get("ecosystem_id", "")
    app_a_id = request.path_params.get("app_a", "")
    app_b_id = request.path_params.get("app_b", "")

    engine = _get_ecosystem_engine(ecosystem_id)
    if not engine:
        return JSONResponse(
            {"error": f"Ecosistema '{ecosystem_id}' no encontrado."},
            status_code=404,
        )

    flows_data = _build_flows_between_apps(engine, app_a_id, app_b_id)
    if flows_data is None:
        return JSONResponse(
            {"error": f"Una o ambas apps no encontradas: '{app_a_id}', '{app_b_id}'."},
            status_code=404,
        )

    return JSONResponse(flows_data)


async def route_eco_app_detail(request: Request) -> JSONResponse:
    """API: detalle completo de una app del ecosistema."""
    ecosystem_id = request.path_params.get("ecosystem_id", "")
    app_id = request.path_params.get("app_id", "")

    engine = _get_ecosystem_engine(ecosystem_id)
    if not engine:
        return JSONResponse(
            {"error": f"Ecosistema '{ecosystem_id}' no encontrado."},
            status_code=404,
        )

    app = engine.get_app(app_id)
    if not app:
        return JSONResponse(
            {"error": f"App '{app_id}' no encontrada en el ecosistema."},
            status_code=404,
        )

    deps = engine.get_app_dependencies(app_id)
    shared = engine.get_shared_entities()
    app_shared = [s for s in shared if app_id in s.defined_in_apps]

    contracts_exposed = [
        c for c in engine.get_contracts() if c.provider_app == app_id
    ]
    contracts_consumed = [
        c for c in engine.get_contracts() if app_id in c.consumer_apps
    ]

    return JSONResponse({
        "app_id": app.app_id,
        "name": app.name,
        "description": app.description,
        "team": app.team,
        "coupling_type": app.coupling_type,
        "story_count": app.story_count,
        "entities": app.entities_snapshot,
        "flows": app.flows_snapshot,
        "contracts_exposed": [
            {
                "contract_id": c.contract_id,
                "name": c.name,
                "type": c.type,
                "version": c.version,
                "consumers": c.consumer_apps,
                "entities": c.entities_involved,
            }
            for c in contracts_exposed
        ],
        "contracts_consumed": [
            {
                "contract_id": c.contract_id,
                "name": c.name,
                "type": c.type,
                "version": c.version,
                "provider": c.provider_app,
                "entities": c.entities_involved,
            }
            for c in contracts_consumed
        ],
        "depends_on": deps.get("depends_on", []),
        "depended_by": deps.get("depended_by", []),
        "shared_entities": [
            {
                "entity": s.entity_name,
                "apps": s.defined_in_apps,
                "is_consistent": s.is_consistent,
                "divergence": s.divergence_notes,
                "fields_by_app": s.fields_by_app,
            }
            for s in app_shared
        ],
    })


async def route_eco_health(request: Request) -> JSONResponse:
    """API: indicadores de salud por app del ecosistema."""
    ecosystem_id = request.path_params.get("ecosystem_id", "")

    engine = _get_ecosystem_engine(ecosystem_id)
    if not engine:
        return JSONResponse(
            {"error": f"Ecosistema '{ecosystem_id}' no encontrado."},
            status_code=404,
        )

    conflicts = engine.detect_cross_app_conflicts()
    shared = engine.get_shared_entities()
    apps = engine.get_all_apps()

    health_map: dict[str, dict] = {}
    for app in apps:
        health_info = _calculate_health(app.app_id, conflicts, shared)
        health_map[app.app_id] = health_info

    return JSONResponse({"apps": health_map})


# ─── GRAPH BUILDERS ──────────────────────────────────────────────────────────────


def _build_macro_graph(engine: EcosystemEngine) -> dict:
    """Construye el grafo macro del ecosistema para Cytoscape.js.

    Genera:
    - Compound nodes (clusters) para apps cohesivas.
    - Nodos app con metadata y health.
    - Edges de acoplamiento con grosor proporcional.

    Args:
        engine: EcosystemEngine inicializado.

    Returns:
        Dict con ecosystem info, nodes[] y edges[] para Cytoscape.js.
    """
    registry = engine.registry
    if not registry:
        return {"ecosystem_id": "", "ecosystem_name": "", "nodes": [], "edges": []}

    apps = engine.get_all_apps()
    contracts = engine.get_contracts()
    shared_entities = engine.get_shared_entities()
    conflicts = engine.detect_cross_app_conflicts()

    nodes: list[dict] = []
    edges: list[dict] = []

    # 1. Agrupar apps cohesivas en clusters
    cohesive_apps = [a for a in apps if a.coupling_type == "cohesive"]
    decoupled_apps = [a for a in apps if a.coupling_type == "decoupled"]

    # Crear compound node para el grupo cohesivo (si hay 2+ apps cohesivas)
    if len(cohesive_apps) >= 2:
        cluster_id = "cluster:cohesive-group"
        nodes.append({
            "data": {
                "id": cluster_id,
                "label": "Cluster Cohesivo",
                "type": "cluster",
            }
        })

        for app in cohesive_apps:
            health_info = _calculate_health(app.app_id, conflicts, shared_entities)
            nodes.append({
                "data": {
                    "id": f"app:{app.app_id}",
                    "parent": cluster_id,
                    "label": app.name,
                    "type": "app",
                    "app_id": app.app_id,
                    "team": app.team,
                    "story_count": app.story_count,
                    "coupling_type": app.coupling_type,
                    "entities_count": len(app.entities_snapshot),
                    "flows_count": len(app.flows_snapshot),
                    "health": health_info["health"],
                    "conflicts": health_info["conflicts"],
                    "divergent_entities": health_info["divergent_entities"],
                }
            })
    elif len(cohesive_apps) == 1:
        # Solo 1 cohesiva: no justifica cluster, tratar como individual
        app = cohesive_apps[0]
        health_info = _calculate_health(app.app_id, conflicts, shared_entities)
        nodes.append({
            "data": {
                "id": f"app:{app.app_id}",
                "label": app.name,
                "type": "app",
                "app_id": app.app_id,
                "team": app.team,
                "story_count": app.story_count,
                "coupling_type": app.coupling_type,
                "entities_count": len(app.entities_snapshot),
                "flows_count": len(app.flows_snapshot),
                "health": health_info["health"],
                "conflicts": health_info["conflicts"],
                "divergent_entities": health_info["divergent_entities"],
            }
        })

    # 2. Nodos para apps decoupled (sin parent)
    for app in decoupled_apps:
        health_info = _calculate_health(app.app_id, conflicts, shared_entities)
        nodes.append({
            "data": {
                "id": f"app:{app.app_id}",
                "label": app.name,
                "type": "app",
                "app_id": app.app_id,
                "team": app.team,
                "story_count": app.story_count,
                "coupling_type": app.coupling_type,
                "entities_count": len(app.entities_snapshot),
                "flows_count": len(app.flows_snapshot),
                "health": health_info["health"],
                "conflicts": health_info["conflicts"],
                "divergent_entities": health_info["divergent_entities"],
            }
        })

    # 3. Calcular edges de acoplamiento entre cada par de apps
    edges = _calculate_coupling_edges(apps, contracts, shared_entities)

    return {
        "ecosystem_id": registry.ecosystem_id,
        "ecosystem_name": registry.name,
        "description": registry.description,
        "stats": {
            "total_apps": len(apps),
            "total_contracts": len(contracts),
            "shared_entities": len(shared_entities),
            "total_conflicts": len(conflicts),
        },
        "nodes": nodes,
        "edges": edges,
    }


def _calculate_coupling_edges(
    apps: list[AppRegistration],
    contracts: list[ContractDefinition],
    shared_entities: list[SharedEntity],
) -> list[dict]:
    """Calcula la fuerza de acoplamiento entre cada par de apps.

    La fuerza es: num_contratos_entre_ellas + num_entidades_compartidas.
    Solo genera edges para pares con coupling_strength > 0.

    Args:
        apps: Todas las apps del ecosistema.
        contracts: Todos los contratos.
        shared_entities: Entidades compartidas.

    Returns:
        Lista de edges con coupling_strength, contracts_count,
        shared_entities_count, y sync_type.
    """
    edges: list[dict] = []
    app_ids = [a.app_id for a in apps]

    for i, app_a_id in enumerate(app_ids):
        for app_b_id in app_ids[i + 1:]:
            # Contratos entre app_a y app_b (en cualquier direccion)
            pair_contracts = [
                c for c in contracts
                if (c.provider_app == app_a_id and app_b_id in c.consumer_apps)
                or (c.provider_app == app_b_id and app_a_id in c.consumer_apps)
            ]

            # Entidades compartidas entre ambas apps
            pair_entities = [
                e for e in shared_entities
                if app_a_id in e.defined_in_apps and app_b_id in e.defined_in_apps
            ]

            strength = len(pair_contracts) + len(pair_entities)
            if strength == 0:
                continue

            # Determinar sync_type basado en los tipos de contrato
            contract_types = set(c.type for c in pair_contracts)
            if not contract_types:
                sync_type = "implicit"
            elif contract_types <= {"async_event"}:
                sync_type = "async"
            elif "async_event" not in contract_types:
                sync_type = "sync"
            else:
                sync_type = "mixed"

            # Determinar si hay divergencias entre las entidades compartidas
            has_divergence = any(not e.is_consistent for e in pair_entities)

            edges.append({
                "data": {
                    "id": f"coupling:{app_a_id}--{app_b_id}",
                    "source": f"app:{app_a_id}",
                    "target": f"app:{app_b_id}",
                    "type": "coupling",
                    "coupling_strength": strength,
                    "contracts_count": len(pair_contracts),
                    "shared_entities_count": len(pair_entities),
                    "sync_type": sync_type,
                    "has_divergence": has_divergence,
                    "label": f"{len(pair_contracts)} contratos · {len(pair_entities)} entidades",
                    "app_a": app_a_id,
                    "app_b": app_b_id,
                }
            })

    return edges


def _build_flows_between_apps(
    engine: EcosystemEngine, app_a_id: str, app_b_id: str
) -> Optional[dict]:
    """Construye los flujos concretos entre dos apps (vista micro).

    Cruza contratos (provider/consumer) con entidades para identificar
    los flujos punto A → punto B.

    Args:
        engine: EcosystemEngine inicializado.
        app_a_id: ID de la primera app.
        app_b_id: ID de la segunda app.

    Returns:
        Dict con info de apps, coupling summary, y lista de flujos.
        None si alguna app no existe.
    """
    app_a = engine.get_app(app_a_id)
    app_b = engine.get_app(app_b_id)

    if not app_a or not app_b:
        return None

    contracts = engine.get_contracts()
    shared_entities = engine.get_shared_entities()

    # Contratos entre las dos apps
    pair_contracts = [
        c for c in contracts
        if (c.provider_app == app_a_id and app_b_id in c.consumer_apps)
        or (c.provider_app == app_b_id and app_a_id in c.consumer_apps)
    ]

    # Entidades compartidas entre ambas
    pair_shared = [
        e for e in shared_entities
        if app_a_id in e.defined_in_apps and app_b_id in e.defined_in_apps
    ]

    # Construir flujos a partir de los contratos
    flows: list[dict] = []
    for contract in pair_contracts:
        # Determinar direccion
        if contract.provider_app == app_a_id:
            direction = "a_to_b"
            provider = app_a
            consumer = app_b
        else:
            direction = "b_to_a"
            provider = app_b
            consumer = app_a

        # Entidades que viajan en este contrato
        entities_in_transit: list[dict] = []
        for entity_name in contract.entities_involved:
            # Verificar si esta entidad es compartida y tiene divergencia
            entity_shared = next(
                (e for e in pair_shared if e.entity_name.lower() == entity_name.lower()),
                None,
            )

            entities_in_transit.append({
                "name": entity_name,
                "is_consistent": entity_shared.is_consistent if entity_shared else True,
                "divergence": entity_shared.divergence_notes if entity_shared and not entity_shared.is_consistent else "",
            })

        # Buscar HUs que mencionan las entidades del contrato en cada app
        origin_stories = _find_stories_for_entities(
            provider, contract.entities_involved
        )
        target_stories = _find_stories_for_entities(
            consumer, contract.entities_involved
        )

        flows.append({
            "flow_id": f"flow-{contract.contract_id}",
            "flow_name": contract.name,
            "direction": direction,
            "origin": {
                "app_id": provider.app_id,
                "app_name": provider.name,
                "stories": origin_stories,
            },
            "target": {
                "app_id": consumer.app_id,
                "app_name": consumer.name,
                "stories": target_stories,
            },
            "contract": {
                "contract_id": contract.contract_id,
                "name": contract.name,
                "type": contract.type,
                "version": contract.version,
                "spec_reference": contract.spec_reference,
            },
            "entities_in_transit": entities_in_transit,
        })

    # Entidades compartidas sin contrato formal (acoplamiento implicito)
    contracted_entities = set()
    for contract in pair_contracts:
        for e in contract.entities_involved:
            contracted_entities.add(e.lower())

    implicit_shared = [
        e for e in pair_shared
        if e.entity_name.lower() not in contracted_entities
    ]

    return {
        "app_a": {
            "app_id": app_a.app_id,
            "name": app_a.name,
            "team": app_a.team,
            "story_count": app_a.story_count,
        },
        "app_b": {
            "app_id": app_b.app_id,
            "name": app_b.name,
            "team": app_b.team,
            "story_count": app_b.story_count,
        },
        "coupling_summary": {
            "contracts_count": len(pair_contracts),
            "shared_entities_count": len(pair_shared),
            "coupling_strength": len(pair_contracts) + len(pair_shared),
        },
        "flows": flows,
        "implicit_shared_entities": [
            {
                "entity": e.entity_name,
                "is_consistent": e.is_consistent,
                "divergence": e.divergence_notes,
                "fields_by_app": {
                    k: v for k, v in e.fields_by_app.items()
                    if k in (app_a_id, app_b_id)
                },
            }
            for e in implicit_shared
        ],
    }


def _find_stories_for_entities(
    app: AppRegistration, entity_names: list[str]
) -> list[str]:
    """Busca HU IDs en una app que referencian las entidades dadas.

    Opera de forma best-effort: si el snapshot de flows/entities
    del app contiene referencias, las retorna. Si no hay info
    suficiente, retorna lista vacia.

    Args:
        app: App donde buscar.
        entity_names: Entidades a buscar.

    Returns:
        Lista de story IDs que referencian esas entidades.
    """
    # Actualmente el snapshot solo tiene entidades y flujos, no HUs por entidad.
    # Retornamos una lista vacia — el frontend mostrara "Sin HU identificada"
    # hasta que se implemente un indice mas granular.
    # Esto evita lecturas pesadas al .hu-memory/ en cada request de la UI.
    return []


# ─── HEALTH CALCULATION ──────────────────────────────────────────────────────────


def _calculate_health(
    app_id: str,
    conflicts: list[CrossAppConflict],
    shared_entities: list[SharedEntity],
) -> dict:
    """Calcula el indicador de salud de una app.

    Args:
        app_id: ID de la app.
        conflicts: Todos los conflictos del ecosistema.
        shared_entities: Entidades compartidas.

    Returns:
        Dict con health (green/yellow/red), counts de problemas.
    """
    app_conflicts = [c for c in conflicts if app_id in c.apps_involved]
    app_divergences = [
        e for e in shared_entities
        if app_id in e.defined_in_apps and not e.is_consistent
    ]
    dead_contracts = [
        c for c in app_conflicts
        if c.conflict_type == "dead_contract"
    ]

    critical = [c for c in app_conflicts if c.severity == "high"]

    if critical:
        health = "red"
    elif app_conflicts or app_divergences:
        health = "yellow"
    else:
        health = "green"

    return {
        "health": health,
        "conflicts": len(app_conflicts),
        "divergent_entities": len(app_divergences),
        "dead_contracts": len(dead_contracts),
    }


# ─── HELPERS ─────────────────────────────────────────────────────────────────────


def _get_ecosystem_engine(ecosystem_id: str) -> Optional[EcosystemEngine]:
    """Obtiene un EcosystemEngine por ID.

    Si el ecosystem_id coincide con el ecosistema activo, lo retorna directamente.
    Si no, intenta cargarlo desde disco via el manager.

    Args:
        ecosystem_id: ID del ecosistema.

    Returns:
        EcosystemEngine o None si no existe.
    """
    manager = get_ecosystem_manager()
    if not manager:
        return None

    # Verificar si es el activo
    active = manager.get_active()
    if active and active.registry and active.registry.ecosystem_id == ecosystem_id:
        return active

    # Intentar cargarlo
    try:
        engine = manager.switch_ecosystem(ecosystem_id)
        return engine
    except ValueError:
        return None
