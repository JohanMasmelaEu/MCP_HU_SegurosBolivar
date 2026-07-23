"""MCP Server para analisis inteligente de Historias de Usuario.

Panel de 10 expertos, memoria contextual local, segmentacion inteligente
de contexto y motor de estimacion adaptativa.
Soporta multiples workspaces y ecosistemas simultaneos.
Transport: stdio (Docker).
"""

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.engine.workspace_manager import init_workspace_manager
from src.engine.ecosystem_manager import init_ecosystem_manager
from src.tools.project_tools import (
    handle_init_project,
    handle_get_project_summary,
    handle_export_memory,
    handle_import_memory,
)
from src.tools.analysis_tools import (
    handle_analyze_story,
    handle_add_story,
    handle_get_story_context,
    handle_get_expert_analysis,
    handle_explain_for_stakeholder,
)
from src.tools.conflict_tools import (
    handle_detect_conflicts,
    handle_suggest_next_stories,
)
from src.tools.ecosystem_tools import (
    handle_init_ecosystem,
    handle_register_app,
    handle_list_ecosystem,
    handle_get_cross_app_context,
    handle_sync_ecosystem,
)
from src.tools.estimation_tools import (
    handle_estimate_story,
    handle_register_completion,
    handle_get_velocity,
    handle_calibrate_estimates,
)
from src.tools.workspace_tools import (
    handle_list_workspaces,
    handle_switch_workspace,
    handle_reset_workspace,
    handle_list_ecosystems,
    handle_switch_ecosystem,
    handle_reset_ecosystem,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mcp_hu")

# ─── INICIALIZAR MANAGERS ────────────────────────────────────────────────────────
# Los managers se inicializan al importar el modulo. Detectan automaticamente
# memorias legacy y las migran al nuevo formato multi-workspace/ecosistema.

_ws_manager = init_workspace_manager()
_eco_manager = init_ecosystem_manager()

# Restaurar ecosistema activo: primero intenta desde state, luego desde migracion legacy
_active_eco_id = _ws_manager.active_ecosystem_id or _eco_manager.migrated_ecosystem_id
if _active_eco_id:
    _eco_manager.restore_active(_active_eco_id)
    _ws_manager.set_active_ecosystem(_active_eco_id)


def _ensure_dict(value: Any) -> dict:
    """Normaliza un parametro JSON que puede llegar como str o dict.

    Algunos clientes MCP (Kiro, Claude Desktop) deserializan automaticamente
    los parametros JSON antes de pasarlos al handler, mientras que otros
    los envian como string crudo. Esta funcion maneja ambos casos.

    Args:
        value: Valor que puede ser un JSON string, un dict, o cualquier tipo.

    Returns:
        Diccionario parseado listo para usar.

    Raises:
        ValueError: Si el valor no es convertible a dict.
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value)
    raise ValueError(f"Se esperaba str o dict, se recibio: {type(value).__name__}")


def _ensure_str(value: Any) -> str:
    """Normaliza un parametro que puede llegar como dict o str a string.

    Args:
        value: Valor que puede ser un dict o un string.

    Returns:
        String (si era dict, lo serializa a JSON).
    """
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


mcp = FastMCP(
    name="MCP_HU_SegurosBolivar",
    version="2.0.0",
    description=(
        "MCP Server para analisis inteligente de Historias de Usuario. "
        "Panel de 10 expertos, memoria contextual, segmentacion de contexto, "
        "estimacion adaptativa y visibilidad transversal de ecosistemas. "
        "Soporta multiples workspaces y ecosistemas simultaneos. "
        "Produce HUs estandarizadas sin ambiguedades."
    ),
)


# ─── WORKSPACE MANAGEMENT ────────────────────────────────────────────────────────


@mcp.tool()
async def list_workspaces() -> str:
    """Lista todos los workspaces (proyectos) disponibles con su metadata.

    Muestra cual es el workspace activo actualmente.
    Usa switch_workspace para cambiar entre proyectos.
    """
    result = handle_list_workspaces()
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def switch_workspace(workspace_id: str) -> str:
    """Cambia al workspace (proyecto) indicado. Todas las operaciones de HU operaran sobre este workspace.

    Args:
        workspace_id: ID del workspace destino (ver list_workspaces para IDs disponibles).
    """
    result = handle_switch_workspace(workspace_id)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def reset_workspace(workspace_id: str, confirm: bool = False) -> str:
    """Elimina un workspace y toda su memoria permanentemente.

    Args:
        workspace_id: ID del workspace a eliminar.
        confirm: Debe ser true para confirmar la operacion destructiva.
    """
    result = handle_reset_workspace({"workspace_id": workspace_id, "confirm": confirm})
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def list_ecosystems() -> str:
    """Lista todos los ecosistemas disponibles con su metadata.

    Muestra cual es el ecosistema activo actualmente.
    Usa switch_ecosystem para cambiar entre ecosistemas.
    """
    result = handle_list_ecosystems()
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def switch_ecosystem(ecosystem_id: str) -> str:
    """Cambia al ecosistema indicado. Las operaciones de ecosistema operaran sobre este.

    Args:
        ecosystem_id: ID del ecosistema destino (ver list_ecosystems para IDs disponibles).
    """
    result = handle_switch_ecosystem(ecosystem_id)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def reset_ecosystem(ecosystem_id: str, confirm: bool = False) -> str:
    """Elimina un ecosistema y todo su registro permanentemente.

    Args:
        ecosystem_id: ID del ecosistema a eliminar.
        confirm: Debe ser true para confirmar la operacion destructiva.
    """
    result = handle_reset_ecosystem({"ecosystem_id": ecosystem_id, "confirm": confirm})
    return json.dumps(result, ensure_ascii=False, indent=2)


# ─── PROJECT MANAGEMENT ─────────────────────────────────────────────────────────


@mcp.tool()
async def init_project(config: dict) -> str:
    """Inicializa un nuevo proyecto creando un workspace dedicado (.hu-memory/).

    Cada proyecto vive en su propio workspace aislado. Si un workspace con el
    mismo nombre ya existe, usa switch_workspace para activarlo o reset_workspace
    para eliminarlo y recrear.

    Args:
        config: Objeto con project_name, domain, stakeholders y description. Opcionalmente ecosystem_id, app_id, workspace_id.
    """
    config_dict = _ensure_dict(config)
    result = handle_init_project(config_dict)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_project_summary() -> str:
    """Devuelve el estado actual del proyecto: entidades, flujos, HUs, gaps abiertos."""
    result = handle_get_project_summary()
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def export_memory() -> str:
    """Exporta la memoria del proyecto como archivo .zip portable."""
    result = handle_export_memory()
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def import_memory(zip_path: str) -> str:
    """Importa memoria desde un export previo (.zip).

    Args:
        zip_path: Ruta al archivo .hu-memory-export-*.zip.
    """
    result = handle_import_memory(zip_path)
    return json.dumps(result, ensure_ascii=False, indent=2)


# ─── STORY ANALYSIS ─────────────────────────────────────────────────────────────


@mcp.tool()
async def analyze_story(story_text: str) -> str:
    """Analiza una Historia de Usuario con el panel de expertos.

    Acepta cualquier formato de entrada (texto libre, template, bullets).
    Retorna analisis estandarizado con gaps, criterios y preguntas.

    Args:
        story_text: Texto de la HU en cualquier formato.
    """
    text = _ensure_str(story_text)
    result = handle_analyze_story(text)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def add_story(story_json: dict) -> str:
    """Persiste una HU analizada en la memoria y actualiza el grafo de relaciones.

    Args:
        story_json: Objeto JSON completo de la HU (output de analyze_story, posiblemente editado).
    """
    story_dict = _ensure_dict(story_json)
    result = handle_add_story(story_dict)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_story_context(story_id: str) -> str:
    """Obtiene el contexto segmentado relevante para una HU especifica.

    Solo retorna HUs con score de relevancia > 0.5 (ahorro de tokens).

    Args:
        story_id: Identificador de la HU (ej: HU-001).
    """
    result = handle_get_story_context(story_id)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_expert_analysis(story_id: str, expert: str) -> str:
    """Obtiene analisis profundo de una HU desde la perspectiva de un experto.

    Args:
        story_id: Identificador de la HU.
        expert: Nombre del experto (negocio, ux, backend, datos, seguridad, qa, integracion, observabilidad, devops, legal).
    """
    result = handle_get_expert_analysis(story_id, expert)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def explain_for_stakeholder(story_id: str, role: str) -> str:
    """Reformula una HU para un stakeholder especifico.

    Args:
        story_id: Identificador de la HU.
        role: Rol del stakeholder (dev_frontend, dev_backend, qa, po, ux, devops).
    """
    result = handle_explain_for_stakeholder(story_id, role)
    return json.dumps(result, ensure_ascii=False, indent=2)


# ─── CONFLICT DETECTION ──────────────────────────────────────────────────────────


@mcp.tool()
async def detect_conflicts(story_id: str = "") -> str:
    """Detecta duplicaciones, contradicciones y flujos abiertos entre HUs.

    Args:
        story_id: ID de HU especifica para verificar, o vacio para analizar todo el proyecto.
    """
    result = handle_detect_conflicts(story_id if story_id else None)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def suggest_next_stories() -> str:
    """Sugiere HUs faltantes basado en gaps detectados y flujos incompletos."""
    result = handle_suggest_next_stories()
    return json.dumps(result, ensure_ascii=False, indent=2)


# ─── ESTIMATION ──────────────────────────────────────────────────────────────────


@mcp.tool()
async def estimate_story(story_id: str) -> str:
    """Estima esfuerzo para una HU: rango optimista/probable/pesimista + confianza.

    Args:
        story_id: Identificador de la HU ya analizada.
    """
    result = handle_estimate_story(story_id)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def register_completion(completion_json: dict) -> str:
    """Registra la finalizacion de una HU con horas reales (calibra el motor).

    Args:
        completion_json: Objeto con story_id, actual_hours, y notes opcionales.
    """
    data = _ensure_dict(completion_json)
    result = handle_register_completion(data)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_velocity(sprint: str = "") -> str:
    """Obtiene la velocidad del equipo y tendencias de estimacion.

    Args:
        sprint: Sprint especifico, o vacio para ver todos.
    """
    result = handle_get_velocity(sprint if sprint else None)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def calibrate_estimates() -> str:
    """Recalcula manualmente los factores de ajuste basado en el historico completo."""
    result = handle_calibrate_estimates()
    return json.dumps(result, ensure_ascii=False, indent=2)


# ─── ECOSYSTEM ────────────────────────────────────────────────────────────────────


@mcp.tool()
async def init_ecosystem(config: dict) -> str:
    """Inicializa un nuevo ecosistema de apps para visibilidad transversal.

    Cada ecosistema vive aislado. Si un ecosistema con el mismo ID ya existe,
    usa switch_ecosystem para activarlo o reset_ecosystem para eliminarlo.

    Args:
        config: Objeto con ecosystem_id, name, y description.
    """
    config_dict = _ensure_dict(config)
    result = handle_init_ecosystem(config_dict)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def register_app(app_config: dict) -> str:
    """Registra una app en el ecosistema y sincroniza sus entidades/flujos.

    Lee el .hu-memory/ de la app para indexar su estado actual.
    Permite definir contratos de integracion con otras apps.

    Args:
        app_config: Objeto con app_id, name, memory_path, coupling_type (cohesive/decoupled), description, team, contracts (opcional).
    """
    app_dict = _ensure_dict(app_config)
    result = handle_register_app(app_dict)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def list_ecosystem() -> str:
    """Lista todas las apps del ecosistema activo con sus dependencias, contratos y entidades compartidas."""
    result = handle_list_ecosystem()
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_cross_app_context(story_id: str) -> str:
    """Obtiene contexto transversal de otras apps del ecosistema relevante para una HU.

    Busca entidades compartidas, contratos de integracion y apps que
    tocan los mismos dominios que la HU indicada.

    Args:
        story_id: Identificador de la HU del proyecto actual.
    """
    result = handle_get_cross_app_context(story_id)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def sync_ecosystem(app_id: str = "") -> str:
    """Re-sincroniza las apps del ecosistema leyendo sus .hu-memory/ actualizados.

    Args:
        app_id: ID de app especifica para sincronizar, o vacio para sincronizar todas.
    """
    result = handle_sync_ecosystem(app_id if app_id else "")
    return json.dumps(result, ensure_ascii=False, indent=2)


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    logger.info("Iniciando MCP_HU_SegurosBolivar v2.0.0 (stdio)")
    # Arrancar visualizador de grafo en background (puerto 9751)
    from src.engine.visualizer import start_visualizer
    start_visualizer()
    mcp.run(transport="stdio")
