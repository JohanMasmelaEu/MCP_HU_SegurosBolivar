"""Detección automática del IDE cliente conectado al MCP.

Usa el clientInfo del handshake MCP (initialize request) para identificar
qué IDE está usando el agente. No requiere preguntar al usuario.

Clientes conocidos:
- Kiro       → clientInfo.name contiene "kiro"
- Cursor     → clientInfo.name contiene "cursor"
- Claude Code / Claude Desktop → clientInfo.name contiene "claude"
- VS Code (Copilot/Continue) → clientInfo.name contiene "vscode" o "visual-studio"
- Windsurf   → clientInfo.name contiene "windsurf"
- Desconocido → fallback genérico
"""

import logging
import os
from enum import Enum
from typing import Optional

logger = logging.getLogger("mcp_hu.engine.ide_detector")


class IDEClient(str, Enum):
    """IDEs soportados."""
    KIRO = "kiro"
    CURSOR = "cursor"
    CLAUDE = "claude"
    VSCODE = "vscode"
    WINDSURF = "windsurf"
    UNKNOWN = "unknown"


# Mapeo de patrones en clientInfo.name → IDEClient
_CLIENT_PATTERNS: list[tuple[str, IDEClient]] = [
    ("kiro", IDEClient.KIRO),
    ("cursor", IDEClient.CURSOR),
    ("claude", IDEClient.CLAUDE),
    ("windsurf", IDEClient.WINDSURF),
    ("vscode", IDEClient.VSCODE),
    ("visual-studio", IDEClient.VSCODE),
    ("visual studio", IDEClient.VSCODE),
]

# Rutas de configuración MCP por IDE (relativas al workspace)
_MCP_CONFIG_PATHS: dict[IDEClient, dict] = {
    IDEClient.KIRO: {
        "workspace": ".kiro/settings/mcp.json",
        "global": "~/.kiro/settings/mcp.json",
        "docs_url": "https://kiro.dev/docs/mcp",
    },
    IDEClient.CURSOR: {
        "workspace": ".cursor/mcp.json",
        "global": "~/.cursor/mcp.json",
        "docs_url": "https://docs.cursor.com/context/model-context-protocol",
    },
    IDEClient.CLAUDE: {
        "workspace": ".claude/settings.json",
        "global": "~/.claude/settings.json",
        "docs_url": "https://docs.anthropic.com/en/docs/claude-code",
    },
    IDEClient.VSCODE: {
        "workspace": ".vscode/mcp.json",
        "global": "~/.vscode/mcp.json",
        "docs_url": "https://code.visualstudio.com/docs",
    },
    IDEClient.WINDSURF: {
        "workspace": ".windsurf/mcp.json",
        "global": "~/.windsurf/mcp.json",
        "docs_url": "https://docs.windsurf.com",
    },
}

# Estado global del IDE detectado (se setea en el handshake)
_detected_ide: IDEClient = IDEClient.UNKNOWN
_client_name: str = ""
_client_version: str = ""


def detect_ide_from_client_info(client_name: str, client_version: str = "") -> IDEClient:
    """Detecta el IDE basado en el clientInfo.name del handshake MCP.

    Args:
        client_name: Nombre del cliente MCP (viene del initialize request).
        client_version: Versión del cliente (informativo).

    Returns:
        IDEClient detectado.
    """
    global _detected_ide, _client_name, _client_version

    _client_name = client_name
    _client_version = client_version

    name_lower = client_name.lower()

    for pattern, ide in _CLIENT_PATTERNS:
        if pattern in name_lower:
            _detected_ide = ide
            logger.info(
                "IDE detectado: %s (client: %s v%s)",
                ide.value, client_name, client_version,
            )
            return ide

    # Fallback: intentar detectar por variables de entorno
    _detected_ide = _detect_from_env()
    logger.info(
        "IDE detectado por env: %s (client: %s v%s)",
        _detected_ide.value, client_name, client_version,
    )
    return _detected_ide


def _detect_from_env() -> IDEClient:
    """Fallback: detectar IDE por variables de entorno."""
    env_hints = {
        "KIRO_VERSION": IDEClient.KIRO,
        "CURSOR_SESSION": IDEClient.CURSOR,
        "CURSOR_TRACE_ID": IDEClient.CURSOR,
        "VSCODE_PID": IDEClient.VSCODE,
        "TERM_PROGRAM": None,  # check value
    }

    for var, ide in env_hints.items():
        val = os.environ.get(var, "")
        if val:
            if ide is not None:
                return ide
            # TERM_PROGRAM puede ser "cursor", "vscode", etc.
            val_lower = val.lower()
            for pattern, mapped_ide in _CLIENT_PATTERNS:
                if pattern in val_lower:
                    return mapped_ide

    return IDEClient.UNKNOWN


def detect_ide_from_session(session) -> IDEClient:
    """Detecta el IDE desde un objeto ServerSession (lazy, llamado desde tools).

    Args:
        session: mcp.server.session.ServerSession con client_params.

    Returns:
        IDEClient detectado.
    """
    global _detected_ide

    # Si ya se detectó, no re-detectar
    if _detected_ide != IDEClient.UNKNOWN:
        return _detected_ide

    try:
        params = session.client_params
        if params and hasattr(params, "clientInfo") and params.clientInfo:
            return detect_ide_from_client_info(
                client_name=params.clientInfo.name,
                client_version=getattr(params.clientInfo, "version", ""),
            )
    except Exception as e:
        logger.debug("No se pudo detectar IDE desde session: %s", e)

    return _detected_ide


def get_detected_ide() -> IDEClient:
    """Retorna el IDE detectado actualmente."""
    return _detected_ide


def get_client_info() -> dict:
    """Retorna info completa del cliente detectado."""
    ide = _detected_ide
    config = _MCP_CONFIG_PATHS.get(ide, {})

    return {
        "ide": ide.value,
        "client_name": _client_name,
        "client_version": _client_version,
        "config_paths": config,
    }


def get_ide_specific_instructions(ide: Optional[IDEClient] = None) -> str:
    """Genera instrucciones específicas para el IDE detectado.

    Útil para respuestas del MCP que necesiten guiar al usuario
    sobre configuración o acciones específicas del IDE.

    Args:
        ide: IDE específico, o None para usar el detectado.

    Returns:
        Texto con instrucciones específicas del IDE.
    """
    ide = ide or _detected_ide
    config = _MCP_CONFIG_PATHS.get(ide, {})

    if ide == IDEClient.KIRO:
        return (
            f"**Configuración Kiro:**\n"
            f"Archivo: `{config.get('workspace', '')}` o `{config.get('global', '')}`\n"
            f"Reconectar: Panel MCP → Reconnect"
        )
    elif ide == IDEClient.CURSOR:
        return (
            f"**Configuración Cursor:**\n"
            f"Archivo: `{config.get('workspace', '')}` o `{config.get('global', '')}`\n"
            f"Reconectar: Cmd/Ctrl+Shift+P → 'MCP: List Servers' → Restart"
        )
    elif ide == IDEClient.CLAUDE:
        return (
            f"**Configuración Claude Code:**\n"
            f"Archivo: `{config.get('workspace', '')}` o `{config.get('global', '')}`\n"
            f"Reconectar: /mcp o reiniciar sesión"
        )
    elif ide == IDEClient.VSCODE:
        return (
            f"**Configuración VS Code:**\n"
            f"Archivo: `{config.get('workspace', '')}` o `{config.get('global', '')}`\n"
            f"Reconectar: Cmd/Ctrl+Shift+P → 'MCP: Restart Server'"
        )
    elif ide == IDEClient.WINDSURF:
        return (
            f"**Configuración Windsurf:**\n"
            f"Archivo: `{config.get('workspace', '')}` o `{config.get('global', '')}`\n"
            f"Reconectar: Panel MCP → Restart"
        )
    else:
        return (
            "**IDE no identificado.** Configurar MCP según la documentación de tu IDE.\n"
            "El MCP usa transporte stdio — compatible con cualquier cliente MCP estándar."
        )
