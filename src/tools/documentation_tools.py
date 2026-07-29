"""Tool handlers para integración documental con Jira, Confluence y Clockwork Pro.

INVARIANTES DE SEGURIDAD:
- TODA operación contra APIs externas requiere confirmación manual explícita.
- Las tools de API retornan PendingAction como preview. Solo confirm_action ejecuta.
- La allowlist es inmutable — no se amplía por prompt ni por sesión.
- No existe path de código que ejecute DELETE contra Confluence.

Tools offline (sin API, siempre disponibles):
- handle_generate_bitacora: Genera bitácora del proyecto en Markdown + Confluence HTML
- handle_generate_daily_bitacora: Compila bitácora diaria con validación de 8h

Tools de Jira (requieren confirmación):
- handle_jira_query_issue: Consulta detalle de un issue
- handle_jira_search: Búsqueda por JQL
- handle_jira_add_comment: Agrega comentario
- handle_jira_create_subtask: Crea subtarea (nunca issues de primer nivel)
- handle_jira_transition: Mueve issue entre columnas

Tools de Confluence (requieren confirmación):
- handle_confluence_read_page: Lee página completa
- handle_confluence_create_page: Crea página nueva
- handle_confluence_update_page: Actualiza página (con advertencia si es ajena)

Tools de Clockwork Pro (requieren confirmación):
- handle_clockwork_get_assignments: Lista subtareas asignadas en sprint activo
- handle_clockwork_get_activity_types: Obtiene tipos de tarea dinámicamente
- handle_clockwork_register_time: Inicia/detiene timer

Tools de gestión:
- handle_confirm_action: Ejecuta acción previamente preparada y confirmada
- handle_reject_action: Rechaza/cancela acción pendiente
- handle_list_pending_actions: Lista acciones pendientes de confirmación
- handle_check_credentials_status: Verifica qué credenciales están configuradas
"""

import logging

from src.clients.base_client import (
    ActionNotConfirmedError,
    ActionNotFoundError,
    CredentialsNotConfiguredError,
    check_atlassian_credentials,
    check_clockwork_credentials,
)
from src.clients.clockwork_client import get_clockwork_client
from src.clients.confluence_client import get_confluence_client
from src.clients.jira_client import get_jira_client
from src.engine.bitacora import get_bitacora_engine
from src.models.documentation import ActionStatus

logger = logging.getLogger("mcp_hu.tools.documentation")


# ─── OFFLINE TOOLS (siempre disponibles, sin API) ────────────────────────────────


def handle_generate_bitacora() -> dict:
    """Genera bitácora completa del proyecto en formato exportable.

    No requiere tokens ni conexión. Genera Markdown y Confluence Storage Format
    desde la memoria local del proyecto.

    Returns:
        Dict con markdown_content, confluence_html y rutas de archivos.
    """
    engine = get_bitacora_engine()
    return engine.generate_project_bitacora()


def handle_generate_daily_bitacora(data: dict) -> dict:
    """Compila bitácora diaria con entradas de trabajo.

    Aplica la regla de 8 horas y genera formatos exportables.

    Args:
        data: Dict con user_email, entries (list de dicts), y target_date opcional.

    Returns:
        Dict con bitácora, validación de horas y contenido formateado.
    """
    user_email = data.get("user_email", "")
    entries = data.get("entries", [])
    target_date = data.get("target_date")

    if not user_email:
        return {"status": "error", "message": "Se requiere user_email."}
    if not entries:
        return {"status": "error", "message": "Se requiere al menos una entrada en entries."}

    engine = get_bitacora_engine()
    return engine.generate_daily_bitacora(
        user_email=user_email,
        entries=entries,
        target_date=target_date,
    )


# ─── JIRA TOOLS (requieren confirmación manual) ──────────────────────────────────


def handle_jira_get_worklogs(data: dict) -> dict:
    """Prepara consulta de worklogs registrados en un issue de Jira.

    Permite consultar todos los worklogs de un issue, opcionalmente filtrados
    por rango de fechas. Útil para verificar worklogs existentes antes de
    crear nuevos (evitar solapamiento).

    NO ejecuta la consulta. Retorna preview para confirmación del usuario.

    Args:
        data: Dict con issue_key (requerido), started_after (epoch ms, opcional),
              started_before (epoch ms, opcional).

    Returns:
        Dict con la acción pendiente (preview).
    """
    available, missing = check_atlassian_credentials()
    if not available:
        return {
            "status": "error",
            "message": f"Credenciales Atlassian no configuradas. Faltan: {', '.join(missing)}",
        }

    issue_key = data.get("issue_key", "")
    if not issue_key:
        return {"status": "error", "message": "Se requiere issue_key."}

    client = get_jira_client()
    action = client.prepare_get_worklogs(
        issue_key=issue_key,
        started_after=data.get("started_after"),
        started_before=data.get("started_before"),
    )
    return _action_to_preview(action)


def handle_jira_delete_worklog(data: dict) -> dict:
    """Prepara eliminar un worklog propio del usuario en un issue de Jira.

    SOLO elimina worklogs del usuario autenticado. Jira valida ownership.
    Útil para corregir worklogs duplicados o con datos incorrectos.

    NO elimina directamente. Retorna preview para confirmación del usuario.

    Args:
        data: Dict con issue_key y worklog_id.

    Returns:
        Dict con la acción pendiente (preview).
    """
    available, missing = check_atlassian_credentials()
    if not available:
        return {
            "status": "error",
            "message": f"Credenciales Atlassian no configuradas. Faltan: {', '.join(missing)}",
        }

    issue_key = data.get("issue_key", "")
    worklog_id = data.get("worklog_id", "")

    if not issue_key or not worklog_id:
        return {
            "status": "error",
            "message": "Se requieren: issue_key y worklog_id.",
        }

    client = get_jira_client()
    action = client.prepare_delete_worklog(issue_key=issue_key, worklog_id=str(worklog_id))
    return _action_to_preview(action)


def handle_jira_query_issue(issue_key: str) -> dict:
    """Prepara consulta detallada de un issue en Jira.

    NO ejecuta la consulta. Retorna preview para confirmación del usuario.

    Args:
        issue_key: Key del issue (ej: PROJ-123).

    Returns:
        Dict con la acción pendiente (preview) o error si no hay credenciales.
    """
    available, missing = check_atlassian_credentials()
    if not available:
        return {
            "status": "error",
            "message": f"Credenciales Atlassian no configuradas. Faltan: {', '.join(missing)}",
        }

    client = get_jira_client()
    action = client.prepare_get_issue(issue_key)
    return _action_to_preview(action)


def handle_jira_search(jql: str, max_results: int = 50) -> dict:
    """Prepara búsqueda de issues por JQL.

    NO ejecuta la búsqueda. Retorna preview para confirmación del usuario.

    Args:
        jql: Query JQL.
        max_results: Máximo de resultados.

    Returns:
        Dict con la acción pendiente (preview).
    """
    available, missing = check_atlassian_credentials()
    if not available:
        return {
            "status": "error",
            "message": f"Credenciales Atlassian no configuradas. Faltan: {', '.join(missing)}",
        }

    client = get_jira_client()
    action = client.prepare_search_issues(jql, max_results)
    return _action_to_preview(action)


def handle_jira_add_comment(issue_key: str, comment_text: str) -> dict:
    """Prepara agregar un comentario a un issue.

    NO publica el comentario. Retorna preview para confirmación del usuario.

    Args:
        issue_key: Key del issue.
        comment_text: Texto del comentario.

    Returns:
        Dict con la acción pendiente (preview).
    """
    available, missing = check_atlassian_credentials()
    if not available:
        return {
            "status": "error",
            "message": f"Credenciales Atlassian no configuradas. Faltan: {', '.join(missing)}",
        }

    if not comment_text.strip():
        return {"status": "error", "message": "El texto del comentario no puede estar vacío."}

    client = get_jira_client()
    action = client.prepare_add_comment(issue_key, comment_text)
    return _action_to_preview(action)


def handle_jira_create_subtask(data: dict) -> dict:
    """Prepara crear una subtarea dentro de un issue existente.

    SOLO crea subtareas. NUNCA issues de primer nivel.
    NO crea la subtarea. Retorna preview para confirmación del usuario.

    Args:
        data: Dict con parent_key, project_key, summary, description, assignee_account_id.

    Returns:
        Dict con la acción pendiente (preview).
    """
    available, missing = check_atlassian_credentials()
    if not available:
        return {
            "status": "error",
            "message": f"Credenciales Atlassian no configuradas. Faltan: {', '.join(missing)}",
        }

    parent_key = data.get("parent_key", "")
    project_key = data.get("project_key", "")
    summary = data.get("summary", "")

    if not parent_key or not project_key or not summary:
        return {
            "status": "error",
            "message": "Se requieren: parent_key, project_key y summary.",
        }

    client = get_jira_client()
    action = client.prepare_create_subtask(
        parent_key=parent_key,
        project_key=project_key,
        summary=summary,
        description=data.get("description", ""),
        assignee_account_id=data.get("assignee_account_id"),
    )
    return _action_to_preview(action)


def handle_jira_add_worklog(data: dict) -> dict:
    """Prepara registrar un worklog retroactivo en un issue de Jira.

    Permite registrar tiempo trabajado con fecha y hora específicas.
    Clockwork Pro sincroniza automáticamente los worklogs nativos de Jira.
    NO registra el worklog directamente. Retorna preview para confirmación.

    Incluye current_datetime_bogota para eliminar ambigüedad de fechas
    y overlap_check_reminder para recordar al agente verificar solapamiento.

    Args:
        data: Dict con issue_key, started (ISO 8601), time_spent_seconds,
              comment (opcional).

    Returns:
        Dict con la acción pendiente (preview), datetime actual y recordatorio.
    """
    available, missing = check_atlassian_credentials()
    if not available:
        return {
            "status": "error",
            "message": f"Credenciales Atlassian no configuradas. Faltan: {', '.join(missing)}",
        }

    issue_key = data.get("issue_key", "")
    started = data.get("started", "")
    time_spent_seconds = data.get("time_spent_seconds")

    if not issue_key:
        return {"status": "error", "message": "Se requiere issue_key."}
    if not started:
        return {"status": "error", "message": "Se requiere started (formato ISO 8601, ej: 2026-07-28T09:00:00.000-0500)."}
    if not time_spent_seconds or int(time_spent_seconds) <= 0:
        return {"status": "error", "message": "Se requiere time_spent_seconds > 0."}

    client = get_jira_client()
    action = client.prepare_add_worklog(
        issue_key=issue_key,
        started=started,
        time_spent_seconds=int(time_spent_seconds),
        comment=data.get("comment", ""),
    )

    preview = _action_to_preview(action)

    # Inyectar datetime actual (timezone Bogotá) para eliminar ambigüedad
    preview["current_datetime_bogota"] = _get_current_datetime_bogota()

    # Recordatorio de validación de solapamiento
    preview["overlap_check_reminder"] = (
        "IMPORTANTE: Antes de confirmar, verifica que no existan worklogs "
        "en la misma franja horaria usando jira_get_worklogs con el issue_key "
        "y filtrando por la fecha del worklog. Si hay solapamiento, ajusta "
        "las horas o consulta al usuario."
    )

    return preview


def handle_jira_transition(data: dict) -> dict:
    """Prepara mover un issue a otra columna del flujo de trabajo.

    SOLO mueve entre columnas existentes. JAMÁS modifica el flujo.
    NO ejecuta la transición. Retorna preview para confirmación del usuario.

    Args:
        data: Dict con issue_key, transition_id, transition_name.

    Returns:
        Dict con la acción pendiente (preview).
    """
    available, missing = check_atlassian_credentials()
    if not available:
        return {
            "status": "error",
            "message": f"Credenciales Atlassian no configuradas. Faltan: {', '.join(missing)}",
        }

    issue_key = data.get("issue_key", "")
    transition_id = data.get("transition_id", "")
    transition_name = data.get("transition_name", "")

    if not issue_key or not transition_id:
        return {
            "status": "error",
            "message": "Se requieren: issue_key y transition_id. Usar get_transitions primero.",
        }

    client = get_jira_client()
    action = client.prepare_transition_issue(issue_key, transition_id, transition_name)
    return _action_to_preview(action)


# ─── CONFLUENCE TOOLS (requieren confirmación manual) ─────────────────────────────


def handle_confluence_read_page(page_id: str) -> dict:
    """Prepara lectura completa de una página de Confluence.

    NO lee la página. Retorna preview para confirmación del usuario.

    Args:
        page_id: ID numérico de la página.

    Returns:
        Dict con la acción pendiente (preview).
    """
    available, missing = check_atlassian_credentials()
    if not available:
        return {
            "status": "error",
            "message": f"Credenciales Atlassian no configuradas. Faltan: {', '.join(missing)}",
        }

    client = get_confluence_client()
    action = client.prepare_get_page(page_id)
    return _action_to_preview(action)


def handle_confluence_create_page(data: dict) -> dict:
    """Prepara crear una página nueva en Confluence.

    NO crea la página. Retorna preview para confirmación del usuario.

    Args:
        data: Dict con space_key, title, body_html, ancestor_id.

    Returns:
        Dict con la acción pendiente (preview).
    """
    available, missing = check_atlassian_credentials()
    if not available:
        return {
            "status": "error",
            "message": f"Credenciales Atlassian no configuradas. Faltan: {', '.join(missing)}",
        }

    space_key = data.get("space_key", "")
    title = data.get("title", "")
    body_html = data.get("body_html", "")
    ancestor_id = data.get("ancestor_id", "")

    if not space_key or not title or not body_html or not ancestor_id:
        return {
            "status": "error",
            "message": "Se requieren: space_key, title, body_html y ancestor_id.",
        }

    client = get_confluence_client()
    action = client.prepare_create_page(space_key, title, body_html, ancestor_id)
    return _action_to_preview(action)


def handle_confluence_update_page(data: dict) -> dict:
    """Prepara actualizar una página existente en Confluence.

    Si la página es de otro usuario, incluye advertencia ENFÁTICA.
    NO actualiza la página. Retorna preview para confirmación del usuario.

    Args:
        data: Dict con page_id, title, body_html, current_version, is_own_page, author_name.

    Returns:
        Dict con la acción pendiente (preview).
    """
    available, missing = check_atlassian_credentials()
    if not available:
        return {
            "status": "error",
            "message": f"Credenciales Atlassian no configuradas. Faltan: {', '.join(missing)}",
        }

    page_id = data.get("page_id", "")
    title = data.get("title", "")
    body_html = data.get("body_html", "")
    current_version = data.get("current_version", 0)
    is_own_page = data.get("is_own_page", False)
    author_name = data.get("author_name", "desconocido")

    if not page_id or not title or not body_html or not current_version:
        return {
            "status": "error",
            "message": "Se requieren: page_id, title, body_html y current_version.",
        }

    client = get_confluence_client()
    action = client.prepare_update_page(
        page_id=page_id,
        title=title,
        body_html=body_html,
        current_version=current_version,
        is_own_page=is_own_page,
        author_name=author_name,
    )
    return _action_to_preview(action)


# ─── CLOCKWORK PRO TOOLS (requieren confirmación manual) ──────────────────────────


def handle_clockwork_get_assignments(data: dict) -> dict:
    """Prepara consulta de worklogs/asignaciones del usuario en sprint activo.

    Solo muestra subtareas del usuario autenticado en la iteración activa.
    NO ejecuta la consulta. Retorna preview para confirmación.

    Args:
        data: Dict con starting_at, ending_at, account_id, project_keys (opcional).

    Returns:
        Dict con la acción pendiente (preview).
    """
    available, missing = check_clockwork_credentials()
    if not available:
        return {
            "status": "error",
            "message": f"Credenciales Clockwork no configuradas. Faltan: {', '.join(missing)}",
        }

    starting_at = data.get("starting_at", "")
    ending_at = data.get("ending_at", "")
    account_id = data.get("account_id", "")

    if not starting_at or not ending_at or not account_id:
        return {
            "status": "error",
            "message": "Se requieren: starting_at, ending_at y account_id.",
        }

    client = get_clockwork_client()
    action = client.prepare_get_worklogs(
        starting_at=starting_at,
        ending_at=ending_at,
        account_id=account_id,
        project_keys=data.get("project_keys"),
    )
    return _action_to_preview(action)


def handle_clockwork_get_activity_types() -> dict:
    """Prepara consulta de tipos de tarea (Activity Types) de Clockwork.

    Los tipos se obtienen dinámicamente — NUNCA hardcodeados.
    El usuario decide cuál aplica. El agente NO sugiere.
    NO ejecuta la consulta. Retorna preview para confirmación.

    Returns:
        Dict con la acción pendiente (preview).
    """
    available, missing = check_clockwork_credentials()
    if not available:
        return {
            "status": "error",
            "message": f"Credenciales Clockwork no configuradas. Faltan: {', '.join(missing)}",
        }

    client = get_clockwork_client()
    action = client.prepare_get_activity_types()
    return _action_to_preview(action)


def handle_clockwork_start_timer(issue_key: str) -> dict:
    """Prepara inicio de timer en una subtarea.

    NO inicia el timer. Retorna preview para confirmación.

    Args:
        issue_key: Key de la subtarea.

    Returns:
        Dict con la acción pendiente (preview).
    """
    available, missing = check_clockwork_credentials()
    if not available:
        return {
            "status": "error",
            "message": f"Credenciales Clockwork no configuradas. Faltan: {', '.join(missing)}",
        }

    client = get_clockwork_client()
    action = client.prepare_start_timer(issue_key)
    return _action_to_preview(action)


def handle_clockwork_stop_timer(issue_key: str) -> dict:
    """Prepara detener timer en una subtarea.

    NO detiene el timer. Retorna preview para confirmación.

    Args:
        issue_key: Key de la subtarea.

    Returns:
        Dict con la acción pendiente (preview).
    """
    available, missing = check_clockwork_credentials()
    if not available:
        return {
            "status": "error",
            "message": f"Credenciales Clockwork no configuradas. Faltan: {', '.join(missing)}",
        }

    client = get_clockwork_client()
    action = client.prepare_stop_timer(issue_key)
    return _action_to_preview(action)


# ─── GESTIÓN DE ACCIONES (confirm / reject / list) ───────────────────────────────


def handle_confirm_action(action_id: str, service: str) -> dict:
    """Ejecuta una acción previamente preparada y CONFIRMADA por el usuario.

    SOLO ejecuta si:
    1. La acción existe
    2. El status es CONFIRMED
    3. La operación está en la allowlist

    Args:
        action_id: ID de la acción a ejecutar.
        service: Servicio de la acción (jira, confluence, clockwork).

    Returns:
        Dict con el resultado de la ejecución o error.
    """
    client = _get_client_by_service(service)
    if not client:
        return {"status": "error", "message": f"Servicio '{service}' no reconocido."}

    # Confirmar la acción primero (cambiar status a CONFIRMED)
    try:
        client.confirm_action(action_id)
    except ActionNotFoundError:
        return {
            "status": "error",
            "message": f"Acción '{action_id}' no encontrada. Puede haber expirado.",
        }

    # Ejecutar
    try:
        result = client.execute_confirmed(action_id)
        return {
            "status": "success",
            "action_id": action_id,
            "result": result,
            "message": "Acción ejecutada correctamente.",
        }
    except ActionNotConfirmedError:
        return {
            "status": "error",
            "message": f"Acción '{action_id}' no fue confirmada. No se ejecutará.",
        }
    except CredentialsNotConfiguredError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.exception("Error ejecutando acción %s", action_id)
        return {"status": "error", "message": f"Error de ejecución: {e}"}


def handle_reject_action(action_id: str, service: str) -> dict:
    """Rechaza/cancela una acción pendiente.

    Args:
        action_id: ID de la acción a rechazar.
        service: Servicio de la acción.

    Returns:
        Dict con confirmación de rechazo.
    """
    client = _get_client_by_service(service)
    if not client:
        return {"status": "error", "message": f"Servicio '{service}' no reconocido."}

    try:
        action = client.reject_action(action_id)
        return {
            "status": "success",
            "action_id": action_id,
            "message": f"Acción rechazada: {action.description}",
        }
    except ActionNotFoundError:
        return {
            "status": "error",
            "message": f"Acción '{action_id}' no encontrada.",
        }


def handle_list_pending_actions() -> dict:
    """Lista todas las acciones pendientes de confirmación en todos los servicios.

    Returns:
        Dict con las acciones pendientes agrupadas por servicio.
    """
    pending: dict = {"jira": [], "confluence": [], "clockwork": []}

    # Jira
    try:
        jira = get_jira_client()
        for action in jira.get_pending_actions():
            pending["jira"].append(action.model_dump(mode="json"))
    except Exception:
        pass

    # Confluence
    try:
        confluence = get_confluence_client()
        for action in confluence.get_pending_actions():
            pending["confluence"].append(action.model_dump(mode="json"))
    except Exception:
        pass

    # Clockwork
    try:
        clockwork = get_clockwork_client()
        for action in clockwork.get_pending_actions():
            pending["clockwork"].append(action.model_dump(mode="json"))
    except Exception:
        pass

    total = sum(len(v) for v in pending.values())
    return {
        "status": "success",
        "total_pending": total,
        "pending_actions": pending,
        "message": f"{total} acciones pendientes de confirmación." if total > 0
        else "No hay acciones pendientes.",
    }


# ─── UTILIDADES INTERNAS ──────────────────────────────────────────────────────────


def _get_current_datetime_bogota() -> str:
    """Obtiene la fecha y hora actual en timezone America/Bogota.

    Útil para eliminar ambigüedad de 'ayer'/'hoy' cuando el prompt
    del sistema tiene una fecha que puede no coincidir con la hora real
    del usuario (ej: pasada medianoche).

    Returns:
        String ISO 8601 con timezone Colombia (ej: 2026-07-28T14:30:00-05:00).
    """
    from datetime import datetime, timezone, timedelta

    bogota_offset = timezone(timedelta(hours=-5))
    now_bogota = datetime.now(bogota_offset)
    return now_bogota.strftime("%Y-%m-%dT%H:%M:%S-05:00")


def _action_to_preview(action) -> dict:
    """Convierte un PendingAction en un dict de preview para el usuario.

    Args:
        action: PendingAction generada por un cliente.

    Returns:
        Dict con toda la info necesaria para que el usuario confirme o rechace.
    """
    return {
        "status": "pending_confirmation",
        "action_id": action.action_id,
        "service": action.service.value,
        "operation": action.operation,
        "description": action.description,
        "impact": action.impact,
        "method": action.method,
        "endpoint": action.endpoint,
        "payload_preview": action.payload_preview,
        "reversible": action.reversible,
        "message": (
            f"Acción preparada: {action.description}. "
            f"Impacto: {action.impact} "
            f"¿Confirmas la ejecución? Usa confirm_action con action_id='{action.action_id}' "
            f"y service='{action.service.value}' para ejecutar, "
            f"o reject_action para cancelar."
        ),
    }


def _get_client_by_service(service: str):
    """Obtiene el cliente singleton correspondiente al servicio.

    Args:
        service: Nombre del servicio (jira, confluence, clockwork).

    Returns:
        Instancia del cliente o None si no se reconoce.
    """
    if service == "jira":
        return get_jira_client()
    elif service == "confluence":
        return get_confluence_client()
    elif service == "clockwork":
        return get_clockwork_client()
    return None


# ─── VERIFICACIÓN DE CREDENCIALES ─────────────────────────────────────────────────


def handle_check_credentials_status() -> dict:
    """Verifica el estado de configuración de credenciales para todos los servicios.

    NO expone los valores de los tokens — solo indica si están configurados o no.
    Proporciona instrucciones de configuración si faltan credenciales.

    Returns:
        Dict con el estado de cada servicio y guía de configuración.
    """
    import os

    atlassian_available, atlassian_missing = check_atlassian_credentials()
    clockwork_available, clockwork_missing = check_clockwork_credentials()

    # Construir estado detallado sin exponer valores
    atlassian_status = {
        "configured": atlassian_available,
        "services": ["Jira", "Confluence"],
        "variables": {
            "ATLASSIAN_EMAIL": bool(os.environ.get("ATLASSIAN_EMAIL")),
            "ATLASSIAN_API_TOKEN": bool(os.environ.get("ATLASSIAN_API_TOKEN")),
            "ATLASSIAN_DOMAIN": bool(os.environ.get("ATLASSIAN_DOMAIN")),
        },
        "missing": atlassian_missing,
    }

    clockwork_status = {
        "configured": clockwork_available,
        "services": ["Clockwork Pro"],
        "variables": {
            "CLOCKWORK_API_TOKEN": bool(os.environ.get("CLOCKWORK_API_TOKEN")),
        },
        "missing": clockwork_missing,
    }

    all_configured = atlassian_available and clockwork_available

    # Instrucciones de configuración
    setup_instructions = None
    if not all_configured:
        setup_instructions = {
            "atlassian_token": {
                "step_1": "Ir a https://id.atlassian.com/manage-profile/security/api-tokens",
                "step_2": "Click en 'Create API token'",
                "step_3": "Copiar el token (se muestra una vez)",
                "note": "Un solo token sirve para Jira Y Confluence",
            },
            "clockwork_token": {
                "step_1": "En Jira, ir a Apps > Clockwork",
                "step_2": "En la barra lateral, click en 'API tokens'",
                "step_3": "Click en 'Create token' y copiar",
            },
            "configuration_options": [
                {
                    "method": "MCP config (recomendado para Kiro)",
                    "file": ".kiro/settings/mcp.json",
                    "example": {
                        "mcpServers": {
                            "mcp-hu": {
                                "command": "python",
                                "args": ["-m", "src"],
                                "env": {
                                    "ATLASSIAN_EMAIL": "tu.email@segurosbolivar.com",
                                    "ATLASSIAN_API_TOKEN": "tu-token-aqui",
                                    "ATLASSIAN_DOMAIN": "jirasegurosbolivar.atlassian.net",
                                    "CLOCKWORK_API_TOKEN": "tu-token-clockwork-aqui",
                                },
                            }
                        }
                    },
                },
                {
                    "method": "Docker (producción)",
                    "example": "docker run -e ATLASSIAN_EMAIL=... -e ATLASSIAN_API_TOKEN=... -e ATLASSIAN_DOMAIN=... -e CLOCKWORK_API_TOKEN=... mcp-hu-server",
                },
                {
                    "method": "PowerShell (sesión temporal)",
                    "example": '$env:ATLASSIAN_EMAIL = "tu.email@segurosbolivar.com"',
                },
            ],
        }

    return {
        "status": "success",
        "all_configured": all_configured,
        "atlassian": atlassian_status,
        "clockwork": clockwork_status,
        "setup_instructions": setup_instructions,
        "message": (
            "Todas las credenciales configuradas. Las tools de API están disponibles."
            if all_configured
            else (
                f"Credenciales faltantes. "
                f"{'Atlassian: ' + ', '.join(atlassian_missing) + '. ' if atlassian_missing else ''}"
                f"{'Clockwork: ' + ', '.join(clockwork_missing) + '.' if clockwork_missing else ''} "
                f"Ver setup_instructions para instrucciones de configuración."
            )
        ),
    }
