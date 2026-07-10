# Tasks: Ecosystem Memory

## Implementación

- [ ] 1. Crear `src/models/ecosystem.py` con los modelos: `ContractDefinition`, `AppRegistration`, `SharedEntity`, `EcosystemRegistry`
- [ ] 2. Agregar campos opcionales `ecosystem_id` y `app_id` a `ProjectConfig` en `src/models/project.py`
- [ ] 3. Crear `src/engine/ecosystem.py` con `EcosystemEngine` (init, register, sync, query, conflict detection)
- [ ] 4. Crear `src/tools/ecosystem_tools.py` con handlers: `handle_init_ecosystem`, `handle_register_app`, `handle_list_ecosystem`, `handle_get_cross_app_context`, `handle_sync_ecosystem`
- [ ] 5. Registrar los 5 nuevos tools en `src/server.py`
- [ ] 6. Extender `handle_get_story_context` en `analysis_tools.py` para incluir contexto cross-app cuando aplique
- [ ] 7. Extender `handle_detect_conflicts` en `conflict_tools.py` para incluir conflictos cross-app
- [ ] 8. Actualizar `handle_init_project` para aceptar `ecosystem_id` y `app_id` opcionales y vincular al ecosistema
- [ ] 9. Exportar modelos nuevos en `src/models/__init__.py`
- [ ] 10. Verificar que todo compila y el servidor arranca sin errores
