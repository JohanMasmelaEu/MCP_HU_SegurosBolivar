"""Permite ejecutar el paquete con python -m src."""

from src.server import mcp, logger

if __name__ == "__main__":
    logger.info("Iniciando MCP_HU_SegurosBolivar v1.0.0 (stdio)")
    mcp.run(transport="stdio")
