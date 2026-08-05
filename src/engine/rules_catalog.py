"""RulesCatalogEngine: catálogo de reglas transversales corporativas.

Persiste reglas en {base_path}/.hu-rules/catalog.json.
Las reglas aplican a capas SDD y stacks tecnológicos específicos.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.engine.memory import BASE_PATH
from src.models.sdd import ProjectSpec, SDDLayer, TransversalRule

logger = logging.getLogger("mcp_hu.engine.rules_catalog")

RULES_DIR_NAME = ".hu-rules"
CATALOG_FILE_NAME = "catalog.json"


class RulesCatalogEngine:
    """Motor de catálogo de reglas transversales.

    Gestiona reglas corporativas que aplican a una o más capas SDD.
    Persiste en {base_path}/.hu-rules/catalog.json.
    """

    def __init__(self, base_path: Optional[Path] = None) -> None:
        """Inicializa el catálogo de reglas.

        Args:
            base_path: Ruta base donde se persiste. Default: BASE_PATH.
        """
        self._base_path = base_path or BASE_PATH
        self._rules_path = self._base_path / RULES_DIR_NAME
        self._catalog_path = self._rules_path / CATALOG_FILE_NAME
        self._rules: list[TransversalRule] = []

        if self._catalog_path.exists():
            self._load()

    @property
    def rules_path(self) -> Path:
        """Ruta al directorio de reglas."""
        return self._rules_path

    # ─── CRUD ────────────────────────────────────────────────────────────────────

    def add_rule(self, rule: TransversalRule) -> None:
        """Agrega una regla al catálogo.

        Si una regla con el mismo rule_id ya existe, lanza ValueError.

        Args:
            rule: Regla a agregar.

        Raises:
            ValueError: Si el rule_id ya existe.
        """
        existing = self.get_rule(rule.rule_id)
        if existing:
            raise ValueError(f"Regla '{rule.rule_id}' ya existe en el catálogo. Usar update_rule para modificar.")

        self._rules.append(rule)
        self._save()
        logger.info("Regla '%s' agregada al catálogo", rule.rule_id)

    def get_rule(self, rule_id: str) -> Optional[TransversalRule]:
        """Obtiene una regla por su ID.

        Args:
            rule_id: Identificador de la regla.

        Returns:
            TransversalRule o None si no existe.
        """
        return next((r for r in self._rules if r.rule_id == rule_id), None)

    def list_rules(self, category: Optional[str] = None) -> list[TransversalRule]:
        """Lista reglas del catálogo, opcionalmente filtradas por categoría.

        Args:
            category: Categoría para filtrar. None = todas.

        Returns:
            Lista de reglas.
        """
        if category:
            return [r for r in self._rules if r.category == category]
        return list(self._rules)

    def update_rule(self, rule_id: str, updates: dict) -> Optional[TransversalRule]:
        """Actualiza campos de una regla existente.

        Args:
            rule_id: ID de la regla a actualizar.
            updates: Campos a actualizar (parciales).

        Returns:
            Regla actualizada o None si no existe.
        """
        rule = self.get_rule(rule_id)
        if not rule:
            return None

        for key, value in updates.items():
            if hasattr(rule, key) and key not in ("rule_id", "created_at"):
                setattr(rule, key, value)

        rule.updated_at = datetime.now().isoformat()
        self._save()
        logger.info("Regla '%s' actualizada", rule_id)
        return rule

    def remove_rule(self, rule_id: str) -> bool:
        """Elimina una regla del catálogo.

        Args:
            rule_id: ID de la regla a eliminar.

        Returns:
            True si se eliminó, False si no existía.
        """
        original_len = len(self._rules)
        self._rules = [r for r in self._rules if r.rule_id != rule_id]

        if len(self._rules) < original_len:
            self._save()
            logger.info("Regla '%s' eliminada del catálogo", rule_id)
            return True
        return False

    # ─── QUERIES ─────────────────────────────────────────────────────────────────

    def get_rules_for_layer(self, layer: SDDLayer) -> list[TransversalRule]:
        """Obtiene reglas que aplican a una capa específica.

        Incluye reglas con applies_to_layers vacío (aplican a todas).

        Args:
            layer: Capa SDD para filtrar.

        Returns:
            Lista de reglas aplicables.
        """
        return [
            r for r in self._rules
            if not r.applies_to_layers or layer in r.applies_to_layers
        ]

    def get_rules_for_spec(self, spec: ProjectSpec) -> list[TransversalRule]:
        """Obtiene todas las reglas aplicables a un ProjectSpec.

        Filtra por capas con contenido en la spec y por stack tecnológico
        si la spec tiene app_id vinculado.

        Args:
            spec: ProjectSpec para el cual buscar reglas aplicables.

        Returns:
            Lista de reglas aplicables.
        """
        applicable: list[TransversalRule] = []
        spec_layers = set(spec.layers.keys())

        for rule in self._rules:
            # Filtro por capas: si la regla no tiene restricción, aplica siempre
            if rule.applies_to_layers:
                rule_layer_values = {layer.value for layer in rule.applies_to_layers}
                if not rule_layer_values.intersection(spec_layers):
                    continue

            # Filtro por stack: si la regla no tiene restricción, aplica siempre
            # (El stack se infiere del app_id en el futuro, por ahora aplican todas)
            applicable.append(rule)

        return applicable

    # ─── PRIVATE ─────────────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Carga el catálogo desde disco."""
        try:
            data = json.loads(self._catalog_path.read_text(encoding="utf-8"))
            self._rules = [TransversalRule(**r) for r in data.get("rules", [])]
            logger.info("Catálogo cargado: %d reglas", len(self._rules))
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Error cargando catálogo de reglas: %s", e)
            self._rules = []

    def _save(self) -> None:
        """Persiste el catálogo en disco."""
        self._rules_path.mkdir(parents=True, exist_ok=True)
        data = {"rules": [r.model_dump(mode="json") for r in self._rules]}
        self._catalog_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


# ─── INIT / GET ──────────────────────────────────────────────────────────────────

_rules_catalog: Optional[RulesCatalogEngine] = None


def get_rules_catalog() -> Optional[RulesCatalogEngine]:
    """Obtiene la instancia del RulesCatalogEngine (puede ser None si no está inicializado)."""
    return _rules_catalog


def init_rules_catalog(base_path: Optional[Path] = None) -> RulesCatalogEngine:
    """Inicializa y retorna el RulesCatalogEngine global.

    Args:
        base_path: Ruta base. Default: BASE_PATH.

    Returns:
        RulesCatalogEngine inicializado.
    """
    global _rules_catalog
    _rules_catalog = RulesCatalogEngine(base_path=base_path)
    return _rules_catalog
