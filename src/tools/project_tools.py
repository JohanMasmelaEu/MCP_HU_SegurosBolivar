"""Tool implementations: init_project, get_project_summary, export_memory, import_memory."""

import logging
from pathlib import Path

from src.engine.memory import get_memory
from src.models.project import ProjectConfig

logger = logging.getLogger("mcp_hu.tools.project")


def handle_init_project(config_dict: dict) -> dict:
    """Inicializa un nuevo proyecto y crea la memoria local.

    Args:
        config_dict: Diccionario con project_name, domain, stakeholders, description.

    Returns:
        Status de la operacion.
    """
    memory = get_memory()

    if memory.is_initialized:
        return {
            "status": "error",
            "message": "El proyecto ya esta inicializado. Directorio .hu-memory/ ya existe.",
            "path": str(memory.memory_path),
        }

    try:
        config = ProjectConfig(**config_dict)
    except Exception as e:
        return {"status": "error", "message": f"Configuracion invalida: {e}"}

    try:
        memory.init_project(config)
        return {
            "status": "success",
            "project_name": config.project_name,
            "domain": config.domain,
            "stakeholders": config.stakeholders,
            "memory_path": str(memory.memory_path),
            "message": (
                f"Proyecto '{config.project_name}' inicializado. "
                f"Memoria local creada en .hu-memory/. "
                f"Listo para recibir historias de usuario."
            ),
        }
    except Exception as e:
        logger.exception("Error inicializando proyecto")
        return {"status": "error", "message": f"Error: {e}"}


def handle_get_project_summary() -> dict:
    """Devuelve el estado actual del proyecto."""
    memory = get_memory()

    if not memory.is_initialized:
        return {"status": "error", "message": "Proyecto no inicializado. Usar init_project primero."}

    index = memory.index
    if not index:
        return {"status": "error", "message": "No se pudo leer el indice del proyecto."}

    summaries = memory.get_all_summaries()
    entities = memory.get_entities()
    flows = memory.get_flows()
    patterns = memory.get_patterns()

    # Contar gaps abiertos
    open_gaps = 0
    for story in memory.get_all_stories():
        open_gaps += story.total_gaps

    # Flujos incompletos
    incomplete_flows = [f for f in flows if f.status == "incomplete"]

    return {
        "status": "success",
        "project_name": index.config.project_name,
        "domain": index.config.domain,
        "stakeholders": index.config.stakeholders,
        "statistics": {
            "total_stories": len(summaries),
            "stories_by_status": _count_by_status(summaries),
            "total_entities": len(entities),
            "total_flows": len(flows),
            "incomplete_flows": len(incomplete_flows),
            "open_gaps": open_gaps,
            "total_decisions": len(index.decisions),
            "estimation_confidence": patterns.confidence_level,
            "completions_registered": patterns.total_completions,
        },
        "entities": [{"name": e.name, "appears_in": len(e.appears_in)} for e in entities],
        "flows": [{"name": f.name, "stories": len(f.stories_involved), "status": f.status} for f in flows],
        "recent_stories": [
            {"id": s.id, "title": s.title, "status": s.status}
            for s in summaries[-5:]
        ],
    }


def handle_export_memory() -> dict:
    """Exporta la memoria del proyecto como .zip."""
    memory = get_memory()

    if not memory.is_initialized:
        return {"status": "error", "message": "Proyecto no inicializado."}

    try:
        zip_path = memory.export_memory()
        summaries = memory.get_all_summaries()
        return {
            "status": "success",
            "file": str(zip_path),
            "contents": {
                "stories": len(summaries),
                "entities": len(memory.get_entities()),
                "flows": len(memory.get_flows()),
            },
            "message": "Memoria exportada. Archivo portable para backup o importar en otro workspace.",
        }
    except Exception as e:
        logger.exception("Error exportando memoria")
        return {"status": "error", "message": f"Error: {e}"}


def handle_import_memory(zip_path: str) -> dict:
    """Importa memoria desde un .zip previo."""
    memory = get_memory()
    path = Path(zip_path)

    if not path.is_absolute():
        from src.engine.memory import WORKSPACE_PATH
        path = WORKSPACE_PATH / zip_path

    if not path.exists():
        return {"status": "error", "message": f"Archivo no encontrado: {path}"}

    try:
        file_count = memory.import_memory(path)
        summaries = memory.get_all_summaries()
        return {
            "status": "success",
            "files_imported": file_count,
            "stories_recovered": len(summaries),
            "entities_recovered": len(memory.get_entities()),
            "message": f"Memoria importada exitosamente ({file_count} archivos). Proyecto restaurado.",
        }
    except Exception as e:
        logger.exception("Error importando memoria")
        return {"status": "error", "message": f"Error: {e}"}


def _count_by_status(summaries: list) -> dict:
    """Cuenta HUs por status."""
    counts: dict[str, int] = {}
    for s in summaries:
        counts[s.status] = counts.get(s.status, 0) + 1
    return counts
