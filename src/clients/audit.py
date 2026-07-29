"""Auditoría local de operaciones ejecutadas contra APIs externas.

Registra toda operación en .hu-memory/audit-log.jsonl (append-only).
NUNCA incluye tokens, contraseñas, PII ni payloads con datos sensibles.
"""

import json
import logging
from pathlib import Path

from src.models.documentation import ActionStatus, AuditEntry, ExternalService

logger = logging.getLogger("mcp_hu.clients.audit")

# Ruta del audit log (relativa al workspace)
AUDIT_LOG_PATH = Path(".hu-memory/audit-log.jsonl")


def get_audit_log_path() -> Path:
    """Obtiene la ruta del audit log, creando el directorio si no existe.

    Returns:
        Path al archivo de audit log.
    """
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    return AUDIT_LOG_PATH


def record_audit_entry(
    action_id: str,
    service: ExternalService,
    operation: str,
    status: ActionStatus,
    user_confirmed: bool,
    response_code: int | None = None,
    error_message: str | None = None,
) -> None:
    """Registra una entrada de auditoría en el log local.

    Args:
        action_id: Identificador único de la acción.
        service: Servicio externo (jira, confluence, clockwork).
        operation: Operación ejecutada (ej: jira.get_issue).
        status: Estado final de la acción.
        user_confirmed: Si el usuario confirmó manualmente.
        response_code: Código HTTP de respuesta (si aplica).
        error_message: Mensaje de error (si falló).
    """
    entry = AuditEntry(
        action_id=action_id,
        service=service,
        operation=operation,
        status=status,
        user_confirmed=user_confirmed,
        response_code=response_code,
        error_message=error_message,
    )

    try:
        log_path = get_audit_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
    except Exception as e:
        logger.error("Error escribiendo audit log: %s", e)


def get_audit_entries(limit: int = 50) -> list[dict]:
    """Lee las últimas N entradas del audit log.

    Args:
        limit: Número máximo de entradas a retornar.

    Returns:
        Lista de entradas de auditoría (más recientes primero).
    """
    log_path = get_audit_log_path()
    if not log_path.exists():
        return []

    entries: list[dict] = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except Exception as e:
        logger.error("Error leyendo audit log: %s", e)
        return []

    # Retornar las más recientes primero
    return entries[-limit:][::-1]
