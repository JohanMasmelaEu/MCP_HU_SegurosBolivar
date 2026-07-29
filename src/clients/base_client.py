"""Cliente base con Confirmation Gate integrado.

Toda operación contra APIs externas DEBE pasar por este flujo:
1. prepare_action() → genera PendingAction (preview para el usuario)
2. El usuario confirma o rechaza
3. confirm_action() → marca como confirmada
4. execute_confirmed() → ejecuta la request HTTP real

NUNCA se ejecuta una operación sin confirmación manual explícita.
"""

import logging
import os
from datetime import datetime

import httpx

from src.clients.allowlist import (
    ALLOWED_OPERATIONS,
    FORBIDDEN_OPERATIONS,
    OperationForbiddenError,
    OperationNotAllowedError,
)
from src.clients.audit import record_audit_entry
from src.models.documentation import (
    ActionStatus,
    ExternalService,
    PendingAction,
)

logger = logging.getLogger("mcp_hu.clients.base")

# Timeout para requests HTTP (segundos)
HTTP_TIMEOUT = 30.0


class ActionNotFoundError(Exception):
    """Error cuando se busca una acción pendiente que no existe."""

    def __init__(self, action_id: str):
        super().__init__(f"Acción '{action_id}' no encontrada en acciones pendientes.")


class ActionNotConfirmedError(Exception):
    """Error cuando se intenta ejecutar una acción no confirmada."""

    def __init__(self, action_id: str):
        super().__init__(
            f"Acción '{action_id}' NO ha sido confirmada por el usuario. "
            f"No se ejecutará sin confirmación explícita."
        )


class CredentialsNotConfiguredError(Exception):
    """Error cuando los tokens/credenciales no están en variables de entorno."""

    def __init__(self, service: str, missing_vars: list[str]):
        vars_str = ", ".join(missing_vars)
        super().__init__(
            f"Credenciales de {service} no configuradas. "
            f"Variables faltantes: {vars_str}. "
            f"Configurar en variables de entorno para habilitar la integración."
        )


class BaseExternalClient:
    """Cliente base con Confirmation Gate para APIs externas.

    Garantiza que TODA operación:
    - Está en la allowlist
    - Se prepara como preview antes de ejecutar
    - Solo se ejecuta con confirmación manual
    - Se registra en el audit log
    """

    def __init__(self, service: ExternalService):
        """Inicializa el cliente.

        Args:
            service: Servicio externo que maneja este cliente.
        """
        self.service = service
        self._pending_actions: dict[str, PendingAction] = {}

    def prepare_action(
        self,
        operation: str,
        method: str,
        endpoint: str,
        payload: dict | None,
        description: str,
        impact: str,
        reversible: bool = False,
    ) -> PendingAction:
        """Prepara una acción SIN ejecutarla. Retorna PendingAction para preview.

        Valida que la operación esté en la allowlist antes de crear la acción.
        NO ejecuta ninguna request HTTP.

        Args:
            operation: Nombre de la operación (debe estar en ALLOWED_OPERATIONS).
            method: HTTP method (GET, POST, PUT).
            endpoint: URL completa del endpoint.
            payload: Body/params para preview (sin tokens).
            description: Descripción humana de la acción.
            impact: Descripción del efecto que tendrá.
            reversible: Si se puede deshacer la acción.

        Returns:
            PendingAction con estado PENDING.

        Raises:
            OperationForbiddenError: Si la operación está explícitamente prohibida.
            OperationNotAllowedError: Si la operación no está en la allowlist.
        """
        # Verificar prohibición explícita primero
        if operation in FORBIDDEN_OPERATIONS:
            raise OperationForbiddenError(operation)

        # Verificar allowlist
        if operation not in ALLOWED_OPERATIONS:
            raise OperationNotAllowedError(operation)

        action = PendingAction(
            service=self.service,
            operation=operation,
            method=method,
            endpoint=endpoint,
            payload_preview=payload,
            description=description,
            impact=impact,
            reversible=reversible,
        )
        self._pending_actions[action.action_id] = action
        logger.info(
            "Acción preparada: %s [%s] — esperando confirmación del usuario",
            operation,
            action.action_id,
        )
        return action

    def confirm_action(self, action_id: str) -> PendingAction:
        """Marca una acción como confirmada por el usuario.

        Args:
            action_id: ID de la acción a confirmar.

        Returns:
            PendingAction actualizada con status CONFIRMED.

        Raises:
            ActionNotFoundError: Si la acción no existe.
        """
        action = self._pending_actions.get(action_id)
        if not action:
            raise ActionNotFoundError(action_id)

        action.status = ActionStatus.CONFIRMED
        logger.info("Acción confirmada por usuario: %s [%s]", action.operation, action_id)
        return action

    def reject_action(self, action_id: str) -> PendingAction:
        """Marca una acción como rechazada por el usuario.

        Args:
            action_id: ID de la acción a rechazar.

        Returns:
            PendingAction actualizada con status REJECTED.

        Raises:
            ActionNotFoundError: Si la acción no existe.
        """
        action = self._pending_actions.get(action_id)
        if not action:
            raise ActionNotFoundError(action_id)

        action.status = ActionStatus.REJECTED
        logger.info("Acción rechazada por usuario: %s [%s]", action.operation, action_id)

        # Registrar rechazo en audit
        record_audit_entry(
            action_id=action_id,
            service=action.service,
            operation=action.operation,
            status=ActionStatus.REJECTED,
            user_confirmed=False,
        )
        return action

    def execute_confirmed(self, action_id: str) -> dict:
        """Ejecuta una acción previamente confirmada por el usuario.

        SOLO ejecuta si el status es CONFIRMED. De lo contrario, lanza error.

        Args:
            action_id: ID de la acción confirmada a ejecutar.

        Returns:
            Dict con el resultado de la operación.

        Raises:
            ActionNotFoundError: Si la acción no existe.
            ActionNotConfirmedError: Si la acción no fue confirmada.
        """
        action = self._pending_actions.get(action_id)
        if not action:
            raise ActionNotFoundError(action_id)

        if action.status != ActionStatus.CONFIRMED:
            raise ActionNotConfirmedError(action_id)

        # Ejecutar la request HTTP real
        try:
            result = self._do_request(action)
            action.status = ActionStatus.EXECUTED
            action.executed_at = datetime.now().isoformat()
            action.result = result

            # Registrar éxito en audit
            record_audit_entry(
                action_id=action_id,
                service=action.service,
                operation=action.operation,
                status=ActionStatus.EXECUTED,
                user_confirmed=True,
                response_code=result.get("_status_code"),
            )

            logger.info("Acción ejecutada: %s [%s]", action.operation, action_id)
            return result

        except Exception as e:
            action.status = ActionStatus.FAILED
            action.executed_at = datetime.now().isoformat()

            # Registrar fallo en audit
            record_audit_entry(
                action_id=action_id,
                service=action.service,
                operation=action.operation,
                status=ActionStatus.FAILED,
                user_confirmed=True,
                error_message=str(e),
            )

            logger.error("Acción falló: %s [%s] — %s", action.operation, action_id, e)
            return {"status": "error", "message": str(e)}

    def _do_request(self, action: PendingAction) -> dict:
        """Ejecuta la request HTTP real.

        Método interno — NUNCA llamar directamente. Solo desde execute_confirmed.

        Args:
            action: PendingAction confirmada con los datos de la request.

        Returns:
            Dict con la respuesta (incluye _status_code para auditoría).
        """
        headers = self._get_auth_headers()
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"

        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            if action.method == "GET":
                response = client.get(action.endpoint, headers=headers, params=action.payload_preview)
            elif action.method == "POST":
                response = client.post(action.endpoint, headers=headers, json=action.payload_preview)
            elif action.method == "PUT":
                response = client.put(action.endpoint, headers=headers, json=action.payload_preview)
            else:
                raise ValueError(f"Método HTTP no soportado: {action.method}")

        # Parsear respuesta
        result: dict = {}
        if response.status_code in (200, 201, 204):
            if response.content:
                content_type = response.headers.get("content-type", "")
                if content_type.startswith("application/json"):
                    parsed = response.json()
                    # Algunas APIs (ej. Clockwork) retornan arrays JSON
                    # en vez de objetos. Envolver en dict para uniformidad.
                    if isinstance(parsed, list):
                        result = {"data": parsed}
                    else:
                        result = parsed
                else:
                    result = {"raw": response.text}
            result["_status_code"] = response.status_code
        else:
            result = {
                "_status_code": response.status_code,
                "error": response.text[:500],  # Truncar para no exponer datos
            }

        return result

    def _get_auth_headers(self) -> dict:
        """Obtiene los headers de autenticación desde variables de entorno.

        Las subclases sobreescriben este método con su lógica específica.

        Returns:
            Dict con headers de autenticación.
        """
        raise NotImplementedError("Subclases deben implementar _get_auth_headers")

    def get_pending_actions(self) -> list[PendingAction]:
        """Lista todas las acciones pendientes (status PENDING o CONFIRMED).

        Returns:
            Lista de acciones pendientes.
        """
        return [
            action
            for action in self._pending_actions.values()
            if action.status in (ActionStatus.PENDING, ActionStatus.CONFIRMED)
        ]

    def get_action(self, action_id: str) -> PendingAction | None:
        """Obtiene una acción por su ID.

        Args:
            action_id: ID de la acción.

        Returns:
            PendingAction o None si no existe.
        """
        return self._pending_actions.get(action_id)

    def clear_completed_actions(self) -> int:
        """Limpia acciones ya ejecutadas, rechazadas o fallidas de la memoria.

        Returns:
            Número de acciones limpiadas.
        """
        terminal_statuses = (ActionStatus.EXECUTED, ActionStatus.REJECTED, ActionStatus.FAILED)
        to_remove = [
            action_id
            for action_id, action in self._pending_actions.items()
            if action.status in terminal_statuses
        ]
        for action_id in to_remove:
            del self._pending_actions[action_id]
        return len(to_remove)


def check_atlassian_credentials() -> tuple[bool, list[str]]:
    """Verifica si las credenciales de Atlassian están configuradas.

    Returns:
        Tupla (disponible, variables_faltantes).
    """
    required = ["ATLASSIAN_EMAIL", "ATLASSIAN_API_TOKEN", "ATLASSIAN_DOMAIN"]
    missing = [var for var in required if not os.environ.get(var)]
    return len(missing) == 0, missing


def check_clockwork_credentials() -> tuple[bool, list[str]]:
    """Verifica si las credenciales de Clockwork están configuradas.

    Returns:
        Tupla (disponible, variables_faltantes).
    """
    required = ["CLOCKWORK_API_TOKEN"]
    missing = [var for var in required if not os.environ.get(var)]
    return len(missing) == 0, missing
