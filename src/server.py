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
from src.engine.rules_catalog import init_rules_catalog
from src.engine.spec_engine import init_spec_engine
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
from src.tools.sdd_tools import (
    handle_manage_rules_catalog,
    handle_create_spec,
    handle_update_spec_layer,
    handle_approve_spec,
    handle_get_spec,
    handle_list_specs,
    handle_get_constellation,
    handle_add_spec_dependency,
    handle_detect_constellation_gaps,
    handle_export_spec_markdown,
    handle_import_spec,
)
from src.tools.documentation_tools import (
    handle_generate_bitacora,
    handle_generate_daily_bitacora,
    handle_jira_get_worklogs,
    handle_jira_delete_worklog,
    handle_jira_query_issue,
    handle_jira_search,
    handle_jira_add_comment,
    handle_jira_add_worklog,
    handle_jira_create_subtask,
    handle_jira_transition,
    handle_confluence_read_page,
    handle_confluence_create_page,
    handle_confluence_update_page,
    handle_clockwork_get_assignments,
    handle_clockwork_get_activity_types,
    handle_clockwork_start_timer,
    handle_clockwork_stop_timer,
    handle_confirm_action,
    handle_reject_action,
    handle_list_pending_actions,
    handle_check_credentials_status,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mcp_hu")

# ─── INICIALIZAR MANAGERS ────────────────────────────────────────────────────────
# Los managers se inicializan al importar el modulo. Detectan automaticamente
# memorias legacy y las migran al nuevo formato multi-workspace/ecosistema.

_ws_manager = init_workspace_manager()
_eco_manager = init_ecosystem_manager()
_rules_catalog = init_rules_catalog()
_spec_engine = init_spec_engine()

# Restaurar ecosistema activo desde state persistido
_active_eco_id = _ws_manager.active_ecosystem_id
if _active_eco_id:
    _eco_manager.restore_active(_active_eco_id)


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
    instructions=(
        "MCP Server v2.0.0 para analisis inteligente de Historias de Usuario. "
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


# ─── SDD: RULES & SPECS ──────────────────────────────────────────────────────────


@mcp.tool()
async def manage_rules_catalog(action: str, rule_data: dict | None = None) -> str:
    """Gestiona el catálogo de reglas transversales corporativas.

    Permite agregar, listar, actualizar, eliminar y consultar reglas que aplican a capas SDD.

    Args:
        action: Acción: add, list, update, remove, get.
        rule_data: Datos de la regla. Para 'list' puede incluir {category}. Para 'get'/'remove' requiere {rule_id}.
    """
    data = _ensure_dict(rule_data) if rule_data else None
    result = handle_manage_rules_catalog(action, data)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def create_spec(spec_config: dict) -> str:
    """Crea una nueva especificación de proyecto (ProjectSpec) bajo el modelo SDD.

    Inicializa todas las capas SDD vacías y opcionalmente aplica reglas del catálogo.

    Args:
        spec_config: Objeto con spec_id, project_name, app_id (opcional), apply_rules (bool, default true).
    """
    config_dict = _ensure_dict(spec_config)
    result = handle_create_spec(config_dict)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def update_spec_layer(spec_id: str, layer: str, content: dict) -> str:
    """Actualiza el contenido de una capa SDD en una spec.

    Permite almacenar tanto el resumen y listas de items como el detalle expandido
    de cada decisión/constraint/artifact para exportación completa.

    Args:
        spec_id: ID de la spec.
        layer: Capa SDD (negocio, arquitectura, seguridad, gobierno_info, acceso_datos, datos, desarrollo, qa).
        content: Objeto con los siguientes campos:
            - summary (str): Resumen descriptivo de la capa.
            - decisions (list[str]): Lista de decisiones (ej: ["DN-001: Pipeline parametrizable por banderas"]).
            - constraints (list[str]): Lista de restricciones (ej: ["CN-001: Volumen 312K docs/mes"]).
            - artifacts (list[str]): Lista de artefactos/entregables.
            - details (dict[str, str]): Contenido expandido por ID. Clave = ID del item (ej: "DN-001"),
              Valor = descripción completa y detallada. Esto permite exportar el SDD con nivel de
              detalle profesional en lugar de solo bullets superficiales.
    """
    content_dict = _ensure_dict(content)
    result = handle_update_spec_layer(spec_id, layer, content_dict)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def approve_spec(spec_id: str, approver: str) -> str:
    """Aprueba una spec cambiando su status a 'approved'.

    Args:
        spec_id: ID de la spec a aprobar.
        approver: Nombre o ID del aprobador.
    """
    result = handle_approve_spec(spec_id, approver)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_spec(spec_id: str, role: str = "") -> str:
    """Obtiene una spec completa o filtrada por rol (profundidad según RoleDepthMatrix).

    Si se proporciona role, solo muestra capas visibles para ese rol con el nivel de detalle correspondiente.

    Args:
        spec_id: ID de la spec.
        role: Rol del stakeholder (opcional). Si vacío, retorna spec completa.
    """
    result = handle_get_spec(spec_id, role if role else None)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def list_specs() -> str:
    """Lista resúmenes de todas las specs disponibles (id, nombre, status, versión)."""
    result = handle_list_specs()
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_constellation(ecosystem_id: str = "", filter_type: str = "", filter_maturity: str = "") -> str:
    """Obtiene el grafo de specs (constelación) con sus dependencias tipificadas.

    Retorna nodos (specs) y edges (dependencias) en formato Cytoscape.js.

    Args:
        ecosystem_id: ID del ecosistema (opcional, usa activo si vacío).
        filter_type: Filtrar edges por tipo de relación (process, data, functional). Vacío = todos.
        filter_maturity: Filtrar edges por maturity (formalized, draft, reference). Vacío = todos.
    """
    result = handle_get_constellation(
        ecosystem_id if ecosystem_id else None,
        filter_type if filter_type else None,
        filter_maturity if filter_maturity else None,
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def add_spec_dependency(spec_id: str, target_spec_id: str, dependency_type: str, description: str = "") -> str:
    """Agrega una dependencia entre dos specs en la constelación.

    Args:
        spec_id: ID de la spec que depende.
        target_spec_id: ID de la spec de la que se depende.
        dependency_type: Tipo de relación: process, data, o functional.
        description: Descripción opcional de la dependencia.
    """
    result = handle_add_spec_dependency(spec_id, target_spec_id, dependency_type, description)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def detect_constellation_gaps(ecosystem_id: str = "") -> str:
    """Detecta gaps en la constelación de specs: huérfanas, referencias rotas, ciclos, apps sin spec.

    Args:
        ecosystem_id: ID del ecosistema (opcional, usa activo si vacío).
    """
    result = handle_detect_constellation_gaps(ecosystem_id if ecosystem_id else None)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def export_spec_markdown(spec_id: str, output_path: str = "") -> str:
    """Exporta una spec como archivo Markdown estructurado con contenido completo.

    Genera un documento profesional con capas, decisiones expandidas, constraints
    detallados, artefactos, reglas y dependencias. Incluye el campo 'details' de
    cada capa para máximo nivel de detalle.

    IMPORTANTE: Siempre retorna el campo 'markdown' en la respuesta JSON. Si se
    proporciona output_path, intentará escribir el archivo pero si falla (ej: MCP
    en Docker sin acceso al filesystem del host), retorna el markdown igualmente
    para que el llamador lo escriba con sus propias herramientas (fs_write, etc).

    Args:
        spec_id: ID de la spec a exportar.
        output_path: Ruta de salida (opcional). Vacío = solo retornar markdown como string.
                     Si se proporciona, intenta escribir + siempre retorna markdown.
    """
    result = handle_export_spec_markdown(spec_id, output_path if output_path else None)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def import_spec(source_path: str, as_reference: bool = True) -> str:
    """Importa specs desde un archivo Markdown o directorio de Markdowns.

    Las specs importadas entran como draft/reference por defecto.
    Detecta dependencias entre specs basado en el formato del markdown.

    Args:
        source_path: Ruta al archivo .md o directorio con archivos .md.
        as_reference: Si true, specs importadas entran con maturity reference (default true).
    """
    result = handle_import_spec(source_path, as_reference)
    return json.dumps(result, ensure_ascii=False, indent=2)


# ─── DOCUMENTATION & INTEGRATION ─────────────────────────────────────────────────
# INVARIANTES DE SEGURIDAD:
# - TODA operación contra Jira/Confluence/Clockwork requiere confirmación manual.
# - Las tools de API retornan preview (PendingAction). Solo confirm_action ejecuta.
# - La allowlist es inmutable en runtime. No se amplía por prompt ni por sesión.
# - No existe path de código que ejecute DELETE contra Confluence.


@mcp.tool()
async def generate_bitacora() -> str:
    """Genera bitacora completa del proyecto en formato exportable (Markdown + Confluence HTML).

    No requiere tokens ni conexion. Usa la memoria local del proyecto.
    El output se guarda como archivo local y se presenta para copiar-pegar.
    """
    result = handle_generate_bitacora()
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def generate_daily_bitacora(data: dict) -> str:
    """Compila bitacora diaria con entradas de trabajo y validacion de 8 horas.

    Aplica la regla de 8 horas normativas. Si el total excede, pregunta al usuario.

    Args:
        data: Objeto con user_email, entries (lista de subtareas trabajadas), y target_date opcional.
    """
    data_dict = _ensure_dict(data)
    result = handle_generate_daily_bitacora(data_dict)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def jira_get_worklogs(data: dict) -> str:
    """Prepara consulta de worklogs registrados en un issue de Jira. Requiere confirmacion del usuario.

    Permite consultar todos los worklogs de un issue, opcionalmente filtrados por rango de fechas.
    Util para verificar worklogs existentes antes de crear nuevos (evitar solapamiento).

    NO ejecuta la consulta directamente. Retorna preview para confirmacion manual.

    Args:
        data: Objeto con issue_key (requerido), started_after (epoch ms, opcional), started_before (epoch ms, opcional).
    """
    data_dict = _ensure_dict(data)
    result = handle_jira_get_worklogs(data_dict)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def jira_delete_worklog(data: dict) -> str:
    """Prepara eliminar un worklog propio del usuario en un issue de Jira. Requiere confirmacion del usuario.

    SOLO elimina worklogs del usuario autenticado (Jira valida ownership en el servidor).
    Util para corregir worklogs duplicados o registrados con datos incorrectos.

    NO elimina directamente. Muestra preview para confirmacion manual.

    Args:
        data: Objeto con issue_key y worklog_id.
    """
    data_dict = _ensure_dict(data)
    result = handle_jira_delete_worklog(data_dict)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def jira_query_issue(issue_key: str) -> str:
    """Prepara consulta detallada de un issue en Jira. Requiere confirmacion del usuario para ejecutar.

    NO ejecuta la consulta directamente. Retorna preview para confirmacion manual.

    Args:
        issue_key: Key del issue (ej: PROJ-123).
    """
    result = handle_jira_query_issue(issue_key)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def jira_search(jql: str, max_results: int = 50) -> str:
    """Prepara busqueda de issues por JQL. Requiere confirmacion del usuario para ejecutar.

    Args:
        jql: Query JQL para la busqueda.
        max_results: Maximo de resultados (default 50).
    """
    result = handle_jira_search(jql, max_results)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def jira_add_comment(issue_key: str, comment_text: str) -> str:
    """Prepara agregar un comentario a un issue en Jira. Requiere confirmacion del usuario.

    NO publica el comentario directamente. Muestra preview para confirmacion manual.

    Args:
        issue_key: Key del issue.
        comment_text: Texto del comentario a agregar.
    """
    result = handle_jira_add_comment(issue_key, comment_text)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def jira_add_worklog(data: dict) -> str:
    """Prepara registrar un worklog retroactivo en un issue de Jira. Requiere confirmacion del usuario.

    Permite registrar tiempo trabajado con fecha y hora especificas (retroactivo).
    Clockwork Pro sincroniza automaticamente los worklogs nativos de Jira,
    por lo que el registro aparecera en ambos sistemas.

    NO registra el worklog directamente. Muestra preview para confirmacion manual.

    Args:
        data: Objeto con issue_key, started (ISO 8601, ej: 2026-07-28T09:00:00.000-0500), time_spent_seconds, comment (opcional).
    """
    data_dict = _ensure_dict(data)
    result = handle_jira_add_worklog(data_dict)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def jira_create_subtask(data: dict) -> str:
    """Prepara crear una subtarea dentro de un issue existente. Requiere confirmacion del usuario.

    SOLO crea subtareas. NUNCA issues de primer nivel (HU, epicas).
    NO crea la subtarea directamente. Muestra preview para confirmacion manual.

    Args:
        data: Objeto con parent_key, project_key, summary, description (opcional), assignee_account_id (opcional).
    """
    data_dict = _ensure_dict(data)
    result = handle_jira_create_subtask(data_dict)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def jira_transition_issue(data: dict) -> str:
    """Prepara mover un issue a otra columna del flujo. Requiere confirmacion del usuario.

    SOLO mueve entre columnas existentes. JAMAS modifica parametros ni estructura del flujo.
    Usar jira_query_issue primero para ver transiciones disponibles.

    Args:
        data: Objeto con issue_key, transition_id, transition_name.
    """
    data_dict = _ensure_dict(data)
    result = handle_jira_transition(data_dict)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def confluence_read_page(page_id: str) -> str:
    """Prepara lectura completa de una pagina de Confluence. Requiere confirmacion del usuario.

    NO lee la pagina directamente. Retorna preview para confirmacion manual.

    Args:
        page_id: ID numerico de la pagina Confluence.
    """
    result = handle_confluence_read_page(page_id)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def confluence_create_page(data: dict) -> str:
    """Prepara crear una pagina nueva en Confluence. Requiere confirmacion del usuario.

    NO crea la pagina directamente. Muestra preview para confirmacion manual.

    Args:
        data: Objeto con space_key, title, body_html (Confluence Storage Format), ancestor_id (pagina padre).
    """
    data_dict = _ensure_dict(data)
    result = handle_confluence_create_page(data_dict)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def confluence_update_page(data: dict) -> str:
    """Prepara actualizar una pagina existente en Confluence. Requiere confirmacion del usuario.

    Si la pagina es de otro usuario, incluye advertencia enfatica antes de confirmar.
    NO actualiza directamente. Muestra preview para confirmacion manual.

    Args:
        data: Objeto con page_id, title, body_html, current_version, is_own_page (bool), author_name.
    """
    data_dict = _ensure_dict(data)
    result = handle_confluence_update_page(data_dict)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def clockwork_get_assignments(data: dict) -> str:
    """Prepara consulta de asignaciones del usuario en el sprint activo. Requiere confirmacion.

    Solo muestra subtareas del usuario autenticado en la iteracion activa.
    NO ejecuta la consulta directamente.

    Args:
        data: Objeto con starting_at (YYYY-MM-DD), ending_at (YYYY-MM-DD), account_id, project_keys (opcional).
    """
    data_dict = _ensure_dict(data)
    result = handle_clockwork_get_assignments(data_dict)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def clockwork_get_activity_types() -> str:
    """Prepara consulta de tipos de tarea disponibles en Clockwork Pro. Requiere confirmacion.

    Los tipos se obtienen dinamicamente de la API (nunca hardcodeados).
    El usuario decide cual aplica segun el contexto. El agente NO sugiere.
    """
    result = handle_clockwork_get_activity_types()
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def clockwork_start_timer(issue_key: str) -> str:
    """Prepara inicio de timer en una subtarea de Clockwork Pro. Requiere confirmacion.

    NO inicia el timer directamente. Muestra preview para confirmacion manual.

    Args:
        issue_key: Key de la subtarea (ej: PROJ-456).
    """
    result = handle_clockwork_start_timer(issue_key)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def clockwork_stop_timer(issue_key: str) -> str:
    """Prepara detener timer en una subtarea de Clockwork Pro. Requiere confirmacion.

    NO detiene el timer directamente. Muestra preview para confirmacion manual.

    Args:
        issue_key: Key de la subtarea.
    """
    result = handle_clockwork_stop_timer(issue_key)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def confirm_action(action_id: str, service: str) -> str:
    """Ejecuta una accion previamente preparada y CONFIRMADA por el usuario.

    SOLO ejecuta si el usuario ha dado confirmacion explicita en este turno.
    Verifica que la accion existe, esta en la allowlist, y tiene status confirmado.

    Args:
        action_id: ID de la accion pendiente (retornado por las tools de preparacion).
        service: Servicio de la accion (jira, confluence, clockwork).
    """
    result = handle_confirm_action(action_id, service)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def reject_action(action_id: str, service: str) -> str:
    """Rechaza/cancela una accion pendiente sin ejecutarla.

    Args:
        action_id: ID de la accion a rechazar.
        service: Servicio de la accion (jira, confluence, clockwork).
    """
    result = handle_reject_action(action_id, service)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def list_pending_actions() -> str:
    """Lista todas las acciones pendientes de confirmacion en todos los servicios."""
    result = handle_list_pending_actions()
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def check_credentials_status() -> str:
    """Verifica que credenciales estan configuradas para Jira, Confluence y Clockwork Pro.

    No expone valores de tokens — solo indica si estan presentes.
    Si faltan credenciales, muestra instrucciones paso a paso para configurarlas.
    """
    result = handle_check_credentials_status()
    return json.dumps(result, ensure_ascii=False, indent=2)


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    logger.info("Iniciando MCP_HU_SegurosBolivar v2.0.0 (stdio)")
    # Arrancar visualizador de grafo en background (puerto 9751)
    from src.engine.visualizer import start_visualizer
    start_visualizer()
    mcp.run(transport="stdio")
