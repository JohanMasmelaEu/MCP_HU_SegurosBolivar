"""Ecosystem Engine: registro, sincronizacion y consultas cross-app.

Gestiona .hu-ecosystem/ como directorio central que indexa multiples apps.
Principio: read-only sobre los .hu-memory/ de otras apps. Solo escribe en .hu-ecosystem/.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models.ecosystem import (
    AppRegistration,
    ContractDefinition,
    CrossAppConflict,
    EcosystemRegistry,
    SharedEntity,
)

logger = logging.getLogger("mcp_hu.engine.ecosystem")

ECOSYSTEM_PATH = Path(os.environ.get("MCP_ECOSYSTEM_PATH", os.environ.get("MCP_WORKSPACE_PATH", "/workspace")))
ECOSYSTEM_DIR_NAME = ".hu-ecosystem"


class EcosystemEngine:
    """Motor de ecosistema para gestionar relaciones entre apps.

    Lee .hu-memory/ de las apps registradas (read-only) y mantiene
    un indice central en .hu-ecosystem/.
    """

    def __init__(self) -> None:
        """Inicializa detectando si ya existe un ecosistema."""
        self._ecosystem_path = ECOSYSTEM_PATH / ECOSYSTEM_DIR_NAME
        self._registry: Optional[EcosystemRegistry] = None

        if self._ecosystem_path.exists():
            self._load()

    @property
    def is_initialized(self) -> bool:
        """Verifica si el ecosistema ya fue inicializado."""
        return self._ecosystem_path.exists() and (self._ecosystem_path / "ecosystem.json").exists()

    @property
    def ecosystem_path(self) -> Path:
        """Ruta a .hu-ecosystem/."""
        return self._ecosystem_path

    @property
    def registry(self) -> Optional[EcosystemRegistry]:
        """Registro central del ecosistema."""
        return self._registry

    # ─── INITIALIZATION ──────────────────────────────────────────────────────────

    def init_ecosystem(self, ecosystem_id: str, name: str, description: str = "") -> None:
        """Crea la estructura .hu-ecosystem/ con la configuracion inicial.

        Args:
            ecosystem_id: Identificador unico del ecosistema.
            name: Nombre legible del ecosistema.
            description: Descripcion opcional.
        """
        self._ecosystem_path.mkdir(parents=True, exist_ok=True)
        (self._ecosystem_path / "apps").mkdir(exist_ok=True)
        (self._ecosystem_path / "contracts").mkdir(exist_ok=True)

        self._registry = EcosystemRegistry(
            ecosystem_id=ecosystem_id,
            name=name,
            description=description,
        )
        self._save_registry()
        logger.info("Ecosistema '%s' inicializado en %s", name, self._ecosystem_path)

    # ─── APP REGISTRATION ────────────────────────────────────────────────────────

    def register_app(self, app: AppRegistration) -> None:
        """Registra una app en el ecosistema y sincroniza su snapshot.

        Lee el .hu-memory/index.json de la app para indexar sus entidades y flujos.

        Args:
            app: Datos de registro de la app.
        """
        if not self._registry:
            raise RuntimeError("Ecosistema no inicializado.")

        # Verificar si ya existe
        existing_idx = next(
            (i for i, a in enumerate(self._registry.apps) if a.app_id == app.app_id), None
        )

        # Leer snapshot de la app (read-only)
        app = self._sync_app_snapshot(app)

        if existing_idx is not None:
            self._registry.apps[existing_idx] = app
            logger.info("App '%s' actualizada en ecosistema", app.app_id)
        else:
            self._registry.apps.append(app)
            logger.info("App '%s' registrada en ecosistema", app.app_id)

        # Guardar snapshot individual
        self._save_app_snapshot(app)

        # Recalcular entidades compartidas
        self._recalculate_shared_entities()

        self._registry.updated_at = datetime.now().isoformat()
        self._save_registry()

    def sync_app(self, app_id: str) -> Optional[AppRegistration]:
        """Re-sincroniza el snapshot de una app desde su .hu-memory/.

        Args:
            app_id: ID de la app a sincronizar.

        Returns:
            App actualizada o None si no existe.
        """
        if not self._registry:
            return None

        app = self.get_app(app_id)
        if not app:
            return None

        app = self._sync_app_snapshot(app)

        # Actualizar en la lista
        for i, a in enumerate(self._registry.apps):
            if a.app_id == app_id:
                self._registry.apps[i] = app
                break

        self._save_app_snapshot(app)
        self._recalculate_shared_entities()
        self._registry.updated_at = datetime.now().isoformat()
        self._save_registry()

        return app

    def sync_all_apps(self) -> int:
        """Re-sincroniza todas las apps del ecosistema.

        Returns:
            Cantidad de apps sincronizadas exitosamente.
        """
        if not self._registry:
            return 0

        synced = 0
        for app in self._registry.apps:
            result = self.sync_app(app.app_id)
            if result:
                synced += 1

        return synced

    # ─── QUERIES ─────────────────────────────────────────────────────────────────

    def get_app(self, app_id: str) -> Optional[AppRegistration]:
        """Obtiene una app por su ID.

        Args:
            app_id: ID de la app.

        Returns:
            AppRegistration o None.
        """
        if not self._registry:
            return None
        return next((a for a in self._registry.apps if a.app_id == app_id), None)

    def get_all_apps(self) -> list[AppRegistration]:
        """Obtiene todas las apps registradas."""
        if not self._registry:
            return []
        return self._registry.apps

    def get_shared_entities(self) -> list[SharedEntity]:
        """Obtiene entidades que aparecen en mas de una app."""
        if not self._registry:
            return []
        return self._registry.shared_entities

    def get_contracts(self) -> list[ContractDefinition]:
        """Obtiene todos los contratos del ecosistema."""
        if not self._registry:
            return []
        return self._registry.contracts

    def get_app_dependencies(self, app_id: str) -> dict:
        """Calcula las dependencias de una app basado en contratos.

        Args:
            app_id: ID de la app.

        Returns:
            Dict con depends_on (apps de las que depende) y depended_by (apps que dependen de ella).
        """
        if not self._registry:
            return {"depends_on": [], "depended_by": []}

        app = self.get_app(app_id)
        if not app:
            return {"depends_on": [], "depended_by": []}

        depends_on = set()
        depended_by = set()

        for contract in self._registry.contracts:
            if contract.provider_app == app_id:
                # Esta app provee → otras dependen de ella
                for consumer in contract.consumer_apps:
                    depended_by.add(consumer)
            if app_id in contract.consumer_apps:
                # Esta app consume → depende del provider
                depends_on.add(contract.provider_app)

        return {
            "depends_on": sorted(depends_on),
            "depended_by": sorted(depended_by),
        }

    def get_cross_app_context(
        self,
        entity_names: list[str],
        flow_names: list[str],
        current_app_id: Optional[str] = None,
    ) -> dict:
        """Obtiene contexto transversal relevante para una HU.

        Filtra solo la informacion de otras apps que sea relevante
        para las entidades y flujos indicados.

        Args:
            entity_names: Entidades de la HU actual.
            flow_names: Flujos de la HU actual.
            current_app_id: ID de la app actual (para excluirla del resultado).

        Returns:
            Contexto cross-app filtrado por relevancia.
        """
        if not self._registry:
            return {"available": False}

        context: dict = {
            "available": True,
            "ecosystem": self._registry.name,
            "shared_entities_relevant": [],
            "contracts_relevant": [],
            "other_apps_context": [],
        }

        # Entidades compartidas que intersectan con la HU
        entity_names_lower = [e.lower() for e in entity_names]
        for shared in self._registry.shared_entities:
            if shared.entity_name.lower() in entity_names_lower:
                context["shared_entities_relevant"].append({
                    "entity": shared.entity_name,
                    "defined_in_apps": [
                        a for a in shared.defined_in_apps if a != current_app_id
                    ],
                    "is_consistent": shared.is_consistent,
                    "divergence_notes": shared.divergence_notes,
                    "fields_by_app": {
                        k: v for k, v in shared.fields_by_app.items() if k != current_app_id
                    },
                })

        # Contratos que involucran las entidades de la HU
        for contract in self._registry.contracts:
            contract_entities_lower = [e.lower() for e in contract.entities_involved]
            if any(e in contract_entities_lower for e in entity_names_lower):
                context["contracts_relevant"].append({
                    "contract_id": contract.contract_id,
                    "name": contract.name,
                    "type": contract.type,
                    "provider": contract.provider_app,
                    "consumers": contract.consumer_apps,
                    "entities": contract.entities_involved,
                    "version": contract.version,
                })

        # Resumen de otras apps que tocan las mismas entidades/flujos
        flow_names_lower = [f.lower() for f in flow_names]
        for app in self._registry.apps:
            if app.app_id == current_app_id:
                continue

            app_entities_lower = [e.lower() for e in app.entities_snapshot]
            app_flows_lower = [f.lower() for f in app.flows_snapshot]

            entity_overlap = [
                e for e in entity_names_lower if e in app_entities_lower
            ]
            flow_overlap = [
                f for f in flow_names_lower if f in app_flows_lower
            ]

            if entity_overlap or flow_overlap:
                context["other_apps_context"].append({
                    "app_id": app.app_id,
                    "name": app.name,
                    "coupling_type": app.coupling_type,
                    "team": app.team,
                    "shared_entities": entity_overlap,
                    "shared_flows": flow_overlap,
                    "story_count": app.story_count,
                })

        return context

    # ─── CONTRACTS ───────────────────────────────────────────────────────────────

    def add_contract(self, contract: ContractDefinition) -> None:
        """Agrega o actualiza un contrato en el ecosistema.

        Args:
            contract: Definicion del contrato.
        """
        if not self._registry:
            raise RuntimeError("Ecosistema no inicializado.")

        existing_idx = next(
            (i for i, c in enumerate(self._registry.contracts) if c.contract_id == contract.contract_id),
            None,
        )

        if existing_idx is not None:
            self._registry.contracts[existing_idx] = contract
        else:
            self._registry.contracts.append(contract)

        # Guardar contrato individual
        contract_path = self._ecosystem_path / "contracts" / f"{contract.contract_id}.json"
        contract_path.write_text(
            json.dumps(contract.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self._registry.updated_at = datetime.now().isoformat()
        self._save_registry()
        logger.info("Contrato '%s' registrado", contract.contract_id)

    # ─── CONFLICT DETECTION ──────────────────────────────────────────────────────

    def detect_cross_app_conflicts(self) -> list[CrossAppConflict]:
        """Detecta conflictos entre apps del ecosistema.

        Returns:
            Lista de conflictos encontrados.
        """
        if not self._registry:
            return []

        conflicts: list[CrossAppConflict] = []

        # 1. Entidades divergentes
        for shared in self._registry.shared_entities:
            if not shared.is_consistent:
                conflicts.append(CrossAppConflict(
                    conflict_type="entity_divergence",
                    severity="high",
                    apps_involved=shared.defined_in_apps,
                    description=(
                        f"Entidad '{shared.entity_name}' tiene definiciones divergentes "
                        f"entre apps: {', '.join(shared.defined_in_apps)}. "
                        f"{shared.divergence_notes}"
                    ),
                    suggestion=(
                        f"Alinear la definicion de '{shared.entity_name}' entre las apps "
                        f"o documentar explicitamente por que divergen (bounded context)."
                    ),
                ))

        # 2. Contratos sin provider (app consume algo que nadie expone)
        all_app_ids = {a.app_id for a in self._registry.apps}
        for contract in self._registry.contracts:
            if contract.provider_app not in all_app_ids:
                conflicts.append(CrossAppConflict(
                    conflict_type="missing_contract_provider",
                    severity="high",
                    apps_involved=contract.consumer_apps,
                    description=(
                        f"Contrato '{contract.name}' ({contract.contract_id}) "
                        f"tiene provider '{contract.provider_app}' que no esta registrado en el ecosistema."
                    ),
                    suggestion=(
                        f"Registrar la app '{contract.provider_app}' en el ecosistema "
                        f"o corregir el provider del contrato."
                    ),
                ))

        # 3. Contratos muertos (nadie consume)
        for contract in self._registry.contracts:
            if not contract.consumer_apps:
                conflicts.append(CrossAppConflict(
                    conflict_type="dead_contract",
                    severity="low",
                    apps_involved=[contract.provider_app],
                    description=(
                        f"Contrato '{contract.name}' ({contract.contract_id}) "
                        f"expuesto por '{contract.provider_app}' no tiene consumidores registrados."
                    ),
                    suggestion=(
                        "Verificar si el contrato esta en uso por apps no registradas "
                        "o si se puede deprecar."
                    ),
                ))

        # 4. Flujos cross-app con gaps (flujo en app A que referencia entidad de app B sin contrato)
        for app in self._registry.apps:
            app_entities_lower = {e.lower() for e in app.entities_snapshot}
            # Ver si la app tiene entidades que son de otra app pero no hay contrato que las conecte
            for shared in self._registry.shared_entities:
                if app.app_id in shared.defined_in_apps and len(shared.defined_in_apps) > 1:
                    # Verificar que exista un contrato que conecte estas apps para esa entidad
                    other_apps = [a for a in shared.defined_in_apps if a != app.app_id]
                    entity_in_contracts = any(
                        shared.entity_name.lower() in [e.lower() for e in c.entities_involved]
                        for c in self._registry.contracts
                        if c.provider_app in other_apps or app.app_id in c.consumer_apps
                    )
                    if not entity_in_contracts:
                        conflicts.append(CrossAppConflict(
                            conflict_type="cross_app_flow_gap",
                            severity="medium",
                            apps_involved=[app.app_id] + other_apps,
                            description=(
                                f"Entidad '{shared.entity_name}' es compartida entre "
                                f"{app.app_id} y {', '.join(other_apps)} pero no hay "
                                f"contrato registrado que defina como se intercambia."
                            ),
                            suggestion=(
                                f"Definir un contrato (API/evento) que formalice el intercambio "
                                f"de '{shared.entity_name}' entre estas apps."
                            ),
                        ))

        return conflicts

    # ─── PRIVATE METHODS ─────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Carga el registro del ecosistema desde disco."""
        registry_path = self._ecosystem_path / "ecosystem.json"
        if registry_path.exists():
            data = json.loads(registry_path.read_text(encoding="utf-8"))
            self._registry = EcosystemRegistry(**data)
            logger.info(
                "Ecosistema '%s' cargado (%d apps)",
                self._registry.name,
                len(self._registry.apps),
            )

    def _save_registry(self) -> None:
        """Persiste el registro central."""
        if not self._registry:
            return
        registry_path = self._ecosystem_path / "ecosystem.json"
        registry_path.write_text(
            json.dumps(self._registry.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _save_app_snapshot(self, app: AppRegistration) -> None:
        """Persiste el snapshot individual de una app."""
        app_file = self._ecosystem_path / "apps" / f"{app.app_id}.json"
        app_file.parent.mkdir(parents=True, exist_ok=True)
        app_file.write_text(
            json.dumps(app.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _sync_app_snapshot(self, app: AppRegistration) -> AppRegistration:
        """Lee el .hu-memory/index.json de una app para actualizar su snapshot.

        Opera en modo read-only sobre la memoria de la app.

        Args:
            app: App a sincronizar.

        Returns:
            App con snapshot actualizado.
        """
        memory_path = Path(app.memory_path)
        if not memory_path.is_absolute():
            memory_path = ECOSYSTEM_PATH / memory_path

        index_path = memory_path / "index.json"
        if not index_path.exists():
            logger.warning("No se encontro index.json para app '%s' en %s", app.app_id, memory_path)
            return app

        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
            # Extraer entidades
            entities = [e.get("name", "") for e in data.get("entities", [])]
            app.entities_snapshot = entities

            # Extraer flujos
            flows = [f.get("name", "") for f in data.get("flows", [])]
            app.flows_snapshot = flows

            # Story count
            app.story_count = data.get("story_count", 0)

            logger.info(
                "Snapshot de '%s': %d entidades, %d flujos, %d HUs",
                app.app_id, len(entities), len(flows), app.story_count,
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Error leyendo index.json de '%s': %s", app.app_id, e)

        return app

    def _recalculate_shared_entities(self) -> None:
        """Recalcula las entidades compartidas entre apps."""
        if not self._registry:
            return

        # Mapear entidad → apps donde aparece
        entity_apps: dict[str, list[str]] = {}
        for app in self._registry.apps:
            for entity in app.entities_snapshot:
                entity_lower = entity.lower()
                if entity_lower not in entity_apps:
                    entity_apps[entity_lower] = []
                if app.app_id not in entity_apps[entity_lower]:
                    entity_apps[entity_lower].append(app.app_id)

        # Solo entidades en 2+ apps son "compartidas"
        shared: list[SharedEntity] = []
        for entity_name, app_ids in entity_apps.items():
            if len(app_ids) >= 2:
                # Intentar leer campos de cada app (desde sus HUs)
                fields_by_app = self._read_entity_fields(entity_name, app_ids)
                is_consistent = self._check_entity_consistency(fields_by_app)

                divergence_notes = ""
                if not is_consistent:
                    divergence_notes = self._describe_divergence(entity_name, fields_by_app)

                shared.append(SharedEntity(
                    entity_name=entity_name,
                    defined_in_apps=app_ids,
                    fields_by_app=fields_by_app,
                    is_consistent=is_consistent,
                    divergence_notes=divergence_notes,
                ))

        self._registry.shared_entities = shared

    def _read_entity_fields(self, entity_name: str, app_ids: list[str]) -> dict[str, list[str]]:
        """Lee los campos conocidos de una entidad en cada app.

        Args:
            entity_name: Nombre de la entidad (lowercase).
            app_ids: IDs de las apps donde aparece.

        Returns:
            {app_id: [campos]} leidos de los .hu-memory/.
        """
        fields_by_app: dict[str, list[str]] = {}

        for app_id in app_ids:
            app = self.get_app(app_id)
            if not app:
                continue

            memory_path = Path(app.memory_path)
            if not memory_path.is_absolute():
                memory_path = ECOSYSTEM_PATH / memory_path

            index_path = memory_path / "index.json"
            if not index_path.exists():
                fields_by_app[app_id] = []
                continue

            try:
                data = json.loads(index_path.read_text(encoding="utf-8"))
                entities = data.get("entities", [])
                for entity_data in entities:
                    if entity_data.get("name", "").lower() == entity_name:
                        fields_by_app[app_id] = entity_data.get("fields", [])
                        break
                else:
                    fields_by_app[app_id] = []
            except (json.JSONDecodeError, KeyError):
                fields_by_app[app_id] = []

        return fields_by_app

    @staticmethod
    def _check_entity_consistency(fields_by_app: dict[str, list[str]]) -> bool:
        """Verifica si los campos de una entidad son consistentes entre apps.

        Args:
            fields_by_app: Campos por app.

        Returns:
            True si son consistentes (iguales o subconjuntos).
        """
        non_empty = [set(f) for f in fields_by_app.values() if f]
        if len(non_empty) <= 1:
            return True

        # Consistente si uno es subconjunto del otro (permite extension)
        all_fields = set()
        for field_set in non_empty:
            all_fields.update(field_set)

        # Si todos son subconjuntos del union, es consistente
        # Inconsistente si hay campos contradictorios (heuristica: >30% diferente)
        for field_set in non_empty:
            if len(field_set) > 0 and len(field_set & all_fields) / len(all_fields) < 0.5:
                return False

        return True

    @staticmethod
    def _describe_divergence(entity_name: str, fields_by_app: dict[str, list[str]]) -> str:
        """Genera una nota descriptiva de la divergencia.

        Args:
            entity_name: Nombre de la entidad.
            fields_by_app: Campos por app.

        Returns:
            Descripcion de la divergencia.
        """
        parts = []
        for app_id, fields in fields_by_app.items():
            if fields:
                parts.append(f"{app_id}: [{', '.join(fields[:5])}]")
        return f"Campos divergentes para '{entity_name}': " + " vs ".join(parts)


# ─── SINGLETON ───────────────────────────────────────────────────────────────────

_ecosystem_instance: Optional[EcosystemEngine] = None


def get_ecosystem() -> EcosystemEngine:
    """Obtiene la instancia singleton del EcosystemEngine."""
    global _ecosystem_instance
    if _ecosystem_instance is None:
        _ecosystem_instance = EcosystemEngine()
    return _ecosystem_instance
