"""Spec SDD Visualizer: backend para la pantalla dedicada de specs.

Provee handlers de rutas para:
- UI HTML de la vista dedicada de spec.
- API de listado de specs.
- API de detalle de spec (con filtrado por rol opcional).
- API de actualización de capas (PUT) para edición inline desde la UI.

Se integra con el servidor Starlette existente en visualizer.py (puerto 9751).
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from src.engine.spec_engine import get_spec_engine
from src.engine.memory import get_memory
from src.models.sdd import LayerContent, SDDLayer

logger = logging.getLogger("mcp_hu.engine.spec_visualizer")

HTML_PATH = Path(__file__).parent / "spec_visualizer_ui.html"
STORY_DETAIL_HTML_PATH = Path(__file__).parent / "story_detail_ui.html"


# ─── ROUTE HANDLERS ──────────────────────────────────────────────────────────────


async def route_spec_index(request: Request) -> HTMLResponse:
    """Sirve la UI HTML de la vista dedicada de spec/SDD.

    GET /spec
    """
    try:
        html = HTML_PATH.read_text(encoding="utf-8")
        return HTMLResponse(content=html, status_code=200)
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Spec Visualizer UI not found</h1>",
            status_code=500,
        )


async def route_api_specs(request: Request) -> JSONResponse:
    """API: lista todas las specs disponibles.

    GET /api/specs
    Retorna lista con spec_id, project_name, status, version, app_id.
    """
    spec_engine = get_spec_engine()
    if not spec_engine:
        return JSONResponse({"specs": [], "error": "SpecEngine no disponible."}, status_code=500)

    specs = spec_engine.list_specs()
    return JSONResponse({"specs": specs})


async def route_api_spec_detail(request: Request) -> JSONResponse:
    """API: detalle completo de una spec.

    GET /api/spec/{spec_id}?role=optional
    Si role viene como query param, filtra capas por profundidad usando RoleDepthMatrix.
    Sin role, retorna la spec completa con todas las capas.
    """
    spec_id = request.path_params.get("spec_id", "")
    role = request.query_params.get("role", "")

    spec_engine = get_spec_engine()
    if not spec_engine:
        return JSONResponse({"error": "SpecEngine no disponible."}, status_code=500)

    if role:
        result = spec_engine.get_spec_for_role(spec_id, role)
        if not result:
            return JSONResponse({"error": f"Spec '{spec_id}' no encontrada."}, status_code=404)
        return JSONResponse(result)

    spec = spec_engine.get_spec(spec_id)
    if not spec:
        return JSONResponse({"error": f"Spec '{spec_id}' no encontrada."}, status_code=404)

    return JSONResponse(spec.model_dump(mode="json"))


async def route_api_spec_update_layer(request: Request) -> JSONResponse:
    """API: actualiza una capa de la spec desde la UI de edición.

    PUT /api/spec/{spec_id}/layer/{layer}
    Body JSON: { summary, decisions, constraints, artifacts, details }

    Permite edición inline desde la pantalla dedicada del SDD.
    """
    spec_id = request.path_params.get("spec_id", "")
    layer_name = request.path_params.get("layer", "")

    spec_engine = get_spec_engine()
    if not spec_engine:
        return JSONResponse({"error": "SpecEngine no disponible."}, status_code=500)

    try:
        sdd_layer = SDDLayer(layer_name)
    except ValueError:
        valid = [l.value for l in SDDLayer]
        return JSONResponse(
            {"error": f"Capa '{layer_name}' no válida. Opciones: {valid}"},
            status_code=400,
        )

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "Body JSON inválido."}, status_code=400)

    try:
        layer_content = LayerContent(**body)
    except Exception as e:
        return JSONResponse({"error": f"Contenido de capa inválido: {e}"}, status_code=400)

    updated = spec_engine.update_layer(spec_id, sdd_layer, layer_content)
    if not updated:
        return JSONResponse({"error": f"Spec '{spec_id}' no encontrada."}, status_code=404)

    return JSONResponse({
        "status": "success",
        "spec_id": spec_id,
        "layer": layer_name,
        "message": f"Capa '{layer_name}' actualizada en spec '{spec_id}'.",
    })


async def route_api_spec_refine(request: Request) -> JSONResponse:
    """API: formaliza un input crudo en una entrada tipificada para el SDD.

    POST /api/spec/{spec_id}/refine
    Body JSON:
    {
        "layer": "negocio",
        "section": "decisions" | "constraints" | "artifacts",
        "raw_input": "texto libre del stakeholder",
        "context": {  // opcional — items existentes para dar continuidad
            "existing_ids": ["DN-001", "DN-002"],
            "summary": "resumen de la capa para contexto"
        }
    }

    Retorna:
    {
        "status": "success",
        "refined": {
            "id": "DN-003",
            "title": "DN-003: Titulo formalizado",
            "detail": "Descripcion tecnica expandida..."
        },
        "original_input": "texto original"
    }

    El stakeholder puede hacer preview del resultado formalizado antes de aceptarlo.
    """
    spec_id = request.path_params.get("spec_id", "")

    spec_engine = get_spec_engine()
    if not spec_engine:
        return JSONResponse({"error": "SpecEngine no disponible."}, status_code=500)

    spec = spec_engine.get_spec(spec_id)
    if not spec:
        return JSONResponse({"error": f"Spec '{spec_id}' no encontrada."}, status_code=404)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "Body JSON inválido."}, status_code=400)

    layer_name = body.get("layer", "")
    section = body.get("section", "")
    raw_input = body.get("raw_input", "").strip()
    context = body.get("context", {})

    if not raw_input:
        return JSONResponse({"error": "raw_input es requerido."}, status_code=400)
    if section not in ("decisions", "constraints", "artifacts"):
        return JSONResponse({"error": "section debe ser: decisions, constraints, artifacts."}, status_code=400)

    # Determine next ID
    layer_content = spec.layers.get(layer_name)
    existing_items = []
    if layer_content:
        existing_items = getattr(layer_content, section, [])

    next_id = _generate_next_id(section, layer_name, existing_items, context.get("existing_ids", []))

    # Formalize the input
    refined = _formalize_input(raw_input, section, layer_name, next_id, context.get("summary", ""))

    return JSONResponse({
        "status": "success",
        "refined": refined,
        "original_input": raw_input,
    })


def _generate_next_id(section: str, layer_name: str, existing_items: list, existing_ids: list) -> str:
    """Genera el siguiente ID tipificado para un item.

    Formato por sección y capa:
    - decisions: DN-XXX (Negocio), DA-XXX (Arquitectura), DS-XXX (Seguridad), etc.
    - constraints: CN-XXX, CA-XXX, CS-XXX, etc.
    - artifacts: HU-XXX (default)

    Args:
        section: Tipo de sección (decisions, constraints, artifacts).
        layer_name: Nombre de la capa SDD.
        existing_items: Items actuales en la capa para determinar secuencia.
        existing_ids: IDs proporcionados por el contexto del cliente.

    Returns:
        Siguiente ID disponible.
    """
    import re

    # Prefix map por capa
    layer_prefixes = {
        "negocio": "N",
        "arquitectura": "A",
        "seguridad": "S",
        "gobierno_info": "GI",
        "acceso_datos": "AD",
        "datos": "D",
        "desarrollo": "DE",
        "qa": "QA",
    }

    section_prefixes = {
        "decisions": "D",
        "constraints": "C",
        "artifacts": "HU",
    }

    layer_suffix = layer_prefixes.get(layer_name, "X")
    section_prefix = section_prefixes.get(section, "X")

    if section == "artifacts":
        prefix = "HU"
    else:
        prefix = section_prefix + layer_suffix

    # Find max existing number
    all_ids = existing_ids[:]
    for item in existing_items:
        m = re.match(r"^([A-Z]{1,5}-\d{1,4})", item)
        if m:
            all_ids.append(m.group(1))

    max_num = 0
    for id_str in all_ids:
        m = re.match(r"^[A-Z]{1,5}-(\d{1,4})$", id_str)
        if m:
            num = int(m.group(1))
            if num > max_num:
                max_num = num

    next_num = max_num + 1
    return f"{prefix}-{next_num:03d}"


def _formalize_input(raw_input: str, section: str, layer_name: str, item_id: str, layer_summary: str) -> dict:
    """Formaliza un input crudo en una entrada tipificada del SDD.

    Aplica heurísticas para:
    1. Extraer el concepto clave del input.
    2. Generar un título conciso y técnico.
    3. Expandir el detalle con justificación, impacto y contexto.

    Args:
        raw_input: Texto libre del stakeholder.
        section: Tipo de sección (decisions, constraints, artifacts).
        layer_name: Capa SDD donde se agregará.
        item_id: ID generado para el item.
        layer_summary: Resumen de la capa para contextualizar.

    Returns:
        Dict con id, title, detail formalizados.
    """
    # Normalize input
    cleaned = raw_input.strip()
    if cleaned.endswith("."):
        cleaned = cleaned[:-1]

    # Detect if input already looks formalized (has an ID prefix)
    import re
    existing_id_match = re.match(r"^([A-Z]{1,5}-\d{1,4})[\s:]+(.+)$", cleaned)
    if existing_id_match:
        # Already partially formalized — use existing ID and text
        item_id = existing_id_match.group(1)
        cleaned = existing_id_match.group(2)

    # Generate concise title (first sentence or up to 80 chars)
    title_text = _extract_title(cleaned)
    title = f"{item_id}: {title_text}"

    # Generate expanded detail
    detail = _expand_detail(cleaned, section, layer_name, layer_summary)

    return {
        "id": item_id,
        "title": title,
        "detail": detail,
    }


def _extract_title(text: str) -> str:
    """Extrae un título conciso del input.

    Estrategia:
    - Si hay un punto medio, toma la primera oración.
    - Si es muy largo (>80 chars), trunca inteligentemente.
    - Capitaliza y limpia.

    Args:
        text: Texto del cual extraer título.

    Returns:
        Título conciso.
    """
    # First sentence
    sentences = text.split(". ")
    first = sentences[0].strip()

    # Capitalize first letter
    if first and first[0].islower():
        first = first[0].upper() + first[1:]

    # Truncate if too long
    if len(first) > 100:
        # Find last space before 100 chars
        cut = first[:100].rfind(" ")
        if cut > 40:
            first = first[:cut]

    # Remove trailing connectors
    for suffix in [" y", " e", " o", " que", " para", " con", " sin", " pero"]:
        if first.endswith(suffix):
            first = first[: -len(suffix)]

    return first


def _expand_detail(text: str, section: str, layer_name: str, layer_summary: str) -> str:
    """Genera el detalle expandido formalizado.

    Estructura del detalle según el tipo de sección:
    - decisions: Qué se decide, Por qué (justificación), Impacto
    - constraints: Qué se restringe, Origen de la restricción, Consecuencia si se viola
    - artifacts: Qué se entrega, Criterio de aceptación, Dependencias

    Args:
        text: Input completo del usuario.
        section: Tipo de sección.
        layer_name: Capa para contextualizar.
        layer_summary: Resumen de la capa.

    Returns:
        Detalle expandido con estructura.
    """
    layer_labels = {
        "negocio": "negocio",
        "arquitectura": "arquitectura",
        "seguridad": "seguridad",
        "gobierno_info": "gobierno de información",
        "acceso_datos": "acceso a datos",
        "datos": "datos",
        "desarrollo": "desarrollo",
        "qa": "calidad",
    }
    layer_label = layer_labels.get(layer_name, layer_name)

    if section == "decisions":
        detail = (
            f"Decisión de {layer_label}: {text}\n\n"
            f"Justificación: [Pendiente — describir por qué se toma esta decisión y qué alternativas se descartaron]\n\n"
            f"Impacto: [Pendiente — describir qué componentes o flujos se ven afectados por esta decisión]"
        )
    elif section == "constraints":
        detail = (
            f"Restricción de {layer_label}: {text}\n\n"
            f"Origen: [Pendiente — indicar si es regulatoria, técnica, de negocio o institucional]\n\n"
            f"Consecuencia si se viola: [Pendiente — describir qué sucede si no se cumple esta restricción]"
        )
    else:  # artifacts
        detail = (
            f"Entregable: {text}\n\n"
            f"Criterio de aceptación: [Pendiente — condiciones verificables para considerar completo este artefacto]\n\n"
            f"Dependencias: [Pendiente — de qué otros artefactos o decisiones depende]"
        )

    return detail


# ─── IMPACT ANALYSIS ──────────────────────────────────────────────────────────────

# Matriz de impacto cross-layer: cuando una capa cambia, qué otras capas se afectan.
# Cada entrada define: capa_origen → [(capa_destino, tipo_impacto, razón)]
LAYER_IMPACT_MATRIX: dict[str, list[dict]] = {
    "negocio": [
        {"layer": "arquitectura", "impact": "high", "reason": "Decisiones de negocio definen patrones y componentes arquitectónicos necesarios"},
        {"layer": "datos", "impact": "high", "reason": "Reglas de negocio determinan el modelo de datos y entidades"},
        {"layer": "seguridad", "impact": "medium", "reason": "Procesos de negocio pueden requerir controles de seguridad específicos"},
        {"layer": "qa", "impact": "medium", "reason": "Nuevas reglas de negocio requieren casos de prueba de aceptación"},
        {"layer": "gobierno_info", "impact": "low", "reason": "Cambios de negocio pueden afectar políticas de retención y compliance"},
    ],
    "arquitectura": [
        {"layer": "desarrollo", "impact": "high", "reason": "Patrones arquitectónicos definen cómo se implementa el código"},
        {"layer": "datos", "impact": "high", "reason": "Decisiones de arquitectura afectan esquemas y acceso a datos"},
        {"layer": "seguridad", "impact": "medium", "reason": "Componentes arquitectónicos necesitan controles de seguridad"},
        {"layer": "qa", "impact": "medium", "reason": "Cambios arquitectónicos requieren pruebas de integración"},
        {"layer": "acceso_datos", "impact": "medium", "reason": "Nuevos componentes pueden requerir permisos y roles de acceso"},
    ],
    "seguridad": [
        {"layer": "arquitectura", "impact": "high", "reason": "Restricciones de seguridad pueden requerir componentes adicionales (auth, crypto)"},
        {"layer": "desarrollo", "impact": "high", "reason": "Políticas de seguridad definen patrones obligatorios en el código"},
        {"layer": "acceso_datos", "impact": "high", "reason": "Cambios en seguridad afectan directamente quién accede a qué datos"},
        {"layer": "qa", "impact": "medium", "reason": "Nuevas políticas requieren pruebas de seguridad y penetración"},
        {"layer": "gobierno_info", "impact": "medium", "reason": "Seguridad y gobierno de información están acoplados por regulación"},
    ],
    "gobierno_info": [
        {"layer": "seguridad", "impact": "high", "reason": "Políticas de gobierno definen controles de seguridad obligatorios"},
        {"layer": "datos", "impact": "high", "reason": "Gobierno define retención, clasificación y ciclo de vida de datos"},
        {"layer": "acceso_datos", "impact": "medium", "reason": "Lineamientos de gobierno afectan permisos y auditoría"},
        {"layer": "negocio", "impact": "low", "reason": "Restricciones regulatorias pueden limitar procesos de negocio"},
    ],
    "acceso_datos": [
        {"layer": "seguridad", "impact": "high", "reason": "Control de acceso es implementado por la capa de seguridad"},
        {"layer": "datos", "impact": "medium", "reason": "Permisos afectan cómo se modelan vistas y queries"},
        {"layer": "desarrollo", "impact": "medium", "reason": "Controles de acceso se implementan en el código"},
    ],
    "datos": [
        {"layer": "desarrollo", "impact": "high", "reason": "Cambios en modelo de datos requieren ajustes en repositorios y servicios"},
        {"layer": "arquitectura", "impact": "medium", "reason": "Nuevas entidades pueden requerir nuevos componentes o servicios"},
        {"layer": "qa", "impact": "medium", "reason": "Cambios en datos requieren actualizar fixtures y pruebas de integración"},
        {"layer": "acceso_datos", "impact": "low", "reason": "Nuevas tablas/campos pueden necesitar permisos específicos"},
    ],
    "desarrollo": [
        {"layer": "qa", "impact": "high", "reason": "Cambios en patrones de código requieren actualizar pruebas unitarias"},
        {"layer": "datos", "impact": "low", "reason": "Cambios en implementación pueden revelar necesidad de ajustes en modelo"},
    ],
    "qa": [
        {"layer": "desarrollo", "impact": "medium", "reason": "Nuevos criterios de calidad pueden requerir refactoring"},
        {"layer": "negocio", "impact": "low", "reason": "Hallazgos en QA pueden revelar gaps en reglas de negocio"},
    ],
}


async def route_api_spec_impact(request: Request) -> JSONResponse:
    """API: analiza el impacto cross-layer de un cambio propuesto.

    POST /api/spec/{spec_id}/impact
    Body JSON:
    {
        "layer": "negocio",
        "change_type": "add" | "edit" | "delete",
        "change_description": "texto del cambio propuesto"
    }

    Retorna:
    {
        "status": "success",
        "source_layer": "negocio",
        "impacts": [
            {"layer": "arquitectura", "label": "Arquitectura", "impact": "high", "reason": "..."},
            ...
        ]
    }
    """
    spec_id = request.path_params.get("spec_id", "")

    spec_engine = get_spec_engine()
    if not spec_engine:
        return JSONResponse({"error": "SpecEngine no disponible."}, status_code=500)

    spec = spec_engine.get_spec(spec_id)
    if not spec:
        return JSONResponse({"error": f"Spec '{spec_id}' no encontrada."}, status_code=404)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "Body JSON inválido."}, status_code=400)

    layer_name = body.get("layer", "")
    change_type = body.get("change_type", "edit")
    change_description = body.get("change_description", "")

    if layer_name not in LAYER_IMPACT_MATRIX:
        return JSONResponse({"error": f"Capa '{layer_name}' no tiene matriz de impacto definida."}, status_code=400)

    # Get base impacts from matrix
    raw_impacts = LAYER_IMPACT_MATRIX.get(layer_name, [])

    # Enrich impacts: only show layers that exist in the spec (have content)
    from src.models.sdd import SDD_LAYER_META
    impacts = []
    for imp in raw_impacts:
        target_layer = imp["layer"]
        target_content = spec.layers.get(target_layer)
        has_content = bool(target_content and (target_content.summary or target_content.decisions or target_content.constraints))

        meta = SDD_LAYER_META.get(target_layer, {})
        label = target_layer.replace("_", " ").capitalize()

        # Elevate impact for deletes
        impact_level = imp["impact"]
        if change_type == "delete" and impact_level == "medium":
            impact_level = "high"

        impacts.append({
            "layer": target_layer,
            "label": label,
            "impact": impact_level,
            "reason": imp["reason"],
            "has_content": has_content,
            "suggestion": _generate_impact_suggestion(target_layer, change_type, change_description),
        })

    # Sort by impact level (high first)
    impact_order = {"high": 0, "medium": 1, "low": 2}
    impacts.sort(key=lambda x: impact_order.get(x["impact"], 3))

    return JSONResponse({
        "status": "success",
        "source_layer": layer_name,
        "change_type": change_type,
        "impacts": impacts,
    })


def _generate_impact_suggestion(target_layer: str, change_type: str, description: str) -> str:
    """Genera una sugerencia de acción para la capa impactada.

    Args:
        target_layer: Capa que recibe el impacto.
        change_type: Tipo de cambio (add, edit, delete).
        description: Descripción del cambio.

    Returns:
        Sugerencia textual de qué revisar o actualizar.
    """
    suggestions = {
        "arquitectura": {
            "add": "Verificar si se necesitan nuevos componentes o servicios para soportar este cambio.",
            "edit": "Revisar si los patrones arquitectónicos actuales siguen siendo válidos.",
            "delete": "Evaluar si algún componente arquitectónico queda sin justificación.",
        },
        "datos": {
            "add": "Evaluar si se requieren nuevas tablas, campos o relaciones en el modelo.",
            "edit": "Revisar si el modelo de datos actual sigue siendo consistente.",
            "delete": "Verificar si alguna entidad o campo queda huérfano.",
        },
        "seguridad": {
            "add": "Validar si el nuevo elemento requiere controles de seguridad específicos.",
            "edit": "Revisar si las políticas de seguridad existentes cubren el cambio.",
            "delete": "Confirmar que no se eliminan controles de seguridad necesarios.",
        },
        "desarrollo": {
            "add": "Planificar la implementación siguiendo los patrones establecidos.",
            "edit": "Revisar código existente que puede verse afectado.",
            "delete": "Identificar código que puede eliminarse o simplificarse.",
        },
        "qa": {
            "add": "Diseñar casos de prueba para validar el nuevo comportamiento.",
            "edit": "Actualizar pruebas existentes que cubren esta funcionalidad.",
            "delete": "Remover pruebas obsoletas y validar que no hay regresiones.",
        },
        "gobierno_info": {
            "add": "Evaluar implicaciones de compliance y retención de datos.",
            "edit": "Verificar que el cambio cumple con políticas vigentes.",
            "delete": "Confirmar que no se violan políticas de retención o auditoría.",
        },
        "acceso_datos": {
            "add": "Definir permisos y roles necesarios para el nuevo elemento.",
            "edit": "Revisar si los permisos actuales siguen siendo apropiados.",
            "delete": "Revocar permisos que ya no son necesarios.",
        },
        "negocio": {
            "add": "Validar alineamiento con los procesos de negocio existentes.",
            "edit": "Confirmar con stakeholders de negocio que el cambio es aceptable.",
            "delete": "Verificar que no se rompen flujos de negocio dependientes.",
        },
    }

    layer_suggestions = suggestions.get(target_layer, {})
    return layer_suggestions.get(change_type, "Revisar si esta capa requiere ajustes.")


async def route_api_spec_stories(request: Request) -> JSONResponse:
    """API: lista las HUs asociadas al proyecto/spec actual.

    GET /api/spec/{spec_id}/stories
    Retorna lista resumida de historias de usuario disponibles en la memoria
    del workspace activo, con id, titulo, status y narrativa.
    """
    spec_id = request.path_params.get("spec_id", "")

    spec_engine = get_spec_engine()
    if not spec_engine:
        return JSONResponse({"stories": [], "error": "SpecEngine no disponible."}, status_code=500)

    spec = spec_engine.get_spec(spec_id)
    if not spec:
        return JSONResponse({"stories": [], "error": f"Spec '{spec_id}' no encontrada."}, status_code=404)

    try:
        memory = get_memory()
        all_stories = memory.get_all_stories()
        stories_data = []
        for story in all_stories:
            stories_data.append({
                "id": story.id,
                "title": story.title,
                "status": story.status,
                "narrative": story.narrative.model_dump(mode="json") if story.narrative else None,
                "complexity_tags": story.complexity_tags,
                "total_gaps": story.total_gaps,
                "total_questions": story.total_questions,
            })
        return JSONResponse({"stories": stories_data, "spec_id": spec_id})
    except RuntimeError as exc:
        logger.warning("No se pudo cargar stories: %s", exc)
        return JSONResponse({"stories": [], "warning": str(exc)})


async def route_story_index(request: Request) -> HTMLResponse:
    """Sirve la UI HTML de detalle de una Historia de Usuario.

    GET /story?id=HU-XXX
    Renderiza la pagina de detalle completo de la HU. El frontend
    usa el query param 'id' para cargar datos desde /api/story/{id}.
    """
    try:
        html = STORY_DETAIL_HTML_PATH.read_text(encoding="utf-8")
        return HTMLResponse(content=html, status_code=200)
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Story Detail UI not found</h1>",
            status_code=500,
        )


async def route_api_spec_associations(request: Request) -> JSONResponse:
    """API: gestiona asociaciones entre HUs y items de capas del SDD.

    POST /api/spec/{spec_id}/associations
    Body JSON:
    {
        "action": "add" | "remove",
        "layer": "negocio",
        "item_id": "DN-001",
        "story_id": "HU-001"
    }

    GET /api/spec/{spec_id}/associations
    Retorna todas las asociaciones de la spec agrupadas por capa.

    Permite vincular HUs específicas a decisiones, restricciones o artefactos
    individuales dentro de una capa del SDD, creando trazabilidad bidireccional.
    """
    spec_id = request.path_params.get("spec_id", "")

    spec_engine = get_spec_engine()
    if not spec_engine:
        return JSONResponse({"error": "SpecEngine no disponible."}, status_code=500)

    spec = spec_engine.get_spec(spec_id)
    if not spec:
        return JSONResponse({"error": f"Spec '{spec_id}' no encontrada."}, status_code=404)

    if request.method == "GET":
        all_associations: dict[str, dict[str, list[str]]] = {}
        for layer_name, layer_content in spec.layers.items():
            if layer_content.associations:
                all_associations[layer_name] = layer_content.associations
        return JSONResponse({"spec_id": spec_id, "associations": all_associations})

    # POST: add or remove association
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "Body JSON inválido."}, status_code=400)

    action = body.get("action", "")
    layer_name = body.get("layer", "")
    item_id = body.get("item_id", "").strip()
    story_id = body.get("story_id", "").strip()

    if action not in ("add", "remove"):
        return JSONResponse({"error": "action debe ser 'add' o 'remove'."}, status_code=400)
    if not layer_name or not item_id or not story_id:
        return JSONResponse({"error": "Campos requeridos: layer, item_id, story_id."}, status_code=400)

    try:
        sdd_layer = SDDLayer(layer_name)
    except ValueError:
        valid = [layer.value for layer in SDDLayer]
        return JSONResponse({"error": f"Capa '{layer_name}' no válida. Opciones: {valid}"}, status_code=400)

    layer_content = spec.layers.get(sdd_layer.value)
    if not layer_content:
        return JSONResponse({"error": f"Capa '{layer_name}' no tiene contenido."}, status_code=404)

    if action == "add":
        if item_id not in layer_content.associations:
            layer_content.associations[item_id] = []
        if story_id not in layer_content.associations[item_id]:
            layer_content.associations[item_id].append(story_id)
            logger.info("Asociación añadida: %s → %s en capa '%s' de spec '%s'", story_id, item_id, layer_name, spec_id)
    elif action == "remove":
        if item_id in layer_content.associations and story_id in layer_content.associations[item_id]:
            layer_content.associations[item_id].remove(story_id)
            if not layer_content.associations[item_id]:
                del layer_content.associations[item_id]
            logger.info("Asociación removida: %s → %s en capa '%s' de spec '%s'", story_id, item_id, layer_name, spec_id)
        else:
            return JSONResponse({"error": f"Asociación no encontrada: {story_id} → {item_id}"}, status_code=404)

    spec.updated_at = datetime.now().isoformat()
    spec_engine._save_spec(spec)

    return JSONResponse({
        "status": "success",
        "action": action,
        "spec_id": spec_id,
        "layer": layer_name,
        "item_id": item_id,
        "story_id": story_id,
        "current_associations": layer_content.associations.get(item_id, []),
    })
