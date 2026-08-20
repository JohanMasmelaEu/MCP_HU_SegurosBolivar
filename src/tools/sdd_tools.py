"""Tool implementations: manage_rules_catalog, create_spec, update_spec_layer, approve_spec, get_spec, list_specs."""

import logging
from typing import Optional

from src.engine.rules_catalog import get_rules_catalog
from src.engine.spec_engine import get_spec_engine
from src.models.sdd import LayerContent, SDDLayer, TransversalRule

logger = logging.getLogger("mcp_hu.tools.sdd")


def handle_manage_rules_catalog(action: str, rule_data: Optional[dict] = None) -> dict:
    """Gestiona el catálogo de reglas transversales.

    Args:
        action: Acción a realizar: add, list, update, remove, get.
        rule_data: Datos de la regla (requerido para add, update, get, remove).

    Returns:
        Resultado de la operación.
    """
    catalog = get_rules_catalog()
    if not catalog:
        return {"status": "error", "message": "RulesCatalogEngine no disponible. El servidor no se inicializó correctamente."}

    if action == "list":
        category = rule_data.get("category") if rule_data else None
        rules = catalog.list_rules(category=category)
        return {
            "status": "success",
            "total_rules": len(rules),
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "name": r.name,
                    "version": r.version,
                    "category": r.category,
                    "applies_to_layers": [l.value for l in r.applies_to_layers],
                    "applies_to_stacks": r.applies_to_stacks,
                    "created_at": r.created_at,
                }
                for r in rules
            ],
        }

    if action == "get":
        if not rule_data or not rule_data.get("rule_id"):
            return {"status": "error", "message": "Se requiere 'rule_id' para obtener una regla."}
        rule = catalog.get_rule(rule_data["rule_id"])
        if not rule:
            return {"status": "error", "message": f"Regla '{rule_data['rule_id']}' no encontrada."}
        return {"status": "success", "rule": rule.model_dump(mode="json")}

    if action == "add":
        if not rule_data:
            return {"status": "error", "message": "Se requiere 'rule_data' para agregar una regla."}
        try:
            rule = TransversalRule(**rule_data)
        except Exception as e:
            return {"status": "error", "message": f"Datos de regla inválidos: {e}"}
        try:
            catalog.add_rule(rule)
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        return {
            "status": "success",
            "rule_id": rule.rule_id,
            "message": f"Regla '{rule.rule_id}' agregada al catálogo.",
        }

    if action == "update":
        if not rule_data or not rule_data.get("rule_id"):
            return {"status": "error", "message": "Se requiere 'rule_id' y campos a actualizar."}
        rule_id = rule_data.pop("rule_id")
        updated = catalog.update_rule(rule_id, rule_data)
        if not updated:
            return {"status": "error", "message": f"Regla '{rule_id}' no encontrada."}
        return {
            "status": "success",
            "rule_id": rule_id,
            "message": f"Regla '{rule_id}' actualizada.",
        }

    if action == "remove":
        if not rule_data or not rule_data.get("rule_id"):
            return {"status": "error", "message": "Se requiere 'rule_id' para eliminar."}
        removed = catalog.remove_rule(rule_data["rule_id"])
        if not removed:
            return {"status": "error", "message": f"Regla '{rule_data['rule_id']}' no encontrada."}
        return {
            "status": "success",
            "rule_id": rule_data["rule_id"],
            "message": f"Regla '{rule_data['rule_id']}' eliminada del catálogo.",
        }

    return {"status": "error", "message": f"Acción '{action}' no válida. Opciones: add, list, update, remove, get."}


def handle_create_spec(spec_config: dict) -> dict:
    """Crea una nueva ProjectSpec y opcionalmente aplica reglas del catálogo.

    Args:
        spec_config: Dict con spec_id, project_name, app_id (opcional), apply_rules (bool, opcional).

    Returns:
        Status de la operación.
    """
    engine = get_spec_engine()
    if not engine:
        return {"status": "error", "message": "SpecEngine no disponible. El servidor no se inicializó correctamente."}

    spec_id = spec_config.get("spec_id")
    project_name = spec_config.get("project_name")

    if not spec_id or not project_name:
        return {"status": "error", "message": "Se requiere 'spec_id' y 'project_name'."}

    app_id = spec_config.get("app_id")
    apply_rules = spec_config.get("apply_rules", True)

    try:
        spec = engine.create_spec(spec_id, project_name, app_id=app_id)
    except ValueError as e:
        return {"status": "error", "message": str(e)}

    rules_applied = 0
    if apply_rules:
        updated = engine.apply_catalog_rules(spec_id)
        if updated:
            rules_applied = len(updated.rules_applied)

    return {
        "status": "success",
        "spec_id": spec.spec_id,
        "project_name": spec.project_name,
        "app_id": spec.app_id,
        "rules_applied": rules_applied,
        "message": (
            f"Spec '{spec_id}' creada para proyecto '{project_name}'. "
            f"{rules_applied} reglas del catálogo aplicadas."
        ),
    }


def handle_update_spec_layer(spec_id: str, layer: str, content: dict) -> dict:
    """Actualiza una capa de una spec.

    Args:
        spec_id: ID de la spec.
        layer: Valor del SDDLayer (ej: 'negocio', 'arquitectura').
        content: Dict con summary, decisions, constraints, artifacts.

    Returns:
        Status de la operación.
    """
    engine = get_spec_engine()
    if not engine:
        return {"status": "error", "message": "SpecEngine no disponible. El servidor no se inicializó correctamente."}

    try:
        sdd_layer = SDDLayer(layer)
    except ValueError:
        valid = [l.value for l in SDDLayer]
        return {"status": "error", "message": f"Capa '{layer}' no válida. Opciones: {valid}"}

    try:
        layer_content = LayerContent(**content)
    except Exception as e:
        return {"status": "error", "message": f"Contenido de capa inválido: {e}"}

    updated = engine.update_layer(spec_id, sdd_layer, layer_content)
    if not updated:
        return {"status": "error", "message": f"Spec '{spec_id}' no encontrada."}

    return {
        "status": "success",
        "spec_id": spec_id,
        "layer": layer,
        "message": f"Capa '{layer}' actualizada en spec '{spec_id}'.",
    }


def handle_approve_spec(spec_id: str, approver: str) -> dict:
    """Aprueba una spec.

    Args:
        spec_id: ID de la spec.
        approver: Nombre/ID del aprobador.

    Returns:
        Status de la operación.
    """
    engine = get_spec_engine()
    if not engine:
        return {"status": "error", "message": "SpecEngine no disponible. El servidor no se inicializó correctamente."}

    if not spec_id or not approver:
        return {"status": "error", "message": "Se requiere 'spec_id' y 'approver'."}

    updated = engine.approve_spec(spec_id, approver)
    if not updated:
        return {"status": "error", "message": f"Spec '{spec_id}' no encontrada."}

    return {
        "status": "success",
        "spec_id": spec_id,
        "status_new": updated.status,
        "approved_by": updated.approved_by,
        "message": f"Spec '{spec_id}' aprobada por '{approver}'.",
    }


def handle_get_spec(spec_id: str, role: Optional[str] = None) -> dict:
    """Obtiene una spec, opcionalmente filtrada por rol.

    Args:
        spec_id: ID de la spec.
        role: Rol del stakeholder para filtrar por profundidad. None = completa.

    Returns:
        Spec completa o filtrada.
    """
    engine = get_spec_engine()
    if not engine:
        return {"status": "error", "message": "SpecEngine no disponible. El servidor no se inicializó correctamente."}

    if role:
        result = engine.get_spec_for_role(spec_id, role)
        if not result:
            return {"status": "error", "message": f"Spec '{spec_id}' no encontrada."}
        return {"status": "success", **result}

    spec = engine.get_spec(spec_id)
    if not spec:
        return {"status": "error", "message": f"Spec '{spec_id}' no encontrada."}

    return {"status": "success", "spec": spec.model_dump(mode="json")}


def handle_list_specs() -> dict:
    """Lista resúmenes de todas las specs.

    Returns:
        Lista de specs con metadata básica.
    """
    engine = get_spec_engine()
    if not engine:
        return {"status": "error", "message": "SpecEngine no disponible. El servidor no se inicializó correctamente."}

    specs = engine.list_specs()
    return {
        "status": "success",
        "total_specs": len(specs),
        "specs": specs,
    }



# ─── CONSTELLATION TOOLS ─────────────────────────────────────────────────────────


def _get_constellation_engine():
    """Obtiene una instancia de ConstellationEngine con el ecosistema y specs activos.

    Returns:
        ConstellationEngine o None si faltan dependencias.
    """
    from src.engine.constellation import ConstellationEngine
    from src.engine.ecosystem import get_ecosystem
    from src.engine.spec_engine import get_spec_engine

    spec_engine = get_spec_engine()
    if not spec_engine:
        return None

    try:
        ecosystem = get_ecosystem()
    except RuntimeError:
        ecosystem = None

    if not ecosystem or not ecosystem.is_initialized:
        # Crear un engine sin ecosistema — solo specs
        from src.engine.ecosystem import EcosystemEngine
        ecosystem = EcosystemEngine()

    return ConstellationEngine(ecosystem, spec_engine)


def handle_get_constellation(ecosystem_id: Optional[str] = None, filter_type: Optional[str] = None, filter_maturity: Optional[str] = None) -> dict:
    """Retorna el grafo de specs del ecosistema activo.

    Args:
        ecosystem_id: ID del ecosistema (opcional, usa activo si None).
        filter_type: Filtro por tipo de relación (process, data, functional).
        filter_maturity: Filtro por maturity (formalized, draft, reference).

    Returns:
        Grafo en formato Cytoscape.js con nodos y edges.
    """
    engine = _get_constellation_engine()
    if not engine:
        return {"status": "error", "message": "ConstellationEngine no disponible. Verificar SpecEngine y EcosystemEngine."}

    graph = engine.build_constellation()

    # Aplicar filtros opcionales
    if filter_type:
        graph["edges"] = [e for e in graph["edges"] if e["data"].get("dependency_type") == filter_type]
    if filter_maturity:
        graph["edges"] = [e for e in graph["edges"] if e["data"].get("maturity") == filter_maturity]

    return {
        "status": "success",
        "total_nodes": len(graph["nodes"]),
        "total_edges": len(graph["edges"]),
        "graph": graph,
    }


def handle_add_spec_dependency(spec_id: str, target_spec_id: str, dependency_type: str, description: str = "") -> dict:
    """Agrega una dependencia entre dos specs.

    Args:
        spec_id: ID de la spec que depende.
        target_spec_id: ID de la spec de la que se depende.
        dependency_type: Tipo (process, data, functional).
        description: Descripción opcional.

    Returns:
        Status de la operación.
    """
    engine = get_spec_engine()
    if not engine:
        return {"status": "error", "message": "SpecEngine no disponible."}

    if dependency_type not in ("process", "data", "functional"):
        return {"status": "error", "message": f"dependency_type '{dependency_type}' no válido. Opciones: process, data, functional."}

    spec = engine.get_spec(spec_id)
    if not spec:
        return {"status": "error", "message": f"Spec '{spec_id}' no encontrada."}

    # Verificar que no exista ya la misma dependencia
    already_exists = any(
        d.target_spec_id == target_spec_id and d.dependency_type == dependency_type
        for d in spec.dependencies
    )
    if already_exists:
        return {"status": "error", "message": f"Dependencia '{spec_id}' → '{target_spec_id}' ({dependency_type}) ya existe."}

    from src.models.sdd import SpecDependency as SpecDep

    new_dep = SpecDep(
        target_spec_id=target_spec_id,
        dependency_type=dependency_type,
        description=description,
        maturity="draft",
    )
    spec.dependencies.append(new_dep)
    spec.updated_at = __import__("datetime").datetime.now().isoformat()
    engine._save_spec(spec)

    return {
        "status": "success",
        "spec_id": spec_id,
        "target_spec_id": target_spec_id,
        "dependency_type": dependency_type,
        "message": f"Dependencia agregada: '{spec_id}' → '{target_spec_id}' ({dependency_type}).",
    }


def handle_detect_constellation_gaps(ecosystem_id: Optional[str] = None) -> dict:
    """Detecta gaps en la constelación de specs.

    Args:
        ecosystem_id: ID del ecosistema (opcional, usa activo si None).

    Returns:
        Lista de gaps detectados.
    """
    engine = _get_constellation_engine()
    if not engine:
        return {"status": "error", "message": "ConstellationEngine no disponible."}

    gaps = engine.detect_gaps()

    return {
        "status": "success",
        "total_gaps": len(gaps),
        "by_type": {
            "orphan_spec": len([g for g in gaps if g["type"] == "orphan_spec"]),
            "unresolved_reference": len([g for g in gaps if g["type"] == "unresolved_reference"]),
            "dependency_cycle": len([g for g in gaps if g["type"] == "dependency_cycle"]),
            "app_without_spec": len([g for g in gaps if g["type"] == "app_without_spec"]),
        },
        "gaps": gaps,
    }



# ─── EXPORT / IMPORT TOOLS ───────────────────────────────────────────────────────


def handle_export_spec_markdown(spec_id: str, output_path: Optional[str] = None) -> dict:
    """Exporta una spec como archivo Markdown con contenido completo.

    Genera un documento estructurado con capas, decisiones expandidas,
    constraints detallados, artefactos y dependencias.

    IMPORTANTE: Siempre retorna el campo 'markdown' en la respuesta para que
    el llamador pueda escribir el archivo con sus propias herramientas si el
    MCP no tiene acceso directo al filesystem del host (ej: Docker).

    Args:
        spec_id: ID de la spec a exportar.
        output_path: Ruta de salida opcional. Si se proporciona, intenta guardar
                     el archivo ahí además de retornar el markdown.

    Returns:
        Status con el markdown generado y opcionalmente la ruta donde se guardó.
    """
    engine = get_spec_engine()
    if not engine:
        return {"status": "error", "message": "SpecEngine no disponible."}

    spec = engine.get_spec(spec_id)
    if not spec:
        return {"status": "error", "message": f"Spec '{spec_id}' no encontrada."}

    markdown = _render_spec_to_markdown(spec)

    # Intentar escribir archivo si se proporcionó output_path
    if output_path:
        write_result = _try_write_output(output_path, markdown)
        return {
            "status": "success",
            "spec_id": spec_id,
            "markdown": markdown,
            "output_path": write_result.get("path"),
            "file_written": write_result["written"],
            "write_warning": write_result.get("warning"),
            "message": (
                f"Spec '{spec_id}' exportada. "
                f"{'Archivo guardado en ' + write_result['path'] + '.' if write_result['written'] else 'ADVERTENCIA: No se pudo escribir el archivo — use el campo markdown para guardarlo manualmente.'}"
            ),
        }

    return {
        "status": "success",
        "spec_id": spec_id,
        "markdown": markdown,
        "message": f"Spec '{spec_id}' exportada como markdown.",
    }


def _try_write_output(output_path: str, content: str) -> dict:
    """Intenta escribir el contenido en la ruta indicada.

    Valida accesibilidad y permisos antes de escribir. Maneja el caso
    donde el MCP corre en Docker y el path del host no es accesible.

    Args:
        output_path: Ruta absoluta o relativa donde escribir.
        content: Contenido markdown a escribir.

    Returns:
        Dict con 'written' (bool), 'path' (str), y opcionalmente 'warning' (str).
    """
    from pathlib import Path

    out = Path(output_path)

    try:
        # Verificar si el directorio padre existe o se puede crear
        out.parent.mkdir(parents=True, exist_ok=True)

        # Verificar que podemos escribir en el directorio
        if not out.parent.exists():
            return {
                "written": False,
                "path": str(out),
                "warning": (
                    f"No se pudo crear el directorio '{out.parent}'. "
                    "Si el MCP corre en Docker, el path del host no es accesible. "
                    "Use el campo 'markdown' de la respuesta para guardar el archivo manualmente."
                ),
            }

        out.write_text(content, encoding="utf-8")

        # Verificar que efectivamente se escribió
        if out.exists() and out.stat().st_size > 0:
            return {"written": True, "path": str(out)}
        else:
            return {
                "written": False,
                "path": str(out),
                "warning": "write_text no lanzó error pero el archivo no se encuentra o está vacío.",
            }

    except PermissionError:
        return {
            "written": False,
            "path": str(out),
            "warning": (
                f"Sin permisos para escribir en '{out}'. "
                "Use el campo 'markdown' de la respuesta para guardar el archivo manualmente."
            ),
        }
    except OSError as e:
        return {
            "written": False,
            "path": str(out),
            "warning": (
                f"Error de filesystem al escribir: {e}. "
                "Si el MCP corre en Docker, rutas absolutas del host no son accesibles desde el container. "
                "Use el campo 'markdown' de la respuesta para guardar el archivo manualmente."
            ),
        }


def _render_spec_to_markdown(spec) -> str:
    """Genera el markdown completo de una spec con contenido expandido.

    Renderiza todas las capas con sus decisiones, constraints y artefactos.
    Si el campo 'details' tiene contenido expandido por ID, lo incluye
    como sub-sección debajo de cada item para máximo detalle.

    Args:
        spec: ProjectSpec a renderizar.

    Returns:
        String con el markdown completo.
    """
    from src.models.sdd import SDD_LAYER_META

    lines: list[str] = []
    lines.append(f"# {spec.project_name} — Software Design Document v{spec.version}")
    lines.append("")
    lines.append(f"**Status:** {spec.status}  ")
    approvers = ", ".join(spec.approved_by) if spec.approved_by else "Pendiente de aprobación"
    lines.append(f"**Aprobado por:** {approvers}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Capas")
    lines.append("")

    for layer_value, content in spec.layers.items():
        if not content.summary and not content.decisions and not content.constraints and not content.artifacts:
            continue

        meta = SDD_LAYER_META.get(layer_value, {})
        category = meta.get("category", "").capitalize()
        layer_title = layer_value.replace("_", " ").capitalize()

        lines.append(f"### {layer_title} ({category})")
        lines.append("")

        # Summary
        if content.summary:
            lines.append(content.summary)
            lines.append("")

        # Decisiones con detalle expandido
        if content.decisions:
            lines.append("#### Decisiones")
            lines.append("")
            for d in content.decisions:
                lines.append(f"- **{d}**")
                # Buscar detalle expandido por ID (ej: "DN-001" extraído del string)
                detail_text = _find_detail_for_item(d, content.details)
                if detail_text:
                    # Indentar el detalle como sub-contenido
                    for detail_line in detail_text.strip().split("\n"):
                        lines.append(f"  {detail_line}")
                    lines.append("")
            lines.append("")

        # Restricciones con detalle expandido
        if content.constraints:
            lines.append("#### Restricciones")
            lines.append("")
            for c in content.constraints:
                lines.append(f"- **{c}**")
                detail_text = _find_detail_for_item(c, content.details)
                if detail_text:
                    for detail_line in detail_text.strip().split("\n"):
                        lines.append(f"  {detail_line}")
                    lines.append("")
            lines.append("")

        # Artefactos con detalle expandido
        if content.artifacts:
            lines.append("#### Artefactos")
            lines.append("")
            for a in content.artifacts:
                lines.append(f"- **{a}**")
                detail_text = _find_detail_for_item(a, content.details)
                if detail_text:
                    for detail_line in detail_text.strip().split("\n"):
                        lines.append(f"  {detail_line}")
                    lines.append("")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Reglas aplicadas
    if spec.rules_applied:
        lines.append("## Reglas aplicadas")
        lines.append("")
        catalog = get_rules_catalog()
        for rule_id in spec.rules_applied:
            rule = catalog.get_rule(rule_id) if catalog else None
            if rule:
                lines.append(f"- **{rule.rule_id}**: {rule.name} (v{rule.version})")
            else:
                lines.append(f"- {rule_id}")
        lines.append("")

    # Dependencias
    if spec.dependencies:
        lines.append("## Dependencias")
        lines.append("")
        for dep in spec.dependencies:
            lines.append(f"- → **{dep.target_spec_id}** ({dep.dependency_type}, {dep.maturity})")
            if dep.description:
                lines.append(f"  {dep.description}")
        lines.append("")

    return "\n".join(lines)


def _find_detail_for_item(item_text: str, details: dict[str, str]) -> Optional[str]:
    """Busca el detalle expandido para un item en el diccionario de details.

    Estrategia de matching:
    1. Match exacto por clave (ej: "DN-001: Pipeline parametrizable" → busca "DN-001: Pipeline parametrizable")
    2. Match por prefijo ID (ej: si el item empieza con "DN-001:", busca clave "DN-001")
    3. Match parcial (si alguna clave del dict está contenida al inicio del item)

    Args:
        item_text: Texto del item (decisión, constraint o artifact).
        details: Diccionario de detalles expandidos.

    Returns:
        Texto detallado o None si no se encuentra.
    """
    if not details:
        return None

    # 1. Match exacto
    if item_text in details:
        return details[item_text]

    # 2. Match por prefijo ID (ej: "DN-001: texto largo" → buscar clave "DN-001")
    import re
    id_match = re.match(r"^([A-Z]{1,5}-\d{1,4})", item_text)
    if id_match:
        item_id = id_match.group(1)
        if item_id in details:
            return details[item_id]

    # 3. Match parcial — clave contenida al inicio del item
    for key in details:
        if item_text.startswith(key):
            return details[key]

    return None


def handle_import_spec(source_path: str, as_reference: bool = True) -> dict:
    """Importa specs desde un archivo Markdown o directorio.

    Args:
        source_path: Ruta al archivo .md o directorio con .md files.
        as_reference: Si True, specs importadas entran con status='draft' y maturity='reference'.

    Returns:
        Resumen de lo importado.
    """
    from pathlib import Path

    engine = get_spec_engine()
    if not engine:
        return {"status": "error", "message": "SpecEngine no disponible."}

    source = Path(source_path)
    if not source.exists():
        return {"status": "error", "message": f"Ruta '{source_path}' no encontrada."}

    files_to_process: list[Path] = []
    if source.is_file() and source.suffix == ".md":
        files_to_process.append(source)
    elif source.is_dir():
        files_to_process = list(source.glob("*.md"))
    else:
        return {"status": "error", "message": f"'{source_path}' no es un archivo .md ni un directorio."}

    imported_specs: list[str] = []
    imported_deps: int = 0
    errors: list[str] = []

    for md_file in files_to_process:
        try:
            result = _parse_spec_markdown(md_file, as_reference, engine)
            if result:
                imported_specs.append(result["spec_id"])
                imported_deps += result.get("deps_count", 0)
        except Exception as e:
            errors.append(f"{md_file.name}: {e}")

    return {
        "status": "success",
        "specs_imported": len(imported_specs),
        "dependencies_detected": imported_deps,
        "spec_ids": imported_specs,
        "errors": errors,
        "message": (
            f"{len(imported_specs)} specs importadas, {imported_deps} dependencias detectadas."
            + (f" {len(errors)} errores." if errors else "")
        ),
    }


def _parse_spec_markdown(md_file, as_reference: bool, engine) -> Optional[dict]:
    """Parsea un archivo markdown para crear un ProjectSpec.

    Args:
        md_file: Path al archivo .md.
        as_reference: Si True, importa con status draft.
        engine: SpecEngine para persistir.

    Returns:
        Dict con spec_id y deps_count, o None si no se pudo parsear.
    """
    from src.models.sdd import LayerContent, SpecDependency as SpecDep

    content = md_file.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Extraer título y spec_id
    project_name = md_file.stem
    spec_id = md_file.stem.lower().replace(" ", "-")

    for line in lines:
        if line.startswith("# "):
            # Intentar extraer nombre del patrón "# Name — Specification vX.Y.Z"
            title = line[2:].strip()
            if " — " in title:
                project_name = title.split(" — ")[0].strip()
                spec_id = project_name.lower().replace(" ", "-")
            else:
                project_name = title
                spec_id = project_name.lower().replace(" ", "-")
            break

    # Verificar si ya existe
    existing = engine.get_spec(spec_id)
    if existing:
        return {"spec_id": spec_id, "deps_count": 0}

    # Crear spec
    spec = engine.create_spec(spec_id, project_name)

    # Parsear capas
    current_layer: Optional[str] = None
    current_section: Optional[str] = None
    layer_data: dict[str, dict] = {}

    layer_keywords = {
        "negocio": "negocio",
        "arquitectura": "arquitectura",
        "seguridad": "seguridad",
        "gobierno": "gobierno_info",
        "acceso": "acceso_datos",
        "datos": "datos",
        "desarrollo": "desarrollo",
        "qa": "qa",
    }

    for line in lines:
        if line.startswith("### "):
            # Detectar capa
            layer_title = line[4:].strip().lower()
            current_layer = None
            for kw, layer_val in layer_keywords.items():
                if kw in layer_title:
                    current_layer = layer_val
                    if current_layer not in layer_data:
                        layer_data[current_layer] = {"summary": "", "decisions": [], "constraints": [], "artifacts": []}
                    break
            current_section = None
        elif line.startswith("**Decisiones:**"):
            current_section = "decisions"
        elif line.startswith("**Restricciones:**"):
            current_section = "constraints"
        elif line.startswith("**Artefactos:**"):
            current_section = "artifacts"
        elif line.startswith("- ") and current_layer and current_section:
            layer_data[current_layer][current_section].append(line[2:].strip())
        elif current_layer and not line.startswith("**") and not line.startswith("#") and line.strip():
            if current_section is None:
                # Es parte del summary
                layer_data[current_layer]["summary"] += (" " if layer_data[current_layer]["summary"] else "") + line.strip()

    # Aplicar capas parseadas
    from src.models.sdd import SDDLayer
    for layer_val, data in layer_data.items():
        try:
            sdd_layer = SDDLayer(layer_val)
            layer_content = LayerContent(**data)
            engine.update_layer(spec_id, sdd_layer, layer_content)
        except (ValueError, Exception):
            pass

    # Parsear dependencias
    deps_count = 0
    in_deps_section = False
    for line in lines:
        if line.startswith("## Dependencias"):
            in_deps_section = True
            continue
        if in_deps_section and line.startswith("## "):
            break
        if in_deps_section and line.startswith("- → "):
            # Formato: - → target_spec_id (type, maturity)
            dep_text = line[4:].strip()
            parts = dep_text.split(" (")
            if parts:
                target_id = parts[0].strip()
                dep_type = "functional"
                maturity = "reference"
                if len(parts) > 1:
                    meta = parts[1].rstrip(")")
                    meta_parts = [m.strip() for m in meta.split(",")]
                    if meta_parts:
                        dep_type = meta_parts[0] if meta_parts[0] in ("process", "data", "functional") else "functional"
                    if len(meta_parts) > 1:
                        maturity = meta_parts[1] if meta_parts[1] in ("formalized", "draft", "reference") else "reference"

                new_dep = SpecDep(
                    target_spec_id=target_id,
                    dependency_type=dep_type,
                    maturity=maturity if as_reference else maturity,
                )
                # Reload spec and add dependency
                spec_reloaded = engine.get_spec(spec_id)
                if spec_reloaded:
                    spec_reloaded.dependencies.append(new_dep)
                    engine._save_spec(spec_reloaded)
                    deps_count += 1

    return {"spec_id": spec_id, "deps_count": deps_count}
