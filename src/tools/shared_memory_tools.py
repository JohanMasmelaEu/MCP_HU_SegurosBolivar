"""Tool handlers para memoria compartida (shared memory).

Solo se ejecutan cuando el usuario lo pide explícitamente.
El agente IDE NO debe invocar estos tools automáticamente.
"""

import logging

from typing import Optional

from src.engine.shared_memory import SharedMemoryEngine, get_shared_memory

logger = logging.getLogger("mcp_hu.tools.shared_memory")


def handle_sync_shared_memory(params: dict) -> dict:
    """Handler principal de sync_shared_memory.

    Args:
        params: Objeto con:
            - action: "export" | "import" | "status" (default: "status")
            - scope: "all" | "entities" | "flows" | "decisions" (solo para export, default: "all")

    Returns:
        Resultado de la operación.
    """
    action = params.get("action", "status")
    scope = params.get("scope", "all")

    try:
        shared = get_shared_memory()
    except RuntimeError as e:
        return {"status": "error", "message": str(e)}

    if action == "status":
        return {"status": "success", **shared.get_status()}

    elif action == "export":
        return shared.export_to_shared(scope=scope)

    elif action == "import":
        return shared.import_from_shared()

    elif action == "wiki":
        return shared.generate_wiki_bundle()

    else:
        return {
            "status": "error",
            "message": f"Acción no válida: '{action}'. Usar 'export', 'import', 'status' o 'wiki'.",
        }


def handle_generate_wiki_content() -> dict:
    """Handler dedicado para generar el contenido completo de la wiki.

    Returns:
        Bundle con todas las páginas de la wiki como Markdown.
    """
    try:
        shared = get_shared_memory()
    except RuntimeError as e:
        return {"status": "error", "message": str(e)}

    return shared.generate_wiki_bundle()


def handle_export_memory_to_wiki(wiki_path: str) -> dict:
    """Handler para exportar la memoria del workspace al repo de wiki clonado.

    Args:
        wiki_path: Ruta local al repo de la wiki clonado.

    Returns:
        Resultado con archivos escritos y resumen.
    """
    if not wiki_path or not wiki_path.strip():
        return {"status": "error", "message": "Se requiere la ruta al repo de la wiki clonado."}

    try:
        shared = get_shared_memory()
    except RuntimeError as e:
        return {"status": "error", "message": str(e)}

    return shared.export_to_wiki_repo(wiki_path.strip())


def handle_import_wiki_to_memory(wiki_path: str) -> dict:
    """Handler para importar contenido desde un repo de wiki clonado.

    Args:
        wiki_path: Ruta local al repo de la wiki clonado.

    Returns:
        Resultado con resumen de cambios.
    """
    if not wiki_path or not wiki_path.strip():
        return {"status": "error", "message": "Se requiere la ruta al repo de la wiki clonado."}

    try:
        shared = get_shared_memory()
    except RuntimeError as e:
        return {"status": "error", "message": str(e)}

    return shared.import_from_wiki_repo(wiki_path.strip())


def handle_migrate_workspace_to_shared(
    workspace_id: Optional[str] = None, confirm: bool = False
) -> dict:
    """Migra un workspace existente generando su estructura shared/.

    Args:
        workspace_id: ID del workspace. None = usa el activo.
        confirm: Debe ser True para ejecutar.

    Returns:
        Resultado de la migración.
    """
    from src.engine.workspace_manager import get_workspace_manager

    manager = get_workspace_manager()
    if manager is None:
        return {"status": "error", "message": "WorkspaceManager no inicializado."}

    # Resolver workspace
    if workspace_id:
        # Verificar que existe
        workspaces = manager.list_workspaces()
        target = next((w for w in workspaces if w.workspace_id == workspace_id), None)
        if target is None:
            available = [w.workspace_id for w in workspaces]
            return {
                "status": "error",
                "message": f"Workspace '{workspace_id}' no encontrado. Disponibles: {available}",
            }
        # Temporalmente switchear para obtener el memory engine
        from src.engine.memory import MemoryEngine
        from pathlib import Path

        base = manager._base_path / workspace_id
        memory = MemoryEngine(base_path=base)
    else:
        # Usar workspace activo
        try:
            from src.engine.memory import get_memory
            memory = get_memory()
        except RuntimeError as e:
            return {"status": "error", "message": str(e)}
        workspace_id = manager.active_workspace_id or "activo"

    if not memory.is_initialized:
        return {
            "status": "error",
            "message": f"Workspace '{workspace_id}' no tiene memoria inicializada.",
        }

    # Preview sin confirm
    index = memory.index
    if index is None:
        return {"status": "error", "message": "Índice de memoria vacío."}

    entity_count = len(index.entities)
    flow_count = len(index.flows)
    decision_count = len(index.decisions)
    total = entity_count + flow_count + decision_count

    if not confirm:
        return {
            "status": "preview",
            "workspace_id": workspace_id,
            "project_name": index.config.project_name,
            "to_migrate": {
                "entities": entity_count,
                "flows": flow_count,
                "decisions": decision_count,
                "total": total,
            },
            "message": (
                f"Workspace '{workspace_id}' ({index.config.project_name}): "
                f"{total} elementos para migrar a shared/ "
                f"({entity_count} entidades, {flow_count} flujos, {decision_count} decisiones). "
                "Pasar confirm=true para ejecutar."
            ),
        }

    if total == 0:
        return {
            "status": "success",
            "message": f"Workspace '{workspace_id}' no tiene entidades, flujos ni decisiones para migrar.",
        }

    # Ejecutar migración
    shared = SharedMemoryEngine(memory)
    result = shared.export_to_shared(scope="all")

    if result["status"] == "success":
        result["workspace_id"] = workspace_id
        result["message"] = (
            f"✅ Workspace '{workspace_id}' migrado exitosamente. "
            f"{result['total']} archivos Markdown creados en .hu-memory/shared/. "
            "Hacer commit y push para compartir con el equipo."
        )

    return result
