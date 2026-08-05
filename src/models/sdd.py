"""Modelos SDD (Spec-Driven Development): capas, reglas transversales, profundidad por rol y specs."""

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ─── 2.1: SDDLayer ────────────────────────────────────────────────────────────────


class SDDLayer(str, Enum):
    """Capas del modelo SDD para clasificacion de decisiones y artefactos."""

    NEGOCIO = "negocio"
    ARQUITECTURA = "arquitectura"
    SEGURIDAD = "seguridad"
    GOBIERNO_INFO = "gobierno_info"
    ACCESO_DATOS = "acceso_datos"
    DATOS = "datos"
    DESARROLLO = "desarrollo"
    QA = "qa"


SDD_LAYER_META: dict[str, dict] = {
    SDDLayer.NEGOCIO: {"category": "strategic", "description": "Procesos de negocio, reglas de dominio, stakeholders"},
    SDDLayer.ARQUITECTURA: {"category": "strategic", "description": "Decisiones de arquitectura, patrones, stack tecnológico"},
    SDDLayer.SEGURIDAD: {"category": "strategic", "description": "Políticas de seguridad, autenticación, autorización"},
    SDDLayer.GOBIERNO_INFO: {"category": "strategic", "description": "Gobierno de información, lineamientos de datos"},
    SDDLayer.ACCESO_DATOS: {"category": "strategic", "description": "Control de acceso a datos, quién puede ver/operar qué"},
    SDDLayer.DATOS: {"category": "tactical", "description": "Modelo de datos, persistencia, migraciones"},
    SDDLayer.DESARROLLO: {"category": "tactical", "description": "Estándares de código, patrones de implementación"},
    SDDLayer.QA: {"category": "tactical", "description": "Estrategia de testing, cobertura, criterios de calidad"},
}


# ─── 2.5: EXPERT_SDD_LAYER_MAP (migrado desde story.py) ──────────────────────────


EXPERT_SDD_LAYER_MAP: dict[str, str] = {
    "negocio": SDDLayer.NEGOCIO.value,
    "ux": SDDLayer.DESARROLLO.value,
    "backend": SDDLayer.DESARROLLO.value,
    "datos": SDDLayer.DATOS.value,
    "seguridad": SDDLayer.SEGURIDAD.value,
    "qa": SDDLayer.QA.value,
    "integracion": SDDLayer.ARQUITECTURA.value,
    "observabilidad": SDDLayer.ARQUITECTURA.value,
    "devops": SDDLayer.ARQUITECTURA.value,
    "legal": SDDLayer.GOBIERNO_INFO.value,
}


# ─── 2.2: TransversalRule ─────────────────────────────────────────────────────────


class TransversalRule(BaseModel):
    """Regla transversal del catálogo corporativo aplicable a specs."""

    rule_id: str = Field(description="Identificador único (ej: rule-code-style)")
    name: str = Field(description="Nombre descriptivo")
    version: str = Field(default="1.0.0")
    category: Literal["code_style", "security", "architecture", "changelog", "tech_stack", "custom"] = Field(
        description="Categoría de la regla"
    )
    content: str = Field(description="Contenido de la regla en markdown")
    applies_to_layers: list[SDDLayer] = Field(
        default_factory=list, description="Capas donde aplica esta regla. Vacío = todas las capas"
    )
    applies_to_stacks: list[str] = Field(
        default_factory=list, description="Tech stacks donde aplica (ej: java-spring-boot). Vacío = todos"
    )
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: Optional[str] = None


# ─── 2.3: RoleDepthMatrix ─────────────────────────────────────────────────────────


DepthLevel = Literal["full", "context", "n/a"]


class RoleDepthMatrix(BaseModel):
    """Matriz de profundidad por rol y capa SDD.

    Define qué nivel de detalle ve cada stakeholder en cada capa:
    - full: acceso completo (decisions, constraints, artifacts)
    - context: solo resumen
    - n/a: capa no visible para ese rol
    """

    matrix: dict[str, dict[str, DepthLevel]] = Field(
        description="Mapeo {StakeholderRole.value → {SDDLayer.value → DepthLevel}}"
    )

    def get_depth(self, role: str, layer: str) -> DepthLevel:
        """Obtiene el nivel de profundidad para un rol en una capa.

        Args:
            role: Valor del StakeholderRole.
            layer: Valor del SDDLayer.

        Returns:
            DepthLevel correspondiente o 'n/a' si no está definido.
        """
        return self.matrix.get(role, {}).get(layer, "n/a")

    def get_visible_layers(self, role: str) -> list[str]:
        """Obtiene las capas visibles para un rol (full o context).

        Args:
            role: Valor del StakeholderRole.

        Returns:
            Lista de valores SDDLayer donde el rol tiene acceso.
        """
        return [layer for layer, depth in self.matrix.get(role, {}).items() if depth != "n/a"]


# ─── 2.4: ProjectSpec ─────────────────────────────────────────────────────────────


class LayerContent(BaseModel):
    """Contenido de una capa dentro de un ProjectSpec."""

    summary: str = Field(default="", description="Resumen de la capa")
    decisions: list[str] = Field(default_factory=list, description="Decisiones tomadas")
    constraints: list[str] = Field(default_factory=list, description="Restricciones aplicables")
    artifacts: list[str] = Field(default_factory=list, description="Referencias a artefactos (docs, diagramas)")


class SpecDependency(BaseModel):
    """Dependencia entre dos ProjectSpecs en la constelación."""

    target_spec_id: str = Field(description="ID de la spec de la que se depende")
    dependency_type: Literal["process", "data", "functional"] = Field(description="Tipo de relación")
    description: str = Field(default="")
    maturity: Literal["formalized", "draft", "reference"] = Field(default="reference")
    contracts: list[str] = Field(
        default_factory=list, description="contract_ids del ecosistema que materializan esta dependencia a nivel técnico"
    )


class ProjectSpec(BaseModel):
    """Especificación de proyecto bajo el modelo SDD.

    Agrupa decisiones por capa, reglas aplicadas, dependencias con otras specs
    y control de profundidad por rol.
    """

    spec_id: str = Field(description="Identificador único de la spec")
    project_name: str = Field(description="Nombre del proyecto")
    version: str = Field(default="0.1.0")
    status: Literal["draft", "approved", "superseded"] = Field(default="draft")
    approved_by: list[str] = Field(default_factory=list)
    layers: dict[str, LayerContent] = Field(
        default_factory=dict, description="{SDDLayer.value → LayerContent}"
    )
    rules_applied: list[str] = Field(
        default_factory=list, description="rule_ids del catálogo aplicados a esta spec"
    )
    dependencies: list[SpecDependency] = Field(default_factory=list)
    role_depth_override: Optional[RoleDepthMatrix] = Field(
        default=None, description="Override de la matrix de profundidad. None = usar DEFAULT_ROLE_DEPTH"
    )
    app_id: Optional[str] = Field(default=None, description="app_id vinculado en el ecosistema")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: Optional[str] = None


# ─── 2.6: DEFAULT_ROLE_DEPTH ──────────────────────────────────────────────────────


DEFAULT_ROLE_DEPTH = RoleDepthMatrix(matrix={
    "dev_frontend": {
        SDDLayer.NEGOCIO.value: "context",
        SDDLayer.ARQUITECTURA.value: "context",
        SDDLayer.SEGURIDAD.value: "n/a",
        SDDLayer.GOBIERNO_INFO.value: "n/a",
        SDDLayer.ACCESO_DATOS.value: "n/a",
        SDDLayer.DATOS.value: "context",
        SDDLayer.DESARROLLO.value: "full",
        SDDLayer.QA.value: "context",
    },
    "dev_backend": {
        SDDLayer.NEGOCIO.value: "context",
        SDDLayer.ARQUITECTURA.value: "context",
        SDDLayer.SEGURIDAD.value: "context",
        SDDLayer.GOBIERNO_INFO.value: "n/a",
        SDDLayer.ACCESO_DATOS.value: "context",
        SDDLayer.DATOS.value: "context",
        SDDLayer.DESARROLLO.value: "full",
        SDDLayer.QA.value: "context",
    },
    "qa": {
        SDDLayer.NEGOCIO.value: "context",
        SDDLayer.ARQUITECTURA.value: "n/a",
        SDDLayer.SEGURIDAD.value: "context",
        SDDLayer.GOBIERNO_INFO.value: "n/a",
        SDDLayer.ACCESO_DATOS.value: "n/a",
        SDDLayer.DATOS.value: "context",
        SDDLayer.DESARROLLO.value: "context",
        SDDLayer.QA.value: "full",
    },
    "po": {
        SDDLayer.NEGOCIO.value: "full",
        SDDLayer.ARQUITECTURA.value: "n/a",
        SDDLayer.SEGURIDAD.value: "context",
        SDDLayer.GOBIERNO_INFO.value: "full",
        SDDLayer.ACCESO_DATOS.value: "n/a",
        SDDLayer.DATOS.value: "n/a",
        SDDLayer.DESARROLLO.value: "n/a",
        SDDLayer.QA.value: "context",
    },
    "ux": {
        SDDLayer.NEGOCIO.value: "context",
        SDDLayer.ARQUITECTURA.value: "n/a",
        SDDLayer.SEGURIDAD.value: "n/a",
        SDDLayer.GOBIERNO_INFO.value: "n/a",
        SDDLayer.ACCESO_DATOS.value: "n/a",
        SDDLayer.DATOS.value: "n/a",
        SDDLayer.DESARROLLO.value: "full",
        SDDLayer.QA.value: "context",
    },
    "devops": {
        SDDLayer.NEGOCIO.value: "n/a",
        SDDLayer.ARQUITECTURA.value: "full",
        SDDLayer.SEGURIDAD.value: "context",
        SDDLayer.GOBIERNO_INFO.value: "n/a",
        SDDLayer.ACCESO_DATOS.value: "n/a",
        SDDLayer.DATOS.value: "n/a",
        SDDLayer.DESARROLLO.value: "context",
        SDDLayer.QA.value: "n/a",
    },
    "arquitecto": {
        SDDLayer.NEGOCIO.value: "context",
        SDDLayer.ARQUITECTURA.value: "full",
        SDDLayer.SEGURIDAD.value: "context",
        SDDLayer.GOBIERNO_INFO.value: "context",
        SDDLayer.ACCESO_DATOS.value: "context",
        SDDLayer.DATOS.value: "full",
        SDDLayer.DESARROLLO.value: "full",
        SDDLayer.QA.value: "context",
    },
    "seguridad": {
        SDDLayer.NEGOCIO.value: "n/a",
        SDDLayer.ARQUITECTURA.value: "context",
        SDDLayer.SEGURIDAD.value: "full",
        SDDLayer.GOBIERNO_INFO.value: "context",
        SDDLayer.ACCESO_DATOS.value: "full",
        SDDLayer.DATOS.value: "context",
        SDDLayer.DESARROLLO.value: "context",
        SDDLayer.QA.value: "n/a",
    },
    "dba": {
        SDDLayer.NEGOCIO.value: "n/a",
        SDDLayer.ARQUITECTURA.value: "context",
        SDDLayer.SEGURIDAD.value: "n/a",
        SDDLayer.GOBIERNO_INFO.value: "n/a",
        SDDLayer.ACCESO_DATOS.value: "full",
        SDDLayer.DATOS.value: "full",
        SDDLayer.DESARROLLO.value: "context",
        SDDLayer.QA.value: "n/a",
    },
    "legal": {
        SDDLayer.NEGOCIO.value: "context",
        SDDLayer.ARQUITECTURA.value: "n/a",
        SDDLayer.SEGURIDAD.value: "full",
        SDDLayer.GOBIERNO_INFO.value: "full",
        SDDLayer.ACCESO_DATOS.value: "context",
        SDDLayer.DATOS.value: "n/a",
        SDDLayer.DESARROLLO.value: "n/a",
        SDDLayer.QA.value: "n/a",
    },
    "negocio": {
        SDDLayer.NEGOCIO.value: "full",
        SDDLayer.ARQUITECTURA.value: "n/a",
        SDDLayer.SEGURIDAD.value: "context",
        SDDLayer.GOBIERNO_INFO.value: "full",
        SDDLayer.ACCESO_DATOS.value: "n/a",
        SDDLayer.DATOS.value: "n/a",
        SDDLayer.DESARROLLO.value: "n/a",
        SDDLayer.QA.value: "context",
    },
})
