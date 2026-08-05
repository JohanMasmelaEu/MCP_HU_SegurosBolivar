# Jerarquía Visual — Red Neuronal & Ecosistema — Diseño Técnico

> **Referencia obligatoria:** `.kiro/specs/design-system/design.md` — tokens NLVS, componentes, reglas de rendimiento
> **Archivos a modificar:**
> - `src/engine/visualizer_ui.html` — Red Neuronal (Cambios 1, 2, 3, 6)
> - `src/engine/ecosystem_visualizer_ui.html` — Ecosistema (Cambios 4, 5)

---

## Diagnóstico

### Red Neuronal — `visualizer_ui.html`

La función `layoutCfg('concentric')` (líneas 363-374) asigna peso fijo:
```js
concentric: n => n.data('type')==='story'?3:n.data('type')==='flow'?2:1,
levelWidth: ()=>1, minNodeSpacing:100,
```
Todas las stories reciben peso 3 sin importar conexiones, gaps, o status. Los nodos story tienen tamaño fijo `width:50, height:50`.

El CSS (líneas 10-26) no tiene tokens NLVS — sin blur, sin neo, sin orgánico. El nav (línea 272) usa inline styles.

### Ecosistema — `ecosystem_visualizer_ui.html`

El layout `macroLayout` (líneas 1387-1403) usa valores fijos:
```js
idealEdgeLength: 250, nodeRepulsion: 10000
```
Los nodos app tienen tamaño fijo `width: 180, height: 90`. Los estilos de health (líneas 1325-1327) solo cambian border-color, no tamaño ni prominencia.

---

## Diseño de solución

### 1. Fórmula de jerarquía concéntrica (Red Neuronal)

```
peso(story) = 1 + (degree × 2) + gaps + questions + dependencies.length
peso(entity) = 0
peso(flow) = 0
```

Donde `degree` = `node.degree()` (in-degree + out-degree en el grafo Cytoscape).

`levelWidth` se calcula dinámicamente: `Math.max(1, Math.ceil(nodes.maxDegree() / 4))` para distribuir en 3-5 anillos en vez de aplanar.

### 2. Fórmula de tamaño proporcional (Red Neuronal)

```
size(story) = clamp(36, 36 + degree × 3, 72)
opacity(story) = status === 'analyzed' ? 0.95 : status === 'refined' ? 0.75 : 0.6
```

**Restricción:** Cytoscape no expone `degree` como data field nativo. Hay que pre-calcularlo después de `cy = cytoscape({...})`:
```js
cy.nodes('[type="story"]').forEach(function(n) {
  n.data('degree', n.degree());
});
```

### 3. Fórmula de jerarquía en Ecosistema

**Tamaño de nodo app:**
```
width = clamp(140, 140 + (entities + flows + stories) × 4, 260)
height = clamp(70, 70 + (entities + flows) × 3, 130)
fontSize = clamp(11, 11 + importance × 0.3, 16)
```

**nodeRepulsion por health:**
```
nodeRepulsion(red) = 4000      → al centro (se repelen poco)
nodeRepulsion(yellow) = 7000
nodeRepulsion(green) = 12000   → a la periferia (se repelen mucho)
```

**idealEdgeLength por acoplamiento:**
```
idealEdgeLength(edge) = clamp(120, 300 - coupling_strength × 30, 300)
```

**Health styles:**

| Health | border-width | shadow-blur | shadow-opacity |
|--------|-------------|------------|----------------|
| red    | 3           | 36         | 0.8            |
| yellow | 2           | 28         | 0.6 (default)  |
| green  | 1           | 20         | 0.4            |

### 4. Tokens NLVS para Red Neuronal

Copiar el bloque completo de `:root` y `@media (prefers-color-scheme: light)` desde `.kiro/specs/design-system/design.md` secciones 2.1 y 2.2.

Agregar aliases de legacy para no romper CSS existente:
```css
--radius: var(--radius-lg);
--blur: var(--blur-medium);
```

Componentes a actualizar:

| Componente | Filosofía | Cambio |
|---|---|---|
| `.glass-panel` | Liquid Glass + Neo | `backdrop-filter: var(--blur-medium)`, `box-shadow: var(--neo-panel)`, pseudo `::before` refracción |
| `#toolbar` | Skeu + Liquid Glass | `background: var(--sku-metal)`, `backdrop-filter: var(--blur-medium)` |
| `#toolbar button` | Neo | Normal: `var(--neo-raised)`, Active: `var(--neo-pressed)` |
| `#panel` | Liquid Glass + Viridiformismo | `backdrop-filter: var(--blur-heavy)`, `border-image: linear-gradient(prismático)` |
| `#legend` | Liquid Glass | `backdrop-filter: var(--blur-light)` |
| `body::before` | Viridiformismo | Gradientes con `--organic-green`, `--organic-moss`, animación `meshShift 3s forwards` |
| `.view-selector` | Skeu + Liquid Glass | `var(--sku-metal)`, `backdrop-filter`, `var(--neo-panel)` |

### 5. Nav bar unificado

```html
<nav class="view-selector" role="tablist" aria-label="Vistas de analisis">
  <a href="/" class="view-tab active" role="tab" aria-selected="true">Red Neuronal</a>
  <a href="/ecosystem" class="view-tab" role="tab" aria-selected="false">Ecosistema</a>
</nav>
```

CSS idéntico al de `ecosystem_visualizer_ui.html`:
- `background: var(--sku-metal)` + `backdrop-filter`
- `.view-tab.active` con `color: var(--accent-blue)` y `border-bottom: 2px solid var(--accent-blue)`

---

## Performance

- Degree se pre-calcula **una vez** después de crear cy — O(n)
- Tamaños se aplican **una vez** en `layoutstop` — O(n)
- No se agregan event listeners adicionales al loop de layout
- `animate: false` en Red Neuronal (ya estaba), `animate: 'end'` en Ecosistema (ya estaba)
- El cálculo de `nodeRepulsion` como función es nativo de cose-bilkent — no agrega overhead
