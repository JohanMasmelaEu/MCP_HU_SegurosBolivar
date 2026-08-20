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
