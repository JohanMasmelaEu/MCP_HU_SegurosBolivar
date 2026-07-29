"""Modelos Pydantic para la integración documental con Jira, Confluence y Clockwork Pro."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ActionStatus(str, Enum):
    """Estado de una acción pendiente contra APIs externas."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    EXECUTED = "executed"
    REJECTED = "rejected"
    FAILED = "failed"


class ExternalService(str, Enum):
    """Servicios externos soportados por la integración."""

    JIRA = "jira"
    CONFLUENCE = "confluence"
    CLOCKWORK = "clockwork"


class PendingAction(BaseModel):
    """Acción preparada pendiente de confirmación manual del usuario.

    Toda operación contra APIs externas pasa por este modelo.
    El agente genera el PendingAction como preview y SOLO se ejecuta
    cuando el usuario confirma explícitamente.
    """

    action_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    service: ExternalService
    operation: str = Field(description="Operación allowlisted (ej: jira.get_issue)")
    method: str = Field(description="HTTP method: GET, POST, PUT")
    endpoint: str = Field(description="URL completa del endpoint (sin token)")
    payload_preview: Optional[dict] = Field(
        default=None, description="Body resumido para preview (sin datos sensibles)"
    )
    description: str = Field(description="Descripción humana de qué hará la acción")
    impact: str = Field(description="Qué efecto tendrá en el sistema destino")
    reversible: bool = Field(default=False, description="Si la acción se puede deshacer")
    status: ActionStatus = ActionStatus.PENDING
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    executed_at: Optional[str] = None
    result: Optional[dict] = None


class AuditEntry(BaseModel):
    """Registro de auditoría de una operación ejecutada contra APIs externas.

    Se persiste en .hu-memory/audit-log.jsonl (append-only).
    NUNCA incluye tokens, contraseñas ni payloads con datos sensibles.
    """

    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    action_id: str
    service: ExternalService
    operation: str
    status: ActionStatus
    user_confirmed: bool
    response_code: Optional[int] = None
    error_message: Optional[str] = None


class BitacoraEntry(BaseModel):
    """Entrada individual de bitácora diaria (una subtarea trabajada)."""

    date: str = Field(description="Fecha en formato YYYY-MM-DD")
    subtask_key: str = Field(description="Key de la subtarea en Jira (ej: PROJ-123)")
    subtask_summary: str = Field(description="Título de la subtarea")
    parent_key: str = Field(description="Key del issue padre")
    activity_type: Optional[str] = Field(
        default=None, description="Tipo de tarea de Clockwork (dinámico, elegido por usuario)"
    )
    description: str = Field(description="Descripción del trabajo realizado")
    start_time: Optional[str] = Field(default=None, description="Hora inicio HH:MM (24h)")
    end_time: Optional[str] = Field(default=None, description="Hora fin HH:MM (24h)")
    hours: float = Field(description="Horas dedicadas a esta entrada")
    is_overtime: bool = Field(default=False, description="Si esta entrada es hora extra")
    overtime_reason: Optional[str] = Field(
        default=None, description="Justificación de la hora extra (obligatoria si is_overtime)"
    )


class DailyBitacora(BaseModel):
    """Bitácora completa de un día de trabajo."""

    date: str = Field(description="Fecha en formato YYYY-MM-DD")
    user_email: str = Field(description="Email del usuario")
    entries: list[BitacoraEntry] = Field(default_factory=list)
    total_hours: float = 0.0
    regular_hours: float = 0.0
    overtime_hours: float = 0.0
    overtime_approved: bool = False
    overtime_reason: Optional[str] = Field(
        default=None, description="Motivo global de horas extra (si aplica)"
    )
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class WorkHoursConfig(BaseModel):
    """Configuración de horas laborales — invariante de negocio.

    Día laboral = 8 horas sin incluir almuerzo.
    Horas extras requieren aprobación explícita + justificación.
    Si el usuario no confirma ni da motivo, se registran solo 8h.
    """

    daily_hours: float = Field(default=8.0, description="Horas laborales por día (sin almuerzo)")
    includes_lunch: bool = Field(default=False, description="Las 8h NO incluyen almuerzo")
    overtime_requires_approval: bool = Field(
        default=True, description="Horas extra requieren confirmación explícita"
    )
    overtime_requires_reason: bool = Field(
        default=True, description="Horas extra requieren justificación escrita"
    )
    default_to_regular_on_ignore: bool = Field(
        default=True, description="Si no confirma/ignora, solo se registran las 8h normativas"
    )
