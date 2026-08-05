# NLVS Design System — Requirements

## Problema

La UI del MCP Visualizer (ecosystem_visualizer_ui.html) tiene:
1. **Sin sistema de diseño formal** — los estilos se agregaron ad-hoc sin guía consistente
2. **Sin especificación legible por agentes** — cualquier LLM/IDE que toque la UI genera estilos inconsistentes porque no tiene referencia de qué seguir
3. **Brechas de diseño** — la UI es glassmorphism plano sin las 4 filosofías objetivo (neomorfismo, liquid glass, viridiformismo, skeuomorfismo)
4. **Bugs de UI** — toolbar overflow, idioma mezclado, accesibilidad nula, animaciones infinitas desperdiciando GPU
5. **Inconsistencia entre vistas** — Ecosistema y Constelación parecen apps diferentes

## Objetivo

Crear un **Design System como especificación** (NLVS) que:
- Sea la fuente de verdad para toda UI del MCP
- Sea legible e implementable por cualquier agente (Claude, Copilot, Cursor, Kiro, humano)
- Se auto-inyecte cuando un agente toque archivos de UI (via steering)
- Incluya restricciones de rendimiento para que el diseño no degrade el MCP en Docker
- Cubra dark + light theme
- Corrija los 18 bugs actuales como parte de la implementación

## Requerimientos

### RD-01: Especificación como código
- DEBE existir un archivo `design.md` con tokens, componentes, reglas de rendimiento, y checklist de accesibilidad
- DEBE existir un archivo `steering/design-system.md` que se inyecte automáticamente cuando un agente modifica archivos `**/visualizer**`
- La especificación DEBE ser suficiente para que un agente sin contexto previo genere UI consistente

### RD-02: Tokens CSS centralizados
- TODOS los colores, radios, blurs, sombras, y transiciones DEBEN definirse como variables CSS en `:root`
- NUNCA hardcodear valores — todo por variable
- Las variables DEBEN cubrir dark theme (default) y light theme (media query)

### RD-03: Cuatro filosofías integradas sin sobrecarga
- Neomorfismo: sombras dual (elevado/hundido) en botones y cards
- Liquid Glass: blur variable con refracción en paneles y overlays
- Viridiformismo: gradientes orgánicos, border-radius asimétricos, tonos vegetales
- Skeuomorfismo: textura metal en toolbar, LED indicators en filtros activos
- La suma de las 4 NUNCA debe producir sobrecarga visual ni de rendimiento

### RD-04: Performance budget
- Máximo 3 elementos simultáneos con `backdrop-filter`
- `animation: infinite` SOLO para loading spinner
- Cytoscape: `quality: 'default'`, `animate: 'end'`, max 80 nodos visibles
- Sin CDN externo — todo bundleado en `/static/vendor/`

### RD-05: Accesibilidad mínima
- Todo interactivo con `aria-label`, `:focus-visible`, `cursor: pointer`
- Tabs con `role="tab"` + `aria-selected`
- Toggles con `aria-pressed`
- Colapsables con `aria-expanded`

### RD-06: Idioma único (español)
- TODA la UI en español
- Data attributes en inglés (valores del API)
- Mapa de traducción `UI_LABELS` para conversión

### RD-07: Consistencia visual entre vistas
- Todas las vistas Cytoscape DEBEN compartir vocabulario visual base
- Misma paleta, misma forma de nodo, mismas sombras
- Diferencias permitidas: tamaño de nodo, idealEdgeLength

## Criterios de aceptación

1. El archivo `design.md` existe y cubre tokens, componentes, rendimiento, accesibilidad
2. El steering se inyecta al modificar archivos de visualización
3. Los 18 bugs actuales están corregidos
4. La UI funciona en dark Y light theme
5. Un agente sin contexto previo puede generar un componente nuevo consistente leyendo solo la spec
6. El rendimiento no se degrada: ≤3 backdrop-filters, 0 animaciones infinitas decorativas, layout Cytoscape < 2s
