"""Modelos Pydantic para Historias de Usuario y su analisis."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ExpertType(str, Enum):
    """Tipos de expertos disponibles en el panel."""

    NEGOCIO = "negocio"
    UX = "ux"
    BACKEND = "backend"
    DATOS = "datos"
    SEGURIDAD = "seguridad"
    QA = "qa"
    INTEGRACION = "integracion"
    OBSERVABILIDAD = "observabilidad"
    DEVOPS = "devops"
    LEGAL = "legal"


from src.models.sdd import EXPERT_SDD_LAYER_MAP  # noqa: F401 — re-export for backward compat


class StakeholderRole(str, Enum):
    """Roles de stakeholders para explicaciones contextualizadas."""

    DEV_FRONTEND = "dev_frontend"
    DEV_BACKEND = "dev_backend"
    QA = "qa"
    PO = "po"
    UX = "ux"
    DEVOPS = "devops"
    ARQUITECTO = "arquitecto"
    SEGURIDAD = "seguridad"
    DBA = "dba"
    LEGAL = "legal"
    NEGOCIO = "negocio"


class Narrative(BaseModel):
    """Formato estandarizado de la narrativa de una HU."""

    as_a: str = Field(description="Como [rol]")
    i_want: str = Field(description="Quiero [accion]")
    so_that: str = Field(description="Para que [beneficio]")


class AcceptanceCriterion(BaseModel):
    """Criterio de aceptacion en formato Given/When/Then."""

    given: str = Field(description="Dado [precondicion]")
    when: str = Field(description="Cuando [accion]")
    then: str = Field(description="Entonces [resultado esperado]")


class QuestionStatus(str, Enum):
    """Estado de una pregunta en una HU."""

    OPEN = "open"
    RESOLVED = "resolved"


class QuestionResolution(BaseModel):
    """Registro de resolucion de una pregunta."""

    resolved_by: str = Field(description="Quien resolvio la pregunta")
    resolved_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    note: str = Field(default="", description="Nota o respuesta de resolucion")


class Question(BaseModel):
    """Pregunta estructurada con estado y historial de resolucion."""

    id: str = Field(default_factory=lambda: str(uuid4())[:8], description="ID unico corto")
    text: str = Field(description="Texto de la pregunta")
    status: QuestionStatus = Field(default=QuestionStatus.OPEN)
    expert: str = Field(default="negocio", description="Experto que origino la pregunta")
    ac_reference: str = Field(default="", description="Referencia al criterio de aceptacion")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    created_by: str = Field(default="system", description="Quien creo la pregunta")
    resolution: Optional[QuestionResolution] = Field(default=None, description="Datos de resolucion")


class ExpertSection(BaseModel):
    """Seccion de analisis de un experto individual."""

    expert: ExpertType
    rules: list[str] = Field(default_factory=list, description="Reglas de negocio detectadas")
    gaps: list[str] = Field(default_factory=list, description="Huecos o ambiguedades encontradas")
    questions: list[str] = Field(default_factory=list, description="Preguntas pendientes por resolver")
    edge_cases: list[str] = Field(default_factory=list, description="Casos borde identificados")
    suggestions: list[str] = Field(default_factory=list, description="Sugerencias del experto")


class StoryAnalysis(BaseModel):
    """Resultado completo del analisis multi-experto de una HU."""

    id: str = Field(description="Identificador unico (ej: HU-001)")
    title: str = Field(description="Titulo conciso de la HU")
    narrative: Narrative
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    expert_analysis: list[ExpertSection] = Field(default_factory=list)
    entities_detected: list[str] = Field(default_factory=list)
    flows_detected: list[str] = Field(default_factory=list)
    complexity_tags: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list, description="IDs de HUs de las que depende")
    impacts: list[str] = Field(default_factory=list, description="IDs de HUs que esta HU impacta")
    total_gaps: int = 0
    total_questions: int = 0
    structured_questions: list[Question] = Field(default_factory=list, description="Preguntas con estado y resolucion")
    status: str = Field(default="analyzed", description="analyzed | refined | completed")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: Optional[str] = None


class StorySummary(BaseModel):
    """Resumen comprimido de una HU para indexacion (ahorro de tokens)."""

    id: str
    title: str
    entities: list[str]
    flows: list[str]
    complexity_tags: list[str]
    dependencies: list[str]
    status: str
    keywords: list[str] = Field(default_factory=list, description="Keywords extraidos para TF-IDF")
