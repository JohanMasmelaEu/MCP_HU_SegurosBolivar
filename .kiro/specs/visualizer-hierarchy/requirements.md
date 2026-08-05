# Jerarquía Visual — Red Neuronal & Ecosistema — Requirements

## Problema

Las visualizaciones de Red Neuronal (`visualizer_ui.html`) y Ecosistema (`ecosystem_visualizer_ui.html`) carecen de jerarquía visual y no comparten el mismo sistema de diseño NLVS:

1. **Red Neuronal sin jerarquía** — El layout concéntrico asigna peso fijo a TODAS las stories (peso 3), sin diferenciar por grado de conexión, gaps, o status. Todas las HUs se ven iguales.
2. **Ecosistema sin jerarquía** — El layout cose-bilkent usa parámetros fijos (`nodeRepulsion: 10000`, `idealEdgeLength: 250`) sin diferenciar apps por salud, acoplamiento, o importancia.
3. **Red Neuronal sin NLVS** — El `visualizer_ui.html` usa CSS básico sin los tokens NLVS (liquid glass, neomorfismo, viridiformismo, skeuomorfismo) que ya existen en el ecosistema.
4. **Nav inconsistente** — El nav bar de Red Neuronal usa estilos inline que no coinciden con el `.view-selector` del ecosistema.

## Objetivo

Aplicar **jerarquía visual basada en datos** y **unificar el design system NLVS** en ambas visualizaciones para que:
- Los nodos más importantes (más conexiones, más gaps, peor salud) sean visualmente más prominentes
- Ambas vistas compartan los mismos tokens CSS y principios de diseño
- El nav bar sea visualmente idéntico en ambas vistas

## Requerimientos

### RH-01: Jerarquía concéntrica por degree centrality (Red Neuronal)
- La función `concentric` DEBE calcular peso basado en: `degree * 2 + gaps + questions + dependencies.length`
- Las stories más conectadas y con más problemas DEBEN quedar al centro
- Entities y flows DEBEN quedar en la periferia (peso 0)
- `levelWidth` DEBE distribuir en 3-5 anillos (no aplanar)

### RH-02: Tamaño proporcional de nodos story (Red Neuronal)
- El tamaño de cada story DEBE variar entre 36px y 72px basado en degree
- La opacity DEBE variar por status: analyzed=0.95, refined=0.75, otro=0.6
- El degree DEBE pre-calcularse después de crear la instancia de Cytoscape

### RH-03: Jerarquía por salud en Ecosistema
- Apps con `health="red"` DEBEN tener `border-width: 3`, `shadow-blur: 36`, `shadow-opacity: 0.8`
- Apps con `health="yellow"` DEBEN tener `border-width: 2`, `shadow-blur: 28`
- Apps con `health="green"` DEBEN tener `border-width: 1`, `shadow-blur: 20`, `shadow-opacity: 0.4`
- El `nodeRepulsion` DEBE ser función de health: red=4000, yellow=7000, green=12000

### RH-04: Tamaño dinámico de nodos app (Ecosistema)
- El tamaño de cada app DEBE variar basado en `entities_count + flows_count + story_count`
- Width: min 140px, max 260px
- Height: min 70px, max 130px
- Font-size: proporcional, min 11px, max 16px
- Los tamaños DEBEN aplicarse post-layout con `cy.on('layoutstop')`

### RH-05: Unificación NLVS en Red Neuronal
- El `:root` de `visualizer_ui.html` DEBE contener TODOS los tokens NLVS definidos en `.kiro/specs/design-system/design.md` sección 2.1
- DEBE incluir light theme (`@media (prefers-color-scheme: light)`) de sección 2.2
- Los componentes DEBEN usar las variables: `.glass-panel` con blur/neo, `#toolbar` con sku-metal, `#panel` con blur-heavy y borde prismático
- El fondo `body::before` DEBE usar gradientes orgánicos con animación `meshShift 3s forwards` (no infinite)

### RH-06: Nav bar unificado
- El nav bar de Red Neuronal DEBE usar la clase `.view-selector` con los mismos estilos del ecosistema
- DEBE incluir `role="tablist"`, `role="tab"`, `aria-selected` para accesibilidad
- DEBE usar `var(--sku-metal)` como background con backdrop-filter

## Criterios de aceptación

1. Red Neuronal vista concéntrica: HUs con más conexiones y gaps al centro, más grandes; periféricas más pequeñas en anillos exteriores
2. Red Neuronal vista jerárquica (dagre): respeta flujo de dependencias TB
3. Ecosistema vista macro: apps con conflictos visualmente más grandes y prominentes; saludables en periferia
4. Design system NLVS unificado en ambas vistas: liquid glass, neomorfismo, gradientes orgánicos, light theme
5. Performance: cálculos de tamaño se hacen una vez post-layout, sin bucles costosos
6. Nav idéntico visualmente entre ambas vistas
