"""WorkspaceManager: gestiona multiples workspaces (proyectos) dentro del servidor MCP.

Cada workspace es un directorio aislado con su propio .hu-memory/.
El manager mantiene el estado de cual workspace esta activo y permite
crear, listar, switchear y eliminar workspaces.

Toda la persistencia vive dentro de BASE_PATH (el volumen Docker /workspace/).
"""

import json
import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.engine.memory import BASE_PATH, MemoryEngine
from src.models.project import ServerState, WorkspaceInfo

logger = logging.getLogger("mcp_hu.engine.workspace_manager")

STATE_FILE_NAME = "state.json"
WORKSPACES_DIR_NAME = "workspaces"


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


class WorkspaceManager:
    """Gestor de multiples workspaces dentro del servidor MCP.

    Mantiene un directorio workspaces/ con N subdirectorios, cada uno
    con su propio .hu-memory/. Persiste el workspace activo en state.json.
    """

    def __init__(self, base_path: Optional[Path] = None) -> None:
        """Inicializa el manager detectando workspaces existentes.

        Args:
            base_path: Ruta base del servidor. Default: MCP_WORKSPACE_PATH.
        """
        self._base_path = base_path or BASE_PATH
        self._workspaces_path = self._base_path / WORKSPACES_DIR_NAME
        self._state_path = self._base_path / STATE_FILE_NAME
        self._active_memory: Optional[MemoryEngine] = None
        self._state: ServerState = self._load_state()

        self._workspaces_path.mkdir(parents=True, exist_ok=True)
        self._restore_active()

    @property
    def active_workspace_id(self) -> Optional[str]:
        """ID del workspace activo."""
        return self._state.active_workspace

    @property
    def active_ecosystem_id(self) -> Optional[str]:
        """ID del ecosistema activo (leido del state compartido)."""
        return self._state.active_ecosystem

    def set_active_ecosystem(self, ecosystem_id: Optional[str]) -> None:
        """Actualiza el ecosistema activo en el estado persistido.

        Args:
            ecosystem_id: ID del ecosistema a activar, o None para desactivar.
        """
        self._state.active_ecosystem = ecosystem_id
        self._save_state()

    # ─── WORKSPACE OPERATIONS ────────────────────────────────────────────────────

    def list_workspaces(self) -> list[WorkspaceInfo]:
        """Lista todos los workspaces registrados con su metadata.

        Returns:
            Lista de WorkspaceInfo con datos de cada workspace.
        """
        workspaces: list[WorkspaceInfo] = []

        if not self._workspaces_path.exists():
            return workspaces

        for workspace_dir in sorted(self._workspaces_path.iterdir()):
            if not workspace_dir.is_dir():
                continue

            workspace_id = workspace_dir.name
            index_path = workspace_dir / ".hu-memory" / "index.json"

            if index_path.exists():
                try:
                    data = json.loads(index_path.read_text(encoding="utf-8"))
                    config = data.get("config", {})
                    workspaces.append(WorkspaceInfo(
                        workspace_id=workspace_id,
                        project_name=config.get("project_name", workspace_id),
                        domain=config.get("domain", ""),
                        description=config.get("description", ""),
                        ecosystem_id=config.get("ecosystem_id"),
                        app_id=config.get("app_id"),
                        story_count=data.get("story_count", 0),
                        created_at=config.get("created_at", ""),
                    ))
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Error leyendo workspace '%s': %s", workspace_id, e)
                    workspaces.append(WorkspaceInfo(
                        workspace_id=workspace_id,
                        project_name=workspace_id,
                    ))
            else:
                workspaces.append(WorkspaceInfo(
                    workspace_id=workspace_id,
                    project_name=workspace_id,
                ))

        return workspaces

    def create_workspace(self, workspace_id: str, config: dict) -> MemoryEngine:
        """Crea un nuevo workspace e inicializa su memoria.

        Args:
            workspace_id: Identificador unico del workspace. Si no se proporciona,
                          se genera a partir de project_name.
            config: Diccionario de configuracion del proyecto (ProjectConfig fields).

        Returns:
            MemoryEngine inicializado para el nuevo workspace.

        Raises:
            ValueError: Si el workspace_id ya existe.
        """
        if not workspace_id:
            workspace_id = _slugify(config.get("project_name", "default"))

        workspace_path = self._workspaces_path / workspace_id

        if workspace_path.exists() and (workspace_path / ".hu-memory" / "index.json").exists():
            raise ValueError(
                f"Workspace '{workspace_id}' ya existe. "
                f"Usar switch_workspace para activarlo o reset_workspace para reiniciarlo."
            )

        workspace_path.mkdir(parents=True, exist_ok=True)

        from src.models.project import ProjectConfig
        project_config = ProjectConfig(**config)

        engine = MemoryEngine(base_path=workspace_path)
        engine.init_project(project_config)

        # Activar el nuevo workspace
        self._active_memory = engine
        self._state.active_workspace = workspace_id
        self._save_state()

        logger.info("Workspace '%s' creado y activado", workspace_id)
        return engine

    def switch_workspace(self, workspace_id: str) -> MemoryEngine:
        """Cambia al workspace indicado.

        Args:
            workspace_id: ID del workspace a activar.

        Returns:
            MemoryEngine del workspace activado.

        Raises:
            ValueError: Si el workspace no existe.
        """
        workspace_path = self._workspaces_path / workspace_id

        if not workspace_path.exists():
            raise ValueError(
                f"Workspace '{workspace_id}' no encontrado. "
                f"Usar list_workspaces para ver los disponibles."
            )

        engine = MemoryEngine(base_path=workspace_path)

        if not engine.is_initialized:
            raise ValueError(
                f"Workspace '{workspace_id}' existe pero no tiene memoria inicializada."
            )

        self._active_memory = engine
        self._state.active_workspace = workspace_id
        self._save_state()

        logger.info("Workspace switcheado a '%s'", workspace_id)
        return engine

    def reset_workspace(self, workspace_id: str, confirm: bool = False) -> bool:
        """Elimina un workspace completamente.

        Args:
            workspace_id: ID del workspace a eliminar.
            confirm: Debe ser True para confirmar la eliminacion.

        Returns:
            True si se elimino exitosamente.

        Raises:
            ValueError: Si confirm es False o el workspace no existe.
        """
        if not confirm:
            raise ValueError(
                "Se requiere confirm=true para eliminar un workspace. "
                "Esta operacion es irreversible."
            )

        workspace_path = self._workspaces_path / workspace_id

        if not workspace_path.exists():
            raise ValueError(f"Workspace '{workspace_id}' no encontrado.")

        shutil.rmtree(str(workspace_path))

        # Si era el activo, desactivar
        if self._state.active_workspace == workspace_id:
            self._active_memory = None
            self._state.active_workspace = None
            self._save_state()

        logger.info("Workspace '%s' eliminado", workspace_id)
        return True

    def get_active(self) -> Optional[MemoryEngine]:
        """Obtiene el MemoryEngine del workspace activo.

        Returns:
            MemoryEngine activo o None si no hay workspace seleccionado.
        """
        return self._active_memory

    # ─── PRIVATE METHODS ─────────────────────────────────────────────────────────

    def _load_state(self) -> ServerState:
        """Carga el estado desde state.json."""
        if self._state_path.exists():
            try:
                data = json.loads(self._state_path.read_text(encoding="utf-8"))
                return ServerState(**data)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Error leyendo state.json: %s. Creando nuevo.", e)
        return ServerState()

    def _save_state(self) -> None:
        """Persiste el estado en state.json."""
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps(self._state.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _restore_active(self) -> None:
        """Restaura el workspace activo desde el estado persistido."""
        if self._state.active_workspace:
            workspace_path = self._workspaces_path / self._state.active_workspace
            if workspace_path.exists():
                engine = MemoryEngine(base_path=workspace_path)
                if engine.is_initialized:
                    self._active_memory = engine
                    logger.info("Workspace activo restaurado: '%s'", self._state.active_workspace)
                else:
                    logger.warning(
                        "Workspace '%s' marcado como activo pero no inicializado.",
                        self._state.active_workspace,
                    )
            else:
                logger.warning(
                    "Workspace '%s' marcado como activo pero no existe en disco.",
                    self._state.active_workspace,
                )
                self._state.active_workspace = None
                self._save_state()


# ─── SINGLETON MANAGER ───────────────────────────────────────────────────────────

_workspace_manager: Optional[WorkspaceManager] = None


def get_workspace_manager() -> Optional[WorkspaceManager]:
    """Obtiene la instancia del WorkspaceManager (puede ser None si no esta inicializado)."""
    return _workspace_manager


def init_workspace_manager(base_path: Optional[Path] = None) -> WorkspaceManager:
    """Inicializa y retorna el WorkspaceManager global.

    Args:
        base_path: Ruta base. Default: MCP_WORKSPACE_PATH.

    Returns:
        WorkspaceManager inicializado.
    """
    global _workspace_manager
    _workspace_manager = WorkspaceManager(base_path=base_path)
    return _workspace_manager
