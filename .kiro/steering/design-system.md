---
inclusion: fileMatch
fileMatchPattern: "**/ecosystem_visualizer_ui**,**/visualizer_ui**,**/visualizer.py,**/ecosystem_visualizer.py"
---

# Sistema de Diseño NLVS — Reglas para agentes de código

> **NLVS** = Neomorfismo + Liquid Glass + Viridiformismo + Skeuomorfismo
> Especificación completa: `.kiro/specs/design-system/design.md`

## Regla 0 — Leer primero

Antes de modificar CUALQUIER archivo de UI (HTML, CSS, JS inline), lee `.kiro/specs/design-system/design.md` completo. Contiene:
- Tokens de diseño (variables CSS obligatorias)
- Reglas por capa de diseño (neomorfismo, liquid glass, viridiformismo, skeuomorfismo)
- Restricciones de rendimiento
- Checklist de accesibilidad
- Catálogo de componentes

## Regla 1 — NUNCA usar estilos inline nuevos

No crear elementos con `style="..."` en JavaScript. Todo estilo nuevo va como clase CSS en el bloque `<style>` del HTML. Los únicos inline permitidos son valores dinámicos calculados en runtime (posición de tooltip, color basado en datos del API).

## Regla 2 — Variables CSS obligatorias

NUNCA hardcodear colores, radios, blurs ni sombras. Usar SIEMPRE las variables definidas en `:root`. Si necesitas un valor nuevo, definirlo primero como variable en `:root` dentro del bloque CSS.

```css
/* ✅ Correcto */
background: var(--surface);
border-color: var(--surface-border);
box-shadow: var(--neo-raised);

/* ❌ Prohibido */
background: rgba(28,28,30,0.72);
border: 1px solid rgba(255,255,255,0.06);
```

## Regla 3 — Dual theme obligatorio

Todo componente nuevo DEBE funcionar en dark Y light theme. Definir estilos base en `:root` (dark) y overrides en `@media (prefers-color-scheme: light)`. No crear componentes que solo se ven bien en dark.

## Regla 4 — Performance budget

| Métrica | Límite |
|---------|--------|
| Animaciones CSS simultáneas | ≤ 3 activas a la vez |
| `animation: infinite` | PROHIBIDO excepto en `.loading-spinner` |
| `backdrop-filter` | Máximo 3 elementos visibles simultáneos con blur |
| Nodos Cytoscape renderizados | ≤ 80 (usar `collapseSmallNodes`) |
| Layout quality Cytoscape | `'default'` (NUNCA `'proof'`) |
| `animate` en layout Cytoscape | `'end'` (NUNCA `true`) |
| Google Fonts / CDN externo | PROHIBIDO — usar system font stack o `/static/vendor/` |

## Regla 5 — Accesibilidad mínima

Todo elemento interactivo DEBE tener:
- `aria-label` descriptivo en español
- `:focus-visible` con outline visible
- `cursor: pointer` si es clickeable
- `:active` con `transform: scale(0.96)` para feedback táctil
- Si es toggle: `aria-pressed="true|false"`
- Si es tab: `role="tab"` + `aria-selected="true|false"`
- Si es colapsable: `aria-expanded="true|false"`

## Regla 6 — Idioma

TODA la UI está en **español**. Los data attributes y valores del API permanecen en inglés (ej: `data-maturity="formalized"`), pero el texto visible al usuario debe estar traducido:
- formalized → Formalizado
- draft → Borrador
- reference → Referencia

## Regla 7 — Nuevos paneles

NUNCA crear paneles con `document.createElement`. Definir el HTML en el body con `display:none` o `transform:translateX(100%)` y mostrarlos con clase `.open` + transición CSS. Esto aplica a paneles de detalle, modales, y cualquier overlay.

## Regla 8 — Consistencia visual entre vistas + Motor de renderizado

**Vista Ecosistema (macro/micro):** usa Cytoscape.js con `NLVS_NODE_BASE`, `NLVS_EDGE_BASE`, `NLVS_HEALTH_COLORS`.

**Vista Constelación:** usa **SVG radial tree** (NO Cytoscape). Ver `design.md` sección 10. El árbol tiene 3 niveles: raíz (ecosistema) → ramas (por status) → hojas (cada spec). Los estilos son CSS puro con variables de `:root`.

Todas las vistas DEBEN compartir:
- Misma paleta de colores (las variables de `:root`)
- Mismas sombras suaves
- Mismas transiciones (`var(--transition-normal)`)
- Glow solo semántico (alertas/gaps), NUNCA decorativo

NUNCA crear una nueva instancia de Cytoscape para la constelación — usar `renderConstellationTree(data)` con SVG.

## Regla 9 — Scrollbar

SIEMPRE definir scrollbar para AMBOS engines:
```css
/* Firefox */
* { scrollbar-width: thin; scrollbar-color: var(--scrollbar-thumb) transparent; }
/* Webkit */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
```
