"""Tool implementations: detect_conflicts, suggest_next_stories."""

import logging
from typing import Optional

from src.engine.memory import get_memory
from src.engine.segmenter import ContextSegmenter

logger = logging.getLogger("mcp_hu.tools.conflict")


def handle_detect_conflicts(story_id: Optional[str] = None) -> dict:
    """Detecta duplicaciones, contradicciones y flujos abiertos.

    Si story_id se proporciona, verifica solo esa HU contra las demas.
    Si es None, analiza todo el proyecto.

    Args:
        story_id: ID de HU especifica o None para todas.

    Returns:
        Reporte de conflictos encontrados.
    """
    memory = get_memory()

    if not memory.is_initialized:
        return {"status": "error", "message": "Proyecto no inicializado."}

    stories = memory.get_all_stories()
    if not stories:
        return {"status": "success", "conflicts_found": 0, "conflicts": [], "message": "No hay HUs para analizar."}

    conflicts = []

    # 1. Detectar duplicaciones (HUs con alta similitud de entidades + flujos)
    summaries = memory.get_all_summaries()
    if len(summaries) >= 2:
        segmenter = ContextSegmenter(summaries, memory.graph)
        for i, summary in enumerate(summaries):
            if story_id and summary.id != story_id:
                continue
            for j, other in enumerate(summaries):
                if i >= j:
                    continue
                if story_id and other.id != story_id and summary.id != story_id:
                    continue

                # Score alto = posible duplicacion
                entity_overlap = _jaccard(summary.entities, other.entities)
                flow_overlap = _jaccard(summary.flows, other.flows)

                if entity_overlap > 0.7 and flow_overlap > 0.5:
                    conflicts.append({
                        "type": "duplication",
                        "severity": "high" if entity_overlap > 0.9 else "medium",
                        "between": [summary.id, other.id],
                        "description": (
                            f"{summary.id} ('{summary.title}') y {other.id} ('{other.title}') "
                            f"comparten {int(entity_overlap*100)}% de entidades y {int(flow_overlap*100)}% de flujos. "
                            f"Posible duplicacion."
                        ),
                        "suggestion": "Evaluar si se deben consolidar en una sola HU o si son perspectivas distintas del mismo flujo.",
                        "entity_overlap": round(entity_overlap, 2),
                        "flow_overlap": round(flow_overlap, 2),
                    })

    # 2. Detectar flujos abiertos (HUs que inician un flujo pero no tienen continuacion)
    flows = memory.get_flows()
    for flow in flows:
        if flow.status == "incomplete" and len(flow.stories_involved) == 1:
            story = memory.get_story(flow.stories_involved[0])
            if story and (not story_id or story.id == story_id):
                conflicts.append({
                    "type": "open_flow",
                    "severity": "medium",
                    "between": [story.id],
                    "description": (
                        f"El flujo '{flow.name}' solo tiene 1 HU ({story.id}). "
                        f"Puede indicar pasos faltantes del flujo."
                    ),
                    "suggestion": f"Crear HUs para los pasos siguientes del flujo '{flow.name}'.",
                })

    # 3. Detectar dependencias no resueltas
    for story in stories:
        if story_id and story.id != story_id:
            continue
        for dep_id in story.dependencies:
            dep = memory.get_story(dep_id)
            if not dep:
                conflicts.append({
                    "type": "missing_dependency",
                    "severity": "high",
                    "between": [story.id, dep_id],
                    "description": (
                        f"{story.id} depende de '{dep_id}' que no existe en el proyecto."
                    ),
                    "suggestion": f"Crear la HU '{dep_id}' o corregir la dependencia en {story.id}.",
                })

    # 4. Detectar contradicciones potenciales (HUs con misma entidad pero reglas distintas)
    # El MCP devuelve el contexto para que Kiro detecte las contradicciones semanticas
    entity_stories: dict[str, list[str]] = {}
    for summary in summaries:
        for entity in summary.entities:
            entity_stories.setdefault(entity, []).append(summary.id)

    entities_with_multiple = {e: ids for e, ids in entity_stories.items() if len(ids) >= 3}

    if entities_with_multiple:
        contradiction_candidates = []
        for entity, story_ids in entities_with_multiple.items():
            if story_id and story_id not in story_ids:
                continue
            contradiction_candidates.append({
                "entity": entity,
                "stories": story_ids,
                "note": f"Entidad '{entity}' aparece en {len(story_ids)} HUs. Verificar consistencia de reglas.",
            })
        if contradiction_candidates:
            conflicts.append({
                "type": "potential_contradiction",
                "severity": "low",
                "between": [],
                "description": "Entidades que aparecen en multiples HUs — verificar consistencia de reglas.",
                "suggestion": "Revisar que las reglas definidas para estas entidades no se contradigan entre HUs.",
                "candidates": contradiction_candidates,
            })

    return {
        "status": "success",
        "scope": story_id or "all",
        "conflicts_found": len(conflicts),
        "conflicts": conflicts,
        "instructions_for_llm": (
            "Revisa los conflictos detectados y proporciona al usuario: "
            "1) Para duplicaciones: si realmente son duplicados o perspectivas complementarias. "
            "2) Para flujos abiertos: que HUs faltan para completar el flujo. "
            "3) Para dependencias faltantes: crear la HU dependencia o corregir la referencia. "
            "4) Para contradicciones potenciales: comparar las reglas de las HUs involucradas."
        ),
    }


def handle_suggest_next_stories() -> dict:
    """Sugiere HUs faltantes basado en gaps y flujos incompletos.

    Returns:
        Lista de sugerencias priorizadas.
    """
    memory = get_memory()

    if not memory.is_initialized:
        return {"status": "error", "message": "Proyecto no inicializado."}

    stories = memory.get_all_stories()
    if not stories:
        return {"status": "success", "suggestions": [], "message": "No hay HUs. Comienza agregando la primera."}

    suggestions = []

    # 1. Gaps abiertos en HUs existentes
    for story in stories:
        if story.total_gaps > 0:
            # Buscar gaps en el analisis de expertos
            for section in story.expert_analysis:
                for gap in section.gaps:
                    suggestions.append({
                        "source": story.id,
                        "type": "gap_resolution",
                        "priority": "high",
                        "description": f"Gap en {story.id} ({section.expert.value}): {gap}",
                        "suggested_action": "Crear HU que resuelva este gap o aclarar en la HU existente.",
                    })

    # 2. Flujos incompletos
    flows = memory.get_flows()
    for flow in flows:
        if flow.status == "incomplete":
            suggestions.append({
                "source": f"flow:{flow.name}",
                "type": "flow_completion",
                "priority": "medium",
                "description": (
                    f"Flujo '{flow.name}' incompleto. "
                    f"HUs actuales: {', '.join(flow.stories_involved)}."
                ),
                "suggested_action": f"Identificar pasos faltantes del flujo '{flow.name}' y crear HUs para cada uno.",
            })

    # 3. Entidades sin CRUD completo (si tienen solo create pero no read/update/delete)
    entities = memory.get_entities()
    for entity in entities:
        if len(entity.appears_in) == 1:
            suggestions.append({
                "source": f"entity:{entity.name}",
                "type": "entity_coverage",
                "priority": "low",
                "description": (
                    f"Entidad '{entity.name}' solo aparece en 1 HU ({entity.appears_in[0]}). "
                    f"Puede necesitar HUs adicionales (consulta, actualizacion, eliminacion)."
                ),
                "suggested_action": f"Evaluar si '{entity.name}' necesita operaciones adicionales.",
            })

    # Ordenar por prioridad
    priority_order = {"high": 0, "medium": 1, "low": 2}
    suggestions.sort(key=lambda s: priority_order.get(s["priority"], 9))

    return {
        "status": "success",
        "total_suggestions": len(suggestions),
        "by_priority": {
            "high": len([s for s in suggestions if s["priority"] == "high"]),
            "medium": len([s for s in suggestions if s["priority"] == "medium"]),
            "low": len([s for s in suggestions if s["priority"] == "low"]),
        },
        "suggestions": suggestions[:20],  # Top 20
        "instructions_for_llm": (
            "Presenta las sugerencias priorizadas al usuario. "
            "Para cada una explica por que se sugiere y como formular la HU faltante. "
            "Prioridad alta = gaps que bloquean implementacion. "
            "Prioridad media = flujos incompletos. "
            "Prioridad baja = cobertura de entidades."
        ),
    }


def _jaccard(list_a: list[str], list_b: list[str]) -> float:
    """Jaccard index entre dos listas."""
    if not list_a or not list_b:
        return 0.0
    set_a = set(x.lower() for x in list_a)
    set_b = set(x.lower() for x in list_b)
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0
