"""Modelos Pydantic para el registro de ecosistemas multi-app."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ContractDefinition(BaseModel):
    """Contrato de integracion entre apps del ecosistema.

    Representa un punto de conexion (API REST, evento async, libreria compartida)
    entre dos o mas apps.
    """

    contract_id: str = Field(description="Identificador unico del contrato (ej: contract-001)")
    name: str = Field(description="Nombre descriptivo del contrato (ej: API Cotizacion)")
    type: Literal["rest_api", "graphql", "async_event", "shared_lib"] = Field(
        description="Tipo de integracion"
    )
    provider_app: str = Field(description="app_id de la app que expone este contrato")
    consumer_apps: list[str] = Field(
        default_factory=list, description="app_ids de las apps que consumen este contrato"
    )
    spec_reference: str = Field(
        default="", description="Ruta o URL al OpenAPI/AsyncAPI/schema del contrato"
    )
    version: str = Field(default="1.0.0", description="Version del contrato")
    entities_involved: list[str] = Field(
        default_factory=list, description="Entidades que cruzan por este contrato"
    )


class AppRegistration(BaseModel):
    """Registro de una app dentro del ecosistema.

    Cada app tiene su propio .hu-memory/ y se vincula al ecosistema
    para visibilidad transversal.
    """

    app_id: str = Field(description="Identificador unico de la app (ej: app-cotizador)")
    name: str = Field(description="Nombre legible de la app (ej: Cotizador Web)")
    memory_path: str = Field(
        description="Ruta absoluta o relativa al directorio .hu-memory/ de la app"
    )
    coupling_type: Literal["cohesive", "decoupled"] = Field(
        description="Tipo de acoplamiento: cohesive (despliegan juntas) o decoupled (independientes)"
    )
    description: str = Field(default="", description="Descripcion de la app")
    team: str = Field(default="", description="Equipo responsable de la app")
    exposes_contracts: list[str] = Field(
        default_factory=list, description="contract_ids que esta app expone"
    )
    consumes_contracts: list[str] = Field(
        default_factory=list, description="contract_ids que esta app consume"
    )
    entities_snapshot: list[str] = Field(
        default_factory=list, description="Entidades indexadas del .hu-memory/ de la app"
    )
    flows_snapshot: list[str] = Field(
        default_factory=list, description="Flujos indexados del .hu-memory/ de la app"
    )
    story_count: int = Field(default=0, description="Cantidad de HUs registradas en la app")
    registered_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class SharedEntity(BaseModel):
    """Entidad que aparece en multiples apps del ecosistema.

    Permite detectar divergencias en la definicion de la misma entidad
    entre distintas apps.
    """

    entity_name: str = Field(description="Nombre de la entidad (PascalCase)")
    defined_in_apps: list[str] = Field(
        default_factory=list, description="app_ids donde aparece esta entidad"
    )
    fields_by_app: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Campos de la entidad por app: {app_id: [campos]}"
    )
    is_consistent: bool = Field(
        default=True, description="True si todas las apps definen la entidad de forma compatible"
    )
    divergence_notes: str = Field(
        default="", description="Descripcion de la inconsistencia si existe"
    )


class EcosystemRegistry(BaseModel):
    """Registro central del ecosistema de apps.

    Agrupa N apps con sus contratos y entidades compartidas.
    Se persiste en .hu-ecosystem/ecosystem.json.
    """

    ecosystem_id: str = Field(description="Identificador unico del ecosistema")
    name: str = Field(description="Nombre del ecosistema (ej: Plataforma Seguros)")
    description: str = Field(default="", description="Descripcion del ecosistema")
    apps: list[AppRegistration] = Field(default_factory=list)
    contracts: list[ContractDefinition] = Field(default_factory=list)
    shared_entities: list[SharedEntity] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: Optional[str] = None


class CrossAppConflict(BaseModel):
    """Conflicto detectado entre apps del ecosistema."""

    conflict_type: Literal[
        "entity_divergence",
        "missing_contract_provider",
        "dead_contract",
        "cross_app_flow_gap",
    ] = Field(description="Tipo de conflicto cross-app")
    severity: Literal["low", "medium", "high"] = Field(default="medium")
    apps_involved: list[str] = Field(description="app_ids involucrados")
    description: str = Field(description="Descripcion del conflicto")
    suggestion: str = Field(default="", description="Sugerencia de resolucion")
