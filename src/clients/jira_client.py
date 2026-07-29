"""Cliente Jira Cloud REST API v3 con operaciones allowlisted.

Operaciones permitidas:
- Consultar issues (HU, upstream, spike, bug, épica) con detalle
- Consultar transiciones disponibles para un issue
- Agregar comentarios a issues
- Crear subtareas dentro de un issue existente
- Mover issues/subtareas entre columnas del flujo existente

PROHIBIDO (no existen métodos):
- Eliminar issues
- Modificar flujo de trabajo (workflow)
- Modificar campos paramétricos o estructurales
- Crear issues de primer nivel (HU, épicas, etc.)
"""

import base64
import logging
import os

from src.clients.base_client import BaseExternalClient, CredentialsNotConfiguredError
from src.models.documentation import ExternalService, PendingAction

logger = logging.getLogger("mcp_hu.clients.jira")


def _get_jira_base_url() -> str:
    """Construye la base URL de Jira desde la variable de entorno.

    Returns:
        URL base de la API REST v3 de Jira Cloud.
    """
    domain = os.environ.get("ATLASSIAN_DOMAIN", "")
    return f"https://{domain}/rest/api/3"


class JiraClient(BaseExternalClient):
    """Cliente Jira con operaciones estrictamente allowlisted.

    Solo permite: consultar issues, agregar comentarios, crear subtareas
    y transicionar issues entre columnas del flujo existente.
    JAMÁS modifica parámetros, estructura o configuración del flujo de trabajo.
    """

    def __init__(self):
        """Inicializa el cliente Jira."""
        super().__init__(service=ExternalService.JIRA)

    def _get_auth_headers(self) -> dict:
        """Obtiene headers de autenticación Basic Auth para Atlassian Cloud.

        Returns:
            Dict con header Authorization.

        Raises:
            CredentialsNotConfiguredError: Si faltan variables de entorno.
        """
        email = os.environ.get("ATLASSIAN_EMAIL")
        token = os.environ.get("ATLASSIAN_API_TOKEN")

        if not email or not token:
            missing = []
            if not email:
                missing.append("ATLASSIAN_EMAIL")
            if not token:
                missing.append("ATLASSIAN_API_TOKEN")
            raise CredentialsNotConfiguredError("Jira", missing)

        credentials = f"{email}:{token}"
        encoded = base64.b64encode(credentials.encode("ascii")).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}

    # ─── READ OPERATIONS ─────────────────────────────────────────────────────────

    def prepare_get_issue(self, issue_key: str) -> PendingAction:
        """Prepara consulta detallada de un issue.

        Args:
            issue_key: Key del issue (ej: PROJ-123).

        Returns:
            PendingAction con preview para confirmación del usuario.
        """
        base_url = _get_jira_base_url()
        fields = "summary,status,assignee,issuetype,priority,subtasks,parent,description,labels,sprint"

        return self.prepare_action(
            operation="jira.get_issue",
            method="GET",
            endpoint=f"{base_url}/issue/{issue_key}?fields={fields}",
            payload=None,
            description=f"Consultar detalle del issue {issue_key}",
            impact="Solo lectura. No modifica nada en Jira.",
        )

    def prepare_search_issues(self, jql: str, max_results: int = 50) -> PendingAction:
        """Prepara búsqueda de issues por JQL.

        Usa el endpoint /rest/api/3/search/jql (el anterior /rest/api/3/search
        fue deprecado por Atlassian y devuelve 410 Gone desde 2024).

        Args:
            jql: Query JQL para la búsqueda.
            max_results: Máximo de resultados (default 50).

        Returns:
            PendingAction con preview para confirmación del usuario.
        """
        base_url = _get_jira_base_url()

        return self.prepare_action(
            operation="jira.search_issues",
            method="POST",
            endpoint=f"{base_url}/search/jql",
            payload={
                "jql": jql,
                "maxResults": max_results,
                "fields": [
                    "summary", "status", "assignee", "issuetype",
                    "priority", "parent", "labels", "sprint",
                ],
            },
            description=f"Buscar issues con JQL: {jql[:100]}",
            impact="Solo lectura. No modifica nada en Jira.",
        )

    def prepare_get_transitions(self, issue_key: str) -> PendingAction:
        """Prepara consulta de transiciones disponibles para un issue.

        Muestra a qué columnas se puede mover el issue desde su estado actual.

        Args:
            issue_key: Key del issue.

        Returns:
            PendingAction con preview para confirmación del usuario.
        """
        base_url = _get_jira_base_url()

        return self.prepare_action(
            operation="jira.get_transitions",
            method="GET",
            endpoint=f"{base_url}/issue/{issue_key}/transitions",
            payload=None,
            description=f"Consultar transiciones disponibles para {issue_key}",
            impact="Solo lectura. No modifica nada en Jira.",
        )

    def prepare_get_subtasks(self, issue_key: str) -> PendingAction:
        """Prepara consulta de subtareas de un issue.

        Usa el endpoint /rest/api/3/search/jql (el anterior /rest/api/3/search
        fue deprecado por Atlassian y devuelve 410 Gone desde 2024).

        Args:
            issue_key: Key del issue padre.

        Returns:
            PendingAction con preview para confirmación del usuario.
        """
        base_url = _get_jira_base_url()
        jql = f"parent = {issue_key} ORDER BY created ASC"

        return self.prepare_action(
            operation="jira.get_subtasks",
            method="POST",
            endpoint=f"{base_url}/search/jql",
            payload={
                "jql": jql,
                "maxResults": 100,
                "fields": ["summary", "status", "assignee", "issuetype", "priority"],
            },
            description=f"Consultar subtareas de {issue_key}",
            impact="Solo lectura. No modifica nada en Jira.",
        )

    # ─── WRITE OPERATIONS ────────────────────────────────────────────────────────

    def prepare_add_comment(self, issue_key: str, comment_text: str) -> PendingAction:
        """Prepara agregar un comentario a un issue.

        Args:
            issue_key: Key del issue.
            comment_text: Texto del comentario.

        Returns:
            PendingAction con preview para confirmación del usuario.
        """
        base_url = _get_jira_base_url()

        # Atlassian Document Format (ADF) para el body del comentario
        adf_body = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": comment_text}
                        ],
                    }
                ],
            }
        }

        return self.prepare_action(
            operation="jira.add_comment",
            method="POST",
            endpoint=f"{base_url}/issue/{issue_key}/comment",
            payload=adf_body,
            description=f"Agregar comentario en {issue_key}: '{comment_text[:80]}...'",
            impact="Se publicará un comentario visible para todo el equipo en Jira.",
            reversible=False,
        )

    def prepare_create_subtask(
        self,
        parent_key: str,
        project_key: str,
        summary: str,
        description: str = "",
        assignee_account_id: str | None = None,
    ) -> PendingAction:
        """Prepara crear una subtarea dentro de un issue existente.

        SOLO crea subtareas. NUNCA issues de primer nivel (HU, épicas, etc.).

        Args:
            parent_key: Key del issue padre (ej: PROJ-100).
            project_key: Key del proyecto Jira (ej: PROJ).
            summary: Título de la subtarea.
            description: Descripción opcional.
            assignee_account_id: Account ID del asignado (opcional).

        Returns:
            PendingAction con preview para confirmación del usuario.
        """
        base_url = _get_jira_base_url()

        fields: dict = {
            "project": {"key": project_key},
            "parent": {"key": parent_key},
            "summary": summary,
            "issuetype": {"name": "Sub-task"},
        }

        if description:
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            }

        if assignee_account_id:
            fields["assignee"] = {"accountId": assignee_account_id}

        return self.prepare_action(
            operation="jira.create_subtask",
            method="POST",
            endpoint=f"{base_url}/issue",
            payload={"fields": fields},
            description=f"Crear subtarea '{summary}' bajo {parent_key}",
            impact=(
                f"Se creará una nueva subtarea en Jira bajo {parent_key}. "
                f"Será visible para todo el equipo."
            ),
            reversible=False,
        )

    def prepare_transition_issue(
        self, issue_key: str, transition_id: str, transition_name: str
    ) -> PendingAction:
        """Prepara mover un issue a otra columna del flujo de trabajo.

        SOLO mueve entre columnas existentes del flujo. JAMÁS modifica
        el flujo de trabajo, sus parámetros ni su estructura.

        Args:
            issue_key: Key del issue a mover.
            transition_id: ID de la transición (obtenido de get_transitions).
            transition_name: Nombre de la columna destino (para display).

        Returns:
            PendingAction con preview para confirmación del usuario.
        """
        base_url = _get_jira_base_url()

        return self.prepare_action(
            operation="jira.transition_issue",
            method="POST",
            endpoint=f"{base_url}/issue/{issue_key}/transitions",
            payload={"transition": {"id": transition_id}},
            description=f"Mover {issue_key} a columna '{transition_name}'",
            impact=(
                f"El issue {issue_key} cambiará de estado a '{transition_name}'. "
                f"Este cambio será visible para todo el equipo."
            ),
            reversible=True,
        )

    # ┌──────────────────────────────────────────────────────────────────────────┐
    # │  NO EXISTEN métodos para:                                                │
    # │  - delete_issue                                                          │
    # │  - update_workflow                                                        │
    # │  - update_field_configuration                                            │
    # │  - create_issue (top-level — solo subtareas permitidas)                  │
    # │  - delete_comment                                                        │
    # │  Estas operaciones están EXPLÍCITAMENTE PROHIBIDAS en la allowlist.       │
    # └──────────────────────────────────────────────────────────────────────────┘


# ─── SINGLETON ────────────────────────────────────────────────────────────────────

_jira_client: JiraClient | None = None


def get_jira_client() -> JiraClient:
    """Obtiene la instancia singleton del cliente Jira.

    Returns:
        JiraClient configurado.
    """
    global _jira_client
    if _jira_client is None:
        _jira_client = JiraClient()
    return _jira_client
