"""EcosystemManager: gestiona multiples ecosistemas dentro del servidor MCP.

Cada ecosistema es un directorio aislado con su propio .hu-ecosystem/.
El manager permite crear, listar, switchear y eliminar ecosistemas.

Toda la persistencia vive dentro de BASE_PATH (el volumen Docker /workspace/).
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Optional

from src.engine.ecosystem import BASE_PATH, EcosystemEngine

logger = logging.getLogger("mcp_hu.engine.ecosystem_manager")

ECOSYSTEMS_DIR_NAME = "ecosystems"


class EcosystemManager:
    """Gestor de multiples ecosistemas dentro del servidor MCP.

    Mantiene un directorio ecosystems/ con N subdirectorios, cada uno
    con su propio .hu-ecosystem/. Comparte estado con WorkspaceManager via state.json.
    """

    def __init__(self, base_path: Optional[Path] = None) -> None:
        """Inicializa el manager detectando ecosistemas existentes.

        Args:
            base_path: Ruta base del servidor. Default: BASE_PATH del ecosystem engine.
        """
        self._base_path = base_path or BASE_PATH
        self._ecosystems_path = self._base_path / ECOSYSTEMS_DIR_NAME
        self._active_ecosystem: Optional[EcosystemEngine] = None

        self._ecosystems_path.mkdir(parents=True, exist_ok=True)

    def restore_active(self, ecosystem_id: Optional[str]) -> None:
        """Restaura el ecosistema activo desde el ID indicado.

        Se llama desde el WorkspaceManager despues de cargar state.json.

        Args:
            ecosystem_id: ID del ecosistema a restaurar, o None.
        """
        if not ecosystem_id:
            return

        ecosystem_path = self._ecosystems_path / ecosystem_id
        if ecosystem_path.exists():
            engine = EcosystemEngine(base_path=ecosystem_path)
            if engine.is_initialized:
                self._active_ecosystem = engine
                logger.info("Ecosistema activo restaurado: '%s'", ecosystem_id)
            else:
                logger.warning(
                    "Ecosistema '%s' marcado como activo pero no inicializado.",
                    ecosystem_id,
                )
        else:
            logger.warning(
                "Ecosistema '%s' marcado como activo pero no existe en disco.",
                ecosystem_id,
            )

    # ─── ECOSYSTEM OPERATIONS ────────────────────────────────────────────────────

    def list_ecosystems(self) -> list[dict]:
        """Lista todos los ecosistemas registrados con su metadata.

        Returns:
            Lista de diccionarios con datos de cada ecosistema.
        """
        ecosystems: list[dict] = []

        if not self._ecosystems_path.exists():
            return ecosystems

        for eco_dir in sorted(self._ecosystems_path.iterdir()):
            if not eco_dir.is_dir():
                continue

            ecosystem_id = eco_dir.name
            registry_path = eco_dir / ".hu-ecosystem" / "ecosystem.json"

            if registry_path.exists():
                try:
                    data = json.loads(registry_path.read_text(encoding="utf-8"))
                    ecosystems.append({
                        "ecosystem_id": data.get("ecosystem_id", ecosystem_id),
                        "name": data.get("name", ecosystem_id),
                        "description": data.get("description", ""),
                        "version": data.get("version", "0.1.0"),
                        "approved_by": data.get("approved_by", []),
                        "apps_count": len(data.get("apps", [])),
                        "contracts_count": len(data.get("contracts", [])),
                        "created_at": data.get("created_at", ""),
                    })
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Error leyendo ecosistema '%s': %s", ecosystem_id, e)
                    ecosystems.append({
                        "ecosystem_id": ecosystem_id,
                        "name": ecosystem_id,
                        "description": "",
                        "apps_count": 0,
                        "contracts_count": 0,
                        "created_at": "",
                    })
            else:
                ecosystems.append({
                    "ecosystem_id": ecosystem_id,
                    "name": ecosystem_id,
                    "description": "",
                    "apps_count": 0,
                    "contracts_count": 0,
                    "created_at": "",
                })

        return ecosystems

    def create_ecosystem(self, ecosystem_id: str, name: str, description: str = "") -> EcosystemEngine:
        """Crea un nuevo ecosistema.

        Args:
            ecosystem_id: Identificador unico del ecosistema.
            name: Nombre legible del ecosistema.
            description: Descripcion opcional.

        Returns:
            EcosystemEngine inicializado para el nuevo ecosistema.

        Raises:
            ValueError: Si el ecosystem_id ya existe.
        """
        ecosystem_path = self._ecosystems_path / ecosystem_id

        if ecosystem_path.exists() and (ecosystem_path / ".hu-ecosystem" / "ecosystem.json").exists():
            raise ValueError(
                f"Ecosistema '{ecosystem_id}' ya existe. "
                f"Usar switch_ecosystem para activarlo o reset_ecosystem para reiniciarlo."
            )

        ecosystem_path.mkdir(parents=True, exist_ok=True)

        engine = EcosystemEngine(base_path=ecosystem_path)
        engine.init_ecosystem(ecosystem_id, name, description)

        # Activar el nuevo ecosistema
        self._active_ecosystem = engine

        logger.info("Ecosistema '%s' creado y activado", ecosystem_id)
        return engine

    def switch_ecosystem(self, ecosystem_id: str) -> EcosystemEngine:
        """Cambia al ecosistema indicado.

        Args:
            ecosystem_id: ID del ecosistema a activar.

        Returns:
            EcosystemEngine del ecosistema activado.

        Raises:
            ValueError: Si el ecosistema no existe.
        """
        ecosystem_path = self._ecosystems_path / ecosystem_id

        if not ecosystem_path.exists():
            raise ValueError(
                f"Ecosistema '{ecosystem_id}' no encontrado. "
                f"Usar list_ecosystems para ver los disponibles."
            )

        engine = EcosystemEngine(base_path=ecosystem_path)

        if not engine.is_initialized:
            raise ValueError(
                f"Ecosistema '{ecosystem_id}' existe pero no esta inicializado."
            )

        self._active_ecosystem = engine

        logger.info("Ecosistema switcheado a '%s'", ecosystem_id)
        return engine

    def reset_ecosystem(self, ecosystem_id: str, confirm: bool = False) -> bool:
        """Elimina un ecosistema completamente.

        Args:
            ecosystem_id: ID del ecosistema a eliminar.
            confirm: Debe ser True para confirmar la eliminacion.

        Returns:
            True si se elimino exitosamente.

        Raises:
            ValueError: Si confirm es False o el ecosistema no existe.
        """
        if not confirm:
            raise ValueError(
                "Se requiere confirm=true para eliminar un ecosistema. "
                "Esta operacion es irreversible."
            )

        ecosystem_path = self._ecosystems_path / ecosystem_id

        if not ecosystem_path.exists():
            raise ValueError(f"Ecosistema '{ecosystem_id}' no encontrado.")

        shutil.rmtree(str(ecosystem_path))

        # Si era el activo, desactivar y persistir el cambio en state.json
        if self._active_ecosystem and self._active_ecosystem.registry:
            if self._active_ecosystem.registry.ecosystem_id == ecosystem_id:
                self._active_ecosystem = None
                # Notificar al WorkspaceManager para que actualice state.json
                from src.engine.workspace_manager import get_workspace_manager
                workspace_manager = get_workspace_manager()
                if workspace_manager:
                    workspace_manager.set_active_ecosystem(None)

        logger.info("Ecosistema '%s' eliminado", ecosystem_id)
        return True

    def get_active(self) -> Optional[EcosystemEngine]:
        """Obtiene el EcosystemEngine del ecosistema activo.

        Returns:
            EcosystemEngine activo o None si no hay ecosistema seleccionado.
        """
        return self._active_ecosystem


# ─── SINGLETON MANAGER ───────────────────────────────────────────────────────────

_ecosystem_manager: Optional[EcosystemManager] = None


def get_ecosystem_manager() -> Optional[EcosystemManager]:
    """Obtiene la instancia del EcosystemManager (puede ser None si no esta inicializado)."""
    return _ecosystem_manager


def init_ecosystem_manager(base_path: Optional[Path] = None) -> EcosystemManager:
    """Inicializa y retorna el EcosystemManager global.

    Args:
        base_path: Ruta base. Default: BASE_PATH del ecosystem engine.

    Returns:
        EcosystemManager inicializado.
    """
    global _ecosystem_manager
    _ecosystem_manager = EcosystemManager(base_path=base_path)
    return _ecosystem_manager
