"""Estimation Engine: patrones adaptativos, calibracion y velocity tracking.

Estima esfuerzo de HUs basado en:
- Complejidad (tags)
- Cantidad de expertos involucrados
- Dependencias
- Historico de desviaciones del equipo

Se calibra automaticamente con cada HU completada.
Confianza: low (<5 completions), medium (5-20), high (>20).
"""

import logging
import math
from collections import Counter

from src.models.estimation import (
    CompletionRecord,
    ComplexityPattern,
    EstimationBreakdown,
    EstimationPatterns,
    SprintVelocity,
    StoryEstimation,
)
from src.models.story import StoryAnalysis

logger = logging.getLogger("mcp_hu.engine.estimator")

# Defaults para cuando no hay historico suficiente
DEFAULT_HOURS_BY_COMPLEXITY: dict[str, float] = {
    "crud": 8.0,
    "formulario_simple": 6.0,
    "formulario_multi_paso": 16.0,
    "listado_paginado": 6.0,
    "filtros": 4.0,
    "upload_archivos": 12.0,
    "integracion_s3": 8.0,
    "integracion_externa": 18.0,
    "validacion_compleja": 12.0,
    "proceso_asincrono": 16.0,
    "notificacion": 6.0,
    "autenticacion": 20.0,
    "reportes": 14.0,
    "batch_masivo": 20.0,
    "migracion_datos": 16.0,
}


class EstimationEngine:
    """Motor de estimacion adaptativa.

    Usa patrones derivados del historico para estimar HUs nuevas.
    Se auto-calibra con cada registro de completion.
    """

    def __init__(self, patterns: EstimationPatterns, completions: list[CompletionRecord]) -> None:
        """Inicializa el motor con patrones y historico.

        Args:
            patterns: Patrones actuales (cargados de patterns.json).
            completions: Historico de completions (cargado de history.json).
        """
        self._patterns = patterns
        self._completions = completions

    @property
    def patterns(self) -> EstimationPatterns:
        """Patrones actuales."""
        return self._patterns

    def estimate(self, story: StoryAnalysis) -> StoryEstimation:
        """Estima esfuerzo para una HU analizada.

        Args:
            story: HU con analysis completo.

        Returns:
            Estimacion con rango y confianza.
        """
        # Base: maximo de horas por complejidad de los tags
        base_hours = self._calculate_base_hours(story.complexity_tags)

        # Multiplicadores
        expert_mult = self._expert_multiplier(len(story.expert_analysis))
        dep_mult = self._dependency_multiplier(len(story.dependencies))
        deviation_mult = self._patterns.global_deviation_avg

        # Horas probables
        probable = base_hours * expert_mult * dep_mult

        # Aplicar desviacion historica para rango
        std_factor = self._get_std_factor(story.complexity_tags)
        optimistic = probable / deviation_mult
        pessimistic = probable * deviation_mult * std_factor

        # Breakdown por area
        breakdown = self._build_breakdown(story, probable)

        # Confianza
        confidence, confidence_reason = self._assess_confidence()

        return StoryEstimation(
            story_id=story.id,
            optimistic_hours=round(optimistic, 1),
            probable_hours=round(probable, 1),
            pessimistic_hours=round(pessimistic, 1),
            confidence=confidence,
            confidence_reason=confidence_reason,
            breakdown=breakdown,
            factors_applied={
                "base_hours": base_hours,
                "expert_multiplier": expert_mult,
                "dependency_multiplier": dep_mult,
                "global_deviation": deviation_mult,
                "complexity_tags": story.complexity_tags,
                "experts_count": len(story.expert_analysis),
                "dependencies_count": len(story.dependencies),
            },
        )

    def register_completion(self, record: CompletionRecord) -> None:
        """Registra una HU completada y recalibra patrones.

        Args:
            record: Registro de finalizacion con horas reales.
        """
        # Calcular desviacion si hay estimacion previa
        if record.estimated_hours and record.estimated_hours > 0:
            record.deviation_factor = record.actual_hours / record.estimated_hours

        self._completions.append(record)
        self._calibrate()

    def calibrate(self) -> EstimationPatterns:
        """Recalcula todos los patrones basado en el historico completo.

        Returns:
            Patrones actualizados.
        """
        self._calibrate()
        return self._patterns

    def get_velocity(self, sprint: str | None = None) -> list[SprintVelocity]:
        """Obtiene velocity por sprint.

        Args:
            sprint: Sprint especifico o None para todos.

        Returns:
            Lista de SprintVelocity.
        """
        if sprint:
            return [v for v in self._patterns.sprints if v.sprint == sprint]
        return self._patterns.sprints

    # ─── PRIVATE ─────────────────────────────────────────────────────────────────

    def _calculate_base_hours(self, complexity_tags: list[str]) -> float:
        """Calcula horas base segun tags de complejidad.

        Usa el maximo de los tags (no suma, porque se superponen).
        """
        if not complexity_tags:
            return 8.0  # Default minimo

        hours_list = []
        for tag in complexity_tags:
            # Buscar en patrones historicos primero
            pattern = next((p for p in self._patterns.by_complexity if p.tag == tag), None)
            if pattern and pattern.sample_size >= 3:
                hours_list.append(pattern.avg_hours)
            else:
                # Fallback a defaults
                hours_list.append(DEFAULT_HOURS_BY_COMPLEXITY.get(tag, 10.0))

        # Maximo como base (no suma, para evitar sobreestimar)
        return max(hours_list) if hours_list else 8.0

    def _expert_multiplier(self, expert_count: int) -> float:
        """Multiplicador por cantidad de expertos."""
        if expert_count <= 1:
            return self._patterns.by_expert_count.get("1", 1.0)
        if expert_count <= 2:
            return self._patterns.by_expert_count.get("2", 1.3)
        return self._patterns.by_expert_count.get("3+", 1.6)

    def _dependency_multiplier(self, dep_count: int) -> float:
        """Multiplicador por cantidad de dependencias."""
        if dep_count == 0:
            return self._patterns.by_dependency_count.get("0", 1.0)
        if dep_count <= 2:
            return self._patterns.by_dependency_count.get("1-2", 1.2)
        return self._patterns.by_dependency_count.get("3+", 1.5)

    def _get_std_factor(self, complexity_tags: list[str]) -> float:
        """Factor de desviacion estandar para el rango pesimista."""
        if not self._completions:
            return 1.3  # Default conservador

        # Buscar std_dev en patrones historicos
        for tag in complexity_tags:
            pattern = next((p for p in self._patterns.by_complexity if p.tag == tag), None)
            if pattern and pattern.std_dev > 0 and pattern.avg_hours > 0:
                return 1.0 + (pattern.std_dev / pattern.avg_hours)

        return 1.3

    def _build_breakdown(self, story: StoryAnalysis, total_hours: float) -> list[EstimationBreakdown]:
        """Construye desglose de horas por area."""
        breakdown = []
        experts = [e.expert.value for e in story.expert_analysis]

        # Distribucion proporcional simplificada
        has_frontend = "ux" in experts
        has_backend = "backend" in experts or "datos" in experts
        has_qa = "qa" in experts

        areas: list[tuple[str, float, str]] = []

        if has_frontend and has_backend:
            areas.append(("frontend", 0.35, "UI + flujo de usuario"))
            areas.append(("backend", 0.40, "API + logica + persistencia"))
            areas.append(("qa", 0.25, "Tests + criterios de aceptacion"))
        elif has_backend:
            areas.append(("backend", 0.60, "API + logica + persistencia"))
            areas.append(("qa", 0.40, "Tests + criterios de aceptacion"))
        elif has_frontend:
            areas.append(("frontend", 0.60, "UI + flujo de usuario"))
            areas.append(("qa", 0.40, "Tests + criterios de aceptacion"))
        else:
            areas.append(("desarrollo", 0.70, "Implementacion"))
            areas.append(("qa", 0.30, "Tests"))

        for area, proportion, reason in areas:
            breakdown.append(EstimationBreakdown(
                area=area,
                hours=round(total_hours * proportion, 1),
                reason=reason,
            ))

        return breakdown

    def _assess_confidence(self) -> tuple[str, str]:
        """Evalua nivel de confianza de las estimaciones.

        Returns:
            Tupla (nivel, razon).
        """
        n = len(self._completions)
        if n < 5:
            return "low", f"Solo {n} HUs completadas en el historico. Estimacion basada en defaults genericos."
        if n < 20:
            return "medium", f"{n} HUs completadas. Patrones emergentes pero no consolidados."
        return "high", f"{n} HUs completadas. Patrones consolidados del equipo."

    def _calibrate(self) -> None:
        """Recalcula todos los patrones a partir del historico."""
        if not self._completions:
            return

        # Recalcular por complejidad
        tag_records: dict[str, list[float]] = {}
        for record in self._completions:
            for tag in record.complexity_tags:
                tag_records.setdefault(tag, []).append(record.actual_hours)

        complexity_patterns = []
        for tag, hours_list in tag_records.items():
            n = len(hours_list)
            avg = sum(hours_list) / n
            std = math.sqrt(sum((h - avg) ** 2 for h in hours_list) / n) if n > 1 else 0.0
            complexity_patterns.append(ComplexityPattern(
                tag=tag,
                avg_hours=round(avg, 1),
                std_dev=round(std, 1),
                sample_size=n,
                min_hours=min(hours_list),
                max_hours=max(hours_list),
            ))
        self._patterns.by_complexity = complexity_patterns

        # Recalcular desviacion global
        deviations = [
            r.deviation_factor for r in self._completions
            if r.deviation_factor is not None and r.deviation_factor > 0
        ]
        if deviations:
            self._patterns.global_deviation_avg = round(sum(deviations) / len(deviations), 2)

        # Actualizar confianza y total
        self._patterns.total_completions = len(self._completions)
        confidence, _ = self._assess_confidence()
        self._patterns.confidence_level = confidence

        # Velocity por sprint
        sprint_records: dict[str, list[CompletionRecord]] = {}
        for record in self._completions:
            if record.sprint:
                sprint_records.setdefault(record.sprint, []).append(record)

        sprints = []
        for sprint_name, records in sprint_records.items():
            sprints.append(SprintVelocity(
                sprint=sprint_name,
                completed_stories=len(records),
                actual_hours=sum(r.actual_hours for r in records),
                planned_hours=sum(r.estimated_hours for r in records if r.estimated_hours),
                deviation_avg=round(
                    sum(r.deviation_factor for r in records if r.deviation_factor) / len(records), 2
                ) if any(r.deviation_factor for r in records) else 1.0,
            ))
        self._patterns.sprints = sprints

        logger.info("Patrones recalibrados: %d tags, %d sprints, desviacion global=%.2f",
                    len(complexity_patterns), len(sprints), self._patterns.global_deviation_avg)
