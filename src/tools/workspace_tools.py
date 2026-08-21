"""Tool implementations: list_workspaces, switch_workspace, reset_workspace,
list_ecosystems, switch_ecosystem, reset_ecosystem.

Herramientas de gestion multi-workspace y multi-ecosistema.
"""

import logging
from typing import Optional

from src.engine.workspace_manager import get_workspace_manager
from src.engine.ecosystem_manager import get_ecosystem_manager

logger = logging.getLogger("mcp_hu.tools.workspace")


# ─── WORKSPACE TOOLS ─────────────────────────────────────────────────────────────


def handle_list_workspaces() -> dict:
    """Lista todos los workspaces disponibles.

    Returns:
        Lista de workspaces con metadata y cual es el activo.
    """
    manager = get_workspace_manager()
    if manager is None:
        return {"status": "error", "message": "WorkspaceManager no inicializado."}

    workspaces = manager.list_workspaces()

    return {
        "status": "success",
        "active_workspace": manager.active_workspace_id,
        "active_ecosystem": manager.active_ecosystem_id,
        "workspaces": [w.model_dump(mode="json") for w in workspaces],
        "total": len(workspaces),
        "message": (
            f"{len(workspaces)} workspace(s) encontrado(s). "
            f"Activo: '{manager.active_workspace_id or 'ninguno'}'."
        ),
    }


def handle_switch_workspace(workspace_id: str) -> dict:
    """Cambia el workspace activo.

    Args:
        workspace_id: ID del workspace a activar.

    Returns:
        Status de la operacion con resumen del workspace.
    """
    manager = get_workspace_manager()
    if manager is None:
        return {"status": "error", "message": "WorkspaceManager no inicializado."}

    if not workspace_id:
        return {"status": "error", "message": "Se requiere 'workspace_id'."}

    try:
        engine = manager.switch_workspace(workspace_id)
        index = engine.index

        result: dict = {
            "status": "success",
            "workspace_id": workspace_id,
            "message": f"Workspace activo cambiado a '{workspace_id}'.",
        }

        if index:
            result["project_name"] = index.config.project_name
            result["domain"] = index.config.domain
            result["story_count"] = index.story_count
            result["entities_count"] = len(index.entities)
            result["flows_count"] = len(index.flows)

        return result
    except ValueError as e:
        return {"status": "error", "message": str(e)}


def handle_reset_workspace(params: dict) -> dict:
    """Elimina un workspace.

    Args:
        params: Dict con workspace_id y confirm (bool).

    Returns:
        Status de la operacion.
    """
    manager = get_workspace_manager()
    if manager is None:
        return {"status": "error", "message": "WorkspaceManager no inicializado."}

    workspace_id = params.get("workspace_id")
    confirm = params.get("confirm", False)

    if not workspace_id:
        return {"status": "error", "message": "Se requiere 'workspace_id'."}

    try:
        manager.reset_workspace(workspace_id, confirm=confirm)
        return {
            "status": "success",
            "message": f"Workspace '{workspace_id}' eliminado exitosamente.",
        }
    except ValueError as e:
        return {"status": "error", "message": str(e)}


def handle_rename_workspace(workspace_id: str, new_name: str) -> dict:
    """Renombra un workspace (cambia su nombre y directorio).

    Args:
        workspace_id: ID actual del workspace a renombrar.
        new_name: Nuevo nombre del proyecto.

    Returns:
        Status con el nuevo workspace_id generado.
    """
    manager = get_workspace_manager()
    if manager is None:
        return {"status": "error", "message": "WorkspaceManager no inicializado."}

    if not workspace_id:
        return {"status": "error", "message": "Se requiere 'workspace_id'."}
    if not new_name or not new_name.strip():
        return {"status": "error", "message": "Se requiere 'new_name' (nombre nuevo del proyecto)."}

    try:
        new_id = manager.rename_workspace(workspace_id, new_name.strip())
        return {
            "status": "success",
            "old_workspace_id": workspace_id,
            "new_workspace_id": new_id,
            "new_name": new_name.strip(),
            "message": f"Workspace '{workspace_id}' renombrado a '{new_name.strip()}' (nuevo ID: '{new_id}').",
        }
    except ValueError as e:
        return {"status": "error", "message": str(e)}


# ─── ECOSYSTEM TOOLS ─────────────────────────────────────────────────────────────


def handle_list_ecosystems() -> dict:
    """Lista todos los ecosistemas disponibles.

    Returns:
        Lista de ecosistemas con metadata y cual es el activo.
    """
    eco_manager = get_ecosystem_manager()
    ws_manager = get_workspace_manager()

    if eco_manager is None:
        return {"status": "error", "message": "EcosystemManager no inicializado."}

    ecosystems = eco_manager.list_ecosystems()
    active_id: Optional[str] = None
    if ws_manager:
        active_id = ws_manager.active_ecosystem_id

    return {
        "status": "success",
        "active_ecosystem": active_id,
        "ecosystems": ecosystems,
        "total": len(ecosystems),
        "message": (
            f"{len(ecosystems)} ecosistema(s) encontrado(s). "
            f"Activo: '{active_id or 'ninguno'}'."
        ),
    }


def handle_switch_ecosystem(ecosystem_id: str) -> dict:
    """Cambia el ecosistema activo.

    Args:
        ecosystem_id: ID del ecosistema a activar.

    Returns:
        Status de la operacion con resumen del ecosistema.
    """
    eco_manager = get_ecosystem_manager()
    ws_manager = get_workspace_manager()

    if eco_manager is None:
        return {"status": "error", "message": "EcosystemManager no inicializado."}

    if not ecosystem_id:
        return {"status": "error", "message": "Se requiere 'ecosystem_id'."}

    try:
        engine = eco_manager.switch_ecosystem(ecosystem_id)

        # Persistir en el state compartido
        if ws_manager:
            ws_manager.set_active_ecosystem(ecosystem_id)

        registry = engine.registry
        result: dict = {
            "status": "success",
            "ecosystem_id": ecosystem_id,
            "message": f"Ecosistema activo cambiado a '{ecosystem_id}'.",
        }

        if registry:
            result["name"] = registry.name
            result["description"] = registry.description
            result["apps_count"] = len(registry.apps)
            result["contracts_count"] = len(registry.contracts)

        return result
    except ValueError as e:
        return {"status": "error", "message": str(e)}


def handle_reset_ecosystem(params: dict) -> dict:
    """Elimina un ecosistema.

    Args:
        params: Dict con ecosystem_id y confirm (bool).

    Returns:
        Status de la operacion.
    """
    eco_manager = get_ecosystem_manager()
    ws_manager = get_workspace_manager()

    if eco_manager is None:
        return {"status": "error", "message": "EcosystemManager no inicializado."}

    ecosystem_id = params.get("ecosystem_id")
    confirm = params.get("confirm", False)

    if not ecosystem_id:
        return {"status": "error", "message": "Se requiere 'ecosystem_id'."}

    try:
        eco_manager.reset_ecosystem(ecosystem_id, confirm=confirm)

        # Limpiar del state si era el activo
        if ws_manager and ws_manager.active_ecosystem_id == ecosystem_id:
            ws_manager.set_active_ecosystem(None)

        return {
            "status": "success",
            "message": f"Ecosistema '{ecosystem_id}' eliminado exitosamente.",
        }
    except ValueError as e:
        return {"status": "error", "message": str(e)}
