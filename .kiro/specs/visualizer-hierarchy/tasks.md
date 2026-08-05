# Jerarquía Visual — Red Neuronal & Ecosistema — Tasks

> **Referencia obligatoria:** Leer COMPLETO `design.md` de este spec antes de implementar.
> **Referencia NLVS:** `.kiro/specs/design-system/design.md` — tokens, componentes, rendimiento.

---

## Fase A — Unificación NLVS en Red Neuronal (hacer PRIMERO)

### TA.1 Reemplazar variables CSS por tokens NLVS completos
- [ ] **Archivo:** `src/engine/visualizer_ui.html`
- **Líneas:** 11-26 (bloque `:root`)
- **Qué hacer:** Reemplazar el bloque `:root` actual por el bloque completo definido en `.kiro/specs/design-system/design.md` sección 2.1. Agregar aliases de legacy al final: `--radius: var(--radius-lg); --blur: var(--blur-medium);`
- **Regla:** No borrar variables existentes que ya coincidan — solo agregar las que faltan y renombrar las que cambien.

### TA.2 Agregar light theme completo
- [ ] **Archivo:** `src/engine/visualizer_ui.html`
- **Dónde:** Después del cierre de `:root {}`
- **Qué hacer:** Agregar el bloque `@media (prefers-color-scheme: light)` completo de `.kiro/specs/design-system/design.md` sección 2.2.

### TA.3 Actualizar componentes CSS a NLVS
- [ ] **Archivo:** `src/engine/visualizer_ui.html`
- **Qué hacer:** Actualizar estos componentes para usar los nuevos tokens (ver `design.md` de este spec, sección 4):
  1. `.glass-panel` → agregar `backdrop-filter: var(--blur-medium)`, `box-shadow: var(--neo-panel)`, pseudo `::before` con gradiente de refracción
  2. `#toolbar` → cambiar a `background: var(--sku-metal)`, agregar `backdrop-filter: var(--blur-medium)`, `box-shadow: var(--neo-panel)`
  3. `#toolbar button` → agregar `box-shadow: var(--neo-raised)` normal, `var(--neo-pressed)` en `.active`
  4. `.toggle-group` → agregar `box-shadow: var(--neo-pressed)`, `background: rgba(0,0,0,0.3)`
  5. `#panel` → cambiar background a `linear-gradient(180deg, rgba(36,36,40,0.85) 0%, rgba(22,22,26,0.92) 100%)`, agregar `backdrop-filter: var(--blur-heavy)`, agregar `border-image: linear-gradient(prismático)` (ver design-system/design.md sección 3.4)
  6. `#legend` → agregar `backdrop-filter: var(--blur-light)`, `box-shadow: var(--neo-panel)`
- **Dependencia:** TA.1

### TA.4 Fondo orgánico con animación finita
- [ ] **Archivo:** `src/engine/visualizer_ui.html`
- **Sección CSS:** `body::before`
- **Qué hacer:**
  1. Reemplazar los gradientes existentes por gradientes orgánicos con `var(--organic-green)`, `var(--organic-teal)`, `var(--organic-moss)`
  2. Cambiar animación de `infinite alternate` a `meshShift 3s ease-out forwards`
  3. Cambiar keyframe `meshShift` a: `0% { opacity:0; transform:scale(1.05); } 100% { opacity:1; transform:scale(1); }`
- **Dependencia:** TA.1

---

## Fase B — Jerarquía en Red Neuronal

### TB.1 Reescribir función layoutCfg() con degree centrality
- [ ] **Archivo:** `src/engine/visualizer_ui.html`
- **Líneas:** 363-374 (función `layoutCfg`)
- **Qué hacer:** Reemplazar completamente la función con:
  ```js
  function layoutCfg(name) {
    if (name === 'dagre') return {
      name: 'dagre', rankDir: 'TB', nodeSep: 80, edgeSep: 40, rankSep: 120,
      animate: false, fit: true, padding: 80,
      sort: function(a, b) { return (b.data('gaps') || 0) - (a.data('gaps') || 0); }
    };
    return {
      name: 'concentric',
      concentric: function(node) {
        var type = node.data('type');
        if (type === 'entity' || type === 'flow') return 0;
        var degree = node.degree();
        var gaps = node.data('gaps') || 0;
        var questions = node.data('questions') || 0;
        var deps = (node.data('dependencies') || []).length;
        return 1 + (degree * 2) + gaps + questions + deps;
      },
      levelWidth: function(nodes) { return Math.max(1, Math.ceil(nodes.maxDegree() / 4)); },
      minNodeSpacing: 80, animate: false, fit: true, padding: 80,
      startAngle: -Math.PI / 2, clockwise: true, equidistant: false,
    };
  }
  ```
- **Efecto:** HUs con más conexiones y problemas quedan al centro; entities/flows en periferia.

### TB.2 Tamaño proporcional de nodos story post-layout
- [ ] **Archivo:** `src/engine/visualizer_ui.html`
- **Sección JS:** Después de `cy = cytoscape({...})` en `renderGraph()` (línea ~510)
- **Qué hacer:**
  1. Pre-calcular degree:
     ```js
     cy.nodes('[type="story"]').forEach(function(n) { n.data('degree', n.degree()); });
     ```
  2. Aplicar tamaños dinámicos después del layout:
     ```js
     cy.nodes('[type="story"]').forEach(function(n) {
       var d = n.degree();
       var size = Math.max(36, Math.min(72, 36 + d * 3));
       n.style({ 'width': size, 'height': size });
       var s = n.data('status');
       var opacity = s === 'analyzed' ? 0.95 : s === 'refined' ? 0.75 : 0.6;
       n.style('background-opacity', opacity);
     });
     ```
- **Importante:** NO usar `mapData` en el estilo initial — calcular post-layout para tener acceso a `degree()`.
- **Dependencia:** TB.1

---

## Fase C — Jerarquía en Ecosistema

### TC.1 Health styles con prominencia variable
- [ ] **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Sección JS:** Array `macroStyles` — selectores de health (~líneas 1325-1327)
- **Qué hacer:** Reemplazar los estilos de health por versiones con prominencia variable:
  ```js
  { selector: 'node[health="red"]', style: {
    'border-color': 'rgba(255,69,58,0.5)', 'border-width': 3,
    'shadow-color': 'rgba(255,69,58,0.2)', 'shadow-blur': 36, 'shadow-opacity': 0.8,
  }},
  { selector: 'node[health="yellow"]', style: {
    'border-color': 'rgba(255,159,10,0.4)', 'border-width': 2,
    'shadow-color': 'rgba(255,159,10,0.15)', 'shadow-blur': 28,
  }},
  { selector: 'node[health="green"]', style: {
    'border-color': 'rgba(34,140,80,0.5)', 'border-width': 1,
    'shadow-color': 'rgba(34,140,80,0.18)', 'shadow-blur': 20, 'shadow-opacity': 0.4,
  }},
  ```

### TC.2 Layout con nodeRepulsion y idealEdgeLength dinámicos
- [ ] **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Sección JS:** Objeto `macroLayout` (~líneas 1387-1403)
- **Qué hacer:** Reemplazar `nodeRepulsion: 10000` e `idealEdgeLength: 250` por funciones:
  ```js
  idealEdgeLength: function(edge) {
    var strength = edge.data('coupling_strength') || 1;
    return Math.max(120, 300 - strength * 30);
  },
  nodeRepulsion: function(node) {
    var health = node.data('health');
    if (health === 'red') return 4000;
    if (health === 'yellow') return 7000;
    return 12000;
  },
  ```
  Cambiar `gravity: 0.2` a `gravity: 0.25` y agregar `gravityRange: 1.5`.
- **Efecto:** Apps con conflictos quedan más al centro; apps saludables se van a la periferia.

### TC.3 Tamaño dinámico post-layout de nodos app
- [ ] **Archivo:** `src/engine/ecosystem_visualizer_ui.html`
- **Sección JS:** Después de crear cy en `buildCytoscape()` (~línea 1529)
- **Qué hacer:** Agregar handler `layoutstop`:
  ```js
  cy.on('layoutstop', function() {
    hideLoading('cy');
    cy.nodes('[type="app"]').forEach(function(node) {
      var entities = node.data('entities_count') || 0;
      var flows = node.data('flows_count') || 0;
      var stories = node.data('story_count') || 0;
      var conflicts = node.data('conflicts') || 0;
      var importance = entities + flows + stories + conflicts * 5;
      var w = Math.max(140, Math.min(260, 140 + importance * 3));
      var h = Math.max(70, Math.min(130, 70 + importance * 2));
      node.style({ 'width': w, 'height': h });
      var fontSize = Math.max(11, Math.min(16, 11 + importance * 0.3));
      node.style('font-size', fontSize);
    });
  });
  ```
- **Dependencia:** TC.2

---

## Fase D — Nav bar unificado

### TD.1 Reemplazar nav inline por .view-selector
- [ ] **Archivo:** `src/engine/visualizer_ui.html`
- **Línea:** 272 (nav con estilos inline)
- **Qué hacer:**
  1. Reemplazar el HTML del nav por:
     ```html
     <nav class="view-selector" role="tablist" aria-label="Vistas de analisis">
       <a href="/" class="view-tab active" role="tab" aria-selected="true">Red Neuronal</a>
       <a href="/ecosystem" class="view-tab" role="tab" aria-selected="false">Ecosistema</a>
     </nav>
     ```
  2. Agregar CSS para `.view-selector` y `.view-tab` (copiar del ecosistema):
     ```css
     .view-selector {
       position: fixed; top: 0; left: 0; right: 0; z-index: 100;
       display: flex; align-items: center; gap: 0;
       background: var(--sku-metal);
       backdrop-filter: blur(30px) saturate(1.6);
       -webkit-backdrop-filter: blur(30px) saturate(1.6);
       border-bottom: 1px solid var(--surface-border);
       padding: 0 24px; height: 40px;
       box-shadow: 0 1px 0 rgba(255,255,255,0.04) inset, 0 4px 20px rgba(0,0,0,0.3);
     }
     .view-tab {
       padding: 8px 20px; text-decoration: none;
       font-size: 11px; font-weight: 600; letter-spacing: 0.8px;
       text-transform: uppercase; color: var(--text-secondary);
       border-bottom: 2px solid transparent; transition: all 0.2s;
     }
     .view-tab:hover { color: var(--text-primary); }
     .view-tab.active {
       color: var(--accent-blue);
       border-bottom: 2px solid var(--accent-blue);
     }
     ```
  3. Eliminar los estilos inline del nav anterior.
- **Dependencia:** TA.1 (necesita las variables NLVS)

---

## Orden de ejecución

```
Fase A: TA.1 → TA.2 → TA.3 → TA.4      (NLVS en Red Neuronal — PRIMERO)
         ↓
Fase B: TB.1 → TB.2                       (Jerarquía en Red Neuronal)
Fase C: TC.1 → TC.2 → TC.3               (Jerarquía en Ecosistema — paralelo con B)
         ↓
Fase D: TD.1                               (Nav unificado — después de A)
```

**Fase A es prerequisito de B y D.** Fase C puede ejecutarse en paralelo con B+D ya que modifica un archivo diferente.

## Resumen de impacto

| Fase | Tareas | Archivo | Riesgo |
|------|--------|---------|--------|
| A | 4 | `visualizer_ui.html` | Bajo — solo CSS, no cambia lógica |
| B | 2 | `visualizer_ui.html` | Medio — cambia lógica de layout |
| C | 3 | `ecosystem_visualizer_ui.html` | Medio — cambia layout y estilos |
| D | 1 | `visualizer_ui.html` | Bajo — solo HTML/CSS del nav |
