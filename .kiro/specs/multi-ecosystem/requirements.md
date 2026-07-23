# Multi-Ecosystem Support — Requirements

## Problema

El MCP actualmente opera con un **unico workspace** (`/workspace/.hu-memory/`) y un **unico ecosistema** (`/workspace/.hu-ecosystem/`). Si un usuario inicializa un proyecto mockup y luego quiere trabajar con un ecosistema real, el servidor rechaza la operacion porque la carpeta ya existe. No hay forma de:

1. Tener multiples ecosistemas coexistiendo.
2. Tener multiples proyectos (workspaces) simultaneos.
3. Seleccionar cual workspace/ecosistema esta activo.
4. Reiniciar un workspace sin acceso manual al filesystem del contenedor.

## Requerimientos Funcionales

### RF-01: Multiples Workspaces (Proyectos)
- El servidor DEBE soportar N workspaces independientes, cada uno con su propia memoria (`.hu-memory/`).
- Cada workspace se identifica por un `workspace_id` unico (slug: alfanumerico + guiones).
- La estructura en disco sera: `<BASE_PATH>/workspaces/<workspace_id>/.hu-memory/`.

### RF-02: Multiples Ecosistemas
- El servidor DEBE soportar N ecosistemas independientes, cada uno con su propio registro (`.hu-ecosystem/`).
- Cada ecosistema se identifica por su `ecosystem_id`.
- La estructura en disco sera: `<BASE_PATH>/ecosystems/<ecosystem_id>/.hu-ecosystem/`.

### RF-03: Workspace Activo (Seleccion)
- El servidor DEBE mantener un "workspace activo" en memoria.
- Si no hay workspace activo, todas las operaciones de HU retornan un error indicando que se debe seleccionar uno.
- El usuario puede cambiar el workspace activo en cualquier momento via `switch_workspace`.

### RF-04: Ecosistema Activo (Seleccion)
- El servidor DEBE mantener un "ecosistema activo" en memoria.
- Los tools existentes de ecosistema operan sobre el ecosistema activo.
- El usuario puede cambiar el ecosistema activo via `switch_ecosystem`.

### RF-05: Listado
- `list_workspaces`: Lista todos los workspaces registrados con su metadata (nombre, dominio, fecha, HUs count).
- `list_ecosystems`: Lista todos los ecosistemas con sus apps registradas.

### RF-06: Reset / Eliminacion
- `reset_workspace(workspace_id)`: Elimina el workspace y su `.hu-memory/`. Requiere confirmacion explicita (parametro `confirm: true`).
- `reset_ecosystem(ecosystem_id)`: Elimina el ecosistema y su `.hu-ecosystem/`. Requiere confirmacion explicita.

### RF-07: Backward Compatibility
- Si existe un `.hu-memory/` legacy en la ruta raiz (antes del refactor), el servidor DEBE migrar automaticamente a la nueva estructura como workspace "default".
- Si existe un `.hu-ecosystem/` legacy, migrar como ecosistema con su `ecosystem_id` original.

### RF-08: Vinculacion Workspace-Ecosistema
- Al inicializar un proyecto (`init_project`) con `ecosystem_id`, el workspace se vincula al ecosistema activo correspondiente.
- Un workspace puede pertenecer a un ecosistema especifico o ser independiente.

## Requerimientos No Funcionales

### RNF-01: Sin Perdida de Datos
- La migracion de formato legacy a multi-workspace NUNCA debe eliminar datos existentes.

### RNF-02: Persistencia
- El estado de "workspace activo" y "ecosistema activo" se persiste en un archivo `<BASE_PATH>/state.json` para sobrevivir reinicios del servidor.

### RNF-03: Rendimiento
- El cambio de workspace/ecosistema debe ser instantaneo (<100ms) ya que solo cambia punteros en memoria y re-carga un index.json.

### RNF-04: Atomicidad en Reset
- La eliminacion de un workspace/ecosistema debe ser atomica: o se borra todo o no se borra nada.

## Criterios de Aceptacion

1. Un usuario puede crear multiples workspaces y switchear entre ellos sin reiniciar el servidor.
2. Un usuario puede crear multiples ecosistemas y cada uno es independiente.
3. Los tools existentes (`analyze_story`, `add_story`, etc.) operan sobre el workspace activo transparentemente.
4. Los tools de ecosistema (`register_app`, `list_ecosystem`) operan sobre el ecosistema activo.
5. Si no hay workspace/ecosistema activo, los tools retornan mensajes claros indicando que usar.
6. La data existente (legacy) se migra automaticamente sin perdida.
