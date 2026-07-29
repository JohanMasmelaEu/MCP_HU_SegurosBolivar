# Tasks: Documentation Integration — Jira, Confluence y Clockwork Pro

## Fase 1: Fundamentos y Seguridad

- [ ] 1. Crear `src/models/documentation.py` con modelos: `ActionStatus`, `ExternalService`, `PendingAction`, `AuditEntry`, `BitacoraEntry`, `DailyBitacora`, `WorkHoursConfig`
- [ ] 2. Crear `src/clients/__init__.py` (package vacío)
- [ ] 3. Crear `src/clients/allowlist.py` con `ALLOWED_OPERATIONS` (frozenset) y `FORBIDDEN_OPERATIONS` (frozenset)
- [ ] 4. Crear `src/clients/base_client.py` con `BaseExternalClient` — Confirmation Gate (prepare_action, confirm_action, execute_confirmed, audit)
- [ ] 5. Crear `src/clients/audit.py` con funciones de escritura en `.hu-memory/audit-log.jsonl` (append-only, sin tokens ni datos sensibles)

## Fase 2: Clientes de API (allowlisted)

- [ ] 6. Crear `src/clients/jira_client.py` con `JiraClient`: prepare_get_issue, prepare_search_issues, prepare_get_transitions, prepare_add_comment, prepare_create_subtask, prepare_transition_issue (SIN delete, SIN update workflow, SIN create top-level)
- [ ] 7. Crear `src/clients/confluence_client.py` con `ConfluenceClient`: prepare_get_page, prepare_get_page_by_title, prepare_create_page, prepare_update_page (SIN delete_page — NUNCA existirá)
- [ ] 8. Crear `src/clients/clockwork_client.py` con `ClockworkClient`: prepare_get_worklogs, prepare_get_activity_types, prepare_start_timer, prepare_stop_timer

## Fase 3: Bitácora Engine (offline)

- [ ] 9. Crear `src/engine/bitacora.py` con `BitacoraEngine`: generate_project_bitacora (formato Confluence Storage Format + Markdown), compile_daily_bitacora, validate_work_hours (regla 8h), format_for_clockwork
- [ ] 10. Implementar generación de Confluence Storage Format (XHTML) para la bitácora del proyecto: HUs analizadas, estimaciones, decisiones, flujos, estado actual
- [ ] 11. Implementar lógica de regla de 8 horas: detección de overtime, prompt al usuario, default a 8h si no confirma, registro con motivo si confirma

## Fase 4: Tools (handlers)

- [ ] 12. Crear `src/tools/documentation_tools.py` con handlers offline: handle_generate_bitacora, handle_generate_daily_bitacora
- [ ] 13. Agregar handlers de Jira: handle_jira_query_issue, handle_jira_search, handle_jira_add_comment, handle_jira_create_subtask, handle_jira_transition
- [ ] 14. Agregar handlers de Confluence: handle_confluence_read_page, handle_confluence_create_page, handle_confluence_update_page
- [ ] 15. Agregar handlers de Clockwork: handle_clockwork_get_assignments, handle_clockwork_get_activity_types, handle_clockwork_register_time
- [ ] 16. Agregar handlers de gestión: handle_confirm_action, handle_reject_action, handle_list_pending_actions

## Fase 5: Registro en MCP Server

- [ ] 17. Registrar tools offline en `src/server.py`: generate_bitacora, generate_daily_bitacora
- [ ] 18. Registrar tools de Jira en `src/server.py`: jira_query_issue, jira_search, jira_add_comment, jira_create_subtask, jira_transition_issue
- [ ] 19. Registrar tools de Confluence en `src/server.py`: confluence_read_page, confluence_create_page, confluence_update_page
- [ ] 20. Registrar tools de Clockwork en `src/server.py`: clockwork_get_assignments, clockwork_get_activity_types, clockwork_register_time
- [ ] 21. Registrar tools de gestión en `src/server.py`: confirm_action, reject_action, list_pending_actions

## Fase 6: Hook de Protección

- [ ] 22. Crear hook PreToolUse `confirm-external-api` que refuerce la verificación de confirmación del usuario antes de ejecutar `confirm_action`

## Fase 7: Configuración y Documentación

- [ ] 23. Actualizar `requirements.txt` con dependencias necesarias (httpx para requests async)
- [ ] 24. Crear steering file `.kiro/steering/documentation-integration.md` con instrucciones de uso para el agente (reglas de confirmación, regla 8h, flujo de bitácora)
- [ ] 25. Verificar que el servidor arranca sin errores con y sin variables de entorno configuradas (degradación graceful)

## Notas de Implementación

### Orden de dependencias:
```
models/documentation.py → clients/allowlist.py → clients/base_client.py
    → clients/jira_client.py
    → clients/confluence_client.py
    → clients/clockwork_client.py
    → engine/bitacora.py
    → tools/documentation_tools.py
    → server.py (registro)
```

### Variables de entorno requeridas (opcionales para degradación):
- `ATLASSIAN_EMAIL` — email de la cuenta Atlassian
- `ATLASSIAN_API_TOKEN` — API token (Jira + Confluence)
- `ATLASSIAN_DOMAIN` — dominio (ej: `jirasegurosbolivar.atlassian.net`)
- `CLOCKWORK_API_TOKEN` — API token de Clockwork Pro

### Criterio de completitud por tarea:
- Cada tarea se considera completa cuando:
  1. El código compila sin errores
  2. Cumple los invariantes de seguridad (INV-01 a INV-04)
  3. No introduce operaciones fuera de la allowlist
  4. No existe ningún path que ejecute DELETE contra Confluence
