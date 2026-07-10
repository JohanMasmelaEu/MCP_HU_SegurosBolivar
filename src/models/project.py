"""Modelos Pydantic para la configuracion del proyecto y memoria."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProjectConfig(BaseModel):
    """Configuracion inicial del proyecto."""

    project_name: str = Field(description="Nombre del proyecto")
    domain: str = Field(description="Dominio de negocio (ej: seguros/siniestros/autos)")
    stakeholders: list[str] = Field(default_factory=list, description="Roles del equipo")
    description: str = Field(default="", description="Descripcion general del proyecto")
    ecosystem_id: Optional[str] = Field(
        default=None, description="ID del ecosistema al que pertenece este proyecto"
    )
    app_id: Optional[str] = Field(
        default=None, description="ID de esta app dentro del ecosistema"
    )
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class EntityInfo(BaseModel):
    """Entidad del dominio detectada en las HUs."""

    name: str = Field(description="Nombre de la entidad (PascalCase)")
    first_seen_in: str = Field(description="ID de la HU donde se detecto por primera vez")
    appears_in: list[str] = Field(default_factory=list, description="IDs de HUs donde aparece")
    fields: list[str] = Field(default_factory=list, description="Campos/atributos conocidos")
    relations: list[str] = Field(default_factory=list, description="Relaciones con otras entidades")


class FlowInfo(BaseModel):
    """Flujo de negocio detectado en las HUs."""

    name: str = Field(description="Nombre del flujo (snake_case)")
    description: str = Field(default="")
    stories_involved: list[str] = Field(default_factory=list, description="IDs de HUs en este flujo")
    status: str = Field(default="incomplete", description="incomplete | complete")
    steps: list[str] = Field(default_factory=list, description="Pasos del flujo identificados")


class Decision(BaseModel):
    """Decision arquitectonica o de negocio tomada durante el analisis."""

    id: str
    description: str
    reason: str
    decided_in: str = Field(description="ID de la HU donde se tomo la decision")
    date: str = Field(default_factory=lambda: datetime.now().isoformat())


class GraphEdge(BaseModel):
    """Arista del grafo de relaciones entre HUs."""

    source: str = Field(description="ID HU origen")
    target: str = Field(description="ID HU destino")
    relation_type: str = Field(description="depends_on | impacts | related_to | contradicts | duplicates")
    weight: float = Field(default=1.0, description="Fuerza de la relacion 0-1")


class ProjectMemory(BaseModel):
    """Estado completo de la memoria del proyecto (indice maestro)."""

    config: ProjectConfig
    story_count: int = 0
    entities: list[EntityInfo] = Field(default_factory=list)
    flows: list[FlowInfo] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    graph_edges: list[GraphEdge] = Field(default_factory=list)


class ConflictReport(BaseModel):
    """Reporte de un conflicto detectado entre HUs."""

    conflict_type: str = Field(description="contradiction | duplication | open_flow | missing_dependency")
    between: list[str] = Field(description="IDs de HUs involucradas")
    description: str
    suggestion: str = Field(default="")
    severity: str = Field(default="medium", description="low | medium | high")
