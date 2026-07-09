"""Context Segmenter: scoring de relevancia entre HUs para optimizar uso de tokens.

Formula de relevancia:
    relevance(HU_new, HU_existing) =
        0.4 x entity_overlap +
        0.3 x flow_overlap +
        0.2 x keyword_similarity (TF-IDF manual) +
        0.1 x dependency_distance

Solo HUs con score > threshold (default 0.5) entran al contexto.
"""

import logging
import math
from collections import Counter
from typing import Optional

import networkx as nx

from src.models.story import StorySummary

logger = logging.getLogger("mcp_hu.engine.segmenter")

DEFAULT_RELEVANCE_THRESHOLD = 0.5

# Pesos de la formula de relevancia
W_ENTITY = 0.4
W_FLOW = 0.3
W_KEYWORD = 0.2
W_DEPENDENCY = 0.1


class ContextSegmenter:
    """Motor de segmentacion de contexto basado en scoring de relevancia.

    Dado un conjunto de HUs existentes (summaries) y una HU objetivo,
    calcula un score de relevancia para cada HU existente y retorna
    solo las que superan el umbral.
    """

    def __init__(self, summaries: list[StorySummary], graph: nx.DiGraph) -> None:
        """Inicializa el segmenter con el corpus de HUs y grafo.

        Args:
            summaries: Resumenes comprimidos de todas las HUs del proyecto.
            graph: Grafo DiGraph de relaciones entre HUs.
        """
        self._summaries = summaries
        self._graph = graph
        self._idf_cache: dict[str, float] = {}
        self._build_idf()

    def get_relevant_context(
        self,
        target_entities: list[str],
        target_flows: list[str],
        target_keywords: list[str],
        target_id: Optional[str] = None,
        threshold: float = DEFAULT_RELEVANCE_THRESHOLD,
        max_results: int = 10,
    ) -> list[tuple[str, float]]:
        """Calcula HUs relevantes para el target y retorna las que superan el umbral.

        Args:
            target_entities: Entidades detectadas en la HU objetivo.
            target_flows: Flujos detectados en la HU objetivo.
            target_keywords: Keywords de la HU objetivo.
            target_id: ID de la HU objetivo (para excluirla del resultado).
            threshold: Score minimo para incluir (default 0.5).
            max_results: Maximo de HUs a retornar.

        Returns:
            Lista de tuplas (story_id, score) ordenada por score descendente.
        """
        if not self._summaries:
            return []

        scored: list[tuple[str, float]] = []

        for summary in self._summaries:
            if target_id and summary.id == target_id:
                continue

            score = self._calculate_relevance(
                target_entities, target_flows, target_keywords, target_id, summary
            )

            if score >= threshold:
                scored.append((summary.id, round(score, 3)))

        # Ordenar por score descendente y limitar
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:max_results]

    def _calculate_relevance(
        self,
        target_entities: list[str],
        target_flows: list[str],
        target_keywords: list[str],
        target_id: Optional[str],
        candidate: StorySummary,
    ) -> float:
        """Calcula el score de relevancia entre target y candidate.

        Args:
            target_entities: Entidades del target.
            target_flows: Flujos del target.
            target_keywords: Keywords del target.
            target_id: ID del target (para distancia en grafo).
            candidate: Summary de la HU candidata.

        Returns:
            Score entre 0 y 1.
        """
        entity_score = self._entity_overlap(target_entities, candidate.entities)
        flow_score = self._flow_overlap(target_flows, candidate.flows)
        keyword_score = self._keyword_similarity(target_keywords, candidate.keywords)
        dep_score = self._dependency_distance(target_id, candidate.id)

        total = (
            W_ENTITY * entity_score
            + W_FLOW * flow_score
            + W_KEYWORD * keyword_score
            + W_DEPENDENCY * dep_score
        )

        return min(total, 1.0)

    @staticmethod
    def _entity_overlap(target: list[str], candidate: list[str]) -> float:
        """Calcula overlap de entidades (Jaccard index).

        Returns:
            Score 0-1.
        """
        if not target or not candidate:
            return 0.0
        target_set = set(e.lower() for e in target)
        candidate_set = set(e.lower() for e in candidate)
        intersection = target_set & candidate_set
        union = target_set | candidate_set
        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def _flow_overlap(target: list[str], candidate: list[str]) -> float:
        """Calcula overlap de flujos (Jaccard index).

        Returns:
            Score 0-1.
        """
        if not target or not candidate:
            return 0.0
        target_set = set(f.lower() for f in target)
        candidate_set = set(f.lower() for f in candidate)
        intersection = target_set & candidate_set
        union = target_set | candidate_set
        return len(intersection) / len(union) if union else 0.0

    def _keyword_similarity(self, target_kw: list[str], candidate_kw: list[str]) -> float:
        """Calcula similitud por keywords usando TF-IDF simplificado + coseno.

        Returns:
            Score 0-1.
        """
        if not target_kw or not candidate_kw:
            return 0.0

        # TF para cada documento
        tf_target = self._compute_tf(target_kw)
        tf_candidate = self._compute_tf(candidate_kw)

        # TF-IDF vectors
        all_terms = set(tf_target.keys()) | set(tf_candidate.keys())
        vec_target = []
        vec_candidate = []

        for term in all_terms:
            idf = self._idf_cache.get(term, 1.0)
            vec_target.append(tf_target.get(term, 0) * idf)
            vec_candidate.append(tf_candidate.get(term, 0) * idf)

        # Cosine similarity
        return self._cosine_similarity(vec_target, vec_candidate)

    def _dependency_distance(self, target_id: Optional[str], candidate_id: str) -> float:
        """Calcula score basado en distancia en el grafo de dependencias.

        Menor distancia = mayor score.

        Returns:
            Score 0-1 (1.0 = vecinos directos, 0 = no conectados).
        """
        if not target_id or not self._graph.has_node(target_id) or not self._graph.has_node(candidate_id):
            return 0.0

        try:
            # Grafo no dirigido para distancia
            undirected = self._graph.to_undirected()
            distance = nx.shortest_path_length(undirected, target_id, candidate_id)
            # Mapear distancia a score: 1→1.0, 2→0.5, 3→0.33, 4+→0.0
            if distance <= 0:
                return 0.0
            if distance > 3:
                return 0.0
            return 1.0 / distance
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return 0.0

    def _build_idf(self) -> None:
        """Construye el cache de IDF basado en todas las HUs del corpus."""
        if not self._summaries:
            return

        n_docs = len(self._summaries)
        doc_freq: Counter = Counter()

        for summary in self._summaries:
            unique_terms = set(summary.keywords)
            for term in unique_terms:
                doc_freq[term] += 1

        # IDF = log(N / df) + 1 (smoothed)
        for term, df in doc_freq.items():
            self._idf_cache[term] = math.log(n_docs / df) + 1.0

    @staticmethod
    def _compute_tf(keywords: list[str]) -> dict[str, float]:
        """Calcula Term Frequency normalizada.

        Args:
            keywords: Lista de keywords (puede tener repetidos).

        Returns:
            Dict term -> TF normalizada.
        """
        if not keywords:
            return {}
        counts = Counter(keywords)
        max_count = max(counts.values())
        return {term: count / max_count for term, count in counts.items()}

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        """Calcula similitud coseno entre dos vectores.

        Returns:
            Score 0-1.
        """
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        magnitude_a = math.sqrt(sum(a * a for a in vec_a))
        magnitude_b = math.sqrt(sum(b * b for b in vec_b))

        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0

        return dot_product / (magnitude_a * magnitude_b)
