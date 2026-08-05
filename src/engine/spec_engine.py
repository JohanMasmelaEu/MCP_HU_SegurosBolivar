"""SpecEngine: gestión de ProjectSpecs con persistencia local y filtrado por rol.

Persiste specs en {base_path}/.hu-specs/{spec_id}.json.
Integra con RulesCatalogEngine para asociar reglas aplicables.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.engine.memory import BASE_PATH
from src.engine.rules_catalog import get_rules_catalog
from src.models.sdd import (
    DEFAULT_ROLE_DEPTH,
    LayerContent,
    ProjectSpec,
    SDDLayer,
)

logger = logging.getLogger("mcp_hu.engine.spec_engine")

SPECS_DIR_NAME = ".hu-specs"


class SpecEngine:
    """Motor de especificaciones SDD.

    Gestiona el ciclo de vida de ProjectSpecs: creación, actualización,
    aprobación y consulta filtrada por rol.
    """

    def __init__(self, base_path: Optional[Path] = None) -> None:
        """Inicializa el engine de specs.

        Args:
            base_path: Ruta base donde se persiste. Default: BASE_PATH.
        """
        self._base_path = base_path or BASE_PATH
        self._specs_path = self._base_path / SPECS_DIR_NAME

    @property
    def specs_path(self) -> Path:
        """Ruta al directorio de specs."""
        return self._specs_path

    # ─── CRUD ────────────────────────────────────────────────────────────────────

    def create_spec(self, spec_id: str, project_name: str, app_id: Optional[str] = None) -> ProjectSpec:
        """Crea una nueva spec con capas vacías.

        Args:
            spec_id: Identificador único de la spec.
            project_name: Nombre del proyecto.
            app_id: app_id opcional para vincular con el ecosistema.

        Returns:
            ProjectSpec creado.

        Raises:
            ValueError: Si ya existe una spec con ese ID.
        """
        if self.get_spec(spec_id) is not None:
            raise ValueError(f"Spec '{spec_id}' ya existe. Usar update_layer para modificar.")

        # Crear spec con todas las capas vacías
        layers = {layer.value: LayerContent() for layer in SDDLayer}

        spec = ProjectSpec(
            spec_id=spec_id,
            project_name=project_name,
            layers=layers,
            app_id=app_id,
        )

        self._save_spec(spec)
        logger.info("Spec '%s' creada para proyecto '%s'", spec_id, project_name)
        return spec

    def update_layer(self, spec_id: str, layer: SDDLayer, content: LayerContent) -> Optional[ProjectSpec]:
        """Actualiza el contenido de una capa en la spec.

        Args:
            spec_id: ID de la spec.
            layer: Capa SDD a actualizar.
            content: Nuevo contenido de la capa.

        Returns:
            Spec actualizada o None si no existe.
        """
        spec = self.get_spec(spec_id)
        if not spec:
            return None

        spec.layers[layer.value] = content
        spec.updated_at = datetime.now().isoformat()
        self._save_spec(spec)
        logger.info("Capa '%s' actualizada en spec '%s'", layer.value, spec_id)
        return spec

    def approve_spec(self, spec_id: str, approver: str) -> Optional[ProjectSpec]:
        """Aprueba una spec cambiando su status y registrando el aprobador.

        Args:
            spec_id: ID de la spec a aprobar.
            approver: Nombre/ID del aprobador.

        Returns:
            Spec aprobada o None si no existe.
        """
        spec = self.get_spec(spec_id)
        if not spec:
            return None

        spec.status = "approved"
        if approver not in spec.approved_by:
            spec.approved_by.append(approver)
        spec.updated_at = datetime.now().isoformat()
        self._save_spec(spec)
        logger.info("Spec '%s' aprobada por '%s'", spec_id, approver)
        return spec

    def get_spec(self, spec_id: str) -> Optional[ProjectSpec]:
        """Obtiene una spec por su ID.

        Args:
            spec_id: Identificador de la spec.

        Returns:
            ProjectSpec o None si no existe.
        """
        spec_file = self._specs_path / f"{spec_id}.json"
        if not spec_file.exists():
            return None

        try:
            data = json.loads(spec_file.read_text(encoding="utf-8"))
            return ProjectSpec(**data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Error cargando spec '%s': %s", spec_id, e)
            return None

    def get_spec_for_role(self, spec_id: str, role: str) -> Optional[dict]:
        """Obtiene la spec filtrada por profundidad según el rol.

        Capas con 'full': incluye todo (summary, decisions, constraints, artifacts).
        Capas con 'context': incluye solo summary.
        Capas con 'n/a': no se incluyen.

        Args:
            spec_id: ID de la spec.
            role: Valor del StakeholderRole.

        Returns:
            Dict con la spec filtrada o None si no existe.
        """
        spec = self.get_spec(spec_id)
        if not spec:
            return None

        depth_matrix = spec.role_depth_override or DEFAULT_ROLE_DEPTH
        visible_layers = depth_matrix.get_visible_layers(role)

        filtered_layers: dict[str, dict] = {}
        for layer_name in visible_layers:
            depth = depth_matrix.get_depth(role, layer_name)
            layer_content = spec.layers.get(layer_name)
            if not layer_content:
                continue

            if depth == "full":
                filtered_layers[layer_name] = layer_content.model_dump(mode="json")
            elif depth == "context":
                filtered_layers[layer_name] = {"summary": layer_content.summary}

        return {
            "spec_id": spec.spec_id,
            "project_name": spec.project_name,
            "version": spec.version,
            "status": spec.status,
            "approved_by": spec.approved_by,
            "role": role,
            "layers": filtered_layers,
            "rules_applied": spec.rules_applied,
            "dependencies": [d.model_dump(mode="json") for d in spec.dependencies],
        }

    def list_specs(self) -> list[dict]:
        """Lista resúmenes de todas las specs.

        Returns:
            Lista de diccionarios con id, name, status, version, app_id.
        """
        specs: list[dict] = []
        if not self._specs_path.exists():
            return specs

        for spec_file in sorted(self._specs_path.glob("*.json")):
            try:
                data = json.loads(spec_file.read_text(encoding="utf-8"))
                specs.append({
                    "spec_id": data.get("spec_id", spec_file.stem),
                    "project_name": data.get("project_name", ""),
                    "status": data.get("status", "draft"),
                    "version": data.get("version", "0.1.0"),
                    "app_id": data.get("app_id"),
                })
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Error leyendo spec '%s': %s", spec_file.name, e)

        return specs

    def apply_catalog_rules(self, spec_id: str) -> Optional[ProjectSpec]:
        """Lee el catálogo de reglas y asocia las aplicables al spec.

        Args:
            spec_id: ID de la spec.

        Returns:
            Spec actualizada o None si no existe o no hay catálogo.
        """
        spec = self.get_spec(spec_id)
        if not spec:
            return None

        catalog = get_rules_catalog()
        if not catalog:
            logger.warning("No hay catálogo de reglas inicializado")
            return spec

        applicable_rules = catalog.get_rules_for_spec(spec)
        spec.rules_applied = [r.rule_id for r in applicable_rules]
        spec.updated_at = datetime.now().isoformat()
        self._save_spec(spec)
        logger.info("Spec '%s': %d reglas aplicadas del catálogo", spec_id, len(spec.rules_applied))
        return spec

    # ─── PRIVATE ─────────────────────────────────────────────────────────────────

    def _save_spec(self, spec: ProjectSpec) -> None:
        """Persiste una spec en disco.

        Args:
            spec: ProjectSpec a guardar.
        """
        self._specs_path.mkdir(parents=True, exist_ok=True)
        spec_file = self._specs_path / f"{spec.spec_id}.json"
        spec_file.write_text(
            json.dumps(spec.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


# ─── INIT / GET ──────────────────────────────────────────────────────────────────

_spec_engine: Optional[SpecEngine] = None


def get_spec_engine() -> Optional[SpecEngine]:
    """Obtiene la instancia del SpecEngine (puede ser None si no está inicializado)."""
    return _spec_engine


def init_spec_engine(base_path: Optional[Path] = None) -> SpecEngine:
    """Inicializa y retorna el SpecEngine global.

    Args:
        base_path: Ruta base. Default: BASE_PATH.

    Returns:
        SpecEngine inicializado.
    """
    global _spec_engine
    _spec_engine = SpecEngine(base_path=base_path)
    return _spec_engine
