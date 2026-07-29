"""Motor de bitácora: generación offline y compilación diaria.

Responsabilidades:
1. Generar bitácora offline (sin API) en Confluence Storage Format + Markdown
2. Compilar bitácora diaria con subtareas, tiempos y avances
3. Aplicar regla de 8 horas (validar overtime con el usuario)
4. Formatear datos para Clockwork Pro

La bitácora offline es el modo por defecto y SIEMPRE está disponible,
independientemente de si hay tokens configurados o no.
"""

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from src.engine.memory import get_memory
from src.models.documentation import (
    BitacoraEntry,
    DailyBitacora,
    WorkHoursConfig,
)

logger = logging.getLogger("mcp_hu.engine.bitacora")

# Configuración de horas — invariante de negocio
WORK_HOURS_CONFIG = WorkHoursConfig()

# Directorio de bitácoras locales
BITACORA_DIR = Path(".hu-memory/bitacoras")


class BitacoraEngine:
    """Motor de generación de bitácoras documentales.

    Genera documentación en formatos exportables (Confluence Storage Format,
    Markdown) y gestiona la lógica de negocio de horas laborales.
    """

    def __init__(self):
        """Inicializa el motor de bitácora."""
        self._ensure_bitacora_dir()

    def _ensure_bitacora_dir(self) -> None:
        """Crea el directorio de bitácoras si no existe."""
        BITACORA_DIR.mkdir(parents=True, exist_ok=True)

    # ─── GENERACIÓN OFFLINE (sin API) ────────────────────────────────────────────

    def generate_project_bitacora(self) -> dict:
        """Genera bitácora completa del proyecto en formato exportable.

        Incluye: resumen del proyecto, HUs analizadas, estimaciones,
        decisiones, flujos y estado actual.

        Returns:
            Dict con markdown, confluence_html y ruta del archivo guardado.
        """
        memory = get_memory()

        if not memory.is_initialized:
            return {
                "status": "error",
                "message": "Proyecto no inicializado. Usar init_project primero.",
            }

        index = memory.index
        if not index:
            return {"status": "error", "message": "No se pudo leer el índice del proyecto."}

        stories = memory.get_all_stories()
        entities = memory.get_entities()
        flows = memory.get_flows()
        summaries = memory.get_all_summaries()

        # Generar Markdown
        markdown = self._build_project_markdown(index, stories, entities, flows)

        # Generar Confluence Storage Format
        confluence_html = self._build_confluence_storage(index, stories, entities, flows)

        # Guardar archivo local
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        md_path = BITACORA_DIR / f"bitacora_proyecto_{timestamp}.md"
        html_path = BITACORA_DIR / f"bitacora_proyecto_{timestamp}.html"

        md_path.write_text(markdown, encoding="utf-8")
        html_path.write_text(confluence_html, encoding="utf-8")

        return {
            "status": "success",
            "markdown_path": str(md_path),
            "html_path": str(html_path),
            "markdown_content": markdown,
            "confluence_html": confluence_html,
            "summary": {
                "project_name": index.config.project_name,
                "stories_count": len(stories),
                "entities_count": len(entities),
                "flows_count": len(flows),
            },
            "message": (
                f"Bitácora generada. Archivos guardados en {BITACORA_DIR}/. "
                "Puedes copiar el contenido directamente a Confluence o usar "
                "las tools de publicación con confirmación manual."
            ),
        }

    def generate_daily_bitacora(
        self,
        user_email: str,
        entries: list[dict],
        target_date: str | None = None,
    ) -> dict:
        """Compila bitácora diaria con las entradas proporcionadas.

        Aplica la regla de 8 horas y genera el formato exportable.

        Args:
            user_email: Email del usuario.
            entries: Lista de entradas con subtask_key, hours, description, etc.
            target_date: Fecha objetivo (default: hoy).

        Returns:
            Dict con la bitácora compilada, validación de horas y formatos.
        """
        if not target_date:
            target_date = date.today().isoformat()

        # Parsear entradas
        bitacora_entries: list[BitacoraEntry] = []
        for entry_dict in entries:
            bitacora_entries.append(BitacoraEntry(**entry_dict))

        # Calcular totales
        total_hours = sum(e.hours for e in bitacora_entries)

        # Aplicar regla de 8 horas
        hours_validation = self._validate_work_hours(total_hours)

        # Construir bitácora
        daily = DailyBitacora(
            date=target_date,
            user_email=user_email,
            entries=bitacora_entries,
            total_hours=total_hours,
            regular_hours=min(total_hours, WORK_HOURS_CONFIG.daily_hours),
            overtime_hours=max(0, total_hours - WORK_HOURS_CONFIG.daily_hours),
        )

        # Generar formatos
        markdown = self._build_daily_markdown(daily)
        confluence_html = self._build_daily_confluence(daily)

        # Guardar localmente
        file_path = BITACORA_DIR / f"bitacora_diaria_{target_date}.md"
        file_path.write_text(markdown, encoding="utf-8")

        return {
            "status": "success",
            "bitacora": daily.model_dump(mode="json"),
            "hours_validation": hours_validation,
            "markdown_content": markdown,
            "confluence_html": confluence_html,
            "file_path": str(file_path),
            "message": (
                f"Bitácora del {target_date} compilada: "
                f"{daily.regular_hours}h regulares"
                + (f" + {daily.overtime_hours}h extra (pendiente aprobación)"
                   if daily.overtime_hours > 0 else "")
                + "."
            ),
        }

    # ─── REGLA DE 8 HORAS ────────────────────────────────────────────────────────

    def _validate_work_hours(self, total_hours: float) -> dict:
        """Valida las horas contra la regla de 8 horas normativas.

        Args:
            total_hours: Total de horas registradas en el día.

        Returns:
            Dict con el resultado de la validación y mensajes para el usuario.
        """
        config = WORK_HOURS_CONFIG
        is_overtime = total_hours > config.daily_hours
        overtime_amount = max(0, total_hours - config.daily_hours)

        if not is_overtime:
            return {
                "is_valid": True,
                "is_overtime": False,
                "total_hours": total_hours,
                "regular_hours": total_hours,
                "overtime_hours": 0,
                "message": f"Horas dentro del rango normativo ({total_hours}/{config.daily_hours}h).",
                "requires_action": False,
            }

        # Hay overtime — requiere decisión del usuario
        return {
            "is_valid": True,
            "is_overtime": True,
            "total_hours": total_hours,
            "regular_hours": config.daily_hours,
            "overtime_hours": overtime_amount,
            "message": (
                f"⚠️ Se exceden las {config.daily_hours} horas normativas. "
                f"Total: {total_hours}h (exceso: {overtime_amount}h). "
                f"¿Deseas registrar solo las {config.daily_hours}h normativas "
                f"o confirmar las horas extra con justificación?"
            ),
            "requires_action": True,
            "options": [
                {
                    "option": "regular_only",
                    "description": f"Registrar solo {config.daily_hours}h normativas (default)",
                },
                {
                    "option": "approve_overtime",
                    "description": (
                        f"Registrar {total_hours}h (requiere justificación escrita)"
                    ),
                },
            ],
            "default_behavior": (
                "Si no se confirma o se ignora, se registrarán solo "
                f"{config.daily_hours} horas normativas."
            ),
        }

    def apply_overtime_decision(
        self,
        daily: DailyBitacora,
        approved: bool,
        reason: str | None = None,
    ) -> DailyBitacora:
        """Aplica la decisión de overtime a la bitácora.

        Args:
            daily: Bitácora diaria con entries.
            approved: True si el usuario aprobó las horas extra.
            reason: Justificación (obligatoria si approved=True).

        Returns:
            DailyBitacora actualizada con la decisión de overtime.
        """
        if approved and not reason:
            # Sin motivo no se aprueban — default a regular
            approved = False

        if approved:
            daily.overtime_approved = True
            daily.overtime_reason = reason
        else:
            # Default conservador: solo 8 horas
            daily.overtime_approved = False
            daily.overtime_hours = 0
            daily.total_hours = WORK_HOURS_CONFIG.daily_hours
            daily.regular_hours = WORK_HOURS_CONFIG.daily_hours

        return daily

    # ─── FORMATEADORES MARKDOWN ──────────────────────────────────────────────────

    def _build_project_markdown(self, index, stories, entities, flows) -> str:
        """Genera Markdown de la bitácora del proyecto.

        Args:
            index: Índice del proyecto (ProjectMemory).
            stories: Lista de StoryAnalysis.
            entities: Lista de EntityInfo.
            flows: Lista de FlowInfo.

        Returns:
            String Markdown completo.
        """
        lines = [
            f"# Bitácora del Proyecto: {index.config.project_name}",
            f"",
            f"**Dominio:** {index.config.domain}",
            f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**Stakeholders:** {', '.join(index.config.stakeholders)}",
            f"",
            f"---",
            f"",
            f"## Resumen",
            f"",
            f"| Métrica | Valor |",
            f"|---------|-------|",
            f"| Historias de Usuario | {len(stories)} |",
            f"| Entidades detectadas | {len(entities)} |",
            f"| Flujos identificados | {len(flows)} |",
            f"",
        ]

        # Historias
        if stories:
            lines.append("## Historias de Usuario")
            lines.append("")
            for story in stories:
                lines.append(f"### {story.id}: {story.title}")
                lines.append("")
                lines.append(f"**Como** {story.narrative.as_a}")
                lines.append(f"**Quiero** {story.narrative.i_want}")
                lines.append(f"**Para que** {story.narrative.so_that}")
                lines.append("")
                if story.acceptance_criteria:
                    lines.append("**Criterios de Aceptación:**")
                    for i, ac in enumerate(story.acceptance_criteria, 1):
                        lines.append(f"  {i}. **Dado** {ac.given}")
                        lines.append(f"     **Cuando** {ac.when}")
                        lines.append(f"     **Entonces** {ac.then}")
                    lines.append("")
                lines.append(f"**Estado:** {story.status} | "
                           f"**Gaps:** {story.total_gaps} | "
                           f"**Complejidad:** {', '.join(story.complexity_tags)}")
                lines.append("")

        # Entidades
        if entities:
            lines.append("## Entidades del Dominio")
            lines.append("")
            lines.append("| Entidad | Primera vez en | Aparece en |")
            lines.append("|---------|---------------|------------|")
            for ent in entities:
                appears = ", ".join(ent.appears_in[:5])
                lines.append(f"| {ent.name} | {ent.first_seen_in} | {appears} |")
            lines.append("")

        # Flujos
        if flows:
            lines.append("## Flujos de Negocio")
            lines.append("")
            for flow in flows:
                status_icon = "✅" if flow.status == "complete" else "🔄"
                lines.append(f"### {status_icon} {flow.name}")
                lines.append(f"")
                if flow.description:
                    lines.append(f"{flow.description}")
                    lines.append("")
                if flow.steps:
                    for step in flow.steps:
                        lines.append(f"  1. {step}")
                    lines.append("")
                lines.append(f"**HUs involucradas:** {', '.join(flow.stories_involved)}")
                lines.append("")

        return "\n".join(lines)

    def _build_daily_markdown(self, daily: DailyBitacora) -> str:
        """Genera Markdown de la bitácora diaria.

        Args:
            daily: Bitácora del día.

        Returns:
            String Markdown.
        """
        lines = [
            f"# Bitácora Diaria — {daily.date}",
            f"",
            f"**Usuario:** {daily.user_email}",
            f"**Generado:** {daily.generated_at}",
            f"",
            f"## Resumen de Horas",
            f"",
            f"| Concepto | Horas |",
            f"|----------|-------|",
            f"| Regulares | {daily.regular_hours} |",
            f"| Extras | {daily.overtime_hours} |",
            f"| **Total** | **{daily.total_hours}** |",
            f"",
        ]

        if daily.overtime_approved and daily.overtime_reason:
            lines.append(f"**Horas extra aprobadas.** Motivo: {daily.overtime_reason}")
            lines.append("")

        lines.append("## Detalle de Actividades")
        lines.append("")
        lines.append("| Subtarea | Descripción | Tipo | Inicio | Fin | Horas |")
        lines.append("|----------|-------------|------|--------|-----|-------|")

        for entry in daily.entries:
            activity = entry.activity_type or "-"
            start = entry.start_time or "-"
            end = entry.end_time or "-"
            overtime_flag = " ⚠️" if entry.is_overtime else ""
            lines.append(
                f"| {entry.subtask_key} | {entry.description[:50]} | "
                f"{activity} | {start} | {end} | {entry.hours}{overtime_flag} |"
            )

        lines.append("")
        return "\n".join(lines)

    # ─── FORMATEADORES CONFLUENCE STORAGE FORMAT ─────────────────────────────────

    def _build_confluence_storage(self, index, stories, entities, flows) -> str:
        """Genera Confluence Storage Format (XHTML) de la bitácora del proyecto.

        Args:
            index: Índice del proyecto.
            stories: Lista de StoryAnalysis.
            entities: Lista de EntityInfo.
            flows: Lista de FlowInfo.

        Returns:
            String XHTML para Confluence Storage Format.
        """
        parts = [
            f'<h1>Bit&aacute;cora del Proyecto: {_escape_html(index.config.project_name)}</h1>',
            f'<p><strong>Dominio:</strong> {_escape_html(index.config.domain)}</p>',
            f'<p><strong>Generado:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>',
            f'<p><strong>Stakeholders:</strong> {_escape_html(", ".join(index.config.stakeholders))}</p>',
            '<hr />',
            '<h2>Resumen</h2>',
            '<table><tbody>',
            '<tr><th>M&eacute;trica</th><th>Valor</th></tr>',
            f'<tr><td>Historias de Usuario</td><td>{len(stories)}</td></tr>',
            f'<tr><td>Entidades detectadas</td><td>{len(entities)}</td></tr>',
            f'<tr><td>Flujos identificados</td><td>{len(flows)}</td></tr>',
            '</tbody></table>',
        ]

        # Historias
        if stories:
            parts.append('<h2>Historias de Usuario</h2>')
            for story in stories:
                parts.append(f'<h3>{_escape_html(story.id)}: {_escape_html(story.title)}</h3>')
                parts.append(
                    f'<p><strong>Como</strong> {_escape_html(story.narrative.as_a)}<br />'
                    f'<strong>Quiero</strong> {_escape_html(story.narrative.i_want)}<br />'
                    f'<strong>Para que</strong> {_escape_html(story.narrative.so_that)}</p>'
                )
                if story.acceptance_criteria:
                    parts.append('<p><strong>Criterios de Aceptaci&oacute;n:</strong></p><ol>')
                    for ac in story.acceptance_criteria:
                        parts.append(
                            f'<li><strong>Dado</strong> {_escape_html(ac.given)} '
                            f'<strong>Cuando</strong> {_escape_html(ac.when)} '
                            f'<strong>Entonces</strong> {_escape_html(ac.then)}</li>'
                        )
                    parts.append('</ol>')
                parts.append(
                    f'<p><em>Estado: {story.status} | '
                    f'Gaps: {story.total_gaps} | '
                    f'Complejidad: {", ".join(story.complexity_tags)}</em></p>'
                )

        # Entidades
        if entities:
            parts.append('<h2>Entidades del Dominio</h2>')
            parts.append('<table><tbody>')
            parts.append('<tr><th>Entidad</th><th>Primera vez en</th><th>Aparece en</th></tr>')
            for ent in entities:
                appears = ", ".join(ent.appears_in[:5])
                parts.append(
                    f'<tr><td>{_escape_html(ent.name)}</td>'
                    f'<td>{_escape_html(ent.first_seen_in)}</td>'
                    f'<td>{_escape_html(appears)}</td></tr>'
                )
            parts.append('</tbody></table>')

        # Flujos
        if flows:
            parts.append('<h2>Flujos de Negocio</h2>')
            for flow in flows:
                status_badge = '&#9989;' if flow.status == "complete" else '&#128260;'
                parts.append(f'<h3>{status_badge} {_escape_html(flow.name)}</h3>')
                if flow.description:
                    parts.append(f'<p>{_escape_html(flow.description)}</p>')
                if flow.steps:
                    parts.append('<ol>')
                    for step in flow.steps:
                        parts.append(f'<li>{_escape_html(step)}</li>')
                    parts.append('</ol>')
                parts.append(
                    f'<p><em>HUs involucradas: {_escape_html(", ".join(flow.stories_involved))}</em></p>'
                )

        return "\n".join(parts)

    def _build_daily_confluence(self, daily: DailyBitacora) -> str:
        """Genera Confluence Storage Format de la bitácora diaria.

        Args:
            daily: Bitácora del día.

        Returns:
            String XHTML para Confluence.
        """
        parts = [
            f'<h1>Bit&aacute;cora Diaria &mdash; {daily.date}</h1>',
            f'<p><strong>Usuario:</strong> {_escape_html(daily.user_email)}</p>',
            '<h2>Resumen de Horas</h2>',
            '<table><tbody>',
            '<tr><th>Concepto</th><th>Horas</th></tr>',
            f'<tr><td>Regulares</td><td>{daily.regular_hours}</td></tr>',
            f'<tr><td>Extras</td><td>{daily.overtime_hours}</td></tr>',
            f'<tr><td><strong>Total</strong></td><td><strong>{daily.total_hours}</strong></td></tr>',
            '</tbody></table>',
        ]

        if daily.overtime_approved and daily.overtime_reason:
            parts.append(
                f'<p><strong>Horas extra aprobadas.</strong> '
                f'Motivo: {_escape_html(daily.overtime_reason)}</p>'
            )

        parts.append('<h2>Detalle de Actividades</h2>')
        parts.append('<table><tbody>')
        parts.append(
            '<tr><th>Subtarea</th><th>Descripci&oacute;n</th>'
            '<th>Tipo</th><th>Inicio</th><th>Fin</th><th>Horas</th></tr>'
        )

        for entry in daily.entries:
            activity = _escape_html(entry.activity_type or "-")
            start = entry.start_time or "-"
            end = entry.end_time or "-"
            overtime_flag = " &#9888;" if entry.is_overtime else ""
            parts.append(
                f'<tr><td>{_escape_html(entry.subtask_key)}</td>'
                f'<td>{_escape_html(entry.description[:80])}</td>'
                f'<td>{activity}</td>'
                f'<td>{start}</td><td>{end}</td>'
                f'<td>{entry.hours}{overtime_flag}</td></tr>'
            )

        parts.append('</tbody></table>')
        return "\n".join(parts)


# ─── UTILIDADES ───────────────────────────────────────────────────────────────────


def _escape_html(text: str) -> str:
    """Escapa caracteres especiales para XHTML/Confluence Storage Format.

    Args:
        text: Texto a escapar.

    Returns:
        Texto con entidades HTML escapadas.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ─── SINGLETON ────────────────────────────────────────────────────────────────────

_bitacora_engine: BitacoraEngine | None = None


def get_bitacora_engine() -> BitacoraEngine:
    """Obtiene la instancia singleton del motor de bitácora.

    Returns:
        BitacoraEngine configurado.
    """
    global _bitacora_engine
    if _bitacora_engine is None:
        _bitacora_engine = BitacoraEngine()
    return _bitacora_engine
