"""Permite ejecutar el paquete con python -m src."""

from src.server import mcp, logger
from src.engine.visualizer import start_visualizer

if __name__ == "__main__":
    logger.info("Iniciando MCP_HU_SegurosBolivar v1.0.0 (stdio)")
    start_visualizer()
    mcp.run(transport="stdio")
