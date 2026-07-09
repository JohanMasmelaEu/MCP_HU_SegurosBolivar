"""Modelos Pydantic para el motor de estimacion adaptativa."""

from typing import Optional

from pydantic import BaseModel, Field


class EstimationBreakdown(BaseModel):
    """Desglose de estimacion por area."""

    area: str = Field(description="frontend | backend | qa | infra | otro")
    hours: float
    reason: str


class StoryEstimation(BaseModel):
    """Estimacion completa de una HU."""

    story_id: str
    optimistic_hours: float
    probable_hours: float
    pessimistic_hours: float
    confidence: str = Field(description="low | medium | high")
    confidence_reason: str
    breakdown: list[EstimationBreakdown] = Field(default_factory=list)
    factors_applied: dict = Field(default_factory=dict)


class CompletionRecord(BaseModel):
    """Registro de una HU completada con tiempo real."""

    story_id: str
    actual_hours: float
    estimated_hours: Optional[float] = None
    deviation_factor: Optional[float] = None
    sprint: str = Field(default="")
    notes: str = Field(default="")
    complexity_tags: list[str] = Field(default_factory=list)
    experts_involved: list[str] = Field(default_factory=list)


class ComplexityPattern(BaseModel):
    """Patron estadistico derivado del historico por tipo de complejidad."""

    tag: str
    avg_hours: float
    std_dev: float
    sample_size: int
    min_hours: float = 0.0
    max_hours: float = 0.0


class SprintVelocity(BaseModel):
    """Velocidad de un sprint."""

    sprint: str
    planned_stories: int = 0
    completed_stories: int = 0
    planned_hours: float = 0.0
    actual_hours: float = 0.0
    deviation_avg: float = 1.0


class EstimationPatterns(BaseModel):
    """Patrones completos del motor de estimacion."""

    by_complexity: list[ComplexityPattern] = Field(default_factory=list)
    by_expert_count: dict[str, float] = Field(
        default_factory=lambda: {"1": 1.0, "2": 1.3, "3+": 1.6},
        description="Multiplicador por cantidad de expertos involucrados",
    )
    by_dependency_count: dict[str, float] = Field(
        default_factory=lambda: {"0": 1.0, "1-2": 1.2, "3+": 1.5},
        description="Multiplicador por cantidad de dependencias",
    )
    sprints: list[SprintVelocity] = Field(default_factory=list)
    global_deviation_avg: float = Field(default=1.3, description="Desviacion promedio global estimado/real")
    confidence_level: str = Field(default="low", description="low | medium | high")
    total_completions: int = 0
