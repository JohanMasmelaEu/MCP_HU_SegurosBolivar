# Changelog — MCP_HU_SegurosBolivar

## [No publicado]

### Corregido
- Se corrigio error de deserializacion en los tools `init_project`, `add_story` y `register_completion`: cuando clientes MCP (Kiro, Claude Desktop) envian parametros JSON ya deserializados como `dict`, el server fallaba con "Input should be a valid string". Se agrego helper `_ensure_dict()` que acepta tanto `str` como `dict`, eliminando la incompatibilidad entre clientes.

### Cambiado
- Se documento en el README la necesidad de usar `docker build --network=host` para evitar el error `Network is unreachable` durante `pip install` en la subred corporativa.
