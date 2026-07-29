"""Cliente Confluence Cloud REST API con operaciones allowlisted.

Operaciones permitidas:
- Leer páginas completas (por ID o por título + espacio)
- Crear páginas nuevas en un espacio bajo un ancestro
- Actualizar páginas existentes (con advertencia enfática si es trabajo ajeno)

PROHIBIDO (no existe método, no existirá NUNCA):
- Eliminar páginas — para eso el usuario va directamente a Confluence
- Editar trabajo ajeno sin aviso y revalidación enfática

La operación DELETE no existe en este archivo. No hay función, no hay endpoint,
no hay branch condicional, no hay parámetro que permita eliminar páginas.
"""

import base64
import logging
import os

from src.clients.base_client import BaseExternalClient, CredentialsNotConfiguredError
from src.models.documentation import ExternalService, PendingAction

logger = logging.getLogger("mcp_hu.clients.confluence")


def _get_confluence_base_url() -> str:
    """Construye la base URL de Confluence desde la variable de entorno.

    Returns:
        URL base de la API REST de Confluence Cloud.
    """
    domain = os.environ.get("ATLASSIAN_DOMAIN", "")
    return f"https://{domain}/wiki/rest/api"


class ConfluenceClient(BaseExternalClient):
    """Cliente Confluence con operaciones estrictamente allowlisted. SIN DELETE.

    Solo permite: leer páginas, crear páginas nuevas, actualizar páginas.
    Si la página a actualizar es de otro usuario, se advierte con énfasis.
    """

    def __init__(self):
        """Inicializa el cliente Confluence."""
        super().__init__(service=ExternalService.CONFLUENCE)

    def _get_auth_headers(self) -> dict:
        """Obtiene headers de autenticación Basic Auth para Atlassian Cloud.

        Usa el mismo token que Jira (son la misma cuenta Atlassian Cloud).

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
            raise CredentialsNotConfiguredError("Confluence", missing)

        credentials = f"{email}:{token}"
        encoded = base64.b64encode(credentials.encode("ascii")).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}

    # ─── READ OPERATIONS ─────────────────────────────────────────────────────────

    def prepare_get_page(self, page_id: str) -> PendingAction:
        """Prepara lectura completa de una página por ID.

        Args:
            page_id: ID numérico de la página Confluence.

        Returns:
            PendingAction con preview para confirmación del usuario.
        """
        base_url = _get_confluence_base_url()

        return self.prepare_action(
            operation="confluence.get_page",
            method="GET",
            endpoint=f"{base_url}/content/{page_id}?expand=body.storage,version,ancestors,history.createdBy",
            payload=None,
            description=f"Leer página Confluence (ID: {page_id})",
            impact="Solo lectura. No modifica nada en Confluence.",
        )

    def prepare_get_page_by_title(self, space_key: str, title: str) -> PendingAction:
        """Prepara búsqueda de página por título dentro de un espacio.

        Args:
            space_key: Key del espacio Confluence (ej: BDCT).
            title: Título exacto de la página.

        Returns:
            PendingAction con preview para confirmación del usuario.
        """
        base_url = _get_confluence_base_url()

        return self.prepare_action(
            operation="confluence.get_page_by_title",
            method="GET",
            endpoint=f"{base_url}/content?spaceKey={space_key}&title={title}&expand=body.storage,version,history.createdBy",
            payload=None,
            description=f"Buscar página '{title}' en espacio {space_key}",
            impact="Solo lectura. No modifica nada en Confluence.",
        )

    # ─── WRITE OPERATIONS ────────────────────────────────────────────────────────

    def prepare_create_page(
        self,
        space_key: str,
        title: str,
        body_html: str,
        ancestor_id: str,
    ) -> PendingAction:
        """Prepara crear una página nueva en Confluence.

        La página se crea como hija del ancestro indicado.

        Args:
            space_key: Key del espacio (ej: BDCT).
            title: Título de la nueva página.
            body_html: Contenido en Confluence Storage Format (XHTML).
            ancestor_id: ID de la página padre.

        Returns:
            PendingAction con preview para confirmación del usuario.
        """
        base_url = _get_confluence_base_url()

        payload = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "ancestors": [{"id": ancestor_id}],
            "body": {
                "storage": {
                    "value": body_html,
                    "representation": "storage",
                }
            },
        }

        return self.prepare_action(
            operation="confluence.create_page",
            method="POST",
            endpoint=f"{base_url}/content",
            payload=payload,
            description=f"Crear página '{title}' en espacio {space_key} bajo página padre {ancestor_id}",
            impact=(
                "Se creará una nueva página en Confluence visible para el equipo. "
                f"Espacio: {space_key}, Padre: {ancestor_id}."
            ),
            reversible=False,
        )

    def prepare_update_page(
        self,
        page_id: str,
        title: str,
        body_html: str,
        current_version: int,
        is_own_page: bool,
        author_name: str,
    ) -> PendingAction:
        """Prepara actualizar una página existente en Confluence.

        Si la página NO fue creada por el usuario actual, la descripción
        incluye una advertencia ENFÁTICA de que es trabajo ajeno.

        Args:
            page_id: ID de la página a actualizar.
            title: Título de la página (puede mantenerse o cambiarse).
            body_html: Nuevo contenido en Confluence Storage Format.
            current_version: Número de versión actual (se incrementa en 1).
            is_own_page: True si el usuario actual es el autor original.
            author_name: Nombre del autor original de la página.

        Returns:
            PendingAction con preview para confirmación del usuario.
        """
        base_url = _get_confluence_base_url()

        new_version = current_version + 1

        payload = {
            "version": {"number": new_version},
            "title": title,
            "type": "page",
            "body": {
                "storage": {
                    "value": body_html,
                    "representation": "storage",
                }
            },
        }

        # Construir impacto según autoría
        if is_own_page:
            impact = (
                f"Se actualizará tu página '{title}' "
                f"(versión {current_version} → {new_version})."
            )
        else:
            impact = (
                f"⚠️ ADVERTENCIA: Esta página fue creada por '{author_name}'. "
                f"Estás a punto de modificar TRABAJO AJENO. "
                f"¿Estás SEGURO de que quieres editar la página '{title}'? "
                f"(versión {current_version} → {new_version})"
            )

        return self.prepare_action(
            operation="confluence.update_page",
            method="PUT",
            endpoint=f"{base_url}/content/{page_id}",
            payload=payload,
            description=f"Actualizar página '{title}' (v{current_version} → v{new_version})",
            impact=impact,
            reversible=True,
        )

    # ┌──────────────────────────────────────────────────────────────────────────────┐
    # │  NO EXISTE delete_page — NUNCA SE IMPLEMENTARÁ                               │
    # │                                                                              │
    # │  Para eliminar páginas, el usuario va directamente a Confluence.              │
    # │  Esta restricción es a prueba de errores de pereza.                          │
    # │  No hay función, no hay endpoint, no hay branch condicional.                 │
    # │                                                                              │
    # │  Si alguien agrega un método delete aquí, viola el invariante INV-02         │
    # │  del requirements.md de esta feature.                                        │
    # └──────────────────────────────────────────────────────────────────────────────┘


# ─── SINGLETON ────────────────────────────────────────────────────────────────────

_confluence_client: ConfluenceClient | None = None


def get_confluence_client() -> ConfluenceClient:
    """Obtiene la instancia singleton del cliente Confluence.

    Returns:
        ConfluenceClient configurado.
    """
    global _confluence_client
    if _confluence_client is None:
        _confluence_client = ConfluenceClient()
    return _confluence_client
