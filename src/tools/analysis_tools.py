"""Tool implementations: analyze_story, add_story, get_story_context, get_expert_analysis, explain_for_stakeholder."""

import logging

from src.engine.ecosystem import get_ecosystem
from src.engine.experts import ExpertClassifier
from src.engine.memory import get_memory
from src.engine.segmenter import ContextSegmenter
from src.models.story import ExpertSection, ExpertType, StoryAnalysis

logger = logging.getLogger("mcp_hu.tools.analysis")

_classifier = ExpertClassifier()


def handle_analyze_story(story_text: str) -> dict:
    """Analiza una HU con el panel de expertos.

    Acepta cualquier formato de entrada. Retorna estructura estandarizada
    con expertos activados, sus focos de analisis, y preguntas.
    El LLM (Kiro) usa esta estructura como guia para generar el analisis profundo.

    Args:
        story_text: Texto de la HU en cualquier formato.

    Returns:
        Estructura de analisis con contexto relevante y expertos activados.
    """
    memory = get_memory()

    if not memory.is_initialized:
        return {"status": "error", "message": "Proyecto no inicializado. Usar init_project primero."}

    # Generar ID
    next_id = memory.get_next_story_id()

    # Clasificar expertos
    activated_experts = _classifier.classify(story_text)

    # Obtener contexto relevante (si hay HUs previas)
    relevant_context = []
    summaries = memory.get_all_summaries()
    if summaries:
        # Extraer keywords del texto para el segmenter
        keywords = _extract_keywords_from_text(story_text)
        # Detectar entidades mencionadas (buscar en entidades conocidas del proyecto)
        known_entities = [e.name for e in memory.get_entities()]
        detected_entities = [e for e in known_entities if e.lower() in story_text.lower()]
        # Detectar flujos mencionados
        known_flows = [f.name for f in memory.get_flows()]
        detected_flows = [f for f in known_flows if f.lower() in story_text.lower().replace(" ", "_")]

        segmenter = ContextSegmenter(summaries, memory.graph)
        relevant = segmenter.get_relevant_context(
            target_entities=detected_entities,
            target_flows=detected_flows,
            target_keywords=keywords,
        )

        # Cargar resumen de HUs relevantes
        for story_id, score in relevant:
            story = memory.get_story(story_id)
            if story:
                relevant_context.append({
                    "id": story.id,
                    "title": story.title,
                    "relevance_score": score,
                    "entities": story.entities_detected,
                    "flows": story.flows_detected,
                    "narrative_summary": f"{story.narrative.as_a} quiere {story.narrative.i_want}",
                })

    # Construir respuesta con contexto para que Kiro analice
    expert_contexts = []
    for expert_type in activated_experts:
        profile = _classifier.get_profile(expert_type)
        expert_contexts.append({
            "expert": expert_type.value,
            "name": profile.name,
            "analysis_focus": profile.analysis_focus,
            "standard_questions": profile.standard_questions,
        })

    return {
        "status": "success",
        "suggested_id": next_id,
        "raw_input": story_text,
        "experts_activated": [e.value for e in activated_experts],
        "expert_contexts": expert_contexts,
        "relevant_stories": relevant_context,
        "known_entities": [e.name for e in memory.get_entities()],
        "known_flows": [f.name for f in memory.get_flows()],
        "instructions_for_llm": (
            "Usa los expert_contexts para analizar la HU desde cada perspectiva. "
            "Para cada experto activado genera: rules, gaps, questions, edge_cases, suggestions. "
            "Estandariza la narrativa en formato as_a/i_want/so_that. "
            "Genera acceptance_criteria en formato given/when/then. "
            "Detecta entities_detected y flows_detected nuevos. "
            "Asigna complexity_tags y dependencies basado en relevant_stories. "
            "Respeta las entidades y flujos ya existentes en el proyecto (known_entities, known_flows)."
        ),
        "output_schema": {
            "id": next_id,
            "title": "string (conciso)",
            "narrative": {"as_a": "...", "i_want": "...", "so_that": "..."},
            "acceptance_criteria": [{"given": "...", "when": "...", "then": "..."}],
            "expert_analysis": [{"expert": "...", "rules": [], "gaps": [], "questions": [], "edge_cases": [], "suggestions": []}],
            "entities_detected": ["PascalCase"],
            "flows_detected": ["snake_case"],
            "complexity_tags": ["tag1", "tag2"],
            "dependencies": ["HU-XXX"],
            "impacts": ["HU-XXX"],
        },
    }


def handle_add_story(story_dict: dict) -> dict:
    """Persiste una HU analizada en la memoria.

    Args:
        story_dict: HU completa (output de analyze_story procesado por Kiro).

    Returns:
        Confirmacion.
    """
    memory = get_memory()

    if not memory.is_initialized:
        return {"status": "error", "message": "Proyecto no inicializado."}

    try:
        story = StoryAnalysis(**story_dict)
    except Exception as e:
        return {"status": "error", "message": f"Estructura de HU invalida: {e}"}

    # Verificar que no exista ya
    existing = memory.get_story(story.id)
    if existing:
        # Actualizar
        story.updated_at = __import__("datetime").datetime.now().isoformat()
        memory.save_story(story)
        return {
            "status": "success",
            "action": "updated",
            "story_id": story.id,
            "message": f"HU '{story.id}' actualizada en memoria.",
        }

    memory.save_story(story)
    return {
        "status": "success",
        "action": "created",
        "story_id": story.id,
        "title": story.title,
        "entities_registered": story.entities_detected,
        "flows_registered": story.flows_detected,
        "message": f"HU '{story.id}' persistida. Grafo y entidades actualizados.",
    }


def handle_get_story_context(story_id: str) -> dict:
    """Obtiene contexto segmentado relevante para una HU.

    Args:
        story_id: ID de la HU.

    Returns:
        Contexto segmentado con HUs relevantes.
    """
    memory = get_memory()

    if not memory.is_initialized:
        return {"status": "error", "message": "Proyecto no inicializado."}

    story = memory.get_story(story_id)
    if not story:
        return {"status": "error", "message": f"HU '{story_id}' no encontrada."}

    summaries = memory.get_all_summaries()
    if len(summaries) <= 1:
        return {
            "status": "success",
            "story_id": story_id,
            "relevant_stories": [],
            "message": "No hay otras HUs para comparar. Contexto vacio.",
        }

    keywords = _extract_keywords_from_text(
        f"{story.title} {story.narrative.i_want} {story.narrative.so_that}"
    )

    segmenter = ContextSegmenter(summaries, memory.graph)
    relevant = segmenter.get_relevant_context(
        target_entities=story.entities_detected,
        target_flows=story.flows_detected,
        target_keywords=keywords,
        target_id=story_id,
    )

    context_stories = []
    for sid, score in relevant:
        s = memory.get_story(sid)
        if s:
            context_stories.append({
                "id": s.id,
                "title": s.title,
                "score": score,
                "entities": s.entities_detected,
                "flows": s.flows_detected,
                "narrative": f"{s.narrative.as_a} quiere {s.narrative.i_want}",
                "dependencies": s.dependencies,
            })

    return {
        "status": "success",
        "story_id": story_id,
        "total_stories_in_project": len(summaries),
        "relevant_stories_count": len(context_stories),
        "tokens_saved_percent": round((1 - len(context_stories) / max(len(summaries) - 1, 1)) * 100),
        "relevant_stories": context_stories,
        "cross_app_context": _get_cross_app_context_for_story(story),
    }


def handle_get_expert_analysis(story_id: str, expert: str) -> dict:
    """Obtiene analisis profundo desde la perspectiva de un experto.

    Args:
        story_id: ID de la HU.
        expert: Nombre del experto.

    Returns:
        Contexto del experto + analisis existente si hay.
    """
    memory = get_memory()

    if not memory.is_initialized:
        return {"status": "error", "message": "Proyecto no inicializado."}

    story = memory.get_story(story_id)
    if not story:
        return {"status": "error", "message": f"HU '{story_id}' no encontrada."}

    try:
        expert_type = ExpertType(expert)
    except ValueError:
        valid = [e.value for e in ExpertType]
        return {"status": "error", "message": f"Experto '{expert}' no valido. Opciones: {valid}"}

    profile = _classifier.get_profile(expert_type)

    # Buscar analisis existente
    existing_analysis = next(
        (ea for ea in story.expert_analysis if ea.expert == expert_type), None
    )

    return {
        "status": "success",
        "story_id": story_id,
        "story_title": story.title,
        "expert": expert_type.value,
        "expert_name": profile.name,
        "expert_description": profile.description,
        "analysis_focus": profile.analysis_focus,
        "standard_questions": profile.standard_questions,
        "existing_analysis": existing_analysis.model_dump(mode="json") if existing_analysis else None,
        "story_narrative": story.narrative.model_dump(mode="json"),
        "story_entities": story.entities_detected,
        "story_flows": story.flows_detected,
        "instructions_for_llm": (
            f"Analiza la HU '{story_id}' desde la perspectiva de {profile.name}. "
            f"Foco: {', '.join(profile.analysis_focus[:3])}. "
            f"Responde las preguntas estandar y detecta gaps adicionales."
        ),
    }


def handle_explain_for_stakeholder(story_id: str, role: str) -> dict:
    """Reformula una HU para un stakeholder especifico.

    Args:
        story_id: ID de la HU.
        role: Rol del stakeholder.

    Returns:
        Contexto para que Kiro genere la explicacion adaptada.
    """
    memory = get_memory()

    if not memory.is_initialized:
        return {"status": "error", "message": "Proyecto no inicializado."}

    story = memory.get_story(story_id)
    if not story:
        return {"status": "error", "message": f"HU '{story_id}' no encontrada."}

    valid_roles = ["dev_frontend", "dev_backend", "qa", "po", "ux", "devops"]
    if role not in valid_roles:
        return {"status": "error", "message": f"Rol '{role}' no valido. Opciones: {valid_roles}"}

    # Contexto adaptado por rol
    role_focus = {
        "dev_frontend": {
            "perspective": "Desarrollador Frontend",
            "focus": "Que pantallas construir, flujos UI, APIs a consumir, estados, validaciones client-side",
            "include": ["ux", "backend_contracts"],
            "exclude": ["infra_details", "db_schema", "legal"],
        },
        "dev_backend": {
            "perspective": "Desarrollador Backend",
            "focus": "Endpoints a crear, validaciones server-side, modelo de datos, integraciones",
            "include": ["backend", "datos", "seguridad"],
            "exclude": ["ui_details", "ux_flows"],
        },
        "qa": {
            "perspective": "QA / Tester",
            "focus": "Criterios de aceptacion exactos, escenarios negativos, datos de prueba, boundary values",
            "include": ["acceptance_criteria", "negative_scenarios"],
            "exclude": ["implementation_details"],
        },
        "po": {
            "perspective": "Product Owner",
            "focus": "Valor de negocio, reglas, prioridad, dependencias, riesgos, impacto en el usuario",
            "include": ["negocio", "dependencies", "gaps"],
            "exclude": ["technical_details"],
        },
        "ux": {
            "perspective": "Disenador UX/UI",
            "focus": "Flujo del usuario paso a paso, estados de pantalla, micro-interacciones, accesibilidad",
            "include": ["ux", "flows", "states"],
            "exclude": ["backend_details", "db_schema"],
        },
        "devops": {
            "perspective": "DevOps / Infra",
            "focus": "Impacto en infra, feature flags, configuracion por ambiente, escalabilidad, despliegue",
            "include": ["devops", "observability"],
            "exclude": ["ui_details", "business_rules"],
        },
    }

    role_info = role_focus[role]

    return {
        "status": "success",
        "story_id": story_id,
        "story_title": story.title,
        "target_role": role,
        "perspective": role_info["perspective"],
        "focus": role_info["focus"],
        "story_full": story.model_dump(mode="json"),
        "instructions_for_llm": (
            f"Reformula la HU '{story_id}' para un {role_info['perspective']}. "
            f"Enfocate en: {role_info['focus']}. "
            f"Incluye: {', '.join(role_info['include'])}. "
            f"Omite detalles de: {', '.join(role_info['exclude'])}. "
            f"Usa lenguaje tecnico apropiado para el rol. "
            f"Estructura: resumen, que construir/validar, contratos relevantes, edge cases para ese rol."
        ),
    }


def _extract_keywords_from_text(text: str) -> list[str]:
    """Extrae keywords de texto libre para el segmenter."""
    stopwords = {"de", "la", "el", "en", "un", "una", "los", "las", "que", "para", "por",
                 "con", "del", "al", "se", "su", "es", "y", "o", "a", "como", "no", "si",
                 "debe", "puede", "cuando", "desde", "hasta", "ser", "tiene", "hay"}
    words = text.lower().split()
    return [w for w in words if len(w) > 2 and w not in stopwords]


def _get_cross_app_context_for_story(story) -> dict:
    """Obtiene contexto cross-app relevante para una HU si hay ecosistema.

    Args:
        story: StoryAnalysis de la HU.

    Returns:
        Dict con contexto cross-app o indicador de no disponible.
    """
    try:
        ecosystem = get_ecosystem()
        if not ecosystem.is_initialized:
            return {"available": False}

        memory = get_memory()
        current_app_id = None
        if memory.index and memory.index.config.app_id:
            current_app_id = memory.index.config.app_id

        context = ecosystem.get_cross_app_context(
            entity_names=story.entities_detected,
            flow_names=story.flows_detected,
            current_app_id=current_app_id,
        )
        return context
    except Exception:
        return {"available": False}
