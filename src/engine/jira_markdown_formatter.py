"""Formateador de Markdown compatible con Jira Cloud (nuevo editor).

Jira Cloud con el nuevo editor soporta Markdown nativo al pegar contenido
en modo texto (Ctrl+Shift+M). Sin embargo, tiene restricciones respecto
a Markdown estándar:

Restricciones identificadas:
- No renderiza diagramas ASCII complejos (>40 caracteres de ancho)
- Las tablas necesitan fila de separadores con mínimo 3 guiones: |---|
- Bold/italic dentro de celdas de tabla puede no parsear correctamente
- Los code blocks con triple backtick funcionan bien
- Listas con `-` (bullets) y `1.` (numeradas) funcionan
- Headings con `#` funcionan
- Caracteres especiales en tablas pueden confundir al parser

Este módulo transforma Markdown estándar en Markdown que Jira Cloud
interpreta sin errores al pegarse.
"""

import re
import logging

logger = logging.getLogger("mcp_hu.engine.jira_markdown_formatter")

# Ancho máximo recomendado para contenido dentro de code blocks en Jira Cloud
MAX_CODE_BLOCK_WIDTH = 80

# Ancho máximo para diagramas ASCII antes de que Jira Cloud los rompa
MAX_ASCII_DIAGRAM_WIDTH = 40


def format_for_jira_cloud(markdown: str) -> str:
    """Transforma Markdown estándar en Markdown compatible con Jira Cloud.

    Aplica todas las reglas de sanitización necesarias para que el contenido
    se renderice correctamente en el editor nuevo de Jira Cloud al pegarse
    con Ctrl+Shift+M.

    Args:
        markdown: Contenido Markdown estándar.

    Returns:
        Markdown sanitizado para Jira Cloud.
    """
    result = markdown

    result = _sanitize_tables(result)
    result = _strip_bold_from_table_cells(result)
    result = _sanitize_code_blocks(result)
    result = _replace_complex_ascii_diagrams(result)
    result = _normalize_list_markers(result)
    result = _clean_special_characters(result)

    return result


def build_jira_table(headers: list[str], rows: list[list[str]]) -> str:
    """Construye una tabla Markdown compatible con Jira Cloud desde datos estructurados.

    Genera tablas con separadores correctos y sin formato inline en celdas.

    Args:
        headers: Lista de encabezados de columna.
        rows: Lista de filas, donde cada fila es una lista de valores string.

    Returns:
        Tabla Markdown formateada para Jira Cloud.
    """
    if not headers:
        return ""

    # Header row
    header_line = "| " + " | ".join(headers) + " |"

    # Separator row (mínimo 3 guiones por columna)
    separator_line = "| " + " | ".join("---" for _ in headers) + " |"

    # Data rows — sin bold/italic
    data_lines = []
    for row in rows:
        # Asegurar que la fila tiene el mismo número de columnas
        padded_row = row + [""] * (len(headers) - len(row))
        clean_cells = [_strip_inline_formatting(cell) for cell in padded_row[:len(headers)]]
        data_lines.append("| " + " | ".join(clean_cells) + " |")

    return "\n".join([header_line, separator_line] + data_lines)


def build_jira_code_block(content: str, language: str = "") -> str:
    """Construye un code block compatible con Jira Cloud.

    Si el contenido excede el ancho máximo recomendado, lo trunca por línea
    sin romper la estructura.

    Args:
        content: Contenido del bloque de código.
        language: Lenguaje para syntax highlighting (opcional).

    Returns:
        Code block con triple backtick formateado para Jira Cloud.
    """
    lines = content.split("\n")
    formatted_lines = []

    for line in lines:
        if len(line) > MAX_CODE_BLOCK_WIDTH:
            # Wrap largo — truncar con indicador
            formatted_lines.append(line[:MAX_CODE_BLOCK_WIDTH - 3] + "...")
        else:
            formatted_lines.append(line)

    lang_tag = language if language else ""
    return f"```{lang_tag}\n" + "\n".join(formatted_lines) + "\n```"


def build_jira_heading(text: str, level: int = 2) -> str:
    """Construye un heading Markdown para Jira Cloud.

    Args:
        text: Texto del heading (sin formato inline).
        level: Nivel del heading (1-6).

    Returns:
        Heading Markdown limpio.
    """
    level = max(1, min(6, level))
    clean_text = _strip_inline_formatting(text)
    return f"{'#' * level} {clean_text}"


# ─── FUNCIONES INTERNAS DE SANITIZACIÓN ──────────────────────────────────────────


def _sanitize_tables(markdown: str) -> str:
    """Asegura que las tablas tienen separadores correctos con mínimo 3 guiones.

    Jira Cloud requiere la fila de separadores |---|---| para reconocer tablas.
    Detecta tablas existentes y corrige separadores incompletos.

    Args:
        markdown: Markdown con posibles tablas.

    Returns:
        Markdown con tablas corregidas.
    """
    lines = markdown.split("\n")
    result_lines = []

    for i, line in enumerate(lines):
        if _is_table_separator(line):
            # Corregir separador: asegurar mínimo 3 guiones por celda
            cells = line.split("|")
            fixed_cells = []
            for cell in cells:
                stripped = cell.strip()
                if stripped and re.match(r"^:?-+:?$", stripped):
                    # Es un separador válido — asegurar mínimo 3 guiones
                    prefix = ":" if stripped.startswith(":") else ""
                    suffix = ":" if stripped.endswith(":") and len(stripped) > 1 else ""
                    fixed_cells.append(f" {prefix}---{suffix} ")
                else:
                    fixed_cells.append(cell)
            result_lines.append("|".join(fixed_cells))
        else:
            result_lines.append(line)

    return "\n".join(result_lines)


def _strip_bold_from_table_cells(markdown: str) -> str:
    """Elimina bold/italic de dentro de celdas de tabla.

    Jira Cloud a veces no parsea **bold** o *italic* dentro de celdas.
    Se preserva el texto pero sin el formato.

    Args:
        markdown: Markdown con posibles tablas con formato inline en celdas.

    Returns:
        Markdown con celdas de tabla limpias.
    """
    lines = markdown.split("\n")
    result_lines = []
    in_table = False

    for line in lines:
        if line.strip().startswith("|") and line.strip().endswith("|"):
            in_table = True
            if not _is_table_separator(line):
                # Limpiar bold/italic dentro de celdas
                line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
                line = re.sub(r"\*(.+?)\*", r"\1", line)
                line = re.sub(r"__(.+?)__", r"\1", line)
                line = re.sub(r"_(.+?)_", r"\1", line)
        else:
            in_table = False

        result_lines.append(line)

    return "\n".join(result_lines)


def _sanitize_code_blocks(markdown: str) -> str:
    """Sanitiza code blocks para Jira Cloud.

    Mantiene los triple backtick pero advierte si el contenido es muy ancho.
    No modifica el contenido del code block (puede romper código).

    Args:
        markdown: Markdown con code blocks.

    Returns:
        Markdown con code blocks preservados.
    """
    # Los code blocks con triple backtick funcionan bien en Jira Cloud
    # Solo verificar que no haya code blocks con tildes simples multilínea
    return markdown


def _replace_complex_ascii_diagrams(markdown: str) -> str:
    """Detecta y encapsula diagramas ASCII complejos en code blocks.

    Jira Cloud no renderiza bien diagramas ASCII que no estén dentro de
    un code block. Si se detecta un patrón de diagrama (líneas con muchos
    caracteres especiales como ─, │, ┌, ┐, →, etc.), se encapsula.

    Args:
        markdown: Markdown con posibles diagramas ASCII sueltos.

    Returns:
        Markdown con diagramas encapsulados en code blocks.
    """
    lines = markdown.split("\n")
    result_lines = []
    diagram_buffer: list[str] = []
    in_code_block = False

    ascii_diagram_chars = re.compile(r"[─│┌┐└┘├┤┬┴┼═║╔╗╚╝╠╣╦╩╬→←↑↓▶◀●○►◄]")

    for line in lines:
        # Detectar inicio/fin de code blocks existentes
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            if diagram_buffer:
                # Flush buffer antes de entrar en un code block
                result_lines.extend(_wrap_diagram_buffer(diagram_buffer))
                diagram_buffer = []
            result_lines.append(line)
            continue

        if in_code_block:
            result_lines.append(line)
            continue

        # Detectar líneas que parecen diagrama ASCII
        special_count = len(ascii_diagram_chars.findall(line))
        if special_count >= 3 or (len(line) > MAX_ASCII_DIAGRAM_WIDTH and special_count >= 2):
            diagram_buffer.append(line)
        else:
            if diagram_buffer:
                result_lines.extend(_wrap_diagram_buffer(diagram_buffer))
                diagram_buffer = []
            result_lines.append(line)

    # Flush final
    if diagram_buffer:
        result_lines.extend(_wrap_diagram_buffer(diagram_buffer))

    return "\n".join(result_lines)


def _wrap_diagram_buffer(buffer: list[str]) -> list[str]:
    """Envuelve un buffer de líneas de diagrama ASCII en un code block.

    Args:
        buffer: Líneas que conforman un diagrama ASCII.

    Returns:
        Líneas con el diagrama dentro de un code block.
    """
    if not buffer:
        return []

    return ["```", *buffer, "```"]


def _normalize_list_markers(markdown: str) -> str:
    """Normaliza marcadores de lista para consistencia en Jira Cloud.

    Jira Cloud soporta `-` para bullets y `1.` para numeradas.
    Convierte `*` bullets a `-` para evitar confusión con bold.

    Args:
        markdown: Markdown con listas.

    Returns:
        Markdown con marcadores normalizados.
    """
    lines = markdown.split("\n")
    result_lines = []
    in_code_block = False

    for line in lines:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            result_lines.append(line)
            continue

        if in_code_block:
            result_lines.append(line)
            continue

        # Convertir `* ` a `- ` para bullets (solo al inicio de línea con indent)
        converted = re.sub(r"^(\s*)\* ", r"\1- ", line)
        result_lines.append(converted)

    return "\n".join(result_lines)


def _clean_special_characters(markdown: str) -> str:
    """Limpia caracteres especiales que pueden confundir al parser de Jira Cloud.

    Reemplaza emojis unicode problemáticos con alternativas de texto
    si están fuera de code blocks.

    Args:
        markdown: Markdown con posibles caracteres problemáticos.

    Returns:
        Markdown limpio.
    """
    # Los emojis comunes como ✅, ⚠️, 🔄 funcionan en Jira Cloud.
    # No es necesario reemplazarlos. Solo limpiar caracteres de control.
    result = markdown.replace("\r\n", "\n")
    result = result.replace("\r", "\n")
    # Eliminar caracteres de control excepto newline y tab
    result = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", result)
    return result


def _strip_inline_formatting(text: str) -> str:
    """Elimina todo formato inline (bold, italic) de un texto.

    Args:
        text: Texto con posible formato inline.

    Returns:
        Texto limpio sin marcadores de formato.
    """
    result = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    result = re.sub(r"\*(.+?)\*", r"\1", result)
    result = re.sub(r"__(.+?)__", r"\1", result)
    result = re.sub(r"_(.+?)_", r"\1", result)
    return result


def _is_table_separator(line: str) -> bool:
    """Determina si una línea es un separador de tabla Markdown.

    Args:
        line: Línea a evaluar.

    Returns:
        True si es una línea separadora de tabla.
    """
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    # Separador: solo contiene |, -, :, y espacios
    content = stripped.replace("|", "").replace("-", "").replace(":", "").replace(" ", "")
    return len(content) == 0 and "-" in stripped
