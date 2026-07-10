# Feature: Ecosystem Memory — Memoria Transversal de Ecosistemas

## Problema

Hoy el MCP opera a nivel de un solo proyecto (un `.hu-memory/`). En Seguros Bolívar muchos productos son **ecosistemas de apps** donde:
- App A (cotizador) depende del API de App B (motor de riesgos)
- App B y App C comparten la entidad `Poliza` pero la definen con campos distintos
- Un cambio en el contrato de App B rompe a todos sus consumidores

Sin visibilidad transversal, cada proyecto analiza sus HUs en aislamiento y no detecta dependencias cruzadas, entidades compartidas ni flujos que cruzan boundaries.

## Objetivo

Permitir que la memoria de cada proyecto se vincule a un **registro de ecosistema** compartido, de modo que al analizar HUs de un proyecto se pueda:
1. Ver qué entidades/contratos comparte con otras apps del ecosistema
2. Detectar dependencias cross-app (sync/async)
3. Identificar conflictos entre definiciones de entidades compartidas
4. Entender el tipo de acoplamiento (cohesionado vs. desacoplado)

## Requisitos Funcionales

### RF-01: Inicializar ecosistema
- El usuario puede crear un ecosistema con nombre, descripción y lista inicial de apps
- Se persiste en un directorio `.hu-ecosystem/` en una ruta configurable (env var `MCP_ECOSYSTEM_PATH`, default al mismo workspace)
- Un ecosistema agrupa N apps, cada una con su propio `.hu-memory/`

### RF-02: Registrar app en el ecosistema
- Cada app se registra con: app_id, nombre, ruta a su `.hu-memory/`, tipo de acoplamiento (cohesive/decoupled), contratos que expone y contratos que consume
- Al registrar una app, se indexan sus entidades y flujos en el registro central

### RF-03: Listar apps y sus relaciones
- Tool que devuelve todas las apps del ecosistema con sus dependencias mutuas
- Muestra qué entidades son compartidas (aparecen en más de una app)
- Muestra qué contratos conectan apps entre sí

### RF-04: Contexto cross-app al analizar HUs
- Cuando se analiza una HU en el proyecto actual, si el proyecto pertenece a un ecosistema, se enriquece el contexto con:
  - Entidades compartidas relevantes (de otras apps)
  - Contratos que expone/consume la app actual
  - HUs de otras apps que tocan las mismas entidades

### RF-05: Detectar conflictos cross-app
- Extender `detect_conflicts` para detectar:
  - Entidad definida de forma inconsistente entre apps
  - Contrato expuesto por App A que no es consumido por nadie (dead contract)
  - Contrato consumido por App B que no existe en ninguna app (missing provider)
  - Flujos que cruzan apps con pasos huérfanos

### RF-06: Vincular proyecto a ecosistema
- Al hacer `init_project`, opcionalmente se puede indicar `ecosystem_id`
- Si existe un ecosistema en la ruta configurada, el proyecto se vincula automáticamente

## Requisitos No Funcionales

### RNF-01: Sin dependencia de red
- Todo funciona local con archivos JSON (igual que la memoria actual)
- El ecosistema es un directorio más en el filesystem, no un servicio externo

### RNF-02: Lectura cross-app es read-only
- El MCP nunca modifica la memoria de otras apps
- Solo lee sus índices para enriquecer el contexto

### RNF-03: Degradación graceful
- Si el ecosistema no existe o una app referenciada no está disponible, el MCP funciona igual que antes (solo proyecto local)

### RNF-04: Eficiencia de tokens
- El contexto cross-app se filtra por relevancia (solo entidades/contratos que intersectan con la HU actual)
- No se dumbean todas las HUs de todas las apps

## Criterios de Aceptación

1. Puedo crear un ecosistema con `init_ecosystem` y registrar 2+ apps con `register_app`
2. `list_ecosystem` muestra apps, entidades compartidas y dependencias entre apps
3. Al analizar una HU que toca una entidad compartida, el contexto incluye info de cómo esa entidad se define en otras apps
4. `detect_conflicts` reporta inconsistencias entre apps (entidades divergentes, contratos rotos)
5. Si no hay ecosistema configurado, todo funciona exactamente como antes (backward compatible)
