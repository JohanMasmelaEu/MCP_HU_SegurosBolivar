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

### Cambiado (Red Neuronal — Alineación Design System)
- Se refactorizó completamente `visualizer_ui.html` para alinear con los principios de diseño NLVS definidos en el proyecto
- Se reemplazó nav inline-styles por componente `.view-selector` con clases `.view-tab` y roles ARIA (`tablist`, `tab`, `aria-selected`)
- Se migró carga de scripts de CDN (unpkg.com) a `/static/vendor/` con fallback visual si no están disponibles
- Se agregó legend colapsable con `toggleLegend()`, `aria-expanded` y animación de rotación
- Se agregó componente toast/snackbar para feedback de acciones (cambio de layout, workspace, ecosistema)
- Se agregaron estilos `.icon-btn` con LED glow skeuomórfico (`::before`) en estado activo, reemplazando botones planos
- Se agregó soporte completo light mode con overrides para `.view-selector`, `#panel`, `#tooltip`, `#toolbar select`
- Se agregó bloque CSS `:focus-visible` para accesibilidad en todos los elementos interactivos
- Se agregaron clases utilitarias: `.skeleton`, `.loading-overlay`, `.loading-spinner`, `.empty-state`
- Se mejoró toolbar a layout full-width fijo con textura metálica `var(--sku-metal)` y `backdrop-filter`
- Se unificó scrollbar con tokens CSS (`--scrollbar-thumb`) para Firefox y Webkit
- Se agregaron atributos ARIA en panel (`role="complementary"`), tooltip (`role="tooltip"`), legend (`role="region"`), y controles (`aria-pressed`, `aria-checked`, `aria-label`)
- Se mejoró animación del panel lateral con `var(--transition-panel)` y border prismático con `border-image` gradiente

### Cambiado (Red Neuronal — Jerarquia Toolbar + Fix Visualizacion)
- Se reestructuró el toolbar en dos filas con jerarquía visual: fila primaria (contexto: workspace, ecosistema, layout, reset) y fila secundaria (capas y filtro)
- Se agregó componente `.toolbar-row` y `.toolbar-group` para agrupación semántica de controles
- Se separó fila secundaria con fondo oscuro sutil (`rgba(0,0,0,0.15)`) para diferenciarla visualmente
- Se movió botón Reset a la derecha con `margin-left:auto` para separarlo de los selectores
- Se corrigió padding del contenedor `#cy` para evitar solapamiento con toolbar de dos filas
- Se agregó fallback CDN en el HTML: si `/static/vendor/` no carga, se inyectan scripts desde unpkg.com
- Se agregaron dagre.min.js y cytoscape-dagre.js al Dockerfile para disponibilidad en Docker

### Cambiado (View Selector — UX de navegacion entre vistas)
- Se rediseñó el nav `.view-selector` en ambos HTML (visualizer_ui y ecosystem_visualizer_ui) con nueva estructura rica
- Se aumentó altura del nav de 40px a 52px para acomodar el contenido con iconos y subtítulos
- Se agregó brand lateral "HU Visualizer" con icono SVG para identidad del producto
- Se agregaron iconos SVG inline en cada tab que representan visualmente el concepto de la vista (red neuronal, topología, constelación)
- Se agregó subtítulo descriptivo (`.view-tab-hint`) debajo de cada label: "Spec como grafo de dependencias", "Topologia entre aplicaciones", "Specs del ecosistema"
- Se mejoró el estado activo del tab con background sutil azul y hint coloreado
- Se agregó tab de Constelación en la vista de Red Neuronal para acceso directo cruzado entre vistas
- Se actualizaron todos los offsets dependientes (`#toolbar top`, `#panel top`, `#cy margin-top`, `#view-macro`, `#view-micro`, `.constellation-tree-container`) de 40px a 52px

### Cambiado (Consistencia UI + Modo Claro Completo)
- Se completó el modo claro (`prefers-color-scheme: light`) en `visualizer_ui.html` con overrides para: .glass-panel, .view-selector-brand, .view-tab-hint, #toolbar, .toolbar-row-secondary, .toggle-group, .icon-btn, .btn-reset, #legend, .toast, .narrative-block, .acceptance-criteria, .panel-section, .stat-pill, todas las variantes .tag-*, todas las variantes .status-*, y body::before
- Se completó el modo claro en `ecosystem_visualizer_ui.html` con overrides para: .view-selector-brand, .view-tab-hint, #toolbar, .toolbar-row-secondary, .toggle-group, .filter-btn, #legend, .toast, .flow-card, .micro-app-block, .micro-connection-label, .seq-diagram, .seq-participant, .narrative-block, y body::before
- Se verificó consistencia de patrones compartidos entre ambos archivos: view-selector con brand/tabs/icons/hints, glass-panel con pseudo-elemento ::before, legend colapsable, toast, toolbar con textura metálica, toggle-group
- Se verificó integridad sintáctica: CSS braces, JS braces, y DIV tags balanceados en ambos archivos

### Corregido
- Se corrigió bug donde el panel de detalle de spec en la constelación no se mostraba al hacer click en un nodo, causado por conflicto de especificidad CSS (estilos inline sobreescribían la regla `.open` del stylesheet)
- Se movieron los estilos iniciales de `#constellation-detail` del atributo `style=""` inline al bloque `<style>`, alineándose con el patrón que ya usaba `#panel`

### Corregido
- Se agregó fallback CDN para Cytoscape.js y cose-bilkent en `ecosystem_visualizer_ui.html`, permitiendo que el grafo cargue fuera de Docker (en entorno local sin `/static/vendor/`)
- Se corrigió `overflow-x: hidden` en `.seq-arrow` que recortaba las puntas de flecha del diagrama de secuencia debido al comportamiento de overflow del navegador
- Se corrigió `overflow: hidden` en `.proc-pipeline-step` que ocultaba los indicadores circulares del rail (`::before` posicionado en `left: -33px`) en el diagrama de proceso
- Se agregó `line-color` y `target-arrow-color` por defecto en `NLVS_EDGE_BASE` para garantizar visibilidad de edges como fallback en Cytoscape
