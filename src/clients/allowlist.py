"""Allowlist inmutable de operaciones permitidas contra APIs externas.

Este archivo es la ÚNICA fuente de verdad sobre qué puede hacer el agente
con los tokens de Jira, Confluence y Clockwork Pro.

INVARIANTES:
- ALLOWED_OPERATIONS es un frozenset: inmutable en runtime.
- No se amplía por prompt, por sesión, por persuasión ni por ningún mecanismo.
- Nuevas capacidades SOLO se agregan modificando este archivo, con review y deploy.
- El agente NO puede invocar operaciones fuera de esta lista bajo ninguna circunstancia.
"""

# ─── OPERACIONES PERMITIDAS (ÚNICA fuente de verdad) ─────────────────────────────

ALLOWED_OPERATIONS: frozenset = frozenset([
    # ─── JIRA (READ) ───
    "jira.get_issue",
    "jira.search_issues",
    "jira.get_transitions",
    "jira.get_subtasks",

    # ─── JIRA (WRITE) ───
    "jira.add_comment",
    "jira.create_subtask",
    "jira.transition_issue",

    # ─── CONFLUENCE (READ) ───
    "confluence.get_page",
    "confluence.get_page_by_title",

    # ─── CONFLUENCE (WRITE) ───
    "confluence.create_page",
    "confluence.update_page",

    # ─── CLOCKWORK PRO (READ) ───
    "clockwork.get_worklogs",
    "clockwork.get_activity_types",

    # ─── CLOCKWORK PRO (WRITE) ───
    "clockwork.start_timer",
    "clockwork.stop_timer",
])


# ─── OPERACIONES EXPLÍCITAMENTE PROHIBIDAS ────────────────────────────────────────
# Documentadas para claridad. No se implementan, no existen métodos para ellas.

FORBIDDEN_OPERATIONS: frozenset = frozenset([
    "confluence.delete_page",           # NUNCA — ir a Confluence directamente
    "jira.delete_issue",                # NUNCA
    "jira.update_workflow",             # NUNCA — paramétrico/estructural
    "jira.update_field_configuration",  # NUNCA — paramétrico/estructural
    "jira.create_issue_top_level",      # NUNCA — solo subtareas permitidas
    "jira.update_issue_type",           # NUNCA — paramétrico
    "jira.delete_comment",              # NUNCA
    "clockwork.delete_worklog",         # NUNCA
    "clockwork.modify_others_worklog",  # NUNCA
])


class OperationNotAllowedError(Exception):
    """Error lanzado cuando se intenta ejecutar una operación fuera de la allowlist."""

    def __init__(self, operation: str):
        self.operation = operation
        super().__init__(
            f"Operación '{operation}' NO está en la allowlist de operaciones permitidas. "
            f"Esta acción está prohibida y no puede ejecutarse bajo ninguna circunstancia."
        )


class OperationForbiddenError(Exception):
    """Error lanzado cuando se intenta una operación explícitamente prohibida."""

    def __init__(self, operation: str):
        self.operation = operation
        super().__init__(
            f"Operación '{operation}' está EXPLÍCITAMENTE PROHIBIDA. "
            f"No existe implementación y no se creará una."
        )
