# Ecosystem Graph Visualizer — Requirements

## Problema

Cuando un ecosistema tiene multiples apps registradas, cada una con su propia red neuronal (grafo de HUs, entidades y flujos), **no existe una forma de ver el panorama completo**: como se conectan las apps entre si, que tan acopladas estan, y como un flujo en un sistema impacta a otro.

El visualizador actual (`localhost:9751`) muestra el grafo de **un solo workspace**. No existe una vista que:

1. Muestre la topologia de cohesion y acoplamiento entre apps a nivel macro.
2. Permita ver los flujos concretos punto A → punto B entre sistemas (nivel micro).
3. Conecte con la red neuronal interna de cada app para ver el detalle (nivel detalle).
4. Sirva como documentacion viva, centralizada y confiable del ecosistema.

## Contexto

Esta funcionalidad vive en la **misma aplicacion** (puerto 9751) con un selector para navegar entre "Red Neuronal" (workspace) y "Ecosistema" (macro/micro). Cualquier persona con conocimiento basico del proyecto debe poder entender el estado actual del ecosistema sin instrucciones adicionales.

## Modelo de Navegacion: Macro → Micro → Detalle

| Nivel | Proposito | Vista |
|-------|-----------|-------|
| **Macro** | Topologia de acoplamiento entre apps. Quién depende de quién y cuanto. | Grafo de apps como bloques con lineas de grosor proporcional al acoplamiento. |
| **Micro** | Flujos concretos punto A → punto B entre dos apps. Como las interacciones cruzan sistemas. | Diagrama tipo secuencia: HUs origen/destino, entidades en transito, contratos. |
| **Detalle** | Red neuronal interna de una app. HUs, entidades, flujos de un workspace. | Navegacion a la vista existente (/) con el workspace de esa app activo. |

## Requerimientos Funcionales

### RF-01: Vista Macro — Topologia de Cohesion y Acoplamiento
- El sistema DEBE mostrar cada app registrada como un nodo/bloque principal.
- Apps con `coupling_type: "cohesive"` DEBEN agruparse visualmente en un cluster (compound node) indicando que despliegan juntas.
- Apps con `coupling_type: "decoupled"` DEBEN flotar independientes.
- Las conexiones entre apps DEBEN tener grosor proporcional a la fuerza de acoplamiento (numero de contratos + entidades compartidas entre ellas).
- Cada nodo app DEBE mostrar: nombre, equipo, cantidad de HUs, tipo de acoplamiento, y badge de salud.

### RF-02: Fuerza de Acoplamiento como Metrica Visual
- El grosor de la linea entre dos apps DEBE representar la fuerza de acoplamiento: mas contratos + mas entidades compartidas = linea mas gruesa.
- El label del edge DEBE mostrar un resumen: "N contratos · M entidades".
- Diferenciar visualmente si la integracion es sincrona (REST/GraphQL), asincrona (eventos), o mixta.

### RF-03: Vista Micro — Flujos Punto A → Punto B
- Al hacer click en una conexion entre dos apps (o seleccionar un par de apps), el sistema DEBE expandir la vista mostrando los flujos concretos entre esas dos apps.
- Cada flujo DEBE mostrar:
  - HU de origen (en App A) y HU de destino (en App B).
  - Direccion del flujo (A→B o B→A).
  - Entidades que viajan en esa interaccion (request/response/event payload).
  - Contrato que habilita el flujo (nombre, tipo, version).
- Si una entidad en transito tiene divergencia entre las apps, DEBE resaltarse con indicador de alerta.
- La vista micro DEBE tener un boton para volver a la vista macro.

### RF-04: Navegacion al Detalle — Workspace de una App
- Desde la vista micro, al hacer click en una HU o en "Ver en [app]", el sistema DEBE:
  - Activar el workspace correspondiente a esa app.
  - Navegar a la vista de Red Neuronal (/).
  - Opcionalmente resaltar la HU especifica en el grafo del workspace.

### RF-05: Indicadores de Salud
- Cada app DEBE mostrar un badge de salud basado en:
  - Cantidad de conflictos cross-app detectados.
  - Entidades con divergencia.
  - Contratos sin provider activo ("dead contracts").
- Codigo de colores: verde (sin problemas), amarillo (warnings), rojo (conflictos criticos).

### RF-06: Panel de Detalle Contextual
- En vista macro: click en app muestra panel con resumen de la app (entidades, flujos, contratos, dependencias).
- En vista micro: click en flujo muestra panel con detalle del flujo (HUs, entidades en transito, divergencias, links a workspaces).

### RF-07: Filtros
- El usuario DEBE poder filtrar por:
  - Tipo de integracion (REST, GraphQL, async, shared_lib).
  - Solo apps con conflictos.
  - Tipo de acoplamiento (cohesive/decoupled).

### RF-08: Selector de Vista en la Misma App
- La vista DEBE servirse en la misma aplicacion (puerto 9751) bajo la ruta `/ecosystem`.
- DEBE existir un selector/tab visible que permita alternar entre "Red Neuronal" y "Ecosistema".
- El selector DEBE ser intuitivo: siempre visible en la parte superior.

### RF-09: Selector de Ecosistema
- Si hay multiples ecosistemas, DEBE haber un dropdown para seleccionar cual visualizar.
- Al cambiar, el grafo se recarga automaticamente.

### RF-10: Documentacion Viva
- La vista DEBE servir como fuente de verdad del estado del ecosistema.
- Cualquier persona con conocimiento basico del proyecto DEBE poder entender:
  - Que sistemas existen y como se relacionan (macro).
  - Como fluyen los datos entre sistemas (micro).
  - Que HUs definen cada interaccion (detalle).
- No requiere instrucciones: layout autoexplicativo, leyenda visible, convenciones claras.

## Requerimientos No Funcionales

### RNF-01: Independencia de la Vista
- La UI del ecosistema DEBE vivir en un archivo HTML nuevo (`ecosystem_visualizer_ui.html`).
- La logica backend DEBE vivir en un archivo Python nuevo (`ecosystem_visualizer.py`).
- Cambios minimos al visualizador existente: agregar rutas en `visualizer.py` y un nav tab en `visualizer_ui.html`.

### RNF-02: Rendimiento
- Vista macro: carga < 2 segundos para ecosistemas de hasta 20 apps y 50 contratos.
- Transicion macro → micro: < 500ms.
- El grafo DEBE ser responsive al redimensionar.

### RNF-03: Sin Dependencias Frontend Adicionales
- Usar Cytoscape.js (ya disponible via CDN).
- Extension cose-bilkent para layout macro.
- CSS y JS embebidos en un solo HTML.

### RNF-04: Usabilidad
- La interfaz DEBE ser autoexplicativa.
- Leyenda visible con codificacion de grosor, colores y formas.
- Tooltips informativos en hover.
- Convenciones similares a diagramas de secuencia y arquitectura que cualquier desarrollador reconoce.

## Criterios de Aceptacion

1. Vista macro: se ven todas las apps con lineas de grosor proporcional al acoplamiento. Apps cohesivas agrupadas en cluster.
2. Click en conexion entre apps transiciona a vista micro mostrando flujos concretos A→B.
3. Cada flujo en micro muestra: HUs origen/destino, entidades en transito, contrato, y alertas de divergencia.
4. Click en "Ver en [app]" activa el workspace y navega a la red neuronal interna.
5. Badge de salud refleja correctamente el estado de conflictos.
6. Filtros reducen complejidad visual sin recargar datos.
7. El visualizador actual de workspace NO tiene regresiones.
8. Un desarrollador nuevo entiende la topologia del ecosistema sin explicacion adicional.
