"""Tool handlers para el plan de trabajo (Gantt).

Incluye:
- get_work_plan: genera el plan desde la memoria
- update_work_plan: modifica fases, deadlines, días por tarea
- validate_work_plan: valida el plan buscando gaps y riesgos
"""

import logging
from datetime import date

from src.engine.gantt_engine import (
    GanttConfig,
    PhaseConfig,
    build_gantt,
    config_from_persisted,
    config_to_dict,
    gantt_to_json,
    get_work_plan_state,
    load_persisted_config,
    save_persisted_config,
    validate_work_plan as engine_validate,
)
from src.engine.memory import get_memory

logger = logging.getLogger("mcp_hu.tools.gantt")


def _parse_date_str(s: str) -> date | None:
    """Parsea fecha YYYY-MM-DD."""
    if not s:
        return None
    try:
        parts = s.split("-")
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        return None


def handle_get_work_plan(params: dict) -> dict:
    """Genera el plan de trabajo (Gantt) desde la memoria del workspace activo.

    Lee todas las HUs con sus dependencias y estimaciones, ejecuta el scheduler
    dependency-aware y retorna el plan completo con métricas.

    Args:
        params: Dict con campos opcionales:
            - project_start: str (YYYY-MM-DD), fecha inicio del proyecto.
            - deadline: str (YYYY-MM-DD), fecha límite.
            - max_concurrent: int, máximo de HUs simultáneas (default 2).

    Returns:
        Plan de trabajo con tasks, métricas, fases y holidays.
    """
    # Si hay parámetros explícitos, construir config desde ellos
    # Si no, build_gantt usará la config persistida automáticamente
    config = None
    if any(params.get(k) for k in ("project_start", "deadline", "max_concurrent")):
        # Cargar persistida como base y aplicar params encima
        memory = get_memory()
        raw = load_persisted_config(memory) or {}
        config = config_from_persisted(raw)

        if params.get("project_start"):
            d = _parse_date_str(params["project_start"])
            if d:
                config.project_start = d
            else:
                return {"status": "error", "message": "Formato inválido para project_start. Usar YYYY-MM-DD."}

        if params.get("deadline"):
            d = _parse_date_str(params["deadline"])
            if d:
                config.deadline = d
            else:
                return {"status": "error", "message": "Formato inválido para deadline. Usar YYYY-MM-DD."}

        if params.get("max_concurrent"):
            try:
                config.max_concurrent = max(1, min(10, int(params["max_concurrent"])))
            except (ValueError, TypeError):
                pass

    result = build_gantt(config)

    if result is None:
        return {
            "status": "error",
            "message": (
                "No se pudo generar el plan de trabajo. "
                "Verifica que hay un workspace activo con HUs analizadas. "
                "Usa init_project + analyze_story + add_story primero."
            ),
        }

    data = gantt_to_json(result)

    # Agregar URL del visualizador
    data["visualizer_url"] = "http://localhost:9751/gantt"
    data["message"] = (
        f"Plan de trabajo generado: {data['metrics']['story_count']} HUs, "
        f"{data['metrics']['total_work_days']} días hábiles con paralelismo "
        f"(ruta crítica: {data['metrics']['critical_path_days']}d). "
        f"Visualizar en: http://localhost:9751/gantt"
    )

    return data


def handle_update_work_plan(params: dict) -> dict:
    """Modifica la configuración del plan de trabajo y la persiste.

    Permite al usuario ajustar fases, deadlines por fase, días por tarea,
    y milestones. Los cambios se guardan en .hu-memory/gantt-config.json
    y son referenciados por todas las herramientas del MCP.

    Args:
        params: Dict con los cambios a aplicar:
            - project_start: str (YYYY-MM-DD), nueva fecha inicio.
            - deadline: str (YYYY-MM-DD), nuevo deadline global.
            - max_concurrent: int, nueva concurrencia máxima.
            - developers: int, cantidad de desarrolladores.
            - phases: list[dict], definición de fases:
                - phase_id: str (ej: "p1", "entrega-1")
                - name: str (nombre de la fase)
                - task_ids: list[str] (IDs de HUs en esta fase)
                - deadline: str (YYYY-MM-DD, deadline de esta fase)
            - task_day_overrides: dict[str, int], override de días por HU.
            - milestones: list[dict], hitos del proyecto:
                - name: str
                - date: str (YYYY-MM-DD)
                - description: str (opcional)

    Returns:
        Configuración actualizada con el plan recalculado.
    """
    memory = get_memory()
    if not memory.is_initialized:
        return {"status": "error", "message": "No hay workspace activo."}

    # Cargar config existente como base
    existing = load_persisted_config(memory) or {}

    # Aplicar cambios
    if params.get("project_start"):
        d = _parse_date_str(params["project_start"])
        if d:
            existing["project_start"] = params["project_start"]
        else:
            return {"status": "error", "message": "Formato inválido para project_start."}

    if "deadline" in params:
        if params["deadline"]:
            d = _parse_date_str(params["deadline"])
            if d:
                existing["deadline"] = params["deadline"]
            else:
                return {"status": "error", "message": "Formato inválido para deadline."}
        else:
            existing["deadline"] = None

    if params.get("max_concurrent"):
        try:
            existing["max_concurrent"] = max(1, min(10, int(params["max_concurrent"])))
        except (ValueError, TypeError):
            pass

    if params.get("developers"):
        try:
            existing["developers"] = max(1, min(20, int(params["developers"])))
        except (ValueError, TypeError):
            pass

    # Phases: reemplazar completamente si se proveen
    if "phases" in params and params["phases"] is not None:
        phases = []
        for ph in params["phases"]:
            phase_data = {
                "phase_id": ph.get("phase_id", ""),
                "name": ph.get("name", ""),
                "task_ids": ph.get("task_ids", []),
            }
            if ph.get("deadline"):
                d = _parse_date_str(ph["deadline"])
                if d:
                    phase_data["deadline"] = ph["deadline"]
            else:
                phase_data["deadline"] = None
            phases.append(phase_data)
        existing["phases"] = phases

    # Task day overrides: merge (no reemplazar)
    if params.get("task_day_overrides"):
        overrides = existing.get("task_day_overrides", {})
        for task_id, days in params["task_day_overrides"].items():
            try:
                day_val = int(days)
                if day_val <= 0:
                    overrides.pop(task_id, None)  # 0 o negativo = quitar override
                else:
                    overrides[task_id] = max(1, min(60, day_val))
            except (ValueError, TypeError):
                pass
        existing["task_day_overrides"] = overrides

    # Milestones
    if "milestones" in params and params["milestones"] is not None:
        existing["milestones"] = params["milestones"]

    # Persistir
    if not save_persisted_config(existing, memory):
        return {"status": "error", "message": "Error guardando configuración."}

    # Recalcular plan con nueva config
    config = config_from_persisted(existing)
    result = build_gantt(config)

    if result is None:
        return {
            "status": "partial",
            "message": "Configuración guardada pero no hay HUs para generar el plan.",
            "config": existing,
        }

    data = gantt_to_json(result)
    data["visualizer_url"] = "http://localhost:9751/gantt"
    data["message"] = (
        f"Plan actualizado y persistido: {data['metrics']['story_count']} HUs, "
        f"{data['metrics']['total_work_days']} días hábiles. "
        f"Config guardada en .hu-memory/gantt-config.json. "
        f"Visualizar en: http://localhost:9751/gantt"
    )

    return data


def handle_validate_work_plan(params: dict) -> dict:
    """Valida el plan de trabajo buscando gaps, riesgos y problemas.

    Analiza el plan actual considerando:
    - Deadlines excedidos (global y por fase)
    - Estimaciones basadas en heurísticas (sin estimate_story)
    - Dependencias rotas o circulares
    - Ruta crítica y tareas sin margen
    - Desbalanceo de carga entre fases
    - HUs en fases incorrectas (oportunidades de mejora)

    Args:
        params: Dict vacío o con opciones futuras.

    Returns:
        Reporte de validación con findings categorizados.
    """
    return engine_validate()


def handle_get_plan_health(params: dict) -> dict:
    """Retorna el estado de salud del plan para consumo cross-tool.

    Esta función es usada internamente por otras herramientas del MCP
    (estimate_story, detect_conflicts, suggest_next_stories) para
    tener visibilidad transversal del estado del proyecto.

    Args:
        params: Dict vacío.

    Returns:
        Resumen del estado de salud del plan.
    """
    state = get_work_plan_state()
    if not state:
        return {
            "status": "no_plan",
            "message": "No hay plan de trabajo configurado. Use get_work_plan para generar uno.",
        }
    state["status"] = "success"
    return state
