"""Memory Engine: lectura/escritura de .hu-memory/, operaciones de grafo, export/import.

Toda la persistencia es JSON local en el workspace del usuario.
El grafo se mantiene en memoria (NetworkX) y se sincroniza con graph.json.
Soporta multiples workspaces via path configurable.
"""

import json
import logging
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import networkx as nx

from src.models.estimation import CompletionRecord, EstimationPatterns
from src.models.project import (
    Decision,
    EntityInfo,
    FlowInfo,
    GraphEdge,
    ProjectConfig,
    ProjectMemory,
)
from src.models.story import StoryAnalysis, StorySummary

logger = logging.getLogger("mcp_hu.engine.memory")

BASE_PATH = Path(os.environ.get("MCP_WORKSPACE_PATH", "/workspace"))
MEMORY_DIR_NAME = ".hu-memory"


class MemoryEngine:
    """Motor de memoria local para el proyecto.

    Lee y escribe archivos JSON en .hu-memory/ del workspace.
    Mantiene un grafo NetworkX en memoria para consultas rapidas de relaciones.
    Acepta un base_path configurable para soportar multiples workspaces.
    """

    def __init__(self, base_path: Optional[Path] = None) -> None:
        """Inicializa el engine detectando si ya existe memoria.

        Args:
            base_path: Ruta base donde se encuentra o creara .hu-memory/.
                       Si es None, usa la ruta legacy BASE_PATH/.hu-memory/.
        """
        if base_path is not None:
            self._memory_path = base_path / MEMORY_DIR_NAME
        else:
            self._memory_path = BASE_PATH / MEMORY_DIR_NAME
        self._graph: nx.DiGraph = nx.DiGraph()
        self._index: Optional[ProjectMemory] = None
        self._patterns: Optional[EstimationPatterns] = None

        if self._memory_path.exists():
            self._load()

    @property
    def is_initialized(self) -> bool:
        """Verifica si el proyecto ya fue inicializado."""
        return self._memory_path.exists() and (self._memory_path / "index.json").exists()

    @property
    def memory_path(self) -> Path:
        """Ruta a .hu-memory/."""
        return self._memory_path

    @property
    def index(self) -> Optional[ProjectMemory]:
        """Indice maestro del proyecto."""
        return self._index

    @property
    def graph(self) -> nx.DiGraph:
        """Grafo de relaciones entre HUs."""
        return self._graph

    # ─── INITIALIZATION ──────────────────────────────────────────────────────────

    def init_project(self, config: ProjectConfig) -> None:
        """Crea la estructura .hu-memory/ con la configuracion inicial.

        Args:
            config: Configuracion del proyecto.
        """
        self._memory_path.mkdir(parents=True, exist_ok=True)
        (self._memory_path / "stories").mkdir(exist_ok=True)
        (self._memory_path / "estimations").mkdir(exist_ok=True)

        self._index = ProjectMemory(config=config)
        self._patterns = EstimationPatterns()
        self._graph = nx.DiGraph()

        self._save_index()
        self._save_graph()
        self._save_patterns()
        self._save_json("estimations/history.json", {"completions": []})

        logger.info("Proyecto '%s' inicializado en %s", config.project_name, self._memory_path)

    # ─── STORY CRUD ──────────────────────────────────────────────────────────────

    def save_story(self, story: StoryAnalysis) -> None:
        """Persiste una HU analizada y actualiza el indice/grafo.

        Args:
            story: HU analizada completa.
        """
        story_path = f"stories/{story.id}.json"
        self._save_json(story_path, story.model_dump(mode="json"))

        # Actualizar entidades
        for entity_name in story.entities_detected:
            self._upsert_entity(entity_name, story.id)

        # Actualizar flujos
        for flow_name in story.flows_detected:
            self._upsert_flow(flow_name, story.id)

        # Actualizar grafo
        self._graph.add_node(story.id, title=story.title, entities=story.entities_detected, flows=story.flows_detected)
        for dep_id in story.dependencies:
            self._graph.add_edge(story.id, dep_id, relation="depends_on", weight=1.0)
        for impact_id in story.impacts:
            self._graph.add_edge(story.id, impact_id, relation="impacts", weight=0.8)

        # Actualizar conteo
        if self._index:
            self._index.story_count = len(list((self._memory_path / "stories").glob("*.json")))

        self._save_index()
        self._save_graph()
        logger.info("HU '%s' persistida", story.id)

    def delete_story(self, story_id: str) -> bool:
        """Elimina permanentemente una HU de la memoria.

        Borra el archivo JSON, remueve el nodo del grafo (con todas sus aristas),
        limpia referencias en entidades y flujos, y actualiza el índice.

        Args:
            story_id: ID de la HU a eliminar (ej: HU-001).

        Returns:
            True si se eliminó correctamente, False si no existía.
        """
        story_path = self._memory_path / "stories" / f"{story_id}.json"
        if not story_path.exists():
            return False

        # Eliminar archivo
        story_path.unlink()
        logger.info("HU '%s' archivo eliminado", story_id)

        # Remover del grafo (nodo + todas las aristas incidentes)
        if self._graph.has_node(story_id):
            self._graph.remove_node(story_id)

        # Limpiar referencias en entidades
        if self._index:
            for entity in self._index.entities:
                if story_id in entity.appears_in:
                    entity.appears_in.remove(story_id)

            # Limpiar referencias en flujos
            for flow in self._index.flows:
                if story_id in flow.stories_involved:
                    flow.stories_involved.remove(story_id)

            # Actualizar conteo
            stories_dir = self._memory_path / "stories"
            self._index.story_count = len(list(stories_dir.glob("*.json"))) if stories_dir.exists() else 0

        self._save_index()
        self._save_graph()
        logger.info("HU '%s' eliminada completamente (grafo, entidades, flujos actualizados)", story_id)
        return True

    def get_story(self, story_id: str) -> Optional[StoryAnalysis]:
        """Carga una HU desde disco.

        Args:
            story_id: ID de la HU (ej: HU-001).

        Returns:
            StoryAnalysis o None si no existe.
        """
        story_path = self._memory_path / "stories" / f"{story_id}.json"
        if not story_path.exists():
            return None
        data = json.loads(story_path.read_text(encoding="utf-8"))
        return StoryAnalysis(**data)

    def get_all_stories(self) -> list[StoryAnalysis]:
        """Carga todas las HUs del proyecto.

        Returns:
            Lista de todas las StoryAnalysis.
        """
        stories = []
        stories_dir = self._memory_path / "stories"
        if not stories_dir.exists():
            return stories
        for f in sorted(stories_dir.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            stories.append(StoryAnalysis(**data))
        return stories

    def get_all_summaries(self) -> list[StorySummary]:
        """Obtiene resumen comprimido de todas las HUs (para indexacion).

        Returns:
            Lista de StorySummary (ligero, sin analisis completo).
        """
        summaries = []
        stories_dir = self._memory_path / "stories"
        if not stories_dir.exists():
            return summaries
        for f in sorted(stories_dir.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            summaries.append(StorySummary(
                id=data["id"],
                title=data["title"],
                entities=data.get("entities_detected", []),
                flows=data.get("flows_detected", []),
                complexity_tags=data.get("complexity_tags", []),
                dependencies=data.get("dependencies", []),
                status=data.get("status", "analyzed"),
                keywords=self._extract_keywords(data),
            ))
        return summaries

    def get_next_story_id(self) -> str:
        """Genera el siguiente ID de HU disponible.

        Returns:
            ID en formato HU-XXX.
        """
        stories_dir = self._memory_path / "stories"
        if not stories_dir.exists():
            return "HU-001"
        existing = list(stories_dir.glob("*.json"))
        if not existing:
            return "HU-001"
        # Filtrar solo archivos con formato HU-NNN para calcular el siguiente
        hu_files = [f for f in existing if f.stem.startswith("HU-") and f.stem.split("-")[1].isdigit()]
        if not hu_files:
            return "HU-001"
        max_num = max(int(f.stem.split("-")[1]) for f in hu_files)
        return f"HU-{max_num + 1:03d}"

    # ─── ENTITIES & FLOWS ────────────────────────────────────────────────────────

    def get_entities(self) -> list[EntityInfo]:
        """Obtiene todas las entidades del dominio."""
        if self._index:
            return self._index.entities
        return []

    def get_flows(self) -> list[FlowInfo]:
        """Obtiene todos los flujos de negocio."""
        if self._index:
            return self._index.flows
        return []

    # ─── ESTIMATIONS ─────────────────────────────────────────────────────────────

    def get_patterns(self) -> EstimationPatterns:
        """Obtiene los patrones de estimacion."""
        if self._patterns is None:
            self._patterns = EstimationPatterns()
        return self._patterns

    def save_patterns(self, patterns: EstimationPatterns) -> None:
        """Persiste los patrones de estimacion."""
        self._patterns = patterns
        self._save_patterns()

    def get_completions(self) -> list[CompletionRecord]:
        """Obtiene el historico de HUs completadas."""
        history_path = self._memory_path / "estimations" / "history.json"
        if not history_path.exists():
            return []
        data = json.loads(history_path.read_text(encoding="utf-8"))
        return [CompletionRecord(**c) for c in data.get("completions", [])]

    def add_completion(self, record: CompletionRecord) -> None:
        """Agrega un registro de HU completada al historico."""
        history_path = self._memory_path / "estimations" / "history.json"
        data = {"completions": []}
        if history_path.exists():
            data = json.loads(history_path.read_text(encoding="utf-8"))
        data["completions"].append(record.model_dump(mode="json"))
        self._save_json("estimations/history.json", data)

    # ─── DECISIONS ───────────────────────────────────────────────────────────────

    def add_decision(self, decision: Decision) -> None:
        """Agrega una decision al registro."""
        if self._index:
            self._index.decisions.append(decision)
            self._save_index()

    # ─── EXPORT / IMPORT ─────────────────────────────────────────────────────────

    def export_memory(self) -> Path:
        """Exporta toda la memoria como archivo .zip.

        Returns:
            Path al archivo zip generado.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d")
        zip_name = f".hu-memory-export-{timestamp}.zip"
        zip_path = self._memory_path.parent / zip_name

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in self._memory_path.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(self._memory_path)
                    zf.write(file_path, arcname)

        logger.info("Memoria exportada a %s", zip_path)
        return zip_path

    def import_memory(self, zip_path: Path) -> int:
        """Importa memoria desde un archivo .zip (reemplaza la existente).

        Args:
            zip_path: Ruta al archivo zip.

        Returns:
            Numero de archivos importados.
        """
        if not zip_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {zip_path}")

        # Backup de memoria actual si existe
        if self._memory_path.exists():
            backup_path = self._memory_path.parent / f".hu-memory-backup-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            shutil.move(str(self._memory_path), str(backup_path))
            logger.info("Backup creado en %s", backup_path)

        self._memory_path.mkdir(parents=True, exist_ok=True)
        file_count = 0

        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                target = self._memory_path / member
                target.parent.mkdir(parents=True, exist_ok=True)
                if not member.endswith("/"):
                    target.write_bytes(zf.read(member))
                    file_count += 1

        self._load()
        logger.info("Memoria importada: %d archivos desde %s", file_count, zip_path)
        return file_count

    # ─── PRIVATE METHODS ─────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Carga el estado completo desde disco."""
        index_path = self._memory_path / "index.json"
        if index_path.exists():
            data = json.loads(index_path.read_text(encoding="utf-8"))
            self._index = ProjectMemory(**data)

        # Reconstruir grafo
        graph_path = self._memory_path / "graph.json"
        if graph_path.exists():
            gdata = json.loads(graph_path.read_text(encoding="utf-8"))
            self._graph = nx.DiGraph()
            for node in gdata.get("nodes", []):
                self._graph.add_node(node["id"], **{k: v for k, v in node.items() if k != "id"})
            for edge in gdata.get("edges", []):
                self._graph.add_edge(edge["source"], edge["target"],
                                     relation=edge.get("relation", "related_to"),
                                     weight=edge.get("weight", 1.0))

        # Cargar patrones
        patterns_path = self._memory_path / "estimations" / "patterns.json"
        if patterns_path.exists():
            pdata = json.loads(patterns_path.read_text(encoding="utf-8"))
            self._patterns = EstimationPatterns(**pdata)
        else:
            self._patterns = EstimationPatterns()

    def _save_index(self) -> None:
        """Persiste el indice maestro."""
        if self._index:
            self._save_json("index.json", self._index.model_dump(mode="json"))

    def _save_graph(self) -> None:
        """Persiste el grafo como JSON."""
        nodes = []
        for node_id, attrs in self._graph.nodes(data=True):
            nodes.append({"id": node_id, **attrs})
        edges = []
        for src, tgt, attrs in self._graph.edges(data=True):
            edges.append({"source": src, "target": tgt, **attrs})
        self._save_json("graph.json", {"nodes": nodes, "edges": edges})

    def _save_patterns(self) -> None:
        """Persiste los patrones de estimacion."""
        if self._patterns:
            self._save_json("estimations/patterns.json", self._patterns.model_dump(mode="json"))

    def _save_json(self, relative_path: str, data: dict) -> None:
        """Escribe un dict como JSON en la ruta indicada."""
        file_path = self._memory_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _upsert_entity(self, entity_name: str, story_id: str) -> None:
        """Crea o actualiza una entidad en el indice."""
        if not self._index:
            return
        existing = next((e for e in self._index.entities if e.name == entity_name), None)
        if existing:
            if story_id not in existing.appears_in:
                existing.appears_in.append(story_id)
        else:
            self._index.entities.append(EntityInfo(
                name=entity_name,
                first_seen_in=story_id,
                appears_in=[story_id],
            ))

    def _upsert_flow(self, flow_name: str, story_id: str) -> None:
        """Crea o actualiza un flujo en el indice."""
        if not self._index:
            return
        existing = next((f for f in self._index.flows if f.name == flow_name), None)
        if existing:
            if story_id not in existing.stories_involved:
                existing.stories_involved.append(story_id)
        else:
            self._index.flows.append(FlowInfo(
                name=flow_name,
                stories_involved=[story_id],
            ))

    @staticmethod
    def _extract_keywords(story_data: dict) -> list[str]:
        """Extrae keywords de una HU para indexacion TF-IDF."""
        text_parts = [
            story_data.get("title", ""),
            story_data.get("narrative", {}).get("as_a", ""),
            story_data.get("narrative", {}).get("i_want", ""),
            story_data.get("narrative", {}).get("so_that", ""),
        ]
        full_text = " ".join(text_parts).lower()
        # Tokenizacion basica: split por espacios, filtrar cortas y stopwords
        stopwords = {"de", "la", "el", "en", "un", "una", "los", "las", "que", "para", "por",
                     "con", "del", "al", "se", "su", "es", "y", "o", "a", "como", "no", "si"}
        words = full_text.split()
        return [w for w in words if len(w) > 2 and w not in stopwords]


# ─── ACCESO VIA WORKSPACE MANAGER ────────────────────────────────────────────────


def get_memory() -> MemoryEngine:
    """Obtiene la instancia activa del MemoryEngine via WorkspaceManager.

    Raises:
        RuntimeError: Si el WorkspaceManager no esta inicializado o no hay workspace activo.
    """
    from src.engine.workspace_manager import get_workspace_manager

    manager = get_workspace_manager()
    if manager is None:
        raise RuntimeError(
            "WorkspaceManager no disponible. El servidor no se inicializó correctamente."
        )

    active = manager.get_active()
    if active is None:
        raise RuntimeError(
            "No hay workspace activo. Usar init_project o switch_workspace primero."
        )

    return active
