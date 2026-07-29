"""Cliente Clockwork Pro API con operaciones allowlisted.

El agente actúa como SECRETARIA de gestión de tiempos:
- Consulta worklogs del usuario en la iteración activa
- Obtiene tipos de tarea (Activity Types) dinámicamente desde la API
- Inicia y detiene timers en subtareas asignadas

Reglas de negocio (invariantes):
- Solo muestra subtareas asignadas al usuario autenticado
- Solo de la iteración/sprint activo
- Tipos de tarea se obtienen dinámicamente (nunca hardcodeados)
- Día laboral = 8 horas (sin almuerzo)
- Horas extras requieren aprobación explícita + justificación
- Sin aprobación = solo 8h normativas (default conservador)

PROHIBIDO (no existen métodos):
- Eliminar worklogs
- Modificar worklogs de otros usuarios
"""

import logging
import os

from src.clients.base_client import BaseExternalClient, CredentialsNotConfiguredError
from src.models.documentation import ExternalService, PendingAction

logger = logging.getLogger("mcp_hu.clients.clockwork")

# Base URL de la API de Clockwork Pro
CLOCKWORK_BASE_URL = "https://api.clockwork.report/v1"

# Timezone por defecto para Colombia
DEFAULT_TIMEZONE = "America/Bogota"


class ClockworkClient(BaseExternalClient):
    """Cliente Clockwork Pro con operaciones estrictamente allowlisted.

    Solo permite: consultar worklogs, obtener activity types,
    iniciar timer y detener timer.
    Todo requiere confirmación manual del usuario.
    """

    def __init__(self):
        """Inicializa el cliente Clockwork Pro."""
        super().__init__(service=ExternalService.CLOCKWORK)

    def _get_auth_headers(self) -> dict:
        """Obtiene headers de autenticación para la API de Clockwork Pro.

        Clockwork usa un token propio independiente del de Atlassian.

        Returns:
            Dict con header Authorization.

        Raises:
            CredentialsNotConfiguredError: Si falta la variable CLOCKWORK_API_TOKEN.
        """
        token = os.environ.get("CLOCKWORK_API_TOKEN")

        if not token:
            raise CredentialsNotConfiguredError("Clockwork Pro", ["CLOCKWORK_API_TOKEN"])

        return {"Authorization": f"Token {token}"}

    # ─── READ OPERATIONS ─────────────────────────────────────────────────────────

    def prepare_get_worklogs(
        self,
        starting_at: str,
        ending_at: str,
        account_id: str,
        project_keys: list[str] | None = None,
    ) -> PendingAction:
        """Prepara consulta de worklogs del usuario en un rango de fechas.

        Solo trae worklogs del usuario autenticado (filtrado por account_id).

        Args:
            starting_at: Fecha inicio en formato YYYY-MM-DD.
            ending_at: Fecha fin en formato YYYY-MM-DD.
            account_id: Account ID del usuario en Atlassian.
            project_keys: Lista de keys de proyecto para filtrar (opcional).

        Returns:
            PendingAction con preview para confirmación del usuario.
        """
        params: dict = {
            "starting_at": starting_at,
            "ending_at": ending_at,
            "account_id": account_id,
            "expand": "issues,worklogs,authors",
            "tz": DEFAULT_TIMEZONE,
        }

        if project_keys:
            # Clockwork espera project_keys[] como array
            params["project_keys"] = project_keys

        return self.prepare_action(
            operation="clockwork.get_worklogs",
            method="GET",
            endpoint=f"{CLOCKWORK_BASE_URL}/worklogs",
            payload=params,
            description=(
                f"Consultar worklogs del usuario del {starting_at} al {ending_at}"
            ),
            impact="Solo lectura. No modifica registros de tiempo.",
        )

    def prepare_get_activity_types(self) -> PendingAction:
        """Prepara consulta de tipos de tarea (Activity Types) disponibles.

        Los tipos de tarea se obtienen SIEMPRE desde la API — nunca se hardcodean.
        Esto garantiza que si el administrador cambia los tipos, el MCP
        sigue funcionando sin modificar código.

        Los Activity Types en Clockwork se obtienen como worklog attributes
        desde la configuración del workspace. Se presentan como opciones
        al usuario y el usuario decide cuál aplica.

        Returns:
            PendingAction con preview para confirmación del usuario.
        """
        # Los activity types en Clockwork se consultan via los atributos
        # configurados en el workspace. Se usa el endpoint de worklogs
        # con expand=worklogs para obtener los attributes disponibles.
        return self.prepare_action(
            operation="clockwork.get_activity_types",
            method="GET",
            endpoint=f"{CLOCKWORK_BASE_URL}/worklogs?expand=worklogs&starting_at=2099-01-01&ending_at=2099-01-02",
            payload=None,
            description="Consultar tipos de tarea (Activity Types) disponibles en Clockwork",
            impact="Solo lectura. No modifica nada.",
        )

    # ─── WRITE OPERATIONS ────────────────────────────────────────────────────────

    def prepare_start_timer(self, issue_key: str) -> PendingAction:
        """Prepara inicio de timer en una subtarea.

        Solo inicia timer en subtareas asignadas al usuario.

        Args:
            issue_key: Key de la subtarea (ej: PROJ-456).

        Returns:
            PendingAction con preview para confirmación del usuario.
        """
        return self.prepare_action(
            operation="clockwork.start_timer",
            method="POST",
            endpoint=f"{CLOCKWORK_BASE_URL}/start_timer",
            payload={"issue_key": issue_key},
            description=f"Iniciar timer en subtarea {issue_key}",
            impact=(
                f"Se iniciará el conteo de tiempo en {issue_key}. "
                f"El tiempo se acumulará hasta que se detenga el timer."
            ),
            reversible=True,
        )

    def prepare_stop_timer(self, issue_key: str) -> PendingAction:
        """Prepara detener timer en una subtarea.

        Al detener, Clockwork registra automáticamente el tiempo transcurrido.

        Args:
            issue_key: Key de la subtarea (ej: PROJ-456).

        Returns:
            PendingAction con preview para confirmación del usuario.
        """
        return self.prepare_action(
            operation="clockwork.stop_timer",
            method="POST",
            endpoint=f"{CLOCKWORK_BASE_URL}/stop_timer",
            payload={"issue_key": issue_key},
            description=f"Detener timer en subtarea {issue_key}",
            impact=(
                f"Se detendrá el timer en {issue_key} y se registrará "
                f"el tiempo transcurrido como worklog."
            ),
            reversible=False,
        )

    # ┌──────────────────────────────────────────────────────────────────────────────┐
    # │  NO EXISTEN métodos para:                                                    │
    # │  - delete_worklog                                                            │
    # │  - modify_others_worklog                                                     │
    # │  Estas operaciones están EXPLÍCITAMENTE PROHIBIDAS en la allowlist.           │
    # └──────────────────────────────────────────────────────────────────────────────┘


# ─── UTILIDADES DE FORMATO ────────────────────────────────────────────────────────


def calculate_time_spent_seconds(start_time: str, end_time: str) -> int:
    """Calcula timeSpentSeconds a partir de hora inicio y fin.

    Args:
        start_time: Hora inicio en formato HH:MM (24h).
        end_time: Hora fin en formato HH:MM (24h).

    Returns:
        Tiempo en segundos.

    Raises:
        ValueError: Si el formato es inválido o end <= start.
    """
    start_parts = start_time.split(":")
    end_parts = end_time.split(":")

    if len(start_parts) != 2 or len(end_parts) != 2:
        raise ValueError(
            f"Formato de hora inválido. Esperado HH:MM. "
            f"Recibido: inicio='{start_time}', fin='{end_time}'"
        )

    start_minutes = int(start_parts[0]) * 60 + int(start_parts[1])
    end_minutes = int(end_parts[0]) * 60 + int(end_parts[1])

    if end_minutes <= start_minutes:
        raise ValueError(
            f"La hora de fin ({end_time}) debe ser posterior a la hora de inicio ({start_time})."
        )

    diff_minutes = end_minutes - start_minutes
    return diff_minutes * 60


def format_started_iso(date: str, start_time: str) -> str:
    """Formatea fecha + hora inicio al formato ISO 8601 que espera Clockwork.

    Args:
        date: Fecha en formato YYYY-MM-DD.
        start_time: Hora inicio en formato HH:MM (24h).

    Returns:
        String ISO 8601 con timezone Colombia (ej: 2026-07-28T09:00:00-05:00).
    """
    return f"{date}T{start_time}:00-05:00"


def calculate_hours_from_times(start_time: str, end_time: str) -> float:
    """Calcula horas decimales entre dos horarios.

    Args:
        start_time: Hora inicio en formato HH:MM.
        end_time: Hora fin en formato HH:MM.

    Returns:
        Horas como float (ej: 1.5 para 1h30m).
    """
    seconds = calculate_time_spent_seconds(start_time, end_time)
    return round(seconds / 3600, 2)


# ─── SINGLETON ────────────────────────────────────────────────────────────────────

_clockwork_client: ClockworkClient | None = None


def get_clockwork_client() -> ClockworkClient:
    """Obtiene la instancia singleton del cliente Clockwork Pro.

    Returns:
        ClockworkClient configurado.
    """
    global _clockwork_client
    if _clockwork_client is None:
        _clockwork_client = ClockworkClient()
    return _clockwork_client
