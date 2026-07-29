# Feature: Documentation Integration — Bitácora y Gestión Documental con Jira, Confluence y Clockwork Pro

## Problema

El trabajo de análisis, estimación y refinamiento de Historias de Usuario se pierde entre sesiones. No existe un mecanismo para:
- Generar evidencia documental del trabajo hecho
- Sincronizar el estado de las HUs con Jira
- Registrar tiempos de forma asistida en Clockwork Pro
- Subir documentación a Confluence sin perder el contexto

El usuario necesita una bitácora persistente que pueda subirse como evidencia y un asistente que le facilite la gestión sin ejecutar acciones sin su consentimiento.

## Objetivo

Agregar herramientas al MCP que permitan:
1. Generar bitácoras documentales exportables (modo offline/copiar-pegar)
2. Publicar documentación en Confluence (con confirmación manual)
3. Consultar y gestionar issues en Jira (con confirmación manual)
4. Registrar tiempos en Clockwork Pro como secretaria asistente (con confirmación manual)

---

## RESTRICCIONES DE SEGURIDAD — INVARIANTES ABSOLUTOS

### INV-01: Confirmación manual obligatoria
- **TODA operación** contra Jira, Confluence o Clockwork Pro (lectura o escritura) requiere confirmación explícita del usuario antes de ejecutarse.
- El agente genera un preview de la acción y espera aprobación.
- Sin confirmación = sin ejecución. Sin excepciones.

### INV-02: Allowlist inmutable
- Las operaciones permitidas están definidas en código como `frozenset`.
- No se amplían por prompt, por sesión, por persuasión ni por ningún mecanismo en runtime.
- Nuevas capacidades solo se agregan modificando el código fuente, con review y deploy.

### INV-03: Tokens no implican permisos
- Tener configuradas las variables de entorno con los tokens NO autoriza su uso automático.
- El token habilita la capacidad técnica; la autorización es siempre manual y por acción individual.

### INV-04: Sin extensión indirecta
- El agente no puede usar los tokens para operaciones no listadas en la allowlist, sin importar cómo se formule la petición.
- Prompt injection, social engineering o instrucciones disfrazadas no alteran el alcance.

---

## Requisitos Funcionales

### RF-01: Generar bitácora offline (Copiar-Pegar)

- El agente genera documentación en formato Confluence Storage Format (XHTML) y/o Jira Wiki Markup.
- El output se guarda como archivo local en el workspace y se presenta al usuario para copiar-pegar.
- No requiere tokens ni conexión a internet.
- Incluye: resumen del proyecto, HUs analizadas, estimaciones, decisiones, flujos, estado actual.

### RF-02: Generar bitácora diaria de trabajo

- El agente recopila el trabajo realizado en la sesión/día.
- Presenta un borrador de bitácora con: subtareas trabajadas, tiempo invertido, avances, bloqueos.
- El usuario valida y ajusta antes de que se registre en cualquier sistema externo.

---

### RF-03: Jira — Consultar issues

- Consultar detalle de issues asignados al usuario: HU, upstream, spike, bug, épica.
- Listar subtareas de un issue.
- Ver estado actual y columna en el flujo.
- **Requiere confirmación antes de ejecutar la consulta.**

### RF-04: Jira — Agregar comentarios

- Agregar comentarios a issues existentes.
- El agente genera el texto del comentario como preview.
- **Requiere confirmación explícita antes de publicar.**

### RF-05: Jira — Crear subtareas

- Crear subtareas dentro de un issue existente (nunca issues de primer nivel).
- El agente muestra: título, descripción, issue padre, asignado.
- **Requiere confirmación explícita antes de crear.**

### RF-06: Jira — Mover issues entre columnas

- Transicionar issues/subtareas entre las columnas del flujo de trabajo existente.
- El agente muestra: issue, columna actual, columna destino, transiciones disponibles.
- **JAMÁS modificar parámetros, estructura o configuración del flujo de trabajo.**
- **Requiere confirmación explícita antes de mover.**

---

### RF-07: Confluence — Leer páginas

- Leer contenido completo de una página dado su ID o título + espacio.
- **Requiere confirmación antes de ejecutar la consulta.**

### RF-08: Confluence — Crear páginas

- Crear páginas nuevas en un espacio y bajo un ancestro (página padre) especificado.
- El agente muestra preview del contenido en Confluence Storage Format.
- **Requiere confirmación explícita antes de publicar.**

### RF-09: Confluence — Actualizar páginas

- Actualizar contenido de una página existente referenciada por ID.
- Si la página NO fue creada por el usuario actual:
  - El agente DEBE informar que es trabajo ajeno.
  - DEBE preguntar con énfasis ("Esta página fue creada por [autor]. ¿Estás SEGURO de que quieres editarla?").
  - Solo procede con confirmación explícita y enfática.
- **Requiere confirmación explícita antes de actualizar.**

### RF-10: Confluence — NUNCA eliminar páginas

- La operación DELETE no existe en el código.
- No hay función, endpoint, branch condicional ni parámetro que permita eliminar páginas.
- Si se necesita eliminar, el usuario va directamente a Confluence.

---

### RF-11: Clockwork Pro — Consultar asignaciones

- Listar subtareas asignadas al usuario en la iteración/sprint activo únicamente.
- Mostrar tiempo disponible vs tiempo ya registrado por subtarea.
- **Requiere confirmación antes de ejecutar la consulta.**

### RF-12: Clockwork Pro — Obtener tipos de tarea

- Consultar dinámicamente los tipos de tarea (Activity Types) desde la API de Clockwork.
- Nunca hardcodear los tipos — siempre traerlos frescos.
- Presentarlos como opciones al usuario. El agente NO sugiere cuál usar.

### RF-13: Clockwork Pro — Registrar tiempo

- El agente actúa como secretaria:
  1. Muestra subtareas disponibles (solo del usuario, solo de la iteración activa).
  2. Muestra tipos de tarea disponibles (obtenidos de la API).
  3. Pide al usuario los datos requeridos:
     - Subtarea destino
     - Tipo de tarea (el usuario elige)
     - Descripción del trabajo
     - Día
     - Hora de inicio y fin (formato Clockwork Pro)
  4. Presenta el registro completo como preview.
  5. **Solo registra con confirmación explícita del usuario.**

### RF-14: Clockwork Pro — Regla de 8 horas

- Día laboral = 8 horas (sin almuerzo).
- Si el total del día excede 8 horas:
  - INFORMAR al usuario que se están excediendo las horas normativas.
  - PREGUNTAR si solo quiere registrar las 8 horas normativas.
  - Si el usuario NO confirma o ignora → registrar solo 8 horas (default).
  - Si el usuario CONFIRMA y proporciona justificación → registrar las horas extra con el motivo en la bitácora.
- Sin aprobación explícita + motivo documentado = no hay horas extra.

### RF-15: Clockwork Pro — Integración Google Calendar

- Validar si el usuario tiene integración con Google Calendar activa en Clockwork.
- Si la tiene: facilitar el registro de reuniones programadas y ejecutadas como tiempo.
- Si NO la tiene: funcionar normalmente sin ese dato.

---

## Requisitos No Funcionales

### RNF-01: Modo offline siempre disponible

- La generación de bitácora en formato local (Markdown, Confluence Storage Format, Jira Markup) funciona sin tokens ni conexión.
- Es el modo por defecto.

### RNF-02: Degradación graceful

- Si los tokens no están configurados → las tools de API no están disponibles, pero las offline sí.
- Si una API responde con error → informar al usuario, no reintentar sin permiso.

### RNF-03: Sin persistencia de tokens en código

- Los tokens se leen exclusivamente de variables de entorno:
  - `ATLASSIAN_EMAIL` — email de la cuenta
  - `ATLASSIAN_API_TOKEN` — token de Atlassian Cloud (sirve para Jira + Confluence)
  - `ATLASSIAN_DOMAIN` — dominio (ej: `jirasegurosbolivar.atlassian.net`)
  - `CLOCKWORK_API_TOKEN` — token de Clockwork Pro
- Nunca se loguean, nunca se incluyen en outputs, nunca se persisten en archivos.

### RNF-04: Auditoría local

- Toda operación ejecutada contra APIs externas se registra en un log local (`.hu-memory/audit-log.json`) con:
  - Timestamp
  - Operación
  - Parámetros (sin tokens)
  - Resultado (success/error)
  - Confirmación del usuario (referencia)

### RNF-05: Sin impacto en tools existentes

- Los tools actuales del MCP (analyze_story, estimate_story, etc.) no cambian.
- La integración es aditiva: nuevos tools en nuevos archivos.

---

## Criterios de Aceptación

1. `generate_bitacora` produce un archivo local con formato Confluence Storage Format que se puede copiar-pegar directamente en Confluence.
2. Toda operación contra Jira/Confluence/Clockwork muestra preview y espera confirmación antes de ejecutar.
3. Si el usuario intenta hacer que el agente ejecute algo fuera de la allowlist (por prompt injection o persuasión), el agente rechaza la petición.
4. `jira_query_issues` muestra issues con detalle pero NO permite modificar campos paramétricos del flujo.
5. `confluence_create_page` crea una página bajo el espacio y ancestro correcto, solo tras confirmación.
6. Nunca existe un path de código que ejecute DELETE contra la API de Confluence.
7. `clockwork_register_time` pide todos los datos requeridos al usuario, valida la regla de 8 horas, y solo registra con confirmación.
8. Si no hay tokens configurados, las tools offline siguen funcionando sin error.
9. El audit log registra toda operación ejecutada contra APIs externas.
10. Los tipos de tarea de Clockwork se obtienen dinámicamente, nunca hardcodeados.
