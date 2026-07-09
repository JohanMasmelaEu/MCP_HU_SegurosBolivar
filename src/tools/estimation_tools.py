"""Tool implementations: estimate_story, register_completion, get_velocity, calibrate_estimates."""

import logging

from src.engine.estimator import EstimationEngine
from src.engine.memory import get_memory
from src.models.estimation import CompletionRecord

logger = logging.getLogger("mcp_hu.tools.estimation")


def handle_estimate_story(story_id: str) -> dict:
    """Estima esfuerzo para una HU analizada.

    Args:
        story_id: ID de la HU.

    Returns:
        Estimacion con rango y confianza.
    """
    memory = get_memory()

    if not memory.is_initialized:
        return {"status": "error", "message": "Proyecto no inicializado."}

    story = memory.get_story(story_id)
    if not story:
        return {"status": "error", "message": f"HU '{story_id}' no encontrada."}

    if not story.complexity_tags:
        return {
            "status": "error",
            "message": (
                f"HU '{story_id}' no tiene complexity_tags asignados. "
                "Ejecutar analyze_story primero para detectar la complejidad."
            ),
        }

    patterns = memory.get_patterns()
    completions = memory.get_completions()
    engine = EstimationEngine(patterns, completions)

    estimation = engine.estimate(story)

    return {
        "status": "success",
        "estimation": estimation.model_dump(mode="json"),
        "note": (
            "Esta estimacion es orientativa. Se calibra automaticamente "
            "con cada HU completada registrada via register_completion."
        ),
    }


def handle_register_completion(data: dict) -> dict:
    """Registra una HU completada con horas reales.

    Args:
        data: Dict con story_id, actual_hours, sprint (opcional), notes (opcional).

    Returns:
        Confirmacion y patrones actualizados.
    """
    memory = get_memory()

    if not memory.is_initialized:
        return {"status": "error", "message": "Proyecto no inicializado."}

    story_id = data.get("story_id")
    actual_hours = data.get("actual_hours")

    if not story_id or actual_hours is None:
        return {"status": "error", "message": "Se requiere story_id y actual_hours."}

    story = memory.get_story(story_id)
    if not story:
        return {"status": "error", "message": f"HU '{story_id}' no encontrada."}

    # Obtener estimacion previa si existe
    patterns = memory.get_patterns()
    completions = memory.get_completions()
    engine = EstimationEngine(patterns, completions)

    estimated_hours = None
    try:
        est = engine.estimate(story)
        estimated_hours = est.probable_hours
    except Exception:
        pass

    record = CompletionRecord(
        story_id=story_id,
        actual_hours=float(actual_hours),
        estimated_hours=estimated_hours,
        sprint=data.get("sprint", ""),
        notes=data.get("notes", ""),
        complexity_tags=story.complexity_tags,
        experts_involved=[e.expert.value for e in story.expert_analysis],
    )

    # Registrar y recalibrar
    engine.register_completion(record)
    memory.add_completion(record)
    memory.save_patterns(engine.patterns)

    # Marcar HU como completada
    story.status = "completed"
    story.updated_at = __import__("datetime").datetime.now().isoformat()
    memory.save_story(story)

    deviation_msg = ""
    if record.deviation_factor:
        deviation_msg = f" Desviacion: {record.deviation_factor:.2f}x."

    return {
        "status": "success",
        "story_id": story_id,
        "actual_hours": actual_hours,
        "estimated_hours": estimated_hours,
        "deviation_factor": record.deviation_factor,
        "patterns_updated": True,
        "new_confidence": engine.patterns.confidence_level,
        "total_completions": engine.patterns.total_completions,
        "message": (
            f"HU '{story_id}' registrada como completada ({actual_hours}h).{deviation_msg} "
            f"Patrones recalibrados. Confianza: {engine.patterns.confidence_level}."
        ),
    }


def handle_get_velocity(sprint: str | None = None) -> dict:
    """Obtiene velocidad del equipo y tendencias.

    Args:
        sprint: Sprint especifico o None para todos.

    Returns:
        Datos de velocidad.
    """
    memory = get_memory()

    if not memory.is_initialized:
        return {"status": "error", "message": "Proyecto no inicializado."}

    patterns = memory.get_patterns()
    completions = memory.get_completions()
    engine = EstimationEngine(patterns, completions)

    velocities = engine.get_velocity(sprint)

    if not velocities:
        return {
            "status": "success",
            "velocities": [],
            "message": "No hay datos de velocity. Registrar completions con sprint para rastrear.",
            "global_stats": {
                "total_completions": patterns.total_completions,
                "global_deviation_avg": patterns.global_deviation_avg,
                "confidence": patterns.confidence_level,
            },
        }

    return {
        "status": "success",
        "velocities": [v.model_dump(mode="json") for v in velocities],
        "global_stats": {
            "total_completions": patterns.total_completions,
            "global_deviation_avg": patterns.global_deviation_avg,
            "confidence": patterns.confidence_level,
        },
        "trend": _calculate_trend(velocities),
    }


def handle_calibrate_estimates() -> dict:
    """Recalcula manualmente todos los factores de estimacion."""
    memory = get_memory()

    if not memory.is_initialized:
        return {"status": "error", "message": "Proyecto no inicializado."}

    patterns = memory.get_patterns()
    completions = memory.get_completions()

    if not completions:
        return {
            "status": "success",
            "message": "No hay completions registrados. Nada que calibrar.",
            "patterns": patterns.model_dump(mode="json"),
        }

    engine = EstimationEngine(patterns, completions)
    updated_patterns = engine.calibrate()
    memory.save_patterns(updated_patterns)

    return {
        "status": "success",
        "message": f"Patrones recalibrados con {len(completions)} completions.",
        "patterns": {
            "global_deviation_avg": updated_patterns.global_deviation_avg,
            "confidence_level": updated_patterns.confidence_level,
            "total_completions": updated_patterns.total_completions,
            "complexity_tags_tracked": len(updated_patterns.by_complexity),
            "sprints_tracked": len(updated_patterns.sprints),
        },
        "by_complexity": [p.model_dump(mode="json") for p in updated_patterns.by_complexity],
    }


def _calculate_trend(velocities: list) -> str:
    """Calcula tendencia de velocidad."""
    if len(velocities) < 2:
        return "insufficient_data"

    recent = velocities[-1].deviation_avg
    previous = velocities[-2].deviation_avg

    if recent < previous:
        return "improving"
    if recent > previous:
        return "degrading"
    return "stable"
