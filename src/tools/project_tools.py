"""Tool implementations: init_project, get_project_summary, export_memory, import_memory."""

import logging
import re
from pathlib import Path

from src.engine.ecosystem import get_ecosystem
from src.engine.memory import get_memory
from src.engine.workspace_manager import get_workspace_manager
from src.engine.ecosystem_manager import get_ecosystem_manager
from src.models.project import ProjectConfig

logger = logging.getLogger("mcp_hu.tools.project")


def _slugify(text: str) -> str:
    """Convierte un texto en un slug valido para IDs de workspace.

    Args:
        text: Texto a convertir.

    Returns:
        Slug alfanumerico con guiones.
    """
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")[:60]


def handle_init_project(config_dict: dict) -> dict:
    """Inicializa un nuevo proyecto creando un workspace dedicado.

    Si se proporciona ecosystem_id y app_id, vincula el proyecto al ecosistema.
    Ya NO bloquea si existe un proyecto — crea un nuevo workspace con ID derivado
    del nombre del proyecto o del workspace_id proporcionado.

    Args:
        config_dict: Diccionario con project_name, domain, stakeholders, description,
                     y opcionalmente ecosystem_id, app_id, workspace_id.

    Returns:
        Status de la operacion.
    """
    manager = get_workspace_manager()

    if manager is None:
        # Fallback legacy (no deberia ocurrir si el server inicializa correctamente)
        return _legacy_init_project(config_dict)

    # Determinar workspace_id
    workspace_id = config_dict.pop("workspace_id", None)
    if not workspace_id:
        project_name = config_dict.get("project_name", "default")
        workspace_id = _slugify(project_name)

    try:
        engine = manager.create_workspace(workspace_id, config_dict)
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.exception("Error inicializando proyecto")
        return {"status": "error", "message": f"Error: {e}"}

    # Vincular al ecosistema si se proporciono ecosystem_id
    ecosystem_linked = False
    ecosystem_id = config_dict.get("ecosystem_id")
    app_id = config_dict.get("app_id")

    if ecosystem_id and app_id:
        try:
            eco_manager = get_ecosystem_manager()
            if eco_manager:
                active_eco = eco_manager.get_active()
                if active_eco and active_eco.is_initialized:
                    registry = active_eco.registry
                    if registry and registry.ecosystem_id == ecosystem_id:
                        ecosystem_linked = True
                        logger.info(
                            "Proyecto vinculado al ecosistema '%s' como app '%s'",
                            ecosystem_id, app_id,
                        )
        except Exception as eco_err:
            logger.warning("No se pudo vincular al ecosistema: %s", eco_err)

    index = engine.index
    result = {
        "status": "success",
        "workspace_id": workspace_id,
        "project_name": index.config.project_name if index else config_dict.get("project_name"),
        "domain": index.config.domain if index else config_dict.get("domain"),
        "stakeholders": index.config.stakeholders if index else config_dict.get("stakeholders", []),
        "memory_path": str(engine.memory_path),
        "message": (
            f"Proyecto '{config_dict.get('project_name', workspace_id)}' inicializado "
            f"en workspace '{workspace_id}'. "
            f"Memoria local creada. Listo para recibir historias de usuario."
        ),
    }

    if ecosystem_id:
        result["ecosystem_id"] = ecosystem_id
        result["app_id"] = app_id
        result["ecosystem_linked"] = ecosystem_linked
        if ecosystem_linked:
            result["message"] += f" Vinculado al ecosistema '{ecosystem_id}'."
        else:
            result["message"] += (
                f" Ecosistema '{ecosystem_id}' configurado pero no encontrado activo. "
                f"Inicializa el ecosistema con init_ecosystem para activar la visibilidad transversal."
            )

    return result


def _legacy_init_project(config_dict: dict) -> dict:
    """Fallback: inicializacion legacy sin WorkspaceManager.

    Args:
        config_dict: Configuracion del proyecto.

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
                f"Proyecto '{config.project_name}' inicializado (modo legacy). "
                f"Memoria local creada en .hu-memory/."
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

    # Info del workspace activo
    ws_manager = get_workspace_manager()
    workspace_info = {}
    if ws_manager:
        workspace_info = {
            "active_workspace": ws_manager.active_workspace_id,
            "active_ecosystem": ws_manager.active_ecosystem_id,
        }

    return {
        "status": "success",
        "project_name": index.config.project_name,
        "domain": index.config.domain,
        "stakeholders": index.config.stakeholders,
        "story_count": index.story_count,
        "entities_count": len(entities),
        "flows_count": len(flows),
        "incomplete_flows": len(incomplete_flows),
        "open_gaps": open_gaps,
        "stories": [s.model_dump(mode="json") for s in summaries],
        "entities": [e.model_dump(mode="json") for e in entities],
        "flows": [f.model_dump(mode="json") for f in flows],
        "estimation_patterns": {
            "total_completions": patterns.total_completions,
            "confidence_level": patterns.confidence_level,
        },
        **workspace_info,
    }


def handle_export_memory() -> dict:
    """Exporta la memoria del proyecto como .zip."""
    memory = get_memory()

    if not memory.is_initialized:
        return {"status": "error", "message": "Proyecto no inicializado."}

    try:
        zip_path = memory.export_memory()
        return {
            "status": "success",
            "path": str(zip_path),
            "message": f"Memoria exportada a {zip_path}",
        }
    except Exception as e:
        logger.exception("Error exportando memoria")
        return {"status": "error", "message": f"Error: {e}"}


def handle_import_memory(zip_path_str: str) -> dict:
    """Importa memoria desde un .zip.

    Args:
        zip_path_str: Ruta al archivo zip.

    Returns:
        Status de la operacion.
    """
    memory = get_memory()

    try:
        zip_path = Path(zip_path_str)
        file_count = memory.import_memory(zip_path)
        return {
            "status": "success",
            "files_imported": file_count,
            "message": f"Memoria importada: {file_count} archivos desde {zip_path}",
        }
    except FileNotFoundError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.exception("Error importando memoria")
        return {"status": "error", "message": f"Error: {e}"}
