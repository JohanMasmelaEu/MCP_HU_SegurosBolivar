# NLVS Design System — Plan de implementación

> **Referencia obligatoria:** `.kiro/specs/design-system/design.md`
> **Steering (reglas):** `.kiro/steering/design-system.md`
>
> Antes de implementar cualquier tarea, LEE COMPLETO el `design.md`.
> Todos los tokens, variables, y componentes están definidos ahí.

---

## Fase 0 — Tokens y base (hacer PRIMERO, todo lo demás depende de esto)

### T0.1 Reemplazar variables CSS hardcodeadas por tokens NLVS
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Líneas:** 24-39 (bloque `:root`)
- **Qué hacer:** Reemplazar el bloque `:root` actual por el bloque completo definido en `design.md` sección 2.1. Incluye las variables nuevas: `--surface-elevated`, `--surface-border-hover`, `--organic-*`, `--radius-*`, `--blur-*`, `--neo-*`, `--sku-*`, `--scrollbar-*`, `--transition-*`.
- **Regla:** No borrar las variables existentes — renombrarlas al nuevo nombre si cambia, o mantenerlas si ya coinciden. El CSS existente que usa `var(--bg)`, `var(--surface)`, etc. debe seguir funcionando.

### T0.2 Agregar light theme completo
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Dónde:** Después del cierre de `:root {` (después de las variables dark)
- **Qué hacer:** Agregar el bloque `@media (prefers-color-scheme: light)` completo definido en `design.md` sección 2.2. Incluye overrides para: superficies, textos, acentos, orgánicos, blurs, sombras neo, skeuomorfismo, y scrollbar.
- **IMPORTANTE:** Dentro de este media query, también agregar overrides para:
  - `.view-selector` → background claro
  - `.glass-panel` → sombras claras
  - `#panel` → fondo y bordes claros
  - `#tooltip` → fondo claro
  - `#toolbar select` → fondo claro
  - `.filter-btn` y `.filter-btn.active` → sombras claras
  - `.entity-pill.consistent` y `.entity-pill.divergent` → colores claros
  - Scrollbar → thumbs oscuros sobre fondo claro
- **Código:** Todo está en `design.md` sección 2.2 — copiar el bloque completo.

### T0.3 Agregar mapa de traducción UI
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Dónde:** En el bloque `<script>`, justo después de las variables de estado global (línea ~820)
- **Qué hacer:** Agregar el objeto `UI_LABELS` definido en `design.md` sección 2.3. Usarlo en todas las funciones de renderizado para traducir valores del API a español.

### T0.4 Agregar scrollbar dual-engine
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Líneas:** 325-328 (reemplazar)
- **Qué hacer:** Reemplazar los selectores `::-webkit-scrollbar` actuales por el bloque dual-engine definido en `design.md` sección 7. Agregar las reglas de Firefox ANTES de las de Webkit.

---

## Fase 1 — Fixes críticos (no requieren rediseño, solo corregir lo roto)

### T1.1 Toolbar responsive con flex-wrap
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Líneas CSS:** 96-99 (`#toolbar`)
- **Qué hacer:** Reemplazar el CSS de `#toolbar` por la versión definida en `design.md` sección 3.6. Cambios clave: agregar `flex-wrap: wrap`, cambiar `left: 16px` a `right: 16px` (ancho completo con márgenes), usar `var(--sku-metal)` como background.
- **Dependencia:** T0.1 (necesita las variables)

### T1.2 Labels de madurez español
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Qué hacer:**
  1. **Líneas 766-768** — Cambiar texto de los botones:
     - `Formalized` → `Formalizado`
     - `Draft` → `Borrador`
     - `Reference` → `Referencia`
     - Mantener `data-maturity="formalized|draft|reference"` sin cambiar
  2. **Líneas 806-808** — Cambiar texto de la leyenda:
     - `Formalized` → `Formalizado`
     - `Draft` → `Borrador`
     - `Reference` → `Referencia`
  3. **En `renderAppDetailHTML`** (~línea 1143) — Usar `UI_LABELS.maturity[detail.maturity]` para el texto visible
- **Dependencia:** T0.3 (necesita UI_LABELS)

### T1.3 Accesibilidad: aria + focus-visible
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Qué hacer (HTML):**
  1. **Líneas 738-742** — Agregar `role="tablist"` a `<nav>`, `role="tab"` y `aria-selected` a cada `<a>`:
     ```html
     <nav class="view-selector" role="tablist" aria-label="Vistas del ecosistema">
       <a href="/" class="view-tab" role="tab" aria-selected="false">Red Neuronal</a>
       <a href="/ecosystem" class="view-tab active" role="tab" aria-selected="true" onclick="showEcosystem(); return false;">Ecosistema</a>
       <a href="/ecosystem#constellation" class="view-tab" role="tab" aria-selected="false" id="tab-constellation" onclick="showConstellation(event)">Constelación</a>
     </nav>
     ```
  2. **Líneas 759-768** — Agregar `aria-label` y `aria-pressed="true"` a cada filtro
  3. **Línea 794** — Agregar `aria-expanded="false"` al botón de la leyenda
- **Qué hacer (CSS):** Agregar el bloque `:focus-visible` definido en `design.md` sección 5.2
- **Qué hacer (JS):**
  1. En `toggleFilter` — agregar `btn.setAttribute('aria-pressed', String(activeFilters[type]))`
  2. En `toggleMaturityFilter` — agregar `btn.setAttribute('aria-pressed', String(maturityFilters[maturity]))`
  3. En `toggleConflictsOnly` — agregar `btn.setAttribute('aria-pressed', String(conflictsOnly))`
  4. En `toggleLegend` — agregar `btn.setAttribute('aria-expanded', !content.classList.contains('collapsed'))`
  5. En `showEcosystem` y `showConstellation` — actualizar `aria-selected` de los tabs

### T1.4 Constellation detail panel: refactor a HTML estático
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Qué hacer:**
  1. **En el HTML** (antes de `</body>`, ~línea 2027): Agregar panel estático:
     ```html
     <div id="constellation-detail" class="glass-panel" style="
       position:fixed; top:48px; right:16px; width:320px; max-height:calc(100vh - 80px);
       overflow-y:auto; z-index:95; padding:20px; font-size:12px;
       transform:translateX(120%); opacity:0; pointer-events:none;
       transition: transform var(--transition-panel), opacity 0.3s ease;
     ">
       <div id="constellation-detail-content"></div>
     </div>
     ```
  2. **CSS:** Agregar:
     ```css
     #constellation-detail.open { transform:translateX(0); opacity:1; pointer-events:auto; }
     ```
  3. **JS:** Reescribir `showConstellationDetail` para usar `panel.classList.add('open')` y escribir en `#constellation-detail-content`. Agregar `hideConstellationDetail` con `classList.remove('open')`.
  4. **JS:** En `renderConstellation`, agregar `constellationCy.on('tap', ...)` para cerrar el panel al hacer click fuera.
  5. **Eliminar** el `document.createElement('div')` y los inline styles del `showConstellationDetail` actual (~líneas 2001-2006).

---

## Fase 2 — Componentes NLVS (aplicar las 4 filosofías de diseño)

### T2.1 Glass panel con refracción liquid glass
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Líneas CSS:** 64-74 (`.glass-panel`)
- **Qué hacer:** Reemplazar el CSS actual de `.glass-panel` por la versión definida en `design.md` sección 3.1. Cambios clave:
  - Agregar `position: relative`
  - Usar `var(--blur-medium)` en vez del valor hardcoded
  - Usar `var(--neo-panel)` para box-shadow
  - Agregar pseudo-elemento `::before` para refracción (gradiente estático, sin blur extra)
- **Rendimiento:** El `::before` NO lleva `backdrop-filter` — es solo un gradiente CSS que simula refracción a costo cero de GPU.

### T2.2 Botones neomórficos con LED skeuomórfico
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Líneas CSS:** 132-143 (`.filter-btn`), 123-131 (`.toggle-group`)
- **Qué hacer:** Reemplazar ambos bloques CSS por las versiones definidas en `design.md` secciones 3.2 y 3.3. Cambios clave:
  - `.filter-btn`: `box-shadow: var(--neo-raised)`, estado activo con `var(--neo-pressed)`, pseudo-elemento `::before` como LED
  - `.toggle-group`: `box-shadow: var(--neo-pressed)` (track hundido), botón activo con elevación y text-shadow
  - Agregar `:active { transform: scale(0.96) }` a ambos
  - Agregar `:focus-visible` a ambos (si no se hizo en T1.3)

### T2.3 Side panel con borde prismático
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Líneas CSS:** 222-233 (`#panel`)
- **Qué hacer:** Reemplazar por la versión definida en `design.md` sección 3.4. Cambio clave:
  - Agregar `border-image: linear-gradient(...)` prismático
  - Usar `var(--blur-heavy)` en vez del valor hardcoded
  - Usar `var(--transition-panel)` para la transición

### T2.4 Flow cards con radius orgánico viridiformista
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Líneas CSS:** 182-194 (`.flow-card`)
- **Qué hacer:** Reemplazar por la versión definida en `design.md` sección 3.5. Cambios clave:
  - `border-radius: var(--radius-organic)` (asimétrico)
  - `box-shadow: var(--neo-raised)`
  - Agregar `:active { transform: scale(0.99) }`

### T2.5 Toolbar con textura metal skeuomórfica
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Líneas CSS:** 96-99 (`#toolbar`)
- **Qué hacer:** Si no se hizo en T1.1, aplicar ahora. Usar `background: var(--sku-metal)` y agregar bordes diferenciados (border-top claro, border-bottom oscuro) que simulen un panel metálico con profundidad.

### T2.6 Fondo body::before con tonos orgánicos
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Líneas CSS:** 47-59 (`body::before`)
- **Qué hacer:**
  1. Reemplazar los gradientes: cambiar el purple por `var(--organic-green)`, agregar un 4to gradiente con `var(--organic-moss)`.
  2. Cambiar la animación de `infinite alternate` a `3s ease-out forwards` (una sola ejecución):
     ```css
     animation: meshShift 3s ease-out forwards;
     ```
  3. Cambiar el keyframe:
     ```css
     @keyframes meshShift {
       0% { opacity: 0; transform: scale(1.05); }
       100% { opacity: 1; transform: scale(1); }
     }
     ```
- **Rendimiento:** Elimina la animación infinita que mantenía la GPU activa permanentemente.

---

## Fase 3 — UX polish

### T3.1 Skeleton loading en panel de detalle
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Qué hacer:**
  1. **CSS:** Agregar el bloque `.skeleton` definido en `design.md` sección 3.7.
  2. **JS en `showAppDetail`** (~línea 1124): Reemplazar `'Cargando detalles...'` por:
     ```javascript
     content.innerHTML = '<div class="skeleton skeleton-line full"></div>'
       + '<div class="skeleton skeleton-line medium"></div>'
       + '<div class="skeleton skeleton-line short"></div>'
       + '<div style="margin-top:16px"><div class="skeleton skeleton-line full"></div>'
       + '<div class="skeleton skeleton-line medium"></div></div>';
     ```
  3. **JS en `switchToMicro`** (~línea 1210): Reemplazar el empty state por skeleton blocks.

### T3.2 Toast/snackbar en vez de tooltip centrado
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Qué hacer:**
  1. **CSS:** Agregar el bloque `.toast` definido en `design.md` sección 3.8.
  2. **HTML:** Agregar `<div id="toast" class="toast"></div>` en el body.
  3. **JS:** Reescribir `showTooltipMessage` para usar el toast:
     ```javascript
     function showTooltipMessage(msg) {
       _clearTooltipTimer();
       var toast = document.getElementById('toast');
       toast.textContent = msg;
       toast.classList.add('visible');
       _tooltipTimer = setTimeout(function() {
         toast.classList.remove('visible');
         _tooltipTimer = null;
       }, 3000);
     }
     ```

### T3.3 Cursor pointer en nodos y edges de Cytoscape
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Qué hacer:** En el array `macroStyles`:
  1. En `node[type="app"]` style (~línea 838): agregar `'cursor': 'pointer'`
  2. En `edge[type="coupling"]` style (~línea 860): agregar `'cursor': 'pointer'`
  3. En los estilos de constelación (~línea 1966): agregar `'cursor': 'pointer'` al selector `node`

### T3.4 Leyenda: opacity 0.75 y empezar expandida
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Qué hacer:**
  1. **CSS línea 275:** Cambiar `opacity: 0.5` a `opacity: 0.75`
  2. **CSS:** Agregar `#legend { cursor: pointer; }` y `#legend:hover { transform: translateY(-2px); }`
  3. **HTML línea 793:** Cambiar `class="legend-header"` a `class="legend-header expanded"`
  4. **HTML línea 794:** Quitar `collapsed` de la clase del botón, cambiar `aria-expanded` a `"true"`, cambiar `&#9654;` a `&#9660;`
  5. **HTML línea 796:** Quitar `collapsed` de la clase del content

### T3.5 Padding micro view
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Línea CSS 158:** Cambiar `padding: 100px 48px 48px` a `padding: 88px 32px 32px`

---

## Fase 4 — Unificación visual de Cytoscape

### T4.1 Estilos constelación unificados con ecosistema
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Líneas JS:** 1966-1989 (estilos de constelación en `renderConstellation`)
- **Qué hacer:** Reemplazar los estilos inline de la constelación por la versión definida en `design.md` sección 4 (Constelación). Cambios clave:
  - Nodos: `round-rectangle` 140×70 (no cuadrados 60×60)
  - Colores: usar `rgba(10,132,255,...)` con opacidad (no colores planos como `#1c1c1e`)
  - Sombras suaves como en ecosistema
  - `idealEdgeLength: 220` (no 150)
  - Agregar `'cursor': 'pointer'` a nodos

### T4.2 Extraer constantes de estilo compartidas
- **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Qué hacer:** En el bloque `<script>`, al inicio (después de las variables de estado):
  1. Definir `NLVS_NODE_BASE`, `NLVS_EDGE_BASE`, y `NLVS_HEALTH_COLORS` como constantes (ver `design.md` sección 4)
  2. Refactorizar `macroStyles` para usar spread: `{ selector: 'node[type="app"]', style: { ...NLVS_NODE_BASE, width: 180, ... } }`
  3. Refactorizar estilos de constelación para usar spread: `{ selector: 'node', style: { ...NLVS_NODE_BASE, width: 140, ... } }`
  4. Refactorizar health colors: generar los selectores desde `NLVS_HEALTH_COLORS` en vez de hardcodearlos 2 veces

**NOTA:** Si el entorno JS del HTML no soporta spread operator (`...`), usar `Object.assign({}, NLVS_NODE_BASE, { width: 180, ... })` en su lugar.

---

## Orden de ejecución

```
Fase 0: T0.1 → T0.2 → T0.3 → T0.4
         ↓
Fase 1: T1.1 → T1.2 → T1.3 → T1.4
         ↓
Fase 2: T2.1 → T2.2 → T2.3 → T2.4 → T2.5 → T2.6
         ↓
Fase 3: T3.1 → T3.2 → T3.3 → T3.4 → T3.5
         ↓
Fase 4: T4.1 → T4.2
```

**Fase 0 es prerequisito de todo.** Las Fases 1-3 pueden ejecutarse en paralelo si se desea, pero el orden recomendado es secuencial para evitar conflictos de merge en el mismo archivo.

## Resumen de impacto

| Fase | Tareas | Cambios | Riesgo |
|------|--------|---------|--------|
| 0 | 4 | Variables CSS + light theme + traducciones + scrollbar | Bajo — no cambia estructura |
| 1 | 4 | Toolbar wrap + español + accesibilidad + panel constellation | Medio — toca HTML y JS |
| 2 | 6 | Componentes NLVS: glass, botones, panel, cards, toolbar, fondo | Medio — cambios CSS significativos |
| 3 | 5 | Skeleton, toast, cursor, leyenda, padding | Bajo — polish puntual |
| 4 | 2 | Cytoscape unificado | Bajo — solo estilos JS |
