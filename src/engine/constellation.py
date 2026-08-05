"""ConstellationEngine: grafo de specs con dependencias tipificadas.

Genera visualización de la constelación de specs del ecosistema,
detecta gaps y permite inferir dependencias desde contratos existentes.
"""

import logging
from typing import Optional

from src.engine.ecosystem import EcosystemEngine
from src.engine.spec_engine import SpecEngine
from src.models.sdd import ProjectSpec, SpecDependency

logger = logging.getLogger("mcp_hu.engine.constellation")


class ConstellationEngine:
    """Motor de constelación: grafo de ProjectSpecs con dependencias tipificadas.

    Combina datos del EcosystemEngine (apps, contratos) con el SpecEngine
    (specs, dependencias) para generar un grafo navegable y detectar gaps.
    """

    def __init__(self, ecosystem_engine: EcosystemEngine, spec_engine: SpecEngine) -> None:
        """Inicializa con un EcosystemEngine y un SpecEngine.

        Args:
            ecosystem_engine: Engine del ecosistema activo.
            spec_engine: Engine de specs.
        """
        self._ecosystem = ecosystem_engine
        self._specs = spec_engine

    # ─── GRAPH GENERATION ────────────────────────────────────────────────────────

    def build_constellation(self) -> dict:
        """Genera el grafo de specs en formato Cytoscape.js.

        Returns:
            Dict con nodes y edges compatibles con Cytoscape.js.
        """
        nodes: list[dict] = []
        edges: list[dict] = []
        specs_list = self._specs.list_specs()

        for spec_summary in specs_list:
            spec = self._specs.get_spec(spec_summary["spec_id"])
            if not spec:
                continue

            layers_with_content = [
                layer_name for layer_name, content in spec.layers.items()
                if content.summary
            ]
            has_strategic = any(
                layer_name in ("negocio", "arquitectura", "seguridad", "gobierno_info", "acceso_datos")
                for layer_name in layers_with_content
            )

            nodes.append({
                "data": {
                    "id": spec.spec_id,
                    "label": spec.project_name,
                    "status": spec.status,
                    "version": spec.version,
                    "app_id": spec.app_id or "",
                    "layers_count": len(layers_with_content),
                    "rules_applied": len(spec.rules_applied),
                    "has_strategic": has_strategic,
                    "approved_by": spec.approved_by,
                },
                "classes": f"spec-{spec.status}",
            })

            for dep in spec.dependencies:
                edges.append({
                    "data": {
                        "id": f"{spec.spec_id}-->{dep.target_spec_id}",
                        "source": spec.spec_id,
                        "target": dep.target_spec_id,
                        "dependency_type": dep.dependency_type,
                        "maturity": dep.maturity,
                        "description": dep.description,
                        "contracts": dep.contracts,
                    },
                    "classes": f"dep-{dep.dependency_type} maturity-{dep.maturity}",
                })

        return {"nodes": nodes, "edges": edges}

    # ─── GAP DETECTION ───────────────────────────────────────────────────────────

    def detect_gaps(self) -> list[dict]:
        """Detecta gaps en la constelación de specs.

        Detecta:
        - Specs huérfanas (sin dependencias entrantes ni salientes)
        - Referencias sin formalizar (target_spec_id que no existe como ProjectSpec)
        - Ciclos de dependencia
        - Apps registradas sin spec vinculada

        Returns:
            Lista de gaps detectados con tipo, descripción y sugerencia.
        """
        gaps: list[dict] = []
        specs_list = self._specs.list_specs()
        spec_ids = {s["spec_id"] for s in specs_list}

        # Cargar todas las specs completas
        all_specs: list[ProjectSpec] = []
        for spec_summary in specs_list:
            spec = self._specs.get_spec(spec_summary["spec_id"])
            if spec:
                all_specs.append(spec)

        # 1. Specs huérfanas
        specs_with_deps_out = set()
        specs_with_deps_in = set()
        for spec in all_specs:
            for dep in spec.dependencies:
                specs_with_deps_out.add(spec.spec_id)
                specs_with_deps_in.add(dep.target_spec_id)

        orphan_specs = spec_ids - specs_with_deps_out - specs_with_deps_in
        for orphan_id in orphan_specs:
            gaps.append({
                "type": "orphan_spec",
                "severity": "low",
                "spec_id": orphan_id,
                "description": f"Spec '{orphan_id}' no tiene dependencias entrantes ni salientes.",
                "suggestion": "Verificar si esta spec debería conectarse con otras del ecosistema.",
            })

        # 2. Referencias sin formalizar
        for spec in all_specs:
            for dep in spec.dependencies:
                if dep.target_spec_id not in spec_ids:
                    gaps.append({
                        "type": "unresolved_reference",
                        "severity": "medium",
                        "spec_id": spec.spec_id,
                        "target_spec_id": dep.target_spec_id,
                        "description": (
                            f"Spec '{spec.spec_id}' depende de '{dep.target_spec_id}' "
                            f"que no existe como ProjectSpec."
                        ),
                        "suggestion": (
                            f"Crear spec '{dep.target_spec_id}' o importar como referencia "
                            f"con import_spec."
                        ),
                    })

        # 3. Ciclos de dependencia (DFS)
        cycles = self._detect_cycles(all_specs, spec_ids)
        for cycle in cycles:
            gaps.append({
                "type": "dependency_cycle",
                "severity": "high",
                "specs_involved": cycle,
                "description": f"Ciclo de dependencia detectado: {' → '.join(cycle)}.",
                "suggestion": "Romper el ciclo redefiniendo la relación como bidireccional o eliminando una dependencia.",
            })

        # 4. Apps sin spec vinculada
        if self._ecosystem.is_initialized:
            apps = self._ecosystem.get_all_apps()
            for app in apps:
                if not app.spec_id:
                    gaps.append({
                        "type": "app_without_spec",
                        "severity": "low",
                        "app_id": app.app_id,
                        "app_name": app.name,
                        "description": f"App '{app.name}' ({app.app_id}) no tiene spec vinculada.",
                        "suggestion": f"Crear spec para '{app.name}' con create_spec y vincular con link_app_to_spec.",
                    })

        return gaps

    # ─── INFER DEPENDENCIES FROM CONTRACTS ───────────────────────────────────────

    def infer_dependencies_from_contracts(self) -> list[dict]:
        """Infiere SpecDependency entre specs a partir de contratos del ecosistema.

        Para cada contrato, busca las apps provider y consumer. Si ambas tienen
        spec_id vinculado, crea una SpecDependency entre esas specs.

        El dependency_type se infiere del tipo de contrato:
        - async_event → process
        - shared_lib → functional
        - rest_api/graphql con entities de dominio → data
        - Default → functional

        El maturity hereda del menor entre las dos specs.

        Returns:
            Lista de dependencias inferidas (resumen).
        """
        if not self._ecosystem.is_initialized:
            return []

        contracts = self._ecosystem.get_contracts()
        apps = self._ecosystem.get_all_apps()
        app_map = {app.app_id: app for app in apps}

        inferred: list[dict] = []

        for contract in contracts:
            provider_app = app_map.get(contract.provider_app)
            if not provider_app or not provider_app.spec_id:
                continue

            for consumer_app_id in contract.consumer_apps:
                consumer_app = app_map.get(consumer_app_id)
                if not consumer_app or not consumer_app.spec_id:
                    continue

                # No crear auto-dependencia
                if provider_app.spec_id == consumer_app.spec_id:
                    continue

                # Inferir dependency_type
                if contract.type == "async_event":
                    dep_type = "process"
                elif contract.type == "shared_lib":
                    dep_type = "functional"
                elif contract.type in ("rest_api", "graphql") and contract.entities_involved:
                    dep_type = "data"
                else:
                    dep_type = "functional"

                # Inferir maturity (menor de las dos specs)
                provider_spec = self._specs.get_spec(provider_app.spec_id)
                consumer_spec = self._specs.get_spec(consumer_app.spec_id)
                maturity = self._infer_maturity(provider_spec, consumer_spec)

                # Crear la dependencia: consumer depende de provider
                new_dep = SpecDependency(
                    target_spec_id=provider_app.spec_id,
                    dependency_type=dep_type,
                    description=f"Inferido desde contrato '{contract.name}' ({contract.contract_id})",
                    maturity=maturity,
                    contracts=[contract.contract_id],
                )

                # Persistir en la spec del consumer (sin duplicar)
                if consumer_spec:
                    already_exists = any(
                        d.target_spec_id == new_dep.target_spec_id
                        and d.dependency_type == new_dep.dependency_type
                        and contract.contract_id in d.contracts
                        for d in consumer_spec.dependencies
                    )
                    if not already_exists:
                        consumer_spec.dependencies.append(new_dep)
                        consumer_spec.updated_at = __import__("datetime").datetime.now().isoformat()
                        self._specs._save_spec(consumer_spec)

                        inferred.append({
                            "source_spec": consumer_app.spec_id,
                            "target_spec": provider_app.spec_id,
                            "dependency_type": dep_type,
                            "maturity": maturity,
                            "contract_id": contract.contract_id,
                        })

        logger.info("Dependencias inferidas desde contratos: %d", len(inferred))
        return inferred

    # ─── PRIVATE METHODS ─────────────────────────────────────────────────────────

    def _detect_cycles(self, all_specs: list[ProjectSpec], spec_ids: set[str]) -> list[list[str]]:
        """Detecta ciclos en el grafo de dependencias usando DFS.

        Args:
            all_specs: Lista de todas las specs.
            spec_ids: Set de spec_ids existentes.

        Returns:
            Lista de ciclos (cada ciclo es una lista de spec_ids).
        """
        # Construir grafo de adyacencia
        graph: dict[str, list[str]] = {sid: [] for sid in spec_ids}
        for spec in all_specs:
            for dep in spec.dependencies:
                if dep.target_spec_id in spec_ids:
                    graph[spec.spec_id].append(dep.target_spec_id)

        cycles: list[list[str]] = []
        visited: set[str] = set()
        rec_stack: set[str] = set()
        path: list[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Encontramos un ciclo
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.discard(node)

        for spec_id in spec_ids:
            if spec_id not in visited:
                dfs(spec_id)

        return cycles

    @staticmethod
    def _infer_maturity(provider_spec: Optional[ProjectSpec], consumer_spec: Optional[ProjectSpec]) -> str:
        """Infiere el maturity de una dependencia basado en el menor de las dos specs.

        Args:
            provider_spec: Spec del provider.
            consumer_spec: Spec del consumer.

        Returns:
            Maturity level: formalized, draft, o reference.
        """
        maturity_order = {"approved": "formalized", "draft": "draft", "superseded": "reference"}
        provider_maturity = maturity_order.get(
            provider_spec.status if provider_spec else "draft", "draft"
        )
        consumer_maturity = maturity_order.get(
            consumer_spec.status if consumer_spec else "draft", "draft"
        )

        # Orden: formalized > draft > reference
        order = ["reference", "draft", "formalized"]
        provider_idx = order.index(provider_maturity) if provider_maturity in order else 1
        consumer_idx = order.index(consumer_maturity) if consumer_maturity in order else 1

        return order[min(provider_idx, consumer_idx)]
