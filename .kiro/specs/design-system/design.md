# NLVS Design System — Especificación Completa

> **NLVS** = **N**eomorfismo + **L**iquid Glass + **V**iridiformismo + **S**keuomorfismo
>
> Este documento es la fuente de verdad para toda UI del MCP_HU_SegurosBolivar.
> Cualquier agente (LLM, IDE, humano) que toque archivos de visualización DEBE seguir esta especificación.

---

## 1. Filosofía de diseño

El sistema NLVS combina 4 corrientes de diseño en capas complementarias:

| Capa | Qué aporta | Dónde se aplica | Restricción de rendimiento |
|------|-----------|-----------------|---------------------------|
| **Neomorfismo** | Profundidad táctil: botones elevados/hundidos con dual-shadow | Botones, toggles, cards interactivas | Max 2 box-shadow por elemento |
| **Liquid Glass** | Transparencia con profundidad: blur variable, refracción, bordes prismáticos | Paneles, toolbar, overlays | Max 3 elementos con `backdrop-filter` visibles simultáneamente |
| **Viridiformismo** | Organicidad: gradientes naturales, border-radius asimétricos, tonos vegetales | Fondo, paneles de detalle, flow cards | Solo gradientes CSS (no SVG patterns) |
| **Skeuomorfismo** | Metáfora física: switches mecánicos, LEDs, textura metálica | Toolbar, toggle-groups, filtros activos | No texturas como imagen — solo gradientes CSS |

**Regla general:** Cada capa se aplica con sutileza. La suma de las 4 no debe producir sobrecarga visual. Si un elemento ya tiene liquid glass (blur), no necesita neomorfismo pesado (dual-shadow grande). Si tiene viridiformismo (radius orgánico), el skeuomorfismo se limita a un LED indicator.

---

## 2. Design Tokens — Variables CSS

Estas variables son OBLIGATORIAS. Todo color, radio, sombra, y blur se referencia por variable. Nunca hardcodear.

### 2.1 Dark Theme (default)

```css
:root {
  /* ─── Superficies ─── */
  --bg: #000000;
  --surface: rgba(28,28,30,0.72);
  --surface-elevated: rgba(44,44,46,0.65);
  --surface-border: rgba(255,255,255,0.08);
  --surface-border-hover: rgba(255,255,255,0.15);

  /* ─── Texto ─── */
  --text-primary: rgba(255,255,255,0.92);
  --text-secondary: rgba(255,255,255,0.55);
  --text-tertiary: rgba(255,255,255,0.35);

  /* ─── Acentos ─── */
  --accent-blue: #0a84ff;
  --accent-purple: #bf5af2;
  --accent-orange: #ff9f0a;
  --accent-green: #30d158;
  --accent-red: #ff453a;
  --accent-teal: #64d2ff;

  /* ─── Orgánicos (viridiformismo) ─── */
  --organic-green: rgba(34,120,80,0.12);
  --organic-teal: rgba(40,140,130,0.08);
  --organic-moss: rgba(80,120,60,0.06);

  /* ─── Radios ─── */
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-xl: 20px;
  --radius-organic: 20px 16px 22px 14px; /* asimétrico orgánico */

  /* ─── Blur (Liquid Glass) ─── */
  --blur-light: blur(20px) saturate(1.4);
  --blur-medium: blur(40px) saturate(1.8) brightness(1.1);
  --blur-heavy: blur(60px) saturate(2) brightness(1.05);

  /* ─── Sombras neomórficas ─── */
  --neo-raised: 4px 4px 8px rgba(0,0,0,0.35), -2px -2px 6px rgba(255,255,255,0.03), inset 0 1px 0 rgba(255,255,255,0.06);
  --neo-pressed: inset 3px 3px 6px rgba(0,0,0,0.35), inset -2px -2px 4px rgba(255,255,255,0.02);
  --neo-panel: 0 0 0 0.5px rgba(255,255,255,0.06) inset, 0 8px 32px -8px rgba(0,0,0,0.5), 0 1px 0 rgba(255,255,255,0.05) inset, 6px 6px 16px rgba(0,0,0,0.3), -3px -3px 10px rgba(255,255,255,0.02);

  /* ─── Skeuomorfismo ─── */
  --sku-led-glow: 0 0 6px var(--accent-blue), 0 0 12px rgba(10,132,255,0.3);
  --sku-metal: linear-gradient(180deg, rgba(60,60,65,0.4) 0%, rgba(40,40,44,0.6) 50%, rgba(35,35,38,0.7) 100%);

  /* ─── Scrollbar ─── */
  --scrollbar-thumb: rgba(255,255,255,0.1);
  --scrollbar-thumb-hover: rgba(255,255,255,0.2);

  /* ─── Transiciones ─── */
  --transition-fast: 0.15s ease;
  --transition-normal: 0.25s cubic-bezier(0.25,1,0.5,1);
  --transition-panel: 0.35s cubic-bezier(0.4,0,0.2,1);
}
```

### 2.2 Light Theme

```css
@media (prefers-color-scheme: light) {
  :root {
    --bg: #f5f5f7;
    --surface: rgba(255,255,255,0.72);
    --surface-elevated: rgba(255,255,255,0.85);
    --surface-border: rgba(0,0,0,0.08);
    --surface-border-hover: rgba(0,0,0,0.15);

    --text-primary: rgba(0,0,0,0.88);
    --text-secondary: rgba(0,0,0,0.55);
    --text-tertiary: rgba(0,0,0,0.35);

    --accent-blue: #007aff;
    --accent-purple: #af52de;
    --accent-orange: #ff9500;
    --accent-green: #28a745;
    --accent-red: #ff3b30;
    --accent-teal: #5ac8fa;

    --organic-green: rgba(34,120,80,0.08);
    --organic-teal: rgba(40,140,130,0.06);
    --organic-moss: rgba(80,120,60,0.04);

    --blur-light: blur(20px) saturate(1.2);
    --blur-medium: blur(40px) saturate(1.4) brightness(1.05);
    --blur-heavy: blur(60px) saturate(1.6) brightness(1.02);

    --neo-raised: 3px 3px 6px rgba(0,0,0,0.06), -2px -2px 4px rgba(255,255,255,0.6), inset 0 1px 0 rgba(255,255,255,0.8);
    --neo-pressed: inset 2px 2px 4px rgba(0,0,0,0.06), inset -1px -1px 3px rgba(255,255,255,0.3);
    --neo-panel: 0 0 0 0.5px rgba(0,0,0,0.04) inset, 0 8px 32px -8px rgba(0,0,0,0.12), 0 1px 0 rgba(255,255,255,0.8) inset, 4px 4px 12px rgba(0,0,0,0.08), -2px -2px 8px rgba(255,255,255,0.5);

    --sku-led-glow: 0 0 4px var(--accent-blue), 0 0 8px rgba(0,122,255,0.2);
    --sku-metal: linear-gradient(180deg, rgba(240,240,244,0.85) 0%, rgba(230,230,234,0.9) 100%);

    --scrollbar-thumb: rgba(0,0,0,0.12);
    --scrollbar-thumb-hover: rgba(0,0,0,0.2);
  }
}
```

### 2.3 Mapa de traducción UI (español)

Todos los textos visibles al usuario están en español. Los data attributes permanecen en inglés.

```javascript
const UI_LABELS = {
  maturity: { formalized: 'Formalizado', draft: 'Borrador', reference: 'Referencia' },
  health: { green: 'Saludable', yellow: 'Con alertas', red: 'Con conflictos' },
  coupling: { cohesive: 'Cohesivo', decoupled: 'Desacoplado', coupled: 'Acoplado' },
  sync_type: { sync: 'Síncrona', async: 'Asíncrona', mixed: 'Mixta', implicit: 'Implícita' },
  contract_status: { active: 'Activo', draft: 'Borrador', deprecated: 'Deprecado' },
};
```

---

## 3. Catálogo de componentes

### 3.1 Glass Panel (contenedor principal)

**Filosofías:** Liquid Glass (blur + refracción) + Neomorfismo (dual-shadow)

```css
.glass-panel {
  position: relative;
  background: linear-gradient(135deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.02) 100%);
  border: 1px solid var(--surface-border);
  backdrop-filter: var(--blur-medium);
  -webkit-backdrop-filter: var(--blur-medium);
  border-radius: var(--radius-lg);
  box-shadow: var(--neo-panel);
}

/* Capa de refracción liquid glass */
.glass-panel::before {
  content: '';
  position: absolute; inset: 0;
  border-radius: inherit;
  background: linear-gradient(135deg,
    rgba(255,255,255,0.08) 0%,
    rgba(255,255,255,0.01) 40%,
    rgba(255,255,255,0.04) 70%,
    rgba(255,255,255,0.0) 100%
  );
  pointer-events: none;
  z-index: 1;
}
```

**Rendimiento:** El `::before` NO lleva `backdrop-filter` adicional — solo es un gradiente estático que simula refracción sin costo de GPU.

### 3.2 Botón de filtro

**Filosofías:** Neomorfismo (elevado/hundido) + Skeuomorfismo (LED cuando activo)

```css
.filter-btn {
  background: linear-gradient(145deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%);
  border: 1px solid var(--surface-border);
  color: var(--text-secondary);
  padding: 5px 14px;
  border-radius: var(--radius-md);
  font-size: 11px;
  cursor: pointer;
  transition: all var(--transition-normal);
  box-shadow: var(--neo-raised);
}

.filter-btn:hover {
  border-color: var(--surface-border-hover);
  color: var(--text-primary);
}

.filter-btn:active {
  transform: scale(0.96);
  transition-duration: 0.1s;
}

.filter-btn:focus-visible {
  outline: 2px solid var(--accent-blue);
  outline-offset: 2px;
}

/* Estado activo: hundido + LED */
.filter-btn.active {
  background: linear-gradient(135deg, rgba(10,132,255,0.2) 0%, rgba(10,132,255,0.08) 100%);
  border-color: rgba(10,132,255,0.35);
  color: var(--accent-blue);
  box-shadow: var(--neo-pressed), 0 0 12px rgba(10,132,255,0.1);
}

/* LED indicator skeuomórfico */
.filter-btn.active::before {
  content: '';
  display: inline-block;
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--accent-blue);
  box-shadow: var(--sku-led-glow);
  margin-right: 6px;
  vertical-align: middle;
}
```

### 3.3 Toggle Group

**Filosofías:** Skeuomorfismo (track hundido) + Neomorfismo (opción activa elevada)

```css
.toggle-group {
  display: flex;
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--surface-border);
  background: rgba(0,0,0,0.3);
  box-shadow: var(--neo-pressed);
  position: relative;
}

.toggle-group button {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  padding: 5px 14px;
  font-size: 11px;
  cursor: pointer;
  transition: all var(--transition-normal);
  position: relative;
  z-index: 1;
}

.toggle-group button:active { transform: scale(0.96); transition-duration: 0.1s; }
.toggle-group button:focus-visible { outline: 2px solid var(--accent-blue); outline-offset: -2px; }

.toggle-group button.active {
  color: #fff;
  text-shadow: 0 0 8px rgba(10,132,255,0.4);
  background: linear-gradient(135deg, rgba(10,132,255,0.3) 0%, rgba(10,132,255,0.15) 100%);
  box-shadow: 0 2px 8px rgba(10,132,255,0.2), inset 0 1px 0 rgba(255,255,255,0.1);
}
```

### 3.4 Side Panel (detalle)

**Filosofías:** Liquid Glass (blur pesado + borde prismático) + Viridiformismo (gradiente orgánico)

```css
#panel {
  position: fixed; top: 40px; right: 0; bottom: 0; width: 380px;
  background: linear-gradient(180deg, rgba(36,36,40,0.85) 0%, rgba(22,22,26,0.92) 100%);
  backdrop-filter: var(--blur-heavy);
  -webkit-backdrop-filter: var(--blur-heavy);
  z-index: 95;
  display: flex; flex-direction: column;
  transform: translateX(100%); opacity: 0; pointer-events: none;
  transition: transform var(--transition-panel), opacity 0.3s ease;
  overflow-y: auto;
  /* Borde prismático liquid glass */
  border-left: 1px solid transparent;
  border-image: linear-gradient(180deg,
    rgba(10,132,255,0.2) 0%,
    rgba(191,90,242,0.15) 30%,
    rgba(34,120,80,0.1) 60%,
    rgba(255,159,10,0.08) 100%
  ) 1;
  box-shadow: -8px 0 40px rgba(0,0,0,0.4), inset 1px 0 0 rgba(255,255,255,0.04);
}

#panel.open { transform: translateX(0); opacity: 1; pointer-events: auto; }
```

**Regla:** Todo panel nuevo (incluyendo constellation-detail) DEBE seguir este patrón: HTML estático + clase `.open` + transición CSS. NUNCA `document.createElement`.

### 3.5 Flow Card (vista micro)

**Filosofías:** Viridiformismo (radius orgánico) + Neomorfismo (elevación)

```css
.flow-card {
  background: linear-gradient(145deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.015) 100%);
  border: 1px solid var(--surface-border);
  backdrop-filter: var(--blur-light);
  -webkit-backdrop-filter: var(--blur-light);
  border-radius: var(--radius-organic); /* ← asimétrico orgánico */
  padding: 18px;
  cursor: pointer;
  transition: all var(--transition-normal);
  box-shadow: var(--neo-raised);
}

.flow-card:hover {
  border-color: rgba(10,132,255,0.3);
  transform: translateY(-2px);
  box-shadow: var(--neo-raised), 0 0 20px rgba(10,132,255,0.05);
}

.flow-card:active { transform: scale(0.99) translateY(0); }
```

### 3.6 Toolbar

**Filosofías:** Skeuomorfismo (textura metal) + Liquid Glass (blur)

```css
#toolbar {
  position: fixed; top: 48px; left: 16px; right: 16px; z-index: 90;
  display: flex; align-items: center; gap: 10px;
  padding: 8px 16px; font-size: 12px;
  flex-wrap: wrap; /* ← OBLIGATORIO para responsive */
  background: var(--sku-metal);
  backdrop-filter: var(--blur-medium);
  -webkit-backdrop-filter: var(--blur-medium);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-lg);
  border-top: 1px solid rgba(255,255,255,0.06);
  border-bottom: 1px solid rgba(0,0,0,0.3);
  box-shadow: var(--neo-panel);
}
```

### 3.7 Loading states

**Skeleton shimmer** (reemplaza texto "Cargando..."):

```css
.skeleton {
  background: linear-gradient(90deg,
    rgba(255,255,255,0.04) 25%,
    rgba(255,255,255,0.08) 50%,
    rgba(255,255,255,0.04) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
  border-radius: var(--radius-sm);
}
.skeleton-line { height: 12px; margin-bottom: 8px; }
.skeleton-line.short { width: 60%; }
.skeleton-line.medium { width: 80%; }
.skeleton-line.full { width: 100%; }

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

**Spinner** (para layout de Cytoscape — ÚNICA animación infinita permitida):

```css
.loading-overlay {
  position: absolute; inset: 0; z-index: 50;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.3);
  backdrop-filter: blur(4px);
  pointer-events: none;
}
.loading-spinner {
  width: 32px; height: 32px;
  border: 3px solid rgba(255,255,255,0.1);
  border-top-color: var(--accent-blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
```

### 3.8 Toast/Snackbar (reemplaza tooltip centrado)

```css
.toast {
  position: fixed;
  bottom: 24px; left: 50%;
  transform: translateX(-50%) translateY(20px);
  opacity: 0;
  background: var(--surface-elevated);
  border: 1px solid var(--surface-border);
  backdrop-filter: var(--blur-light);
  -webkit-backdrop-filter: var(--blur-light);
  border-radius: var(--radius-md);
  padding: 10px 20px;
  font-size: 12px;
  color: var(--text-primary);
  box-shadow: var(--neo-raised);
  transition: all 0.3s ease;
  z-index: 200;
  pointer-events: none;
}
.toast.visible {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}
```

---

## 4. Nodos Cytoscape — Vocabulario visual unificado

TODAS las vistas (Ecosistema, Constelación, futuras) DEBEN usar estos estilos base:

```javascript
/* ─── Estilos base compartidos ─── */
const NLVS_NODE_BASE = {
  'shape': 'round-rectangle',
  'background-opacity': 0.7,
  'border-width': 1,
  'font-weight': 500,
  'text-valign': 'center',
  'text-halign': 'center',
  'color': 'rgba(255,255,255,0.92)',
  'text-wrap': 'wrap',
  'overlay-opacity': 0,
  'cursor': 'pointer',  /* ← OBLIGATORIO */
};

const NLVS_EDGE_BASE = {
  'curve-style': 'bezier',
  'font-size': 9,
  'color': 'rgba(255,255,255,0.5)',
  'text-outline-color': 'rgba(0,0,0,0.8)',
  'text-outline-width': 2,
  'cursor': 'pointer',  /* ← OBLIGATORIO si es clickeable */
};

/* ─── Health: colores compartidos ─── */
const NLVS_HEALTH_COLORS = {
  green:  { border: 'rgba(34,140,80,0.5)',  shadow: 'rgba(34,140,80,0.18)' },  /* verde orgánico */
  yellow: { border: 'rgba(255,159,10,0.4)', shadow: 'rgba(255,159,10,0.15)' },
  red:    { border: 'rgba(255,69,58,0.5)',  shadow: 'rgba(255,69,58,0.2)' },
};
```

### Ecosistema (Macro)
```javascript
/* Nodos: 180×90, sombra suave, text-max-width 160 */
{ selector: 'node[type="app"]', style: {
  ...NLVS_NODE_BASE,
  'width': 180, 'height': 90,
  'background-color': 'rgba(10,132,255,0.05)',
  'border-color': 'rgba(10,132,255,0.35)',
  'font-size': 13,
  'text-max-width': 160,
  'shadow-blur': 28, 'shadow-color': 'rgba(10,132,255,0.15)', 'shadow-opacity': 0.6,
  'shadow-offset-x': 0, 'shadow-offset-y': 4,
}}
```

### Constelación (DEPRECADO — migrar a SVG radial)

> **⚠️ A partir de v1.1.0, la constelación usa SVG radial tree (sección 10), NO Cytoscape.**
> Los estilos Cytoscape de abajo se mantienen solo como referencia durante la migración.
> Una vez completada la migración (Fase 5 en tasks.md), eliminar esta sección.

```javascript
/* DEPRECADO — usar renderConstellationTree() de sección 10.4 en su lugar */
/* Nodos: 140×70, misma paleta, misma forma */
{ selector: 'node', style: {
  ...NLVS_NODE_BASE,
  'width': 140, 'height': 70,
  'background-color': 'rgba(10,132,255,0.05)',
  'border-color': 'rgba(10,132,255,0.35)',
  'font-size': 11,
  'text-max-width': 120,
  'shadow-blur': 20, 'shadow-color': 'rgba(10,132,255,0.12)', 'shadow-opacity': 0.5,
  'shadow-offset-x': 0, 'shadow-offset-y': 3,
}}
```

### Layout Config (compartido)
```javascript
const NLVS_LAYOUT = {
  name: 'cose-bilkent',
  quality: 'default',        /* NUNCA 'proof' */
  animate: 'end',             /* NUNCA true */
  animationDuration: 400,     /* máximo 500ms */
  nodeDimensionsIncludeLabels: true,
  nodeRepulsion: 10000,
  edgeElasticity: 0.3,
  nestingFactor: 0.15,
  gravity: 0.2,
  tile: true,
  tilingPaddingVertical: 40,
  tilingPaddingHorizontal: 40,
  fit: true,
  padding: 60,
};

/* Ecosistema: idealEdgeLength 250 */
/* Constelación: idealEdgeLength 220 */
/* Nuevas vistas: idealEdgeLength entre 200-280 */
```

---

## 5. Accesibilidad — Checklist obligatorio

### 5.1 Estructura semántica
```html
<!-- Nav -->
<nav class="view-selector" role="tablist" aria-label="Vistas del ecosistema">
  <a class="view-tab" role="tab" aria-selected="false">...</a>
  <a class="view-tab active" role="tab" aria-selected="true">...</a>
</nav>

<!-- Filtros toggle -->
<button class="filter-btn active" aria-label="Filtrar integración síncrona" aria-pressed="true">Síncrona</button>

<!-- Leyenda colapsable -->
<button id="legend-toggle-btn" aria-label="Expandir leyenda" aria-expanded="false">▶</button>
```

### 5.2 Focus visible (CSS obligatorio)
```css
.view-tab:focus-visible,
.filter-btn:focus-visible,
.toggle-group button:focus-visible,
.back-btn:focus-visible,
.close-btn:focus-visible,
.diagram-tab:focus-visible,
#toolbar select:focus-visible {
  outline: 2px solid var(--accent-blue);
  outline-offset: 2px;
}
```

### 5.3 Actualización dinámica de aria en JS

Cuando un toggle cambia de estado, SIEMPRE actualizar los atributos:

```javascript
/* En toggleFilter, toggleMaturityFilter, etc: */
btn.setAttribute('aria-pressed', String(nuevoEstado));

/* En switchTab: */
tabs.forEach(t => t.setAttribute('aria-selected', 'false'));
tabActivo.setAttribute('aria-selected', 'true');

/* En toggleLegend: */
btn.setAttribute('aria-expanded', String(!collapsed));
```

---

## 6. Restricciones de rendimiento

### 6.1 Animaciones CSS

| Tipo | Permitido | Ejemplo |
|------|-----------|---------|
| `animation: infinite` | SOLO `.loading-spinner` | `spin 0.8s linear infinite` |
| `animation: forwards` (una sola vez) | Sí | `meshShift 3s ease-out forwards` para intro del fondo |
| `transition` en hover/active | Sí, ≤ 0.3s | `all 0.25s cubic-bezier(...)` |
| `animation: infinite` decorativa | PROHIBIDO | ~~`meshShift 20s infinite alternate`~~ |

### 6.2 backdrop-filter

Máximo **3 elementos simultáneamente visibles** con `backdrop-filter`. Los paneles que están `display:none` o `transform:translateX(100%)` no cuentan.

Elementos que lo usan (por prioridad):
1. `#toolbar` — siempre visible
2. `#panel` — solo cuando `.open`
3. `#tooltip` — solo cuando `.visible`
4. `.loading-overlay` — temporal durante layout

Si se necesita un 5to, quitar el blur del tooltip o del loading.

### 6.3 Cytoscape

| Parámetro | Valor | Por qué |
|-----------|-------|---------|
| `quality` | `'default'` | `'proof'` es 3-10x más lento sin diferencia visible |
| `animate` | `'end'` | `true` anima cada iteración del layout (GPU waste) |
| `animationDuration` | `400` | Suficiente para transición suave |
| MAX_VISIBLE_NODES | `80` | Más nodos = layout exponencial. Usar `collapseSmallNodes()` |

### 6.4 Fondo body::before

```css
body::before {
  /* Gradientes estáticos — NO animación infinita */
  animation: meshShift 3s ease-out forwards; /* UNA sola vez al cargar */
}
@keyframes meshShift {
  0% { opacity: 0; transform: scale(1.05); }
  100% { opacity: 1; transform: scale(1); }
}
```

### 6.5 Lazy loading de vistas

Solo la vista activa carga datos. Las demás marcan un flag y cargan cuando se activan:

```javascript
let constellationLoaded = false;

function switchToConstellation() {
  /* ... cambiar visibilidad ... */
  if (!constellationLoaded) {
    loadConstellation();
    constellationLoaded = true;
  }
}

function switchEcosystem(id) {
  constellationLoaded = false; /* forzar recarga cuando se active */
  /* solo cargar vista activa */
}
```

### 6.6 Cache backend

La API usa cache con invalidación por evento (no TTL puro). El cache se invalida cuando:
- Se registra/modifica una app
- Se crea/modifica un contrato
- Se sincroniza el ecosistema

Ver `ecosystem_visualizer.py: invalidate_graph_cache()`.

---

## 7. Scrollbar dual-engine

SIEMPRE definir para ambos motores de rendering:

```css
/* Firefox */
* {
  scrollbar-width: thin;
  scrollbar-color: var(--scrollbar-thumb) transparent;
}
/* Webkit (Chrome, Edge, Safari) */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--scrollbar-thumb-hover); }
```

---

## 8. Reglas de creación de nuevos componentes

Cuando un agente necesite crear un componente nuevo:

### 8.1 Checklist pre-implementación
- [ ] ¿Usa SOLO variables de `:root`? (no hardcoded colors)
- [ ] ¿Funciona en dark Y light theme?
- [ ] ¿Tiene `:hover`, `:active`, `:focus-visible`?
- [ ] ¿Tiene `aria-label` o `role` apropiado?
- [ ] ¿Tiene `cursor: pointer` si es clickeable?
- [ ] ¿Usa clase CSS (no inline styles)?
- [ ] ¿El border-radius viene de una variable?
- [ ] ¿Las sombras usan `var(--neo-raised)` o `var(--neo-pressed)`?
- [ ] ¿Respeta el budget de backdrop-filter (≤3 simultáneos)?
- [ ] ¿Las animaciones son finitas (no infinite)?

### 8.2 Selección de filosofía por tipo de componente

| Tipo de componente | Filosofía primaria | Filosofía secundaria |
|--------------------|--------------------|----------------------|
| Panel/overlay | Liquid Glass | Viridiformismo (borde prismático) |
| Botón/toggle | Neomorfismo | Skeuomorfismo (LED activo) |
| Card/flow | Viridiformismo | Neomorfismo (elevación) |
| Toolbar/nav | Skeuomorfismo | Liquid Glass (blur) |
| Input/select | Neomorfismo | — |
| Tooltip/toast | Liquid Glass | — |
| Loading state | — | — (minimal) |

### 8.3 Anti-patrones (NUNCA hacer)

- ❌ `document.createElement` para paneles → usar HTML estático + clase `.open`
- ❌ `style="..."` inline en JS → usar clases CSS
- ❌ Tooltip centrado en pantalla → usar toast/snackbar posicionado abajo
- ❌ Google Fonts o CDN externo → system font stack o `/static/vendor/`
- ❌ `animation: infinite` decorativa → `forwards` una sola vez
- ❌ `quality: 'proof'` en Cytoscape → `'default'`
- ❌ Textos en inglés en la UI → TODO en español
- ❌ Scrollbar solo Webkit → agregar reglas Firefox
- ❌ Nodos de Cytoscape sin `cursor: pointer` → SIEMPRE agregar
- ❌ Crear segunda instancia de Cytoscape con estilos diferentes → usar `NLVS_NODE_BASE`

---

## 9. Estructura de archivos

```
src/engine/
├── ecosystem_visualizer_ui.html   ← UI ecosistema (single-file con CSS+JS)
├── ecosystem_visualizer.py        ← Backend API ecosistema
├── visualizer_ui.html             ← UI red neuronal (single-file)
└── visualizer.py                  ← Servidor Starlette + rutas

static/vendor/                     ← Dependencias JS bundleadas (NO CDN)
├── cytoscape.min.js
├── layout-base.js
├── cose-base.js
└── cytoscape-cose-bilkent.js

.kiro/steering/design-system.md    ← Reglas para agentes (auto-inyectado)
.kiro/specs/design-system/
├── design.md                      ← ESTE DOCUMENTO
└── tasks.md                       ← Plan de implementación
```

---

## 10. Referente Visual — Árbol Radial SVG (SkillTree)

> Referente: [SkillTree Map](https://skilltree.altari.ai/) — sección "Audit Engine" (árbol radial SVG)
>
> La constelación de specs DEBE renderizarse como SVG radial tree en vez de Cytoscape.
> Cytoscape permanece solo para la vista Ecosistema (macro/micro graph).

### 10.1 Arquitectura del árbol

El árbol radial tiene 3 niveles jerárquicos:

| Nivel | Qué representa | Radio SVG | Color base |
|-------|----------------|-----------|------------|
| **Raíz** (1 nodo central) | El ecosistema | `r=10` | `var(--accent-blue)` |
| **Ramas** (agrupadores) | Categorías de specs (por status o por capa SDD) | `r=6` | `var(--text-tertiary)` surface |
| **Hojas** (N nodos) | Cada ProjectSpec individual | `r=4` | Por status: approved=green, draft=orange, superseded=red |

**Agrupación de specs en ramas:** Agrupar por `status` del spec:
- Rama "Aprobados" → specs con `status: 'approved'`
- Rama "Borradores" → specs con `status: 'draft'`
- Rama "Supersedidos" → specs con `status: 'superseded'`

Si una rama tiene 0 specs, no se renderiza. Si hay más de 8 hojas en una rama, distribuir en sub-ramas de máximo 8.

### 10.2 Estructura SVG

```html
<div id="constellation-tree" class="constellation-tree-container">
  <!-- KPI Counter (P5) -->
  <div class="constellation-kpi">
    <span class="kpi-count" id="kpi-approved">0</span>
    <span class="kpi-label">de</span>
    <span class="kpi-total" id="kpi-total">0</span>
    <span class="kpi-label">specs aprobadas</span>
  </div>

  <svg id="constellation-svg" viewBox="0 0 700 500" preserveAspectRatio="xMidYMid meet">
    <g class="tree-links"><!-- líneas conectoras --></g>
    <g class="tree-nodes"><!-- círculos: raíz, ramas, hojas --></g>
    <g class="tree-labels"><!-- texto de cada spec --></g>
  </svg>

  <!-- Scanning status (P4) -->
  <div class="constellation-scan-status" id="scan-status">
    <span class="scan-dot"></span>
    <span class="scan-text">Analizando ecosistema…</span>
  </div>
</div>
```

### 10.3 CSS del árbol radial

```css
/* ─── Contenedor del árbol ─── */
.constellation-tree-container {
  position: fixed; top: 40px; left: 0; right: 0; bottom: 0;
  display: none; z-index: 1;
  background: var(--bg);
  overflow: hidden;
}
.constellation-tree-container.active { display: block; }

/* ─── SVG Tree ─── */
#constellation-svg {
  width: 100%; height: 100%;
}

/* ─── Links (líneas conectoras) ─── */
.tree-link {
  stroke: var(--surface-border);
  stroke-width: 1;
  fill: none;
  opacity: 0;
  transition: opacity 0.4s ease;
}
.tree-link.visible { opacity: 1; }

/* ─── Nodos ─── */
.tree-node {
  fill: var(--surface);
  stroke: var(--surface-border);
  stroke-width: 1;
  cursor: pointer;
  opacity: 0;
  transform: scale(0.6);
  transform-origin: center;
  transition: opacity 0.4s ease, transform 0.4s ease, fill 0.3s ease, filter 0.3s ease;
}
.tree-node.loaded {
  opacity: 1;
  transform: scale(1);
}
.tree-node:hover {
  stroke-width: 1.5;
  filter: brightness(1.2);
}

/* ─── Nodo raíz (ecosistema) ─── */
.tree-node-root {
  fill: var(--accent-blue);
  stroke: rgba(10,132,255,0.5);
  stroke-width: 1.5;
}

/* ─── Nodos rama (agrupadores) ─── */
.tree-node-branch {
  fill: var(--surface-elevated);
  stroke: var(--surface-border-hover);
}

/* ─── Nodos hoja (specs) — color por status ─── */
.tree-node-leaf[data-status="approved"] {
  fill: var(--accent-green);
  stroke: rgba(48,209,88,0.5);
}
.tree-node-leaf[data-status="draft"] {
  fill: var(--accent-orange);
  stroke: rgba(255,159,10,0.5);
}
.tree-node-leaf[data-status="superseded"] {
  fill: var(--accent-red);
  stroke: rgba(255,69,58,0.5);
}

/* ─── P3: Glow semántico — solo en specs con gaps/alertas ─── */
.tree-node-leaf.has-gaps {
  filter: drop-shadow(0 0 6px var(--accent-orange));
  animation: pulseGlow 2s ease-in-out 3; /* 3 repeticiones, NO infinite */
}
@keyframes pulseGlow {
  0%, 100% { filter: drop-shadow(0 0 6px var(--accent-orange)); }
  50% { filter: drop-shadow(0 0 12px var(--accent-orange)); }
}

/* ─── Labels ─── */
.tree-label {
  font-family: system-ui, -apple-system, sans-serif; /* NO serif como SkillTree */
  font-size: 9px;
  fill: var(--text-secondary);
  text-anchor: middle;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.4s ease;
}
.tree-label.visible { opacity: 1; }
.tree-label-branch {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  fill: var(--text-tertiary);
}
.tree-label-root {
  font-size: 12px;
  font-weight: 700;
  fill: var(--text-primary);
}
```

### 10.4 JS del árbol radial — Lógica de renderizado

```javascript
/**
 * Renderiza la constelación como SVG radial tree.
 * Reemplaza completamente el renderizado con Cytoscape para esta vista.
 *
 * @param {Object} data - Respuesta de /api/constellation/{id}
 *   data.nodes: [{data: {id, label, status, layers_count, has_strategic, approved_by, app_id}}]
 *   data.edges: [{data: {source, target, dependency_type, maturity}}]
 */
function renderConstellationTree(data) {
  const svg = document.getElementById('constellation-svg');
  if (!svg) return;

  // Limpiar SVG previo
  svg.querySelector('.tree-links').innerHTML = '';
  svg.querySelector('.tree-nodes').innerHTML = '';
  svg.querySelector('.tree-labels').innerHTML = '';

  const nodes = (data.nodes || []).map(n => n.data);
  const totalSpecs = nodes.length;
  const approved = nodes.filter(n => n.status === 'approved').length;

  // Actualizar KPI (P5)
  document.getElementById('kpi-approved').textContent = approved;
  document.getElementById('kpi-total').textContent = totalSpecs;

  // Agrupar specs por status → ramas
  const groups = {};
  const groupLabels = { approved: 'Aprobados', draft: 'Borradores', superseded: 'Supersedidos' };
  nodes.forEach(function(n) {
    const key = n.status || 'draft';
    if (!groups[key]) groups[key] = [];
    groups[key].push(n);
  });

  const branchKeys = Object.keys(groups).filter(k => groups[k].length > 0);
  const cx = 350, cy = 250; // Centro del SVG (viewBox 700×500)
  const branchRadius = 120;  // Distancia raíz → rama
  const leafRadius = 80;     // Distancia rama → hoja

  // Calcular posiciones radiales de las ramas
  const branches = branchKeys.map(function(key, i) {
    const angle = (2 * Math.PI * i / branchKeys.length) - Math.PI / 2;
    return {
      key: key,
      label: groupLabels[key] || key,
      x: cx + branchRadius * Math.cos(angle),
      y: cy + branchRadius * Math.sin(angle),
      angle: angle,
      specs: groups[key],
    };
  });

  // Generar SVG elements
  var linksHtml = '';
  var nodesHtml = '';
  var labelsHtml = '';
  var animIndex = 0;

  // Raíz → Ramas (links)
  branches.forEach(function(b) {
    linksHtml += '<line class="tree-link" x1="' + cx + '" y1="' + cy
      + '" x2="' + b.x + '" y2="' + b.y + '" style="transition-delay:'
      + (animIndex * 30) + 'ms" />';
  });

  // Rama → Hojas (links + positions)
  branches.forEach(function(b) {
    var leafCount = b.specs.length;
    var spreadAngle = Math.min(Math.PI * 0.6, leafCount * 0.25); // Ángulo de apertura

    b.specs.forEach(function(spec, j) {
      var leafAngle = b.angle - spreadAngle / 2 + (spreadAngle * j / Math.max(1, leafCount - 1));
      if (leafCount === 1) leafAngle = b.angle;
      spec._x = b.x + leafRadius * Math.cos(leafAngle);
      spec._y = b.y + leafRadius * Math.sin(leafAngle);
      spec._animDelay = (animIndex + j + 1) * 30;

      linksHtml += '<line class="tree-link" x1="' + b.x + '" y1="' + b.y
        + '" x2="' + spec._x + '" y2="' + spec._y + '" style="transition-delay:'
        + spec._animDelay + 'ms" />';
    });
    animIndex += leafCount + 1;
  });

  // Nodo raíz
  nodesHtml += '<circle class="tree-node tree-node-root" cx="' + cx + '" cy="' + cy
    + '" r="10" style="transition-delay:0ms" />';
  labelsHtml += '<text class="tree-label tree-label-root" x="' + cx + '" y="' + (cy + 24)
    + '" style="transition-delay:50ms">Ecosistema</text>';

  // Nodos rama + labels
  branches.forEach(function(b, i) {
    var delay = (i + 1) * 60;
    nodesHtml += '<circle class="tree-node tree-node-branch" cx="' + b.x + '" cy="' + b.y
      + '" r="6" style="transition-delay:' + delay + 'ms" />';

    // Label posicionado fuera del radio
    var labelX = cx + (branchRadius + 20) * Math.cos(b.angle);
    var labelY = cy + (branchRadius + 20) * Math.sin(b.angle);
    labelsHtml += '<text class="tree-label tree-label-branch" x="' + labelX + '" y="' + labelY
      + '" style="transition-delay:' + (delay + 30) + 'ms">'
      + b.label + ' (' + b.specs.length + ')</text>';
  });

  // Nodos hoja + labels
  branches.forEach(function(b) {
    b.specs.forEach(function(spec) {
      var gapClass = spec.layers_count === 0 ? ' has-gaps' : '';
      nodesHtml += '<circle class="tree-node tree-node-leaf' + gapClass
        + '" cx="' + spec._x + '" cy="' + spec._y + '" r="4" data-status="'
        + spec.status + '" data-spec-id="' + spec.id
        + '" style="transition-delay:' + spec._animDelay + 'ms" />';

      labelsHtml += '<text class="tree-label" x="' + spec._x + '" y="' + (spec._y + 14)
        + '" style="transition-delay:' + (spec._animDelay + 20) + 'ms">'
        + escapeHtml(spec.label.substring(0, 18)) + '</text>';
    });
  });

  // Insertar en SVG
  svg.querySelector('.tree-links').innerHTML = linksHtml;
  svg.querySelector('.tree-nodes').innerHTML = nodesHtml;
  svg.querySelector('.tree-labels').innerHTML = labelsHtml;

  // P4: Scanning animation — activar secuencialmente
  requestAnimationFrame(function() {
    // Mostrar scan status
    var scanEl = document.getElementById('scan-status');
    if (scanEl) scanEl.classList.add('active');

    // Activar todos los elementos con su delay de transición
    svg.querySelectorAll('.tree-link').forEach(function(el) { el.classList.add('visible'); });
    svg.querySelectorAll('.tree-node').forEach(function(el) { el.classList.add('loaded'); });
    svg.querySelectorAll('.tree-label').forEach(function(el) { el.classList.add('visible'); });

    // Ocultar scan status después de la última animación
    var maxDelay = animIndex * 30 + 400;
    setTimeout(function() {
      if (scanEl) scanEl.classList.remove('active');
    }, maxDelay);
  });

  // Click handler en hojas → detalle
  svg.querySelectorAll('.tree-node-leaf').forEach(function(node) {
    node.addEventListener('click', function() {
      var specId = this.getAttribute('data-spec-id');
      var specData = nodes.find(function(n) { return n.id === specId; });
      if (specData) showConstellationDetail(specData);
    });
  });

  // Click en fondo → cerrar detalle
  svg.addEventListener('click', function(evt) {
    if (evt.target === svg || evt.target.tagName === 'svg') {
      hideConstellationDetail();
    }
  });
}
```

### 10.5 KPI Counter (P5)

```css
.constellation-kpi {
  position: absolute;
  top: 16px; left: 24px;
  z-index: 10;
  display: flex;
  align-items: baseline;
  gap: 6px;
  background: var(--surface);
  border: 1px solid var(--surface-border);
  backdrop-filter: var(--blur-light);
  -webkit-backdrop-filter: var(--blur-light);
  border-radius: var(--radius-md);
  padding: 8px 16px;
  box-shadow: var(--neo-raised);
}
.kpi-count {
  font-size: 22px;
  font-weight: 700;
  color: var(--accent-green);
}
.kpi-total {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}
.kpi-label {
  font-size: 12px;
  color: var(--text-secondary);
}
```

### 10.6 Scanning Status (P4)

```css
.constellation-scan-status {
  position: absolute;
  bottom: 24px; left: 50%;
  transform: translateX(-50%) translateY(20px);
  opacity: 0;
  display: flex; align-items: center; gap: 8px;
  background: var(--surface);
  border: 1px solid var(--surface-border);
  backdrop-filter: var(--blur-light);
  -webkit-backdrop-filter: var(--blur-light);
  border-radius: var(--radius-md);
  padding: 8px 16px;
  font-size: 12px;
  color: var(--text-secondary);
  box-shadow: var(--neo-raised);
  transition: all 0.3s ease;
  pointer-events: none;
}
.constellation-scan-status.active {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}
.scan-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--accent-green);
  box-shadow: var(--sku-led-glow);
  animation: blink 0.8s ease-in-out 6; /* 6 repeticiones, NO infinite */
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
```

### 10.7 Hover tooltip en nodos del árbol

```css
.tree-node-tooltip {
  position: absolute;
  padding: 8px 12px;
  background: var(--surface-elevated);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-sm);
  font-size: 11px;
  color: var(--text-primary);
  box-shadow: var(--neo-raised);
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.15s ease;
  z-index: 20;
  max-width: 200px;
  white-space: nowrap;
}
.tree-node-tooltip.visible { opacity: 1; }
```

**Hover en nodos hoja:** Mostrar tooltip con nombre completo del spec, status traducido, y cantidad de capas. Implementar con `mouseenter`/`mouseleave` sobre los `<circle>` del SVG. Posicionar el tooltip relativo al contenedor, no al SVG (para no perder fidelidad con el zoom).

### 10.8 Beneficios del SVG vs Cytoscape para constelación

| Aspecto | Cytoscape (antes) | SVG Radial (ahora) |
|---------|-------------------|---------------------|
| Peso librería | ~300KB (cytoscape + layout plugin) | 0KB (SVG nativo) |
| Layout computation | cose-bilkent en cada render | Cálculo trigonométrico simple |
| Animación | `animate: 'end'` (recalcula posiciones) | CSS transitions con delay (GPU compositing) |
| Customización visual | Limitada a API de Cytoscape | CSS completo (gradients, filters, animations) |
| Interactividad | Event system propio | DOM events nativos |
| Accesibilidad | Nula (canvas interno) | `<title>`, `aria-label`, `tabindex` en SVG |
| Consistencia NLVS | Difícil (API propia de estilos) | Natural (mismas CSS variables) |

---

## 11. Patrones de diseño importados del referente

### 11.1 P3 — Glow semántico

El glow (resplandor) NUNCA es decorativo. Solo se aplica a elementos que requieren atención:

| Contexto | Cuándo aplicar glow | CSS |
|----------|---------------------|-----|
| Spec sin capas | `layers_count === 0` | `.has-gaps { filter: drop-shadow(...) }` |
| App con conflictos | `health === 'red'` | `.health-red { box-shadow: 0 0 8px rgba(255,69,58,0.3) }` |
| Dependencia rota | Edge a spec inexistente | `.broken-dep { stroke: var(--accent-red); stroke-dasharray: 4 4 }` |

**NUNCA** aplicar glow a nodos saludables o para decorar.

### 11.2 P4 — Scanning animation (entrada secuencial)

Cuando la constelación carga, los nodos NO aparecen todos de golpe. Se activan secuencialmente:

1. Nodo raíz aparece primero (delay: 0ms)
2. Líneas raíz→ramas (delay: 60ms por rama)
3. Nodos rama (delay: siguiendo las líneas)
4. Líneas rama→hojas (delay: 30ms por hoja)
5. Nodos hoja (delay: siguiendo las líneas)
6. Labels (delay: +20ms después de su nodo)

Implementación: CSS `transition-delay` calculado en JS, NO `setTimeout` loops ni `animation-delay` infinito.

**Performance:** La animación total no debe exceder 2 segundos. Si hay más de 30 specs, reducir el delay por nodo para mantener el límite.

### 11.3 P5 — Contador KPI

Un badge siempre visible que muestra el estado resumido del ecosistema:

```
[3 de 8 specs aprobadas]
```

El contador se actualiza en cada render de la constelación. Si todas están aprobadas, cambiar color a `var(--accent-green)` completo. Si hay specs con gaps, mostrar un segundo badge:

```
[2 gaps detectados]
```

---

## 12. Versionado del design system

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0.0 | 2026-08-05 | Versión inicial: NLVS tokens, catálogo de componentes, performance budget, accesibilidad |
| 1.1.0 | 2026-08-05 | Referente SkillTree: árbol radial SVG para constelación, glow semántico, scanning animation, KPI counter |
