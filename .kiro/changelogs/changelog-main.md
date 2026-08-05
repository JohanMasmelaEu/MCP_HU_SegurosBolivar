# Changelog — main

## [No publicado]

### Agregado
- Se implementó el NLVS Design System completo (Neomorfismo + Liquid Glass + Viridiformismo + Skeuomorfismo) en `ecosystem_visualizer_ui.html`
- Se agregaron tokens CSS en `:root` con variables para superficies, texto, acentos, orgánicos, radios, blur, sombras neomórficas, skeuomorfismo, scrollbar y transiciones
- Se agregó tema claro completo con `@media (prefers-color-scheme: light)` incluyendo overrides de componentes
- Se agregó mapa de traducción `UI_LABELS` para español en la UI (madurez, salud, acoplamiento, sincronía, estado de contrato)
- Se agregó scrollbar dual-engine (Firefox + Webkit) usando tokens CSS
- Se agregó accesibilidad: `role="tablist"`, `aria-selected`, `aria-pressed`, `aria-expanded`, y bloque CSS `:focus-visible`
- Se agregó panel estático `#constellation-detail` con patrón `.open` (elimina `document.createElement`)
- Se agregó pseudo-elemento `::before` en `.glass-panel` para refracción liquid glass (sin costo GPU)
- Se agregó LED skeuomórfico (`::before`) en botones activos con `var(--sku-led-glow)`
- Se agregó borde prismático en `#panel` con `border-image` gradiente
- Se agregaron clases `.skeleton` con animación shimmer para estados de carga
- Se agregó componente `.toast` como reemplazo del tooltip centrado
- Se agregaron constantes compartidas `NLVS_NODE_BASE`, `NLVS_EDGE_BASE`, `NLVS_HEALTH_COLORS` para Cytoscape
- Se agregó `cursor: pointer` en nodos y edges de Cytoscape (ecosistema y constelación)

### Cambiado
- Se cambió `#toolbar` a full-width responsive con `flex-wrap`, textura metálica `var(--sku-metal)`, y `backdrop-filter`
- Se cambiaron labels de madurez de inglés a español (Formalizado, Borrador, Referencia)
- Se cambió `.flow-card` a `border-radius: var(--radius-organic)` (asimétrico viridiformista)
- Se cambió `body::before` de animación infinita a `3s ease-out forwards` (una sola ejecución)
- Se cambió gradiente de fondo: purple reemplazado por `var(--organic-green)` y `var(--organic-moss)`
- Se cambió `#legend` opacity de 0.5 a 0.75 y empieza expandida por defecto
- Se cambió padding de `#view-micro` de `100px 48px 48px` a `88px 32px 32px`
- Se cambiaron estilos de constelación: nodos `round-rectangle` 140×70, colores rgba con opacidad, sombras suaves, `idealEdgeLength: 220`
- Se refactorizaron `macroStyles` y estilos de constelación para usar `Object.assign` con constantes compartidas

### Agregado (Fase 5 — Árbol Radial SVG)
- Se implementó árbol radial SVG para la vista Constelación, reemplazando completamente Cytoscape en esa vista
- Se agregó contenedor `#constellation-tree` con SVG (`viewBox 700×500`), KPI counter, scan-status y tooltip
- Se agregó CSS completo del árbol radial: `.tree-node` (root/branch/leaf), `.tree-link`, `.tree-label`, `.constellation-kpi`, `.constellation-scan-status`, `.tree-node-tooltip`
- Se agregó animación de scanning secuencial con `transition-delay` calculado por nodo (P4)
- Se agregó KPI counter que muestra specs aprobadas vs total (P5)
- Se agregó glow semántico (`.has-gaps`) con `pulseGlow` limitado a 3 repeticiones (P3)
- Se agregó hover tooltip en nodos hoja del SVG con nombre, estado y capas
- Se agregaron overrides light theme para `.tree-node`, `.tree-label`, `.constellation-kpi`, `.constellation-scan-status`

### Eliminado (Fase 5 — Cleanup Cytoscape constelación)
- Se eliminó variable `constellationCy` (ya no se usa Cytoscape para constelación)
- Se eliminó función `renderConstellation` con lógica Cytoscape (reemplazada por `renderConstellationTree`)
- Se eliminó div `#cy-constellation` (reemplazado por `#constellation-tree` con SVG nativo)
- Se eliminaron llamadas a `showLoading`/`hideLoading` para constelación (el SVG tree tiene su propia animación de scanning)
