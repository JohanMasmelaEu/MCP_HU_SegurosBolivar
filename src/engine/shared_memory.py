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

        No necesita que shared/ exista en disco — lee directamente de la memoria
        local y genera todo el Markdown en memoria.

        Returns:
            Dict con:
                - status: "success" o "error"
                - pages: lista de {title, path, content} — cada página de la wiki
                - full_content: string único con todas las páginas concatenadas,
                  separadas por marcadores claros para que el agente las presente
                  o las copie al portapapeles.
        """
        if not self._memory.is_initialized:
            return {"status": "error", "message": "No hay memoria local inicializada."}

        index = self._memory.index
        if index is None:
            return {"status": "error", "message": "Índice de memoria vacío."}

        pages: list[dict] = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        # ─── Página principal (Home) ─────────────────────────────────────────
        home_lines = [
            "# Memoria Compartida del Proyecto",
            "",
            f"**Proyecto:** {index.config.project_name}",
            f"**Dominio:** {index.config.domain}",
            f"**HUs analizadas:** {index.story_count}",
            "",
        ]

        if index.entities:
            home_lines.append("## Entidades")
            home_lines.append("")
            for e in index.entities:
                hu_count = len(e.appears_in)
                home_lines.append(f"- **{e.name}** — aparece en {hu_count} HU(s)")
            home_lines.append("")

        if index.flows:
            home_lines.append("## Flujos de Negocio")
            home_lines.append("")
            for f in index.flows:
                home_lines.append(f"- **{f.name}** — estado: {f.status}")
            home_lines.append("")

        if index.decisions:
            home_lines.append("## Decisiones")
            home_lines.append("")
            for d in index.decisions:
                home_lines.append(f"- **{d.id}**: {d.description}")
            home_lines.append("")

        home_lines.append(f"---\n_Generado por MCP HU SegurosBolivar — {now}_\n")
        pages.append({
            "title": "Home — Memoria del Proyecto",
            "path": "Home.md",
            "content": "\n".join(home_lines),
        })

        # ─── Páginas de entidades ────────────────────────────────────────────
        for entity in index.entities:
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
            lines.append(f"---\n_Generado: {now}_\n")

            slug = self._slugify(entity.name)
            pages.append({
                "title": f"Entidad: {entity.name}",
                "path": f"entidades/{slug}.md",
                "content": "\n".join(lines),
            })

        # ─── Páginas de flujos ───────────────────────────────────────────────
        for flow in index.flows:
            lines = [
                f"# {flow.name}",
                "",
                f"**Estado:** {flow.status}",
                "",
            ]
            if flow.description:
                lines.append(flow.description)
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
            lines.append(f"---\n_Generado: {now}_\n")

            slug = self._slugify(flow.name)
            pages.append({
                "title": f"Flujo: {flow.name}",
                "path": f"flujos/{slug}.md",
                "content": "\n".join(lines),
            })

        # ─── Páginas de decisiones ───────────────────────────────────────────
        for decision in index.decisions:
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
                f"---\n_Generado: {now}_\n",
            ]

            slug = self._slugify(decision.id)
            pages.append({
                "title": f"Decisión: {decision.id}",
                "path": f"decisiones/{slug}.md",
                "content": "\n".join(lines),
            })

        # ─── Concatenar todo en un solo string ───────────────────────────────
        separator = "\n\n" + "=" * 72 + "\n"
        full_parts = []
        for page in pages:
            header = f"📄 WIKI PAGE: {page['path']}"
            full_parts.append(f"{header}\n{'─' * len(header)}\n\n{page['content']}")

        entity_count = len(index.entities)
        flow_count = len(index.flows)
        decision_count = len(index.decisions)

        return {
            "status": "success",
            "pages": pages,
            "page_count": len(pages),
            "summary": {
                "entities": entity_count,
                "flows": flow_count,
                "decisions": decision_count,
            },
            "full_content": separator.join(full_parts),
            "message": (
                f"Wiki generada: {len(pages)} página(s) "
                f"({entity_count} entidades, {flow_count} flujos, "
                f"{decision_count} decisiones). "
                "Contenido listo para copiar a la wiki de GitHub."
            ),
        }

    # ─── EXPORT TO WIKI REPO ────────────────────────────────────────────────────

    def export_to_wiki_repo(self, wiki_path: str) -> dict:
        """Exporta la memoria del workspace al formato del repo wiki clonado.

        Escribe los archivos Markdown directamente en la estructura de carpetas
        que espera la wiki de GitHub. Si la ruta no es escribible (ej: MCP en Docker
        sin volumen montado), retorna todo el contenido para que el agente lo escriba.

        Estructura que genera:
            wiki_path/
            ├── Home.md                     (o memoria/Home.md si memoria/ ya existe)
            ├── memoria/
            │   ├── entidades/
            │   │   ├── poliza.md
            │   │   └── siniestro.md
            │   ├── flujos/
            │   │   └── registro-poliza.md
            │   └── decisiones/
            │       └── dn-001.md

        Args:
            wiki_path: Ruta local al repo de la wiki clonado.

        Returns:
            Dict con status, archivos escritos, y resumen. Si la escritura falla,
            incluye el contenido de cada página en 'pages' para que el agente escriba.
        """
        # Primero generar el bundle completo
        bundle = self.generate_wiki_bundle()
        if bundle["status"] != "success":
            return bundle

        wiki_dir = Path(wiki_path)

        if not wiki_dir.exists():
            return {
                "status": "error",
                "message": f"Ruta no encontrada: {wiki_path}. Clonar la wiki primero.",
            }

        if not wiki_dir.is_dir():
            return {"status": "error", "message": f"No es un directorio: {wiki_path}"}

        # ─── Detectar si ya existe estructura memoria/ ───────────────────────
        memoria_dir = wiki_dir / "memoria"

        # ─── Intentar escribir ───────────────────────────────────────────────
        files_written = []
        write_failed = False

        try:
            # Crear estructura de carpetas
            memoria_dir.mkdir(parents=True, exist_ok=True)
            (memoria_dir / "entidades").mkdir(exist_ok=True)
            (memoria_dir / "flujos").mkdir(exist_ok=True)
            (memoria_dir / "decisiones").mkdir(exist_ok=True)

            # Mapeo de path del bundle → path real en wiki
            path_mapping = {
                "Home.md": memoria_dir / "Home.md",
            }
            # También poner una copia en la raíz si no existe otro Home.md
            root_home = wiki_dir / "Home.md"

            for page in bundle["pages"]:
                page_path = page["path"]

                if page_path == "Home.md":
                    # Escribir en memoria/Home.md
                    target = memoria_dir / "Home.md"
                    target.write_text(page["content"], encoding="utf-8")
                    files_written.append(str(target.relative_to(wiki_dir)))

                    # Si no existe Home.md en la raíz, crear un índice con link
                    if not root_home.exists():
                        root_content = (
                            "# Wiki del Proyecto\n\n"
                            "- [Memoria del Proyecto](memoria/Home)\n"
                        )
                        root_home.write_text(root_content, encoding="utf-8")
                        files_written.append("Home.md")

                elif page_path.startswith("entidades/"):
                    target = memoria_dir / "entidades" / Path(page_path).name
                    target.write_text(page["content"], encoding="utf-8")
                    files_written.append(str(target.relative_to(wiki_dir)))

                elif page_path.startswith("flujos/"):
                    target = memoria_dir / "flujos" / Path(page_path).name
                    target.write_text(page["content"], encoding="utf-8")
                    files_written.append(str(target.relative_to(wiki_dir)))

                elif page_path.startswith("decisiones/"):
                    target = memoria_dir / "decisiones" / Path(page_path).name
                    target.write_text(page["content"], encoding="utf-8")
                    files_written.append(str(target.relative_to(wiki_dir)))

            # ─── Generar _Sidebar.md para navegación ─────────────────────────
            sidebar_lines = ["## Navegación", "", "- [Home](Home)", "- [Memoria](memoria/Home)", ""]
            index = self._memory.index

            if index and index.entities:
                sidebar_lines.append("### Entidades")
                for e in index.entities:
                    slug = self._slugify(e.name)
                    sidebar_lines.append(f"  - [{e.name}](memoria/entidades/{slug})")
                sidebar_lines.append("")

            if index and index.flows:
                sidebar_lines.append("### Flujos")
                for f in index.flows:
                    slug = self._slugify(f.name)
                    sidebar_lines.append(f"  - [{f.name}](memoria/flujos/{slug})")
                sidebar_lines.append("")

            if index and index.decisions:
                sidebar_lines.append("### Decisiones")
                for d in index.decisions:
                    slug = self._slugify(d.id)
                    sidebar_lines.append(f"  - [{d.id}](memoria/decisiones/{slug})")

            sidebar_path = wiki_dir / "_Sidebar.md"
            sidebar_path.write_text("\n".join(sidebar_lines), encoding="utf-8")
            files_written.append("_Sidebar.md")

        except (PermissionError, OSError) as e:
            write_failed = True
            logger.warning("No se pudo escribir en %s: %s. Retornando contenido.", wiki_path, e)

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
                f"{len(files_written)} archivos escritos en {wiki_path}. "
                "Hacer commit y push para actualizar la wiki de GitHub:\n"
                f"  cd {wiki_path}\n"
                "  git add -A\n"
                '  git commit -m "Sync memoria desde MCP"\n'
                "  git push"
            ),
        }

    # ─── IMPORT FROM WIKI REPO ───────────────────────────────────────────────────

    def import_from_wiki_repo(self, wiki_path: str) -> dict:
        """Importa contenido desde un repo de wiki clonado localmente hacia la memoria del MCP.

        Escanea la ruta buscando archivos .md en las estructuras conocidas:
        - memoria/entidades/*.md  (o entities/*.md)
        - memoria/flujos/*.md     (o flows/*.md)
        - memoria/decisiones/*.md (o decisions/*.md)
        - Cualquier .md suelto en la raíz o subcarpetas

        Hace merge inteligente: solo agrega lo nuevo, actualiza lo que cambió,
        y reporta un resumen detallado.

        Args:
            wiki_path: Ruta local al repo de la wiki clonado (ej: C:/repos/MiRepo.wiki)

        Returns:
            Dict con status, resumen de cambios (added, updated, unchanged), y detalle.
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
            return {"status": "error", "message": "Índice de memoria vacío."}

        # ─── Detectar estructura de la wiki ──────────────────────────────────
        # Buscar carpetas de entidades, flujos y decisiones en variantes conocidas
        entity_dirs = self._find_wiki_dirs(wiki_dir, ["memoria/entidades", "memoria/entities",
                                                       "entidades", "entities",
                                                       "shared/entities"])
        flow_dirs = self._find_wiki_dirs(wiki_dir, ["memoria/flujos", "memoria/flows",
                                                     "flujos", "flows",
                                                     "shared/flows"])
        decision_dirs = self._find_wiki_dirs(wiki_dir, ["memoria/decisiones", "memoria/decisions",
                                                         "decisiones", "decisions",
                                                         "shared/decisions"])

        changes = {
            "entities": {"added": [], "updated": [], "unchanged": []},
            "flows": {"added": [], "updated": [], "unchanged": []},
            "decisions": {"added": [], "updated": [], "unchanged": []},
        }

        # ─── Importar entidades ──────────────────────────────────────────────
        for edir in entity_dirs:
            for md_file in sorted(edir.glob("*.md")):
                entity_data = self._parse_entity_md(md_file)
                if not entity_data:
                    continue

                existing = next((e for e in index.entities if e.name == entity_data["name"]), None)

                if existing is None:
                    # Nueva entidad
                    index.entities.append(EntityInfo(
                        name=entity_data["name"],
                        first_seen_in=entity_data.get("first_seen_in", "wiki-import"),
                        appears_in=entity_data.get("appears_in", []),
                        fields=entity_data.get("fields", []),
                        relations=entity_data.get("relations", []),
                    ))
                    changes["entities"]["added"].append(entity_data["name"])
                else:
                    # Verificar si hay cambios
                    updated = False
                    # Merge appears_in
                    for hu_id in entity_data.get("appears_in", []):
                        if hu_id not in existing.appears_in:
                            existing.appears_in.append(hu_id)
                            updated = True
                    # Merge fields
                    for field in entity_data.get("fields", []):
                        if field not in existing.fields:
                            existing.fields.append(field)
                            updated = True
                    # Merge relations
                    for rel in entity_data.get("relations", []):
                        if rel not in existing.relations:
                            existing.relations.append(rel)
                            updated = True

                    if updated:
                        changes["entities"]["updated"].append(entity_data["name"])
                    else:
                        changes["entities"]["unchanged"].append(entity_data["name"])

        # ─── Importar flujos ─────────────────────────────────────────────────
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

        # ─── Importar decisiones ─────────────────────────────────────────────
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

        # ─── Persistir ───────────────────────────────────────────────────────
        self._memory._save_index()

        # ─── Generar resumen ─────────────────────────────────────────────────
        total_added = (len(changes["entities"]["added"])
                       + len(changes["flows"]["added"])
                       + len(changes["decisions"]["added"]))
        total_updated = (len(changes["entities"]["updated"])
                         + len(changes["flows"]["updated"])
                         + len(changes["decisions"]["updated"]))
        total_unchanged = (len(changes["entities"]["unchanged"])
                           + len(changes["flows"]["unchanged"])
                           + len(changes["decisions"]["unchanged"]))

        # Resumen legible
        summary_lines = [f"Importación desde wiki: {wiki_path}", ""]

        if total_added > 0:
            summary_lines.append(f"### Agregados ({total_added})")
            for category, label in [("entities", "Entidades"), ("flows", "Flujos"), ("decisions", "Decisiones")]:
                if changes[category]["added"]:
                    summary_lines.append(f"  {label}: {', '.join(changes[category]['added'])}")
            summary_lines.append("")

        if total_updated > 0:
            summary_lines.append(f"### Actualizados ({total_updated})")
            for category, label in [("entities", "Entidades"), ("flows", "Flujos"), ("decisions", "Decisiones")]:
                if changes[category]["updated"]:
                    summary_lines.append(f"  {label}: {', '.join(changes[category]['updated'])}")
            summary_lines.append("")

        if total_unchanged > 0:
            summary_lines.append(f"### Sin cambios ({total_unchanged})")
            for category, label in [("entities", "Entidades"), ("flows", "Flujos"), ("decisions", "Decisiones")]:
                if changes[category]["unchanged"]:
                    summary_lines.append(f"  {label}: {', '.join(changes[category]['unchanged'])}")

        if total_added == 0 and total_updated == 0:
            summary_lines.append("La memoria ya estaba al día. Sin cambios.")

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
