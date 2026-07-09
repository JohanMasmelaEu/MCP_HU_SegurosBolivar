"""MCP Server para analisis inteligente de Historias de Usuario.

Panel de 10 expertos, memoria contextual local, segmentacion inteligente
de contexto y motor de estimacion adaptativa.
Transport: stdio (Docker).
"""

import json
import logging

from mcp.server.fastmcp import FastMCP

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
from src.tools.estimation_tools import (
    handle_estimate_story,
    handle_register_completion,
    handle_get_velocity,
    handle_calibrate_estimates,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mcp_hu")

mcp = FastMCP(
    name="MCP_HU_SegurosBolivar",
    version="1.0.0",
    description=(
        "MCP Server para analisis inteligente de Historias de Usuario. "
        "Panel de 10 expertos, memoria contextual, segmentacion de contexto "
        "y estimacion adaptativa. Produce HUs estandarizadas sin ambiguedades."
    ),
)


# ─── PROJECT MANAGEMENT ─────────────────────────────────────────────────────────


@mcp.tool()
async def init_project(config: str) -> str:
    """Inicializa un nuevo proyecto y crea la memoria local (.hu-memory/).

    Args:
        config: JSON con project_name, domain, stakeholders y description.
    """
    config_dict = json.loads(config)
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
    result = handle_analyze_story(story_text)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def add_story(story_json: str) -> str:
    """Persiste una HU analizada en la memoria y actualiza el grafo de relaciones.

    Args:
        story_json: JSON completo de la HU (output de analyze_story, posiblemente editado).
    """
    story_dict = json.loads(story_json)
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
async def register_completion(completion_json: str) -> str:
    """Registra la finalizacion de una HU con horas reales (calibra el motor).

    Args:
        completion_json: JSON con story_id, actual_hours, y notes opcionales.
    """
    data = json.loads(completion_json)
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


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    logger.info("Iniciando MCP_HU_SegurosBolivar v1.0.0 (stdio)")
    mcp.run(transport="stdio")
