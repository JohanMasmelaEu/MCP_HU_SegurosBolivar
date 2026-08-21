"""Shared Memory Engine: capa de memoria compartida via repositorio Git.

Escribe/lee archivos Markdown individuales en .hu-memory/shared/ para que
puedan versionarse en el repo y sincronizarse con la wiki de GitHub.

Principios:
- 1 archivo por entidad/flujo/decisión → merge conflicts casi imposibles
- Formato Markdown → legible sin herramientas, diff limpio en PRs
- Solo el MCP escribe aquí (nunca el agente IDE directamente)
- Solo se ejecuta cuando el usuario lo pide explícitamente
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.engine.memory import MemoryEngine, get_memory

logger = logging.getLogger("mcp_hu.engine.shared_memory")

SHARED_DIR_NAME = "shared"


class SharedMemoryEngine:
    """Motor de memoria compartida que opera sobre .hu-memory/shared/.

    Lee la memoria local (index.json) y la exporta como Markdown individual.
    También puede importar Markdown de shared/ hacia la memoria local.
    """

    def __init__(self, memory_engine: MemoryEngine) -> None:
        self._memory = memory_engine
        self._shared_path = memory_engine.memory_path / SHARED_DIR_NAME

    @property
    def shared_path(self) -> Path:
        return self._shared_path

    @property
    def is_initialized(self) -> bool:
        return self._shared_path.exists() and (self._shared_path / "README.md").exists()

    # ─── INIT ────────────────────────────────────────────────────────────────────

    def init_shared(self) -> dict:
        """Crea la estructura shared/ si no existe."""
        self._shared_path.mkdir(parents=True, exist_ok=True)
        (self._shared_path / "entities").mkdir(exist_ok=True)
        (self._shared_path / "flows").mkdir(exist_ok=True)
        (self._shared_path / "decisions").mkdir(exist_ok=True)

        if not (self._shared_path / "README.md").exists():
            self._write_readme()

        logger.info("Shared memory inicializada en %s", self._shared_path)
        return {
            "status": "success",
            "path": str(self._shared_path),
            "message": "Estructura shared/ creada. Archivos listos para commitear al repo.",
        }

    # ─── EXPORT: local → shared/ ─────────────────────────────────────────────────

    def export_to_shared(self, scope: str = "all") -> dict:
        """Exporta memoria local a archivos Markdown en shared/.

        Args:
            scope: Qué exportar — "all", "entities", "flows", "decisions".

        Returns:
            Resumen de archivos creados/actualizados.
        """
        if not self._memory.is_initialized:
            return {"status": "error", "message": "No hay memoria local inicializada."}

        if not self.is_initialized:
            self.init_shared()

        files_written = []
        index = self._memory.index
        if index is None:
            return {"status": "error", "message": "Índice de memoria vacío."}

        if scope in ("all", "entities"):
            for entity in index.entities:
                path = self._write_entity_md(entity)
                files_written.append(str(path.relative_to(self._shared_path)))

        if scope in ("all", "flows"):
            for flow in index.flows:
                path = self._write_flow_md(flow)
                files_written.append(str(path.relative_to(self._shared_path)))

        if scope in ("all", "decisions"):
            for decision in index.decisions:
                path = self._write_decision_md(decision)
                files_written.append(str(path.relative_to(self._shared_path)))

        # Regenerar README con índice actualizado
        self._write_readme()
        files_written.append("README.md")

        return {
            "status": "success",
            "files_written": files_written,
            "total": len(files_written),
            "message": (
                f"{len(files_written)} archivo(s) exportados a shared/. "
                "Hacer commit y push para compartir con el equipo."
            ),
        }

    # ─── IMPORT: shared/ → local ─────────────────────────────────────────────────

    def import_from_shared(self) -> dict:
        """Lee archivos Markdown de shared/ y mergea con la memoria local.

        No sobreescribe — solo agrega entidades/flujos/decisiones que no existan.

        Returns:
            Resumen de lo importado.
        """
        if not self.is_initialized:
            return {"status": "error", "message": "No existe shared/. Nada que importar."}

        if not self._memory.is_initialized:
            return {"status": "error", "message": "No hay memoria local. Inicializar proyecto primero."}

        index = self._memory.index
        if index is None:
            return {"status": "error", "message": "Índice de memoria vacío."}

        imported = {"entities": 0, "flows": 0, "decisions": 0}

        # Importar entidades
        entities_dir = self._shared_path / "entities"
        if entities_dir.exists():
            for md_file in sorted(entities_dir.glob("*.md")):
                entity_data = self._parse_entity_md(md_file)
                if entity_data and not any(e.name == entity_data["name"] for e in index.entities):
                    from src.models.project import EntityInfo
                    index.entities.append(EntityInfo(
                        name=entity_data["name"],
                        first_seen_in=entity_data.get("first_seen_in", "imported"),
                        appears_in=entity_data.get("appears_in", []),
                        fields=entity_data.get("fields", []),
                        relations=entity_data.get("relations", []),
                    ))
                    imported["entities"] += 1

        # Importar flujos
        flows_dir = self._shared_path / "flows"
        if flows_dir.exists():
            for md_file in sorted(flows_dir.glob("*.md")):
                flow_data = self._parse_flow_md(md_file)
                if flow_data and not any(f.name == flow_data["name"] for f in index.flows):
                    from src.models.project import FlowInfo
                    index.flows.append(FlowInfo(
                        name=flow_data["name"],
                        description=flow_data.get("description", ""),
                        stories_involved=flow_data.get("stories_involved", []),
                        status=flow_data.get("status", "incomplete"),
                        steps=flow_data.get("steps", []),
                    ))
                    imported["flows"] += 1

        # Importar decisiones
        decisions_dir = self._shared_path / "decisions"
        if decisions_dir.exists():
            for md_file in sorted(decisions_dir.glob("*.md")):
                dec_data = self._parse_decision_md(md_file)
                if dec_data and not any(d.id == dec_data["id"] for d in index.decisions):
                    from src.models.project import Decision
                    index.decisions.append(Decision(
                        id=dec_data["id"],
                        description=dec_data.get("description", ""),
                        reason=dec_data.get("reason", ""),
                        decided_in=dec_data.get("decided_in", "imported"),
                        date=dec_data.get("date", datetime.now().isoformat()),
                    ))
                    imported["decisions"] += 1

        # Persistir cambios
        self._memory._save_index()

        total = sum(imported.values())
        return {
            "status": "success",
            "imported": imported,
            "total": total,
            "message": (
                f"Importados {total} elemento(s) desde shared/ "
                f"({imported['entities']} entidades, {imported['flows']} flujos, "
                f"{imported['decisions']} decisiones). "
                "Elementos ya existentes fueron omitidos."
            ) if total > 0 else "Sin elementos nuevos para importar. La memoria local ya está al día.",
        }

    # ─── STATUS ──────────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Retorna el estado actual de la memoria compartida."""
        if not self.is_initialized:
            return {
                "initialized": False,
                "message": "Shared memory no inicializada. Usar export_to_shared para crearla.",
            }

        entity_count = len(list((self._shared_path / "entities").glob("*.md")))
        flow_count = len(list((self._shared_path / "flows").glob("*.md")))
        decision_count = len(list((self._shared_path / "decisions").glob("*.md")))

        return {
            "initialized": True,
            "path": str(self._shared_path),
            "counts": {
                "entities": entity_count,
                "flows": flow_count,
                "decisions": decision_count,
            },
            "total_files": entity_count + flow_count + decision_count,
        }

    # ─── WIKI BUNDLE ─────────────────────────────────────────────────────────────

    def generate_wiki_bundle(self) -> dict:
        """Genera el contenido completo de la wiki como un bundle listo para copiar.

        Incluye TODOS los recursos de la memoria:
        - Entidades del dominio
        - Flujos de negocio
        - Decisiones arquitectónicas
        - Historias de Usuario (narrativa, criterios, dependencias, tags)
        - Specs SDD (las 8 capas con details expandidos)
        - Grafo de dependencias entre HUs
        - Ecosistema y contratos cross-app

        Returns:
            Dict con pages[], full_content, y summary.
        """
        if not self._memory.is_initialized:
            return {"status": "error", "message": "No hay memoria local inicializada."}

        index = self._memory.index
        if index is None:
            return {"status": "error", "message": "Índice de memoria vacío."}

        pages: list[dict] = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        counts = {"entities": 0, "flows": 0, "decisions": 0, "stories": 0,
                  "specs": 0, "graph": 0, "ecosystem": 0, "contracts": 0}

        # ─── 1. Página principal (Home) ──────────────────────────────────────
        stories = self._memory.get_all_stories()
        home_lines = [
            "# Memoria Compartida del Proyecto",
            "",
            f"**Proyecto:** {index.config.project_name}",
            f"**Dominio:** {index.config.domain}",
            f"**HUs analizadas:** {len(stories)}",
            f"**Entidades:** {len(index.entities)}",
            f"**Flujos:** {len(index.flows)}",
            "",
            "## Índice",
            "",
        ]
        if stories:
            home_lines.append(f"- **Historias de Usuario** ({len(stories)} HUs)")
        if index.entities:
            home_lines.append(f"- **Entidades** ({len(index.entities)})")
        if index.flows:
            home_lines.append(f"- **Flujos** ({len(index.flows)})")
        if index.decisions:
            home_lines.append(f"- **Decisiones** ({len(index.decisions)})")
        home_lines.append("- **Grafo de Dependencias**")
        home_lines.append("- **Specs SDD**")
        home_lines.append("- **Ecosistema y Contratos**")
        home_lines.append("")
        home_lines.append("_Consultar la barra lateral para navegar a cada seccion._")

        home_lines.append("")
        home_lines.append(f"---\n_Generado por MCP HU SegurosBolivar - {now}_\n")
        pages.append({"title": "Home", "path": "Home.md", "content": "\n".join(home_lines)})

        # ─── 2. Páginas de HUs ───────────────────────────────────────────────
        for story in stories:
            lines = [
                f"# {story.id}: {story.title}",
                "",
                "## Narrativa",
                "",
                f"**Como** {story.narrative.as_a}",
                f"**Quiero** {story.narrative.i_want}",
                f"**Para que** {story.narrative.so_that}",
                "",
            ]

            if story.acceptance_criteria:
                lines.append("## Criterios de Aceptación")
                lines.append("")
                for i, ac in enumerate(story.acceptance_criteria, 1):
                    lines.append(f"### CA-{i}")
                    lines.append(f"- **Dado** {ac.given}")
                    lines.append(f"- **Cuando** {ac.when}")
                    lines.append(f"- **Entonces** {ac.then}")
                    lines.append("")

            if story.entities_detected:
                lines.append("## Entidades")
                lines.append("")
                for ent in story.entities_detected:
                    lines.append(f"- {ent}")
                lines.append("")

            if story.flows_detected:
                lines.append("## Flujos")
                lines.append("")
                for fl in story.flows_detected:
                    lines.append(f"- {fl}")
                lines.append("")

            if story.complexity_tags:
                lines.append(f"**Complejidad:** {', '.join(story.complexity_tags)}")
                lines.append("")

            if story.dependencies:
                lines.append("## Depende de")
                lines.append("")
                for dep in story.dependencies:
                    lines.append(f"- {dep}")
                lines.append("")

            if story.impacts:
                lines.append("## Impacta a")
                lines.append("")
                for imp in story.impacts:
                    lines.append(f"- {imp}")
                lines.append("")

            lines.append(f"**Estado:** {story.status}  ")
            lines.append(f"**Gaps:** {story.total_gaps} | **Preguntas:** {story.total_questions}")
            lines.append("")
            lines.append(f"---\n_Generado: {now}_\n")

            slug = story.id.lower()
            pages.append({
                "title": f"{story.id}: {story.title}",
                "path": f"historias/{slug}.md",
                "content": "\n".join(lines),
            })
            counts["stories"] += 1

        # ─── 3. Páginas de entidades ─────────────────────────────────────────
        for entity in index.entities:
            lines = [f"# {entity.name}", "", f"**Primera aparición:** {entity.first_seen_in}", ""]
            if entity.appears_in:
                lines.extend(["## Aparece en", ""] + [f"- {h}" for h in entity.appears_in] + [""])
            if entity.fields:
                lines.extend(["## Campos", ""] + [f"- `{f}`" for f in entity.fields] + [""])
            if entity.relations:
                lines.extend(["## Relaciones", ""] + [f"- {r}" for r in entity.relations] + [""])
            lines.append(f"---\n_Generado: {now}_\n")
            slug = self._slugify(entity.name)
            pages.append({"title": f"Entidad: {entity.name}", "path": f"entidades/{slug}.md", "content": "\n".join(lines)})
            counts["entities"] += 1

        # ─── 4. Páginas de flujos ────────────────────────────────────────────
        for flow in index.flows:
            lines = [f"# {flow.name}", "", f"**Estado:** {flow.status}", ""]
            if flow.description:
                lines.extend([flow.description, ""])
            if flow.stories_involved:
                lines.extend(["## HUs involucradas", ""] + [f"- {h}" for h in flow.stories_involved] + [""])
            if flow.steps:
                lines.extend(["## Pasos", ""] + [f"{i}. {s}" for i, s in enumerate(flow.steps, 1)] + [""])
            lines.append(f"---\n_Generado: {now}_\n")
            slug = self._slugify(flow.name)
            pages.append({"title": f"Flujo: {flow.name}", "path": f"flujos/{slug}.md", "content": "\n".join(lines)})
            counts["flows"] += 1

        # ─── 5. Páginas de decisiones ────────────────────────────────────────
        for decision in index.decisions:
            lines = [
                f"# {decision.id}", "",
                f"**Descripción:** {decision.description}", "",
                f"**Razón:** {decision.reason}", "",
                f"**Decidido en:** {decision.decided_in}", "",
                f"**Fecha:** {decision.date}", "",
                f"---\n_Generado: {now}_\n",
            ]
            slug = self._slugify(decision.id)
            pages.append({"title": f"Decisión: {decision.id}", "path": f"decisiones/{slug}.md", "content": "\n".join(lines)})
            counts["decisions"] += 1

        # ─── 6. Grafo de dependencias ────────────────────────────────────────
        graph = self._memory.graph
        if graph.number_of_nodes() > 0:
            lines = ["# Grafo de Dependencias entre HUs", ""]

            # Tabla de dependencias
            lines.extend(["## Dependencias directas", "", "| HU | Depende de | Relación |", "|---|---|---|"])
            for src, tgt, data in sorted(graph.edges(data=True)):
                rel = data.get("relation", "related_to")
                lines.append(f"| {src} | {tgt} | {rel} |")
            lines.append("")

            # Nodos sin dependencias entrantes (raíces)
            roots = [n for n in graph.nodes() if graph.in_degree(n) == 0]
            if roots:
                lines.extend(["## HUs raíz (sin dependencias)", ""] + [f"- **{r}**" for r in sorted(roots)] + [""])

            # Nodos sin dependencias salientes (hojas / bloqueadas)
            leaves = [n for n in graph.nodes() if graph.out_degree(n) == 0]
            if leaves:
                lines.extend(["## HUs hoja (no dependen de nada)", ""] + [f"- {l}" for l in sorted(leaves)] + [""])

            # Camino crítico simple: nodos con más conexiones
            by_degree = sorted(graph.nodes(), key=lambda n: graph.degree(n), reverse=True)
            if by_degree:
                lines.extend(["## HUs más conectadas", "", "| HU | Conexiones |", "|---|---|"])
                for n in by_degree[:10]:
                    lines.append(f"| {n} | {graph.degree(n)} |")
                lines.append("")

            lines.append(f"**Total:** {graph.number_of_nodes()} nodos, {graph.number_of_edges()} aristas")
            lines.append("")
            lines.append(f"---\n_Generado: {now}_\n")

            pages.append({"title": "Grafo de Dependencias", "path": "grafo-dependencias.md", "content": "\n".join(lines)})
            counts["graph"] = graph.number_of_nodes()

        # ─── 7. Specs SDD ────────────────────────────────────────────────────
        self._add_spec_pages(pages, counts, now)

        # ─── 8. Ecosistema y contratos ───────────────────────────────────────
        self._add_ecosystem_pages(pages, counts, now)

        # ─── Concatenar todo ─────────────────────────────────────────────────
        separator = "\n\n" + "=" * 72 + "\n"
        full_parts = []
        for page in pages:
            header = f"WIKI PAGE: {page['path']}"
            full_parts.append(f"{header}\n{'─' * len(header)}\n\n{page['content']}")

        return {
            "status": "success",
            "pages": pages,
            "page_count": len(pages),
            "summary": counts,
            "full_content": separator.join(full_parts),
            "message": (
                f"Wiki generada: {len(pages)} pagina(s) — "
                f"{counts['stories']} HUs, {counts['entities']} entidades, "
                f"{counts['flows']} flujos, {counts['decisions']} decisiones, "
                f"{counts['specs']} specs SDD, "
                f"{counts['contracts']} contratos ecosistema."
            ),
        }

    def _add_spec_pages(self, pages: list, counts: dict, now: str) -> None:
        """Genera páginas wiki para cada Spec SDD del workspace."""
        try:
            from src.engine.spec_engine import get_spec_engine
            spec_engine = get_spec_engine()
            if spec_engine is None:
                return
            all_specs = spec_engine.list_specs()
        except Exception:
            return

        for spec_summary in all_specs:
            try:
                spec = spec_engine.get_spec(spec_summary["spec_id"])
                if spec is None:
                    continue
            except Exception:
                continue

            lines = [
                f"# SDD: {spec.project_name}",
                "",
                f"**Spec ID:** {spec.spec_id}",
                f"**Version:** {spec.version}",
                f"**Estado:** {spec.status}",
                "",
            ]

            if spec.approved_by:
                lines.append(f"**Aprobado por:** {', '.join(spec.approved_by)}")
                lines.append("")

            # Cada capa SDD
            layer_names = {
                "negocio": "Negocio",
                "arquitectura": "Arquitectura",
                "seguridad": "Seguridad",
                "gobierno_info": "Gobierno de Información",
                "acceso_datos": "Acceso a Datos",
                "datos": "Datos",
                "desarrollo": "Desarrollo",
                "qa": "QA",
            }

            for layer_key, layer_label in layer_names.items():
                layer = spec.layers.get(layer_key)
                if layer is None:
                    continue

                has_content = layer.summary or layer.decisions or layer.constraints or layer.artifacts
                if not has_content:
                    continue

                lines.append(f"## {layer_label}")
                lines.append("")

                if layer.summary:
                    lines.append(layer.summary)
                    lines.append("")

                if layer.decisions:
                    lines.append("### Decisiones")
                    lines.append("")
                    for d in layer.decisions:
                        lines.append(f"- {d}")
                        # Expandir details si existe
                        d_id = d.split(":")[0].strip() if ":" in d else ""
                        if d_id and d_id in layer.details:
                            # Indentar el detalle
                            for detail_line in layer.details[d_id].split("\n"):
                                lines.append(f"  > {detail_line}")
                    lines.append("")

                if layer.constraints:
                    lines.append("### Restricciones")
                    lines.append("")
                    for c in layer.constraints:
                        lines.append(f"- {c}")
                        c_id = c.split(":")[0].strip() if ":" in c else ""
                        if c_id and c_id in layer.details:
                            for detail_line in layer.details[c_id].split("\n"):
                                lines.append(f"  > {detail_line}")
                    lines.append("")

                if layer.artifacts:
                    lines.append("### Artefactos")
                    lines.append("")
                    for a in layer.artifacts:
                        lines.append(f"- {a}")
                    lines.append("")

            # Dependencias de la spec
            if spec.dependencies:
                lines.append("## Dependencias con otras Specs")
                lines.append("")
                lines.append("| Target | Tipo | Madurez | Descripción |")
                lines.append("|---|---|---|---|")
                for dep in spec.dependencies:
                    lines.append(f"| {dep.target_spec_id} | {dep.dependency_type} | {dep.maturity} | {dep.description} |")
                lines.append("")

            if spec.rules_applied:
                lines.append(f"**Reglas aplicadas:** {', '.join(spec.rules_applied)}")
                lines.append("")

            lines.append(f"---\n_Generado: {now}_\n")

            slug = self._slugify(spec.spec_id)
            pages.append({
                "title": f"SDD: {spec.project_name}",
                "path": f"specs/{slug}.md",
                "content": "\n".join(lines),
            })
            counts["specs"] += 1

    def _add_ecosystem_pages(self, pages: list, counts: dict, now: str) -> None:
        """Genera páginas wiki para el ecosistema activo y sus contratos."""
        try:
            from src.engine.ecosystem_manager import get_ecosystem_manager
            eco_manager = get_ecosystem_manager()
            if eco_manager is None or eco_manager.active is None:
                return
            eco = eco_manager.active
        except Exception:
            return

        # Página principal del ecosistema
        lines = [
            f"# Ecosistema: {eco.name}",
            "",
            f"**ID:** {eco.ecosystem_id}",
            f"**Versión:** {eco.version}",
            "",
        ]

        if eco.description:
            lines.extend([eco.description, ""])

        # Apps registradas
        if eco.apps:
            lines.extend(["## Apps Registradas", "", "| App | Equipo | Acoplamiento | Madurez | HUs | Entidades |", "|---|---|---|---|---|---|"])
            for app in eco.apps:
                lines.append(
                    f"| **{app.name}** (`{app.app_id}`) | {app.team} | {app.coupling_type} | "
                    f"{app.maturity} | {app.story_count} | {len(app.entities_snapshot)} |"
                )
            lines.append("")

        # Entidades compartidas
        if eco.shared_entities:
            lines.extend(["## Entidades Compartidas", ""])
            for se in eco.shared_entities:
                status = "Consistente" if se.is_consistent else f"DIVERGENTE: {se.divergence_notes}"
                lines.append(f"- **{se.entity_name}** — apps: {', '.join(se.defined_in_apps)} — {status}")
            lines.append("")

        lines.append(f"---\n_Generado: {now}_\n")
        pages.append({"title": f"Ecosistema: {eco.name}", "path": "ecosistema/ecosistema.md", "content": "\n".join(lines)})
        counts["ecosystem"] = len(eco.apps)

        # Página por cada contrato
        for contract in eco.contracts:
            lines = [
                f"# Contrato: {contract.name}",
                "",
                f"**ID:** {contract.contract_id}",
                f"**Tipo:** {contract.type}",
                f"**Versión:** {contract.version}",
                f"**Estado:** {contract.status}",
                "",
                f"**Proveedor:** {contract.provider_app}",
                f"**Consumidores:** {', '.join(contract.consumer_apps) if contract.consumer_apps else 'ninguno'}",
                "",
            ]

            if contract.spec_reference:
                lines.extend([f"**Spec/Schema:** {contract.spec_reference}", ""])

            if contract.entities_involved:
                lines.extend(["## Entidades involucradas", ""] + [f"- {e}" for e in contract.entities_involved] + [""])

            if contract.entities_grouped:
                lines.extend(["## Entidades por categoría", ""])
                # Agrupar por categoría
                by_cat: dict[str, list[str]] = {}
                for eg in contract.entities_grouped:
                    by_cat.setdefault(eg.category, []).append(eg.name)
                for cat, names in sorted(by_cat.items()):
                    lines.append(f"### {cat.title()}")
                    for n in names:
                        lines.append(f"- {n}")
                    lines.append("")

            lines.append(f"---\n_Generado: {now}_\n")

            slug = self._slugify(contract.contract_id)
            pages.append({
                "title": f"Contrato: {contract.name}",
                "path": f"ecosistema/contratos/{slug}.md",
                "content": "\n".join(lines),
            })
            counts["contracts"] += 1

    # ─── EXPORT TO WIKI REPO ────────────────────────────────────────────────────

    def export_to_wiki_repo(self, wiki_path: str) -> dict:
        """Exporta la memoria del workspace al formato del repo wiki clonado.

        Escribe los archivos Markdown directamente en la estructura de carpetas
        que espera la wiki de GitHub. Si la ruta no es escribible (ej: MCP en Docker
        sin volumen montado), retorna todo el contenido para que el agente lo escriba.

        Estructura que genera:
            wiki_path/
            ├── Home.md                         # Índice principal
            ├── _Sidebar.md                     # Navegación lateral
            ├── 01-historias/                    # Historias de Usuario
            │   ├── hu-001.md
            │   └── hu-002.md
            ├── 02-entidades/                    # Entidades del dominio
            │   ├── poliza.md
            │   └── siniestro.md
            ├── 03-flujos/                       # Flujos de negocio
            │   └── registro-poliza.md
            ├── 04-decisiones/                   # Decisiones arquitectónicas
            │   └── dn-001.md
            ├── 05-specs/                        # Specs SDD
            │   └── sdd-mi-proyecto.md
            ├── 06-grafo/                        # Grafo de dependencias
            │   └── dependencias.md
            └── 07-ecosistema/                   # Ecosistema y contratos
                ├── ecosistema.md
                └── contratos/
                    └── contract-001.md

        Args:
            wiki_path: Ruta local al repo de la wiki clonado.

        Returns:
            Dict con status, archivos escritos, y resumen.
        """
        bundle = self.generate_wiki_bundle()
        if bundle["status"] != "success":
            return bundle

        wiki_dir = Path(wiki_path)

        if not wiki_dir.exists():
            return {"status": "error", "message": f"Ruta no encontrada: {wiki_path}. Clonar la wiki primero."}
        if not wiki_dir.is_dir():
            return {"status": "error", "message": f"No es un directorio: {wiki_path}"}

        files_written = []
        write_failed = False

        # Mapeo de prefijos del bundle → carpetas numeradas en el wiki
        folder_map = {
            "historias/": "01-historias",
            "entidades/": "02-entidades",
            "flujos/": "03-flujos",
            "decisiones/": "04-decisiones",
            "specs/": "05-specs",
            "ecosistema/contratos/": "07-ecosistema/contratos",
            "ecosistema/": "07-ecosistema",
        }

        try:
            # Crear todas las carpetas
            for folder in ["01-historias", "02-entidades", "03-flujos", "04-decisiones",
                           "05-specs", "06-grafo", "07-ecosistema", "07-ecosistema/contratos"]:
                (wiki_dir / folder).mkdir(parents=True, exist_ok=True)

            for page in bundle["pages"]:
                page_path = page["path"]

                if page_path == "Home.md":
                    target = wiki_dir / "Home.md"
                elif page_path == "grafo-dependencias.md":
                    target = wiki_dir / "06-grafo" / "dependencias.md"
                else:
                    # Buscar el prefijo más largo que matchee
                    target = None
                    for prefix, folder in sorted(folder_map.items(), key=lambda x: -len(x[0])):
                        if page_path.startswith(prefix):
                            filename = page_path[len(prefix):]
                            target = wiki_dir / folder / filename
                            break

                    if target is None:
                        # Fallback: escribir en la raíz
                        target = wiki_dir / page_path

                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(page["content"], encoding="utf-8")
                files_written.append(str(target.relative_to(wiki_dir)))

            # ─── Generar _Sidebar.md completo ────────────────────────────────
            sidebar = self._generate_sidebar(bundle["pages"])
            sidebar_path = wiki_dir / "_Sidebar.md"
            sidebar_path.write_text(sidebar, encoding="utf-8")
            files_written.append("_Sidebar.md")

        except (PermissionError, OSError) as e:
            write_failed = True
            logger.warning("No se pudo escribir en %s: %s.", wiki_path, e)

        if write_failed:
            return {
                "status": "partial",
                "message": (
                    f"No se pudo escribir en {wiki_path} (posiblemente Docker sin volumen montado). "
                    "El contenido de cada página se incluye en 'pages' para que el agente "
                    "lo escriba con sus propias herramientas de filesystem."
                ),
                "pages": bundle["pages"],
                "page_count": bundle["page_count"],
            }

        return {
            "status": "success",
            "wiki_path": wiki_path,
            "files_written": files_written,
            "total_files": len(files_written),
            "summary": bundle["summary"],
            "message": (
                f"{len(files_written)} archivos escritos en {wiki_path}.\n"
                "Para publicar en la wiki de GitHub:\n"
                f"  cd {wiki_path}\n"
                "  git add -A\n"
                '  git commit -m "Sync memoria desde MCP"\n'
                "  git push"
            ),
        }

    def _generate_sidebar(self, pages: list[dict]) -> str:
        """Genera _Sidebar.md con navegación organizada por sección."""
        lines = ["# Navegación", "", "[Home](Home)", ""]

        # Agrupar páginas por sección
        sections = {
            "historias/": ("Historias de Usuario", "01-historias"),
            "entidades/": ("Entidades", "02-entidades"),
            "flujos/": ("Flujos de Negocio", "03-flujos"),
            "decisiones/": ("Decisiones", "04-decisiones"),
            "specs/": ("Specs SDD", "05-specs"),
            "ecosistema/": ("Ecosistema", "07-ecosistema"),
        }

        for prefix, (label, folder) in sections.items():
            section_pages = [p for p in pages if p["path"].startswith(prefix)]
            if not section_pages:
                continue

            lines.append(f"**{label}**")
            lines.append("")
            for p in section_pages:
                filename = Path(p["path"]).stem
                # Para contratos, usar subcarpeta
                if "contratos/" in p["path"]:
                    lines.append(f"- [{p['title']}]({folder}/contratos/{filename})")
                else:
                    lines.append(f"- [{p['title']}]({folder}/{filename})")
            lines.append("")

        # Grafo
        graph_pages = [p for p in pages if p["path"] == "grafo-dependencias.md"]
        if graph_pages:
            lines.extend(["**Grafo**", "", "- [Dependencias entre HUs](06-grafo/dependencias)", ""])

        return "\n".join(lines)

    # ─── IMPORT FROM WIKI REPO ───────────────────────────────────────────────────

    def import_from_wiki_repo(self, wiki_path: str) -> dict:
        """Importa contenido desde un repo de wiki clonado hacia la memoria del MCP.

        Escanea la ruta buscando archivos .md en las estructuras conocidas
        (soporta tanto la estructura numerada como nombres planos):
        - 01-historias/ | historias/ | memoria/historias/
        - 02-entidades/ | entidades/ | entities/ | memoria/entidades/
        - 03-flujos/ | flujos/ | flows/ | memoria/flujos/
        - 04-decisiones/ | decisiones/ | decisions/ | memoria/decisiones/
        - 05-specs/ | specs/ | memoria/specs/
        - 06-grafo/ | grafo-dependencias.md
        - 07-ecosistema/ | ecosistema/ | memoria/ecosistema/

        Hace merge inteligente: solo agrega lo nuevo, actualiza lo que cambió,
        y reporta un resumen detallado.

        Args:
            wiki_path: Ruta local al repo de la wiki clonado.

        Returns:
            Dict con status, resumen de cambios (added, updated, unchanged).
        """
        from src.models.project import Decision, EntityInfo, FlowInfo

        wiki_dir = Path(wiki_path)

        if not wiki_dir.exists():
            return {"status": "error", "message": f"Ruta no encontrada: {wiki_path}"}
        if not wiki_dir.is_dir():
            return {"status": "error", "message": f"La ruta no es un directorio: {wiki_path}"}
        if not self._memory.is_initialized:
            return {"status": "error", "message": "No hay memoria local inicializada. Usar init_project primero."}

        index = self._memory.index
        if index is None:
            return {"status": "error", "message": "Indice de memoria vacio."}

        # ─── Detectar estructura de la wiki (soporta variantes) ──────────────
        story_dirs = self._find_wiki_dirs(wiki_dir, [
            "01-historias", "historias", "memoria/historias", "stories",
        ])
        entity_dirs = self._find_wiki_dirs(wiki_dir, [
            "02-entidades", "entidades", "entities",
            "memoria/entidades", "memoria/entities", "shared/entities",
        ])
        flow_dirs = self._find_wiki_dirs(wiki_dir, [
            "03-flujos", "flujos", "flows",
            "memoria/flujos", "memoria/flows", "shared/flows",
        ])
        decision_dirs = self._find_wiki_dirs(wiki_dir, [
            "04-decisiones", "decisiones", "decisions",
            "memoria/decisiones", "memoria/decisions", "shared/decisions",
        ])
        spec_dirs = self._find_wiki_dirs(wiki_dir, [
            "05-specs", "specs", "memoria/specs",
        ])
        graph_dirs = self._find_wiki_dirs(wiki_dir, [
            "06-grafo", "grafo",
        ])
        eco_dirs = self._find_wiki_dirs(wiki_dir, [
            "07-ecosistema", "ecosistema", "memoria/ecosistema",
        ])

        changes = {
            "stories": {"added": [], "updated": [], "unchanged": []},
            "entities": {"added": [], "updated": [], "unchanged": []},
            "flows": {"added": [], "updated": [], "unchanged": []},
            "decisions": {"added": [], "updated": [], "unchanged": []},
            "specs": {"added": [], "updated": [], "unchanged": []},
            "graph_edges": {"added": 0, "existing": 0},
            "ecosystem": {"imported": False},
        }

        # ─── 1. Importar HUs ────────────────────────────────────────────────
        for sdir in story_dirs:
            for md_file in sorted(sdir.glob("*.md")):
                story_data = self._parse_story_md(md_file)
                if not story_data:
                    continue

                story_id = story_data["id"]
                existing = self._memory.get_story(story_id)

                if existing is None:
                    from src.models.story import StoryAnalysis, Narrative, AcceptanceCriterion
                    story = StoryAnalysis(
                        id=story_id,
                        title=story_data.get("title", ""),
                        narrative=Narrative(**story_data.get("narrative", {"as_a": "", "i_want": "", "so_that": ""})),
                        acceptance_criteria=[
                            AcceptanceCriterion(**ac) for ac in story_data.get("acceptance_criteria", [])
                        ],
                        entities_detected=story_data.get("entities", []),
                        flows_detected=story_data.get("flows", []),
                        complexity_tags=story_data.get("complexity_tags", []),
                        dependencies=story_data.get("dependencies", []),
                        impacts=story_data.get("impacts", []),
                        status=story_data.get("status", "analyzed"),
                        total_gaps=story_data.get("total_gaps", 0),
                        total_questions=story_data.get("total_questions", 0),
                    )
                    self._memory.save_story(story)
                    changes["stories"]["added"].append(story_id)
                else:
                    # Merge: actualizar campos si wiki tiene datos nuevos
                    updated = False
                    for dep in story_data.get("dependencies", []):
                        if dep not in existing.dependencies:
                            existing.dependencies.append(dep)
                            updated = True
                    for imp in story_data.get("impacts", []):
                        if imp not in existing.impacts:
                            existing.impacts.append(imp)
                            updated = True
                    for tag in story_data.get("complexity_tags", []):
                        if tag not in existing.complexity_tags:
                            existing.complexity_tags.append(tag)
                            updated = True

                    if updated:
                        self._memory.save_story(existing)
                        changes["stories"]["updated"].append(story_id)
                    else:
                        changes["stories"]["unchanged"].append(story_id)

        # ─── 2. Importar entidades ───────────────────────────────────────────
        for edir in entity_dirs:
            for md_file in sorted(edir.glob("*.md")):
                entity_data = self._parse_entity_md(md_file)
                if not entity_data:
                    continue

                existing = next((e for e in index.entities if e.name == entity_data["name"]), None)

                if existing is None:
                    index.entities.append(EntityInfo(
                        name=entity_data["name"],
                        first_seen_in=entity_data.get("first_seen_in", "wiki-import"),
                        appears_in=entity_data.get("appears_in", []),
                        fields=entity_data.get("fields", []),
                        relations=entity_data.get("relations", []),
                    ))
                    changes["entities"]["added"].append(entity_data["name"])
                else:
                    updated = False
                    for hu_id in entity_data.get("appears_in", []):
                        if hu_id not in existing.appears_in:
                            existing.appears_in.append(hu_id)
                            updated = True
                    for field in entity_data.get("fields", []):
                        if field not in existing.fields:
                            existing.fields.append(field)
                            updated = True
                    for rel in entity_data.get("relations", []):
                        if rel not in existing.relations:
                            existing.relations.append(rel)
                            updated = True

                    if updated:
                        changes["entities"]["updated"].append(entity_data["name"])
                    else:
                        changes["entities"]["unchanged"].append(entity_data["name"])

        # ─── 3. Importar flujos ──────────────────────────────────────────────
        for fdir in flow_dirs:
            for md_file in sorted(fdir.glob("*.md")):
                flow_data = self._parse_flow_md(md_file)
                if not flow_data:
                    continue

                existing = next((f for f in index.flows if f.name == flow_data["name"]), None)

                if existing is None:
                    index.flows.append(FlowInfo(
                        name=flow_data["name"],
                        description=flow_data.get("description", ""),
                        stories_involved=flow_data.get("stories_involved", []),
                        status=flow_data.get("status", "incomplete"),
                        steps=flow_data.get("steps", []),
                    ))
                    changes["flows"]["added"].append(flow_data["name"])
                else:
                    updated = False
                    for hu_id in flow_data.get("stories_involved", []):
                        if hu_id not in existing.stories_involved:
                            existing.stories_involved.append(hu_id)
                            updated = True
                    for step in flow_data.get("steps", []):
                        if step not in existing.steps:
                            existing.steps.append(step)
                            updated = True
                    if flow_data.get("description") and not existing.description:
                        existing.description = flow_data["description"]
                        updated = True
                    if flow_data.get("status") != existing.status and flow_data.get("status") == "complete":
                        existing.status = "complete"
                        updated = True

                    if updated:
                        changes["flows"]["updated"].append(flow_data["name"])
                    else:
                        changes["flows"]["unchanged"].append(flow_data["name"])

        # ─── 4. Importar decisiones ──────────────────────────────────────────
        for ddir in decision_dirs:
            for md_file in sorted(ddir.glob("*.md")):
                dec_data = self._parse_decision_md(md_file)
                if not dec_data:
                    continue

                existing = next((d for d in index.decisions if d.id == dec_data["id"]), None)

                if existing is None:
                    index.decisions.append(Decision(
                        id=dec_data["id"],
                        description=dec_data.get("description", ""),
                        reason=dec_data.get("reason", ""),
                        decided_in=dec_data.get("decided_in", "wiki-import"),
                        date=dec_data.get("date", datetime.now().isoformat()),
                    ))
                    changes["decisions"]["added"].append(dec_data["id"])
                else:
                    updated = False
                    if dec_data.get("description") and dec_data["description"] != existing.description:
                        existing.description = dec_data["description"]
                        updated = True
                    if dec_data.get("reason") and dec_data["reason"] != existing.reason:
                        existing.reason = dec_data["reason"]
                        updated = True

                    if updated:
                        changes["decisions"]["updated"].append(dec_data["id"])
                    else:
                        changes["decisions"]["unchanged"].append(dec_data["id"])

        # ─── 5. Importar grafo de dependencias ───────────────────────────────
        graph = self._memory.graph
        # Buscar grafo-dependencias.md en raíz o en 06-grafo/
        graph_files = []
        root_graph = wiki_dir / "grafo-dependencias.md"
        if root_graph.exists():
            graph_files.append(root_graph)
        for gdir in graph_dirs:
            for f in gdir.glob("*.md"):
                graph_files.append(f)

        for gf in graph_files:
            edges = self._parse_graph_md(gf)
            for src, tgt, rel in edges:
                if not graph.has_edge(src, tgt):
                    graph.add_node(src)
                    graph.add_node(tgt)
                    graph.add_edge(src, tgt, relation=rel, weight=1.0 if rel == "depends_on" else 0.8)
                    changes["graph_edges"]["added"] += 1
                else:
                    changes["graph_edges"]["existing"] += 1
        if graph_files:
            self._memory._save_graph()

        # ─── 6. Importar specs SDD (read-only summary) ──────────────────────
        # Las specs se importan como referencia — no se reconstruye el modelo
        # completo porque los details/constraints requieren el SpecEngine
        for sdir in spec_dirs:
            for md_file in sorted(sdir.glob("*.md")):
                spec_data = self._parse_spec_summary_md(md_file)
                if spec_data:
                    changes["specs"]["added"].append(spec_data.get("spec_id", md_file.stem))

        # ─── 7. Importar ecosistema (read-only) ─────────────────────────────
        for edir in eco_dirs:
            eco_main = edir / "ecosistema.md"
            if eco_main.exists():
                changes["ecosystem"]["imported"] = True
                # Los contratos se listan como referencia
                contracts_dir = edir / "contratos"
                if contracts_dir.exists():
                    for cf in contracts_dir.glob("*.md"):
                        changes["specs"]["added"].append(f"contrato:{cf.stem}")

        # ─── Persistir ───────────────────────────────────────────────────────
        self._memory._save_index()

        # ─── Generar resumen ─────────────────────────────────────────────────
        categories = [
            ("stories", "Historias de Usuario"),
            ("entities", "Entidades"),
            ("flows", "Flujos"),
            ("decisions", "Decisiones"),
        ]

        total_added = sum(len(changes[c]["added"]) for c, _ in categories)
        total_updated = sum(len(changes[c]["updated"]) for c, _ in categories)
        total_unchanged = sum(len(changes[c]["unchanged"]) for c, _ in categories)
        total_added += changes["graph_edges"]["added"]

        summary_lines = [f"Importacion desde wiki: {wiki_path}", ""]

        if total_added > 0:
            summary_lines.append(f"### Agregados ({total_added})")
            for cat_key, cat_label in categories:
                if changes[cat_key]["added"]:
                    summary_lines.append(f"  {cat_label}: {', '.join(changes[cat_key]['added'])}")
            if changes["graph_edges"]["added"] > 0:
                summary_lines.append(f"  Aristas del grafo: {changes['graph_edges']['added']} nuevas")
            summary_lines.append("")

        if total_updated > 0:
            summary_lines.append(f"### Actualizados ({total_updated})")
            for cat_key, cat_label in categories:
                if changes[cat_key]["updated"]:
                    summary_lines.append(f"  {cat_label}: {', '.join(changes[cat_key]['updated'])}")
            summary_lines.append("")

        if total_unchanged > 0:
            summary_lines.append(f"### Sin cambios ({total_unchanged})")
            for cat_key, cat_label in categories:
                if changes[cat_key]["unchanged"]:
                    summary_lines.append(f"  {cat_label}: {', '.join(changes[cat_key]['unchanged'])}")

        if changes["specs"]["added"]:
            summary_lines.append("")
            summary_lines.append(f"### Specs/Contratos referenciados ({len(changes['specs']['added'])})")
            for s in changes["specs"]["added"]:
                summary_lines.append(f"  - {s}")

        if changes["ecosystem"]["imported"]:
            summary_lines.append("")
            summary_lines.append("### Ecosistema: importado como referencia")

        if total_added == 0 and total_updated == 0:
            summary_lines.append("La memoria ya estaba al dia. Sin cambios.")

        return {
            "status": "success",
            "wiki_path": wiki_path,
            "changes": changes,
            "totals": {
                "added": total_added,
                "updated": total_updated,
                "unchanged": total_unchanged,
                "scanned": total_added + total_updated + total_unchanged,
            },
            "summary": "\n".join(summary_lines),
            "message": (
                f"Wiki importada: {total_added} nuevos, {total_updated} actualizados, "
                f"{total_unchanged} sin cambios."
            ),
        }

    @staticmethod
    def _find_wiki_dirs(base: Path, candidates: list[str]) -> list[Path]:
        """Busca carpetas existentes entre las candidatas."""
        found = []
        for candidate in candidates:
            d = base / candidate
            if d.exists() and d.is_dir():
                found.append(d)
        return found

    # ─── MARKDOWN WRITERS ────────────────────────────────────────────────────────

    def _write_entity_md(self, entity) -> Path:
        """Escribe una entidad como Markdown."""
        slug = self._slugify(entity.name)
        path = self._shared_path / "entities" / f"{slug}.md"

        lines = [
            f"# {entity.name}",
            "",
            f"**Primera aparición:** {entity.first_seen_in}",
            "",
        ]

        if entity.appears_in:
            lines.append("## Aparece en")
            lines.append("")
            for hu_id in entity.appears_in:
                lines.append(f"- {hu_id}")
            lines.append("")

        if entity.fields:
            lines.append("## Campos")
            lines.append("")
            for field in entity.fields:
                lines.append(f"- `{field}`")
            lines.append("")

        if entity.relations:
            lines.append("## Relaciones")
            lines.append("")
            for rel in entity.relations:
                lines.append(f"- {rel}")
            lines.append("")

        lines.append(f"---\n_Última exportación: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n")

        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def _write_flow_md(self, flow) -> Path:
        """Escribe un flujo como Markdown."""
        slug = self._slugify(flow.name)
        path = self._shared_path / "flows" / f"{slug}.md"

        lines = [
            f"# {flow.name}",
            "",
            f"**Estado:** {flow.status}",
            "",
        ]

        if flow.description:
            lines.append(f"{flow.description}")
            lines.append("")

        if flow.stories_involved:
            lines.append("## HUs involucradas")
            lines.append("")
            for hu_id in flow.stories_involved:
                lines.append(f"- {hu_id}")
            lines.append("")

        if flow.steps:
            lines.append("## Pasos")
            lines.append("")
            for i, step in enumerate(flow.steps, 1):
                lines.append(f"{i}. {step}")
            lines.append("")

        lines.append(f"---\n_Última exportación: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n")

        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def _write_decision_md(self, decision) -> Path:
        """Escribe una decisión como Markdown."""
        slug = self._slugify(decision.id)
        path = self._shared_path / "decisions" / f"{slug}.md"

        lines = [
            f"# {decision.id}",
            "",
            f"**Descripción:** {decision.description}",
            "",
            f"**Razón:** {decision.reason}",
            "",
            f"**Decidido en:** {decision.decided_in}",
            "",
            f"**Fecha:** {decision.date}",
            "",
            f"---\n_Última exportación: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n",
        ]

        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def _write_readme(self) -> None:
        """Genera README.md con índice de todo el contenido shared."""
        index = self._memory.index
        lines = [
            "# Memoria Compartida del Proyecto",
            "",
        ]

        if index:
            lines.append(f"**Proyecto:** {index.config.project_name}")
            lines.append(f"**Dominio:** {index.config.domain}")
            lines.append("")

        lines.extend([
            "## Estructura",
            "",
            "```",
            "shared/",
            "├── entities/    # Entidades del dominio (1 archivo por entidad)",
            "├── flows/       # Flujos de negocio (1 archivo por flujo)",
            "├── decisions/   # Decisiones arquitectónicas",
            "└── README.md    # Este archivo (índice auto-generado)",
            "```",
            "",
            "> **Nota:** Este directorio es generado por el MCP de Historias de Usuario.",
            "> No editar manualmente. Usar el tool `sync_shared_memory` para actualizar.",
            "",
        ])

        # Índice de entidades
        entities_dir = self._shared_path / "entities"
        if entities_dir.exists():
            entity_files = sorted(entities_dir.glob("*.md"))
            if entity_files:
                lines.append("## Entidades")
                lines.append("")
                for f in entity_files:
                    name = f.stem.replace("-", " ").title()
                    lines.append(f"- [{name}](entities/{f.name})")
                lines.append("")

        # Índice de flujos
        flows_dir = self._shared_path / "flows"
        if flows_dir.exists():
            flow_files = sorted(flows_dir.glob("*.md"))
            if flow_files:
                lines.append("## Flujos")
                lines.append("")
                for f in flow_files:
                    name = f.stem.replace("-", " ").replace("_", " ").title()
                    lines.append(f"- [{name}](flows/{f.name})")
                lines.append("")

        # Índice de decisiones
        decisions_dir = self._shared_path / "decisions"
        if decisions_dir.exists():
            dec_files = sorted(decisions_dir.glob("*.md"))
            if dec_files:
                lines.append("## Decisiones")
                lines.append("")
                for f in dec_files:
                    lines.append(f"- [{f.stem.upper()}](decisions/{f.name})")
                lines.append("")

        lines.append(f"---\n_Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n")

        readme_path = self._shared_path / "README.md"
        readme_path.write_text("\n".join(lines), encoding="utf-8")

    # ─── MARKDOWN PARSERS ────────────────────────────────────────────────────────

    def _parse_entity_md(self, path: Path) -> Optional[dict]:
        """Parsea un archivo Markdown de entidad."""
        try:
            content = path.read_text(encoding="utf-8")
            data = {"name": "", "first_seen_in": "imported", "appears_in": [], "fields": [], "relations": []}

            lines = content.split("\n")
            current_section = None

            for line in lines:
                line_stripped = line.strip()

                if line_stripped.startswith("# ") and not data["name"]:
                    data["name"] = line_stripped[2:].strip()
                elif line_stripped.startswith("**Primera aparición:**"):
                    data["first_seen_in"] = line_stripped.split(":**")[1].strip()
                elif line_stripped == "## Aparece en":
                    current_section = "appears_in"
                elif line_stripped == "## Campos":
                    current_section = "fields"
                elif line_stripped == "## Relaciones":
                    current_section = "relations"
                elif line_stripped.startswith("## "):
                    current_section = None
                elif line_stripped.startswith("- ") and current_section:
                    value = line_stripped[2:].strip().strip("`")
                    data[current_section].append(value)

            return data if data["name"] else None
        except Exception as e:
            logger.warning("Error parseando entidad %s: %s", path, e)
            return None

    def _parse_flow_md(self, path: Path) -> Optional[dict]:
        """Parsea un archivo Markdown de flujo."""
        try:
            content = path.read_text(encoding="utf-8")
            data = {"name": "", "description": "", "stories_involved": [], "status": "incomplete", "steps": []}

            lines = content.split("\n")
            current_section = None

            for line in lines:
                line_stripped = line.strip()

                if line_stripped.startswith("# ") and not data["name"]:
                    data["name"] = line_stripped[2:].strip()
                elif line_stripped.startswith("**Estado:**"):
                    data["status"] = line_stripped.split(":**")[1].strip()
                elif line_stripped == "## HUs involucradas":
                    current_section = "stories"
                elif line_stripped == "## Pasos":
                    current_section = "steps"
                elif line_stripped.startswith("## "):
                    current_section = None
                elif line_stripped.startswith("- ") and current_section == "stories":
                    data["stories_involved"].append(line_stripped[2:].strip())
                elif current_section == "steps" and line_stripped and line_stripped[0].isdigit():
                    # "1. paso" → "paso"
                    parts = line_stripped.split(". ", 1)
                    if len(parts) == 2:
                        data["steps"].append(parts[1])

            return data if data["name"] else None
        except Exception as e:
            logger.warning("Error parseando flujo %s: %s", path, e)
            return None

    def _parse_decision_md(self, path: Path) -> Optional[dict]:
        """Parsea un archivo Markdown de decisión."""
        try:
            content = path.read_text(encoding="utf-8")
            data = {"id": "", "description": "", "reason": "", "decided_in": "imported", "date": ""}

            for line in content.split("\n"):
                line_stripped = line.strip()

                if line_stripped.startswith("# ") and not data["id"]:
                    data["id"] = line_stripped[2:].strip()
                elif line_stripped.startswith("**Descripción:**"):
                    data["description"] = line_stripped.split(":**", 1)[1].strip()
                elif line_stripped.startswith("**Razón:**"):
                    data["reason"] = line_stripped.split(":**", 1)[1].strip()
                elif line_stripped.startswith("**Decidido en:**"):
                    data["decided_in"] = line_stripped.split(":**", 1)[1].strip()
                elif line_stripped.startswith("**Fecha:**"):
                    data["date"] = line_stripped.split(":**", 1)[1].strip()

            return data if data["id"] else None
        except Exception as e:
            logger.warning("Error parseando decisión %s: %s", path, e)
            return None

    def _parse_story_md(self, path: Path) -> Optional[dict]:
        """Parsea un archivo Markdown de HU (formato generado por generate_wiki_bundle).

        Ejemplo de formato:
            # HU-001: Titulo
            ## Narrativa
            **Como** actor
            **Quiero** accion
            **Para que** beneficio
            ## Criterios de Aceptación
            ### CA-1
            - **Dado** ...
            - **Cuando** ...
            - **Entonces** ...
            ## Entidades
            - NombreEntidad
            ## Flujos
            - NombreFlujo
            **Complejidad:** tag1, tag2
            ## Depende de
            - HU-002
            ## Impacta a
            - HU-003
            **Estado:** analyzed
            **Gaps:** 0 | **Preguntas:** 0
        """
        import re

        try:
            content = path.read_text(encoding="utf-8")
            data: dict = {
                "id": "", "title": "", "narrative": {}, "acceptance_criteria": [],
                "entities": [], "flows": [], "complexity_tags": [],
                "dependencies": [], "impacts": [], "status": "analyzed",
                "total_gaps": 0, "total_questions": 0,
            }

            lines = content.split("\n")
            current_section = None
            current_ac: Optional[dict] = None

            for line in lines:
                ls = line.strip()

                # Titulo: # HU-001: Mi titulo
                if ls.startswith("# ") and not data["id"]:
                    header = ls[2:].strip()
                    if ":" in header:
                        data["id"] = header.split(":")[0].strip()
                        data["title"] = header.split(":", 1)[1].strip()
                    else:
                        data["id"] = header
                        data["title"] = header

                # Secciones
                elif ls == "## Narrativa":
                    current_section = "narrative"
                elif ls == "## Criterios de Aceptación":
                    current_section = "criteria"
                elif ls == "## Entidades":
                    current_section = "entities"
                elif ls == "## Flujos":
                    current_section = "flows"
                elif ls == "## Depende de":
                    current_section = "deps"
                elif ls == "## Impacta a":
                    current_section = "impacts"
                elif ls.startswith("## "):
                    current_section = None

                # Narrativa
                elif current_section == "narrative":
                    if ls.startswith("**Como**"):
                        data["narrative"]["as_a"] = ls.replace("**Como**", "").strip()
                    elif ls.startswith("**Quiero**"):
                        data["narrative"]["i_want"] = ls.replace("**Quiero**", "").strip()
                    elif ls.startswith("**Para que**"):
                        data["narrative"]["so_that"] = ls.replace("**Para que**", "").strip()

                # Criterios de aceptación
                elif current_section == "criteria":
                    if ls.startswith("### CA-"):
                        if current_ac and current_ac.get("given"):
                            data["acceptance_criteria"].append(current_ac)
                        current_ac = {"given": "", "when": "", "then": ""}
                    elif current_ac is not None:
                        if ls.startswith("- **Dado**"):
                            current_ac["given"] = ls.replace("- **Dado**", "").strip()
                        elif ls.startswith("- **Cuando**"):
                            current_ac["when"] = ls.replace("- **Cuando**", "").strip()
                        elif ls.startswith("- **Entonces**"):
                            current_ac["then"] = ls.replace("- **Entonces**", "").strip()

                # Listas simples
                elif current_section == "entities" and ls.startswith("- "):
                    data["entities"].append(ls[2:].strip())
                elif current_section == "flows" and ls.startswith("- "):
                    data["flows"].append(ls[2:].strip())
                elif current_section == "deps" and ls.startswith("- "):
                    data["dependencies"].append(ls[2:].strip())
                elif current_section == "impacts" and ls.startswith("- "):
                    data["impacts"].append(ls[2:].strip())

                # Campos inline
                elif ls.startswith("**Complejidad:**"):
                    tags = ls.replace("**Complejidad:**", "").strip()
                    data["complexity_tags"] = [t.strip() for t in tags.split(",") if t.strip()]
                elif ls.startswith("**Estado:**"):
                    data["status"] = ls.replace("**Estado:**", "").strip()
                elif ls.startswith("**Gaps:**"):
                    m = re.search(r"\*\*Gaps:\*\*\s*(\d+)", ls)
                    if m:
                        data["total_gaps"] = int(m.group(1))
                    m = re.search(r"\*\*Preguntas:\*\*\s*(\d+)", ls)
                    if m:
                        data["total_questions"] = int(m.group(1))

            # Flush último criterio
            if current_ac and current_ac.get("given"):
                data["acceptance_criteria"].append(current_ac)

            # Validar mínimos
            if not data["id"]:
                return None
            if not data["narrative"]:
                data["narrative"] = {"as_a": "", "i_want": "", "so_that": ""}

            return data
        except Exception as e:
            logger.warning("Error parseando HU %s: %s", path, e)
            return None

    def _parse_graph_md(self, path: Path) -> list[tuple[str, str, str]]:
        """Parsea un archivo Markdown del grafo de dependencias.

        Busca la tabla con formato: | HU | Depende de | Relación |

        Returns:
            Lista de tuplas (source, target, relation).
        """
        edges = []
        try:
            content = path.read_text(encoding="utf-8")
            in_table = False
            for line in content.split("\n"):
                ls = line.strip()
                if ls.startswith("| HU "):
                    in_table = True
                    continue
                if in_table and ls.startswith("|---"):
                    continue
                if in_table and ls.startswith("|"):
                    parts = [p.strip() for p in ls.split("|")[1:-1]]
                    if len(parts) >= 3:
                        edges.append((parts[0], parts[1], parts[2]))
                elif in_table and not ls.startswith("|"):
                    in_table = False
        except Exception as e:
            logger.warning("Error parseando grafo %s: %s", path, e)
        return edges

    def _parse_spec_summary_md(self, path: Path) -> Optional[dict]:
        """Parsea un archivo Markdown de spec SDD (solo extrae metadatos).

        No reconstruye el modelo completo de spec — solo el ID y nombre
        como referencia para el resumen de importación.
        """
        try:
            content = path.read_text(encoding="utf-8")
            data: dict = {"spec_id": "", "project_name": ""}

            for line in content.split("\n"):
                ls = line.strip()
                if ls.startswith("# SDD: ") and not data["project_name"]:
                    data["project_name"] = ls[7:].strip()
                elif ls.startswith("**Spec ID:**"):
                    data["spec_id"] = ls.split(":**", 1)[1].strip()

            return data if data["spec_id"] else None
        except Exception as e:
            logger.warning("Error parseando spec %s: %s", path, e)
            return None

    # ─── UTILS ───────────────────────────────────────────────────────────────────

    @staticmethod
    def _slugify(name: str) -> str:
        """Convierte un nombre a slug para nombre de archivo."""
        import re
        slug = name.lower().strip()
        slug = re.sub(r"[^a-z0-9áéíóúñü\s_-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        return slug.strip("-")


# ─── ACCESO ──────────────────────────────────────────────────────────────────────


def get_shared_memory() -> SharedMemoryEngine:
    """Obtiene instancia de SharedMemoryEngine para el workspace activo."""
    memory = get_memory()
    return SharedMemoryEngine(memory)
