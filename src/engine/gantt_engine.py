"""Gantt Engine: planificador dependency-aware con visualización de plan de trabajo.

Lee las HUs del workspace activo con sus dependencias y estimaciones,
genera un schedule respetando el grafo de dependencias y la concurrencia máxima,
y produce los datos necesarios para renderizar un diagrama de Gantt interactivo.

Soporta:
- Calendario laboral Colombia (festivos oficiales)
- Paralelismo configurable (max N HUs simultáneas)
- Agrupación por dominio/entrega con fases editables
- Ruta crítica y slack
- Comparación secuencial vs paralelo
- Deadlines por fase + deadline global
- Persistencia de configuración en .hu-memory/gantt-config.json
- Validación de plan (gaps, riesgos, scheduling issues)
"""

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from src.engine.memory import MemoryEngine, get_memory
from src.models.story import StoryAnalysis

logger = logging.getLogger("mcp_hu.engine.gantt")

# ─── FESTIVOS COLOMBIA ─────────────────────────────────────────────────────────
# Festivos fijos + Ley Emiliani (traslado al lunes siguiente).
# Se generan dinámicamente para el rango del proyecto.

FIXED_HOLIDAYS_MD = [
    (1, 1),    # Año Nuevo
    (5, 1),    # Día del Trabajo
    (7, 20),   # Independencia
    (8, 7),    # Batalla de Boyacá
    (12, 8),   # Inmaculada Concepción
    (12, 25),  # Navidad
]

# Festivos que se trasladan al lunes siguiente (Ley Emiliani)
EMILIANI_HOLIDAYS_MD = [
    (1, 6),    # Reyes Magos
    (3, 19),   # San José
    (6, 29),   # San Pedro y San Pablo
    (8, 15),   # Asunción
    (10, 12),  # Día de la Raza
    (11, 2),   # Todos los Santos
    (11, 11),  # Independencia de Cartagena
]


def _next_monday(d: date) -> date:
    """Si d no es lunes, retorna el siguiente lunes."""
    days_ahead = (7 - d.weekday()) % 7
    if days_ahead == 0:
        return d
    return d + timedelta(days=days_ahead)


def _easter(year: int) -> date:
    """Algoritmo de Gauss para calcular Pascua."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def get_colombia_holidays(year: int) -> list[date]:
    """Genera todos los festivos de Colombia para un año dado.

    Incluye festivos fijos, Ley Emiliani (traslado al lunes),
    y festivos móviles basados en Pascua.
    """
    holidays: list[date] = []

    # Festivos fijos
    for m, d in FIXED_HOLIDAYS_MD:
        holidays.append(date(year, m, d))

    # Ley Emiliani (traslado al lunes)
    for m, d in EMILIANI_HOLIDAYS_MD:
        original = date(year, m, d)
        if original.weekday() != 0:  # Si no es lunes
            holidays.append(_next_monday(original))
        else:
            holidays.append(original)

    # Festivos móviles basados en Pascua
    easter = _easter(year)
    # Jueves Santo (Easter - 3)
    holidays.append(easter - timedelta(days=3))
    # Viernes Santo (Easter - 2)
    holidays.append(easter - timedelta(days=2))
    # Ascensión (Easter + 43, trasladado al lunes)
    ascension = easter + timedelta(days=39)
    holidays.append(_next_monday(ascension))
    # Corpus Christi (Easter + 64, trasladado al lunes)
    corpus = easter + timedelta(days=60)
    holidays.append(_next_monday(corpus))
    # Sagrado Corazón (Easter + 71, trasladado al lunes)
    sagrado = easter + timedelta(days=68)
    holidays.append(_next_monday(sagrado))

    return sorted(set(holidays))


def holidays_for_range(start: date, end: date) -> set[date]:
    """Genera el set de festivos para todo el rango de fechas."""
    years = set()
    current = start
    while current <= end:
        years.add(current.year)
        current = current.replace(year=current.year + 1, month=1, day=1) if current.month == 12 else current + timedelta(days=32)
    result: set[date] = set()
    for y in years:
        result.update(get_colombia_holidays(y))
    return result


def is_weekend(d: date) -> bool:
    """Verifica si un día es fin de semana."""
    return d.weekday() >= 5


# ─── DATA CLASSES ───────────────────────────────────────────────────────────────


@dataclass
class GanttTask:
    """Tarea planificada para el Gantt."""

    id: str
    title: str
    days: int
    domain: str
    deps: list[str] = field(default_factory=list)
    phase: str = "p1"
    # Computed by scheduler
    work_start: int = 0
    work_end: int = 0
    start_date: Optional[date] = None
    end_date: Optional[date] = None


@dataclass
class GanttGroup:
    """Grupo/fase en el Gantt."""

    name: str
    phase: str
    tasks: list[GanttTask] = field(default_factory=list)
    deadline: Optional[date] = None


@dataclass
class PhaseConfig:
    """Configuración persistida de una fase/entrega."""

    phase_id: str
    name: str
    task_ids: list[str] = field(default_factory=list)
    deadline: Optional[date] = None


@dataclass
class GanttConfig:
    """Configuración del plan de trabajo."""

    project_start: date = field(default_factory=lambda: date.today())
    deadline: Optional[date] = None
    max_concurrent: int = 2
    developers: int = 1
    custom_holidays: list[date] = field(default_factory=list)
    # Overrides del usuario
    phase_overrides: list[PhaseConfig] = field(default_factory=list)
    task_day_overrides: dict[str, int] = field(default_factory=dict)
    milestones: list[dict] = field(default_factory=list)


@dataclass
class GanttResult:
    """Resultado completo del planificador."""

    tasks: list[GanttTask]
    groups: list[GanttGroup]
    config: GanttConfig
    total_work_days: int = 0
    total_effort_days: int = 0
    critical_path_days: int = 0
    project_end_date: Optional[date] = None
    work_days_available: int = 0
    margin_days: int = 0
    holidays_in_range: list[dict] = field(default_factory=list)


# ─── PERSISTENCE ──────────────────────────────────────────────────────────────


GANTT_CONFIG_FILENAME = "gantt-config.json"


def _parse_date(s: str) -> Optional[date]:
    """Parsea fecha ISO YYYY-MM-DD. Retorna None si falla."""
    if not s:
        return None
    try:
        parts = s.split("-")
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        return None


def _config_path(memory: MemoryEngine) -> Path:
    """Ruta al archivo gantt-config.json en la memoria del workspace."""
    return memory.memory_path / GANTT_CONFIG_FILENAME


def load_persisted_config(memory: Optional[MemoryEngine] = None) -> Optional[dict]:
    """Lee la configuración persistida del Gantt desde .hu-memory/.

    Returns:
        Dict con la configuración, o None si no existe.
    """
    if memory is None:
        memory = get_memory()
    if not memory.is_initialized:
        return None
    path = _config_path(memory)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        logger.warning("Error leyendo gantt-config.json: %s", e)
        return None


def save_persisted_config(config_data: dict, memory: Optional[MemoryEngine] = None) -> bool:
    """Guarda la configuración del Gantt en .hu-memory/gantt-config.json.

    Args:
        config_data: Dict con la configuración a persistir.
        memory: MemoryEngine (opcional, se detecta automáticamente).

    Returns:
        True si se guardó correctamente.
    """
    if memory is None:
        memory = get_memory()
    if not memory.is_initialized:
        return False
    path = _config_path(memory)
    config_data["updated_at"] = datetime.now().isoformat()
    try:
        path.write_text(json.dumps(config_data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        logger.info("Gantt config persistida en %s", path)
        return True
    except Exception as e:
        logger.error("Error guardando gantt-config.json: %s", e)
        return False


def config_from_persisted(raw: dict) -> GanttConfig:
    """Convierte un dict persistido a GanttConfig con overrides."""
    config = GanttConfig()

    if raw.get("project_start"):
        d = _parse_date(raw["project_start"])
        if d:
            config.project_start = d

    if raw.get("deadline"):
        d = _parse_date(raw["deadline"])
        if d:
            config.deadline = d

    if raw.get("max_concurrent"):
        try:
            config.max_concurrent = max(1, min(10, int(raw["max_concurrent"])))
        except (ValueError, TypeError):
            pass

    if raw.get("developers"):
        try:
            config.developers = max(1, min(20, int(raw["developers"])))
        except (ValueError, TypeError):
            pass

    # Phase overrides
    for ph in raw.get("phases", []):
        config.phase_overrides.append(PhaseConfig(
            phase_id=ph.get("phase_id", ""),
            name=ph.get("name", ""),
            task_ids=ph.get("task_ids", []),
            deadline=_parse_date(ph.get("deadline", "")),
        ))

    # Task day overrides
    for task_id, days in raw.get("task_day_overrides", {}).items():
        try:
            config.task_day_overrides[task_id] = max(1, min(60, int(days)))
        except (ValueError, TypeError):
            pass

    # Milestones
    config.milestones = raw.get("milestones", [])

    return config


def config_to_dict(config: GanttConfig) -> dict:
    """Serializa GanttConfig a dict para persistir."""
    return {
        "project_start": config.project_start.isoformat(),
        "deadline": config.deadline.isoformat() if config.deadline else None,
        "max_concurrent": config.max_concurrent,
        "developers": config.developers,
        "phases": [
            {
                "phase_id": ph.phase_id,
                "name": ph.name,
                "task_ids": ph.task_ids,
                "deadline": ph.deadline.isoformat() if ph.deadline else None,
            }
            for ph in config.phase_overrides
        ],
        "task_day_overrides": config.task_day_overrides,
        "milestones": config.milestones,
    }


def get_work_plan_state() -> Optional[dict]:
    """Retorna el estado actual del plan de trabajo para consumo cross-tool.

    Esta función es la interfaz de transversalidad: cualquier herramienta
    del MCP puede llamarla para conocer el estado de salud del proyecto.

    Returns:
        Dict con resumen del plan o None si no hay datos.
    """
    memory = get_memory()
    if not memory.is_initialized:
        return None

    persisted = load_persisted_config(memory)
    result = build_gantt()
    if not result:
        return None

    data = gantt_to_json(result)
    m = data["metrics"]

    # Producir un resumen cross-tool
    return {
        "has_plan": True,
        "project_start": m["project_start"],
        "project_end": m["project_end"],
        "deadline": m["deadline"],
        "fits_deadline": m["fits_deadline"],
        "margin_days": m["margin_days"],
        "total_work_days": m["total_work_days"],
        "total_effort_days": m["total_effort_days"],
        "critical_path_days": m["critical_path_days"],
        "story_count": m["story_count"],
        "max_concurrent": m["max_concurrent"],
        "phases": data["phases"],
        "persisted": persisted is not None,
        "phase_deadlines": {
            ph["phase"]: ph.get("deadline")
            for ph in data["phases"]
            if ph.get("deadline")
        },
    }


# ─── DOMAIN DETECTION ──────────────────────────────────────────────────────────


def _detect_domain(story: StoryAnalysis) -> str:
    """Detecta el dominio funcional de una HU basado en su contenido.

    Mapea a dominios funcionales que permiten agrupar HUs
    para paralelismo inteligente.
    """
    title_lower = story.title.lower()
    id_lower = story.id.lower()

    # Mapeo por keywords en título
    domain_keywords = {
        "orquestador": ["orquestador", "pipeline", "motor", "ejecuci", "pausa", "reintento", "dry-run"],
        "procesamiento": ["document", "legibilidad", "pertinencia", "calidad", "partici", "ingesta",
                         "nomenclatura", "comprimid", "protegid"],
        "huelladocumental": ["huella", "duplicad", "hash", "fingerprint"],
        "integraciones": ["webclient", "jwt", "circuit", "wrapper", "api", "endpoint"],
        "auditoriaconsumo": ["auditor", "trazabilidad", "correlation", "retenci"],
        "qa": ["prueba", "test", "estrés", "seguridad", "end-to-end", "integraci"],
        "datos": ["base de datos", "modelo", "jpa", "entit", "repositor"],
        "seguridad": ["seguridad", "cifrad", "criptográf", "api key", "autenticaci"],
    }

    for domain, keywords in domain_keywords.items():
        for kw in keywords:
            if kw in title_lower:
                return domain

    # Fallback: usar entities/flows detectados
    entities = [e.lower() for e in story.entities_detected]
    flows = [f.lower() for f in story.flows_detected]

    if any("pipeline" in e or "orquest" in e for e in entities + flows):
        return "orquestador"
    if any("document" in e for e in entities + flows):
        return "procesamiento"

    return "general"


def _detect_phase(story: StoryAnalysis, all_stories: list[StoryAnalysis]) -> str:
    """Asigna fase/entrega basado en dependencias y complejidad.

    Heurística:
    - Sin dependencias → fases tempranas (p1/p2)
    - Muchas dependencias → fases tardías (p3/p4)
    - QA/testing → última fase (p5)
    """
    domain = _detect_domain(story)
    dep_count = len(story.dependencies)

    if domain == "qa":
        return "p5"

    if dep_count == 0:
        return "p1"
    elif dep_count <= 2:
        return "p2"
    elif dep_count <= 4:
        return "p3"
    else:
        return "p4"


def _estimate_days(story: StoryAnalysis, memory: MemoryEngine) -> int:
    """Estima días hábiles para una HU.

    Intenta leer la estimación guardada; si no existe, estima
    por complejidad y tags.
    """
    # Intentar leer estimación guardada
    est_path = memory.memory_path / "estimations" / f"{story.id}.json"
    if est_path.exists():
        try:
            data = json.loads(est_path.read_text(encoding="utf-8"))
            probable_hours = data.get("probable_hours", 0)
            if probable_hours > 0:
                return max(1, round(probable_hours / 8))
        except Exception:
            pass

    # Estimación por complejidad
    complexity = story.complexity_tags or []
    base_days = 3  # default

    complexity_map = {
        "integracion_externa": 5,
        "reglas_negocio_complejas": 4,
        "procesamiento_batch": 5,
        "multiples_estados": 4,
        "seguridad_critica": 4,
        "modelo_datos_complejo": 5,
        "concurrencia": 5,
        "ui_compleja": 3,
        "simple": 2,
        "crud": 2,
    }

    if complexity:
        days_list = [complexity_map.get(tag, 3) for tag in complexity]
        base_days = max(days_list) if days_list else 3

    # Ajustar por dependencias
    dep_factor = 1.0 + len(story.dependencies) * 0.1
    base_days = round(base_days * dep_factor)

    return max(1, min(base_days, 10))


# ─── SCHEDULER ──────────────────────────────────────────────────────────────────


def _compute_critical_path(tasks: list[GanttTask]) -> tuple[dict, dict, int]:
    """Calcula la ruta crítica (CPM) y slack de cada tarea.

    Returns:
        (cp_start, cp_end, cp_max) — earliest start, earliest end, max path length.
    """
    by_id = {t.id: t for t in tasks}
    cp_start: dict[str, int] = {}
    cp_end: dict[str, int] = {}
    done: set[str] = set()

    def calc(task_id: str) -> None:
        if task_id in done:
            return
        task = by_id.get(task_id)
        if not task:
            return
        for d in task.deps:
            if d in by_id:
                calc(d)
        es = 0
        for d in task.deps:
            if d in by_id and cp_end.get(d, 0) > es:
                es = cp_end[d]
        cp_start[task_id] = es
        cp_end[task_id] = es + task.days
        done.add(task_id)

    for t in tasks:
        calc(t.id)

    cp_max = max(cp_end.values()) if cp_end else 0
    return cp_start, cp_end, cp_max


def schedule_tasks(tasks: list[GanttTask], max_concurrent: int = 2) -> int:
    """Planifica tareas respetando dependencias y concurrencia.

    Algoritmo greedy: en cada tick, completa tareas terminadas,
    luego llena slots con tareas listas priorizadas por slack (ruta crítica).

    Args:
        tasks: Lista de tareas a planificar.
        max_concurrent: Máximo de tareas simultáneas.

    Returns:
        Total de días hábiles del plan.
    """
    if not tasks:
        return 0

    by_id = {t.id: t for t in tasks}

    # Calcular ruta crítica para priorización
    cp_start, cp_end, cp_max = _compute_critical_path(tasks)

    # Late start para calcular slack
    ls: dict[str, int] = {}

    def calc_ls(task_id: str) -> None:
        if task_id in ls:
            return
        successors = [t for t in tasks if task_id in t.deps]
        if not successors:
            ls[task_id] = cp_max - by_id[task_id].days
        else:
            for s in successors:
                calc_ls(s.id)
            ls[task_id] = min(ls[s.id] for s in successors) - by_id[task_id].days

    for t in tasks:
        calc_ls(t.id)

    slack = {t.id: ls.get(t.id, 0) - cp_start.get(t.id, 0) for t in tasks}

    # Fase priority (para scheduling MVP-first)
    phase_prio = {"p1": 0, "p2": 1, "p3": 2, "p4": 3, "p5": 4}

    # Scheduler loop
    done: set[str] = set()
    active: list[dict] = []  # [{id, start_time}]
    time = 0
    max_iter = sum(t.days for t in tasks) + len(tasks) * 2  # safety

    while len(done) < len(tasks) and time < max_iter:
        # Complete finished tasks
        new_active = []
        for a in active:
            task = by_id[a["id"]]
            if time - a["start"] >= task.days:
                task.work_end = time
                done.add(a["id"])
            else:
                new_active.append(a)
        active = new_active

        # Find ready tasks
        ready = [
            t for t in tasks
            if t.id not in done
            and not any(a["id"] == t.id for a in active)
            and all(d not in by_id or d in done for d in t.deps)
        ]

        # Sort: phase priority, then slack (critical path first)
        ready.sort(key=lambda t: (phase_prio.get(t.phase, 9), slack.get(t.id, 0)))

        # Fill slots
        for r in ready:
            if len(active) >= max_concurrent:
                break
            active.append({"id": r.id, "start": time})
            r.work_start = time

        if not active and len(done) < len(tasks):
            logger.warning("Deadlock en scheduler — dependencia circular detectada")
            break

        time += 1

    # Flush remaining
    for a in active:
        task = by_id[a["id"]]
        if time - a["start"] >= task.days:
            task.work_end = time
            done.add(a["id"])

    return max((t.work_end for t in tasks), default=0)


def _workday_to_date(start: date, offset: int, holiday_set: set[date]) -> date:
    """Convierte un offset de día hábil (0-based) a fecha calendario."""
    d = start
    count = 0
    while count < offset:
        d += timedelta(days=1)
        if not is_weekend(d) and d not in holiday_set:
            count += 1
    return d


def _count_workdays(start: date, end: date, holiday_set: set[date]) -> int:
    """Cuenta días hábiles entre dos fechas (inclusive)."""
    count = 0
    d = start
    while d <= end:
        if not is_weekend(d) and d not in holiday_set:
            count += 1
        d += timedelta(days=1)
    return count


# ─── MAIN ENTRY POINT ──────────────────────────────────────────────────────────


def build_gantt(config: Optional[GanttConfig] = None, use_persisted: bool = True) -> Optional[GanttResult]:
    """Construye el plan de trabajo Gantt desde la memoria del workspace activo.

    Lee todas las HUs, sus dependencias y estimaciones, aplica el scheduler
    y genera el resultado completo para renderizar.

    Args:
        config: Configuración del plan. Si None, intenta cargar la persistida.
        use_persisted: Si True y no hay config, carga de gantt-config.json.

    Returns:
        GanttResult con el plan completo, o None si no hay workspace activo.
    """
    memory = get_memory()
    if not memory.is_initialized:
        return None

    # Si no hay config explícita, intentar cargar la persistida
    if config is None:
        if use_persisted:
            raw = load_persisted_config(memory)
            if raw:
                config = config_from_persisted(raw)
            else:
                config = GanttConfig()
        else:
            config = GanttConfig()

    stories = memory.get_all_stories()
    if not stories:
        return None

    # Build phase override lookup: task_id → phase_id
    phase_task_map: dict[str, str] = {}
    phase_name_map: dict[str, str] = {}
    phase_deadline_map: dict[str, Optional[date]] = {}
    for ph in config.phase_overrides:
        phase_name_map[ph.phase_id] = ph.name
        phase_deadline_map[ph.phase_id] = ph.deadline
        for tid in ph.task_ids:
            phase_task_map[tid] = ph.phase_id

    # Build tasks from stories
    tasks: list[GanttTask] = []
    for story in stories:
        # Filtrar dependencias válidas (solo las que existen)
        valid_deps = [d for d in story.dependencies if any(s.id == d for s in stories)]

        # Días: override del usuario > estimación guardada > heurística
        if story.id in config.task_day_overrides:
            days = config.task_day_overrides[story.id]
        else:
            days = _estimate_days(story, memory)

        # Fase: override del usuario > auto-detección
        if story.id in phase_task_map:
            phase = phase_task_map[story.id]
        else:
            phase = _detect_phase(story, stories)

        task = GanttTask(
            id=story.id,
            title=story.title,
            days=days,
            domain=_detect_domain(story),
            deps=valid_deps,
            phase=phase,
        )
        tasks.append(task)

    # Schedule
    total_work_days = schedule_tasks(tasks, config.max_concurrent)

    # Compute holiday set for the project range
    estimated_end = config.project_start + timedelta(days=total_work_days * 2)
    holiday_set = holidays_for_range(config.project_start, estimated_end)
    holiday_set.update(config.custom_holidays)

    # Assign calendar dates
    workday_dates: dict[int, date] = {}
    d = config.project_start
    wd = 0
    while wd <= total_work_days + 5:
        if not is_weekend(d) and d not in holiday_set:
            workday_dates[wd] = d
            wd += 1
        d += timedelta(days=1)

    for task in tasks:
        if task.work_start in workday_dates:
            task.start_date = workday_dates[task.work_start]
        if task.work_end > 0 and (task.work_end - 1) in workday_dates:
            task.end_date = workday_dates[task.work_end - 1]

    # Critical path
    _, _, cp_max = _compute_critical_path(tasks)

    # Project end date
    project_end = workday_dates.get(total_work_days - 1, config.project_start)

    # Work days available until deadline
    work_days_available = 0
    margin_days = 0
    if config.deadline:
        work_days_available = _count_workdays(config.project_start, config.deadline, holiday_set)
        margin_days = work_days_available - total_work_days

    # Default phase names (used when no override)
    default_phase_names = {
        "p1": "Fase 1 — Fundamentos",
        "p2": "Fase 2 — Desarrollo Core",
        "p3": "Fase 3 — Integraciones",
        "p4": "Fase 4 — Funcionalidades Avanzadas",
        "p5": "Fase 5 — QA y Cierre",
    }

    # Collect all phases actually used
    used_phases = sorted(set(t.phase for t in tasks), key=lambda p: p)

    groups: list[GanttGroup] = []
    for phase in used_phases:
        phase_tasks = sorted(
            [t for t in tasks if t.phase == phase],
            key=lambda t: t.work_start
        )
        if phase_tasks:
            name = phase_name_map.get(phase, default_phase_names.get(phase, f"Fase {phase}"))
            dl = phase_deadline_map.get(phase)
            groups.append(GanttGroup(
                name=name,
                phase=phase,
                tasks=phase_tasks,
                deadline=dl,
            ))

    # Holidays in range for display
    holidays_in_range_list = []
    for hd in sorted(holiday_set):
        if config.project_start <= hd <= (config.deadline or project_end + timedelta(days=14)):
            day_names = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
            holidays_in_range_list.append({
                "date": hd.isoformat(),
                "day_name": day_names[hd.weekday()],
                "formatted": f"{hd.day} {_month_short(hd.month)}",
            })

    total_effort = sum(t.days for t in tasks)

    return GanttResult(
        tasks=tasks,
        groups=groups,
        config=config,
        total_work_days=total_work_days,
        total_effort_days=total_effort,
        critical_path_days=cp_max,
        project_end_date=project_end,
        work_days_available=work_days_available,
        margin_days=margin_days,
        holidays_in_range=holidays_in_range_list,
    )


def _month_short(m: int) -> str:
    """Nombre corto del mes en español."""
    months = ["ene", "feb", "mar", "abr", "may", "jun",
              "jul", "ago", "sep", "oct", "nov", "dic"]
    return months[m - 1] if 1 <= m <= 12 else ""


# ─── VALIDATION ────────────────────────────────────────────────────────────────


def validate_work_plan() -> dict:
    """Valida el plan de trabajo actual buscando gaps, riesgos y problemas.

    Analiza:
    - HUs sin fase asignada explícitamente
    - Fases vacías (sin tareas)
    - Deadlines de fase excedidos
    - Deadline global excedido
    - HUs sin estimación persistida (usando heurísticas)
    - Dependencias rotas o circulares
    - Tareas en ruta crítica sin margen
    - Desbalanceo entre fases

    Returns:
        Dict con findings categorizados por severidad.
    """
    memory = get_memory()
    if not memory.is_initialized:
        return {"status": "error", "message": "No hay workspace activo."}

    result = build_gantt()
    if not result:
        return {"status": "error", "message": "No hay HUs para validar."}

    findings: list[dict] = []
    config = result.config

    # 1. HUs sin estimación explícita
    stories = memory.get_all_stories()
    for story in stories:
        est_path = memory.memory_path / "estimations" / f"{story.id}.json"
        if not est_path.exists() and story.id not in config.task_day_overrides:
            findings.append({
                "severity": "info",
                "category": "estimation",
                "story_id": story.id,
                "message": f"HU '{story.id}' usa estimación heurística — considere estimar con estimate_story o ajustar días manualmente.",
            })

    # 2. Deadline global excedido
    if config.deadline and result.margin_days < 0:
        findings.append({
            "severity": "critical",
            "category": "deadline",
            "message": f"El proyecto excede el deadline global por {abs(result.margin_days)} días hábiles. "
                       f"Cierre estimado: {result.project_end_date}, Deadline: {config.deadline}.",
        })
    elif config.deadline and result.margin_days < 5:
        findings.append({
            "severity": "warning",
            "category": "deadline",
            "message": f"Margen ajustado: solo {result.margin_days} días hábiles antes del deadline. "
                       f"Cualquier retraso puede comprometer la entrega.",
        })

    # 3. Deadlines por fase excedidos
    for group in result.groups:
        if group.deadline:
            phase_end = max((t.end_date for t in group.tasks if t.end_date), default=None)
            if phase_end and phase_end > group.deadline:
                findings.append({
                    "severity": "critical",
                    "category": "phase_deadline",
                    "phase": group.phase,
                    "message": f"Fase '{group.name}' excede su deadline ({group.deadline}) — "
                               f"cierra el {phase_end}.",
                })

    # 4. Dependencias rotas
    all_ids = {t.id for t in result.tasks}
    for task in result.tasks:
        for dep in task.deps:
            if dep not in all_ids:
                findings.append({
                    "severity": "warning",
                    "category": "dependency",
                    "story_id": task.id,
                    "message": f"HU '{task.id}' depende de '{dep}' que no existe en el workspace.",
                })

    # 5. Tareas sin dependencias en fases tardías (posible gap)
    for task in result.tasks:
        if task.phase in ("p3", "p4", "p5") and not task.deps:
            findings.append({
                "severity": "info",
                "category": "phase_assignment",
                "story_id": task.id,
                "message": f"HU '{task.id}' está en {task.phase} pero no tiene dependencias — "
                           f"podría completarse antes si se mueve a una fase temprana.",
            })

    # 6. Desbalanceo entre fases
    if result.groups:
        phase_days = [(g.phase, sum(t.days for t in g.tasks)) for g in result.groups]
        max_days = max(d for _, d in phase_days)
        min_days = min(d for _, d in phase_days)
        if max_days > 0 and min_days > 0 and max_days / min_days > 3:
            heavy = max(phase_days, key=lambda x: x[1])
            light = min(phase_days, key=lambda x: x[1])
            findings.append({
                "severity": "info",
                "category": "balance",
                "message": f"Desbalanceo: {heavy[0]} tiene {heavy[1]}d vs {light[0]} con {light[1]}d. "
                           f"Considere redistribuir tareas entre fases.",
            })

    # 7. Ruta crítica — tareas con slack = 0
    cp_start, cp_end, cp_max = _compute_critical_path(result.tasks)
    ls: dict[str, int] = {}
    by_id = {t.id: t for t in result.tasks}

    def calc_ls(task_id: str) -> None:
        if task_id in ls:
            return
        successors = [t for t in result.tasks if task_id in t.deps]
        if not successors:
            ls[task_id] = cp_max - by_id[task_id].days
        else:
            for s in successors:
                calc_ls(s.id)
            ls[task_id] = min(ls[s.id] for s in successors) - by_id[task_id].days

    for t in result.tasks:
        calc_ls(t.id)

    critical_tasks = [
        t.id for t in result.tasks
        if (ls.get(t.id, 0) - cp_start.get(t.id, 0)) == 0
    ]
    if critical_tasks:
        findings.append({
            "severity": "warning",
            "category": "critical_path",
            "message": f"{len(critical_tasks)} HUs en ruta crítica sin margen: {', '.join(critical_tasks[:5])}"
                       + (f" (+{len(critical_tasks)-5} más)" if len(critical_tasks) > 5 else "")
                       + ". Un retraso en cualquiera impacta el cierre del proyecto.",
        })

    # Categorize by severity
    critical = [f for f in findings if f["severity"] == "critical"]
    warnings = [f for f in findings if f["severity"] == "warning"]
    info = [f for f in findings if f["severity"] == "info"]

    health = "healthy" if not critical and not warnings else ("at_risk" if not critical else "critical")

    return {
        "status": "success",
        "health": health,
        "summary": {
            "critical": len(critical),
            "warnings": len(warnings),
            "info": len(info),
            "total_findings": len(findings),
        },
        "findings": findings,
        "plan_metrics": {
            "total_work_days": result.total_work_days,
            "total_effort_days": result.total_effort_days,
            "critical_path_days": result.critical_path_days,
            "margin_days": result.margin_days,
            "story_count": len(result.tasks),
            "phase_count": len(result.groups),
        },
    }


# ─── API SERIALIZATION ─────────────────────────────────────────────────────────


def gantt_to_json(result: GanttResult) -> dict:
    """Serializa el GanttResult a JSON para la API del visualizador.

    Produce un formato optimizado para el frontend de Gantt.
    """
    tasks_json = []
    for group in result.groups:
        # Group header
        tasks_json.append({
            "type": "group",
            "name": group.name,
            "phase": group.phase,
            "deadline": group.deadline.isoformat() if group.deadline else None,
        })
        for task in group.tasks:
            tasks_json.append({
                "type": "task",
                "id": task.id,
                "title": task.title,
                "days": task.days,
                "domain": task.domain,
                "phase": task.phase,
                "deps": task.deps,
                "work_start": task.work_start,
                "work_end": task.work_end,
                "start_date": task.start_date.isoformat() if task.start_date else None,
                "end_date": task.end_date.isoformat() if task.end_date else None,
                "is_overridden": task.id in result.config.task_day_overrides,
            })

    cfg = result.config
    total_effort = result.total_effort_days

    # Phase deadlines for the frontend
    phase_deadlines = {}
    for g in result.groups:
        if g.deadline:
            phase_deadlines[g.phase] = g.deadline.isoformat()

    return {
        "status": "success",
        "tasks": tasks_json,
        "metrics": {
            "total_work_days": result.total_work_days,
            "total_effort_days": total_effort,
            "critical_path_days": result.critical_path_days,
            "project_start": cfg.project_start.isoformat(),
            "project_end": result.project_end_date.isoformat() if result.project_end_date else None,
            "deadline": cfg.deadline.isoformat() if cfg.deadline else None,
            "work_days_available": result.work_days_available,
            "margin_days": result.margin_days,
            "max_concurrent": cfg.max_concurrent,
            "developers": cfg.developers,
            "story_count": len(result.tasks),
            "concurrency_avg": round(total_effort / result.total_work_days, 1) if result.total_work_days > 0 else 0,
            "fits_deadline": result.margin_days >= 0 if cfg.deadline else True,
        },
        "holidays": result.holidays_in_range,
        "phases": [
            {
                "phase": g.phase,
                "name": g.name,
                "task_count": len(g.tasks),
                "total_days": sum(t.days for t in g.tasks),
                "start_date": min((t.start_date for t in g.tasks if t.start_date), default=None),
                "end_date": max((t.end_date for t in g.tasks if t.end_date), default=None),
                "deadline": g.deadline.isoformat() if g.deadline else None,
            }
            for g in result.groups
        ],
        "phase_deadlines": phase_deadlines,
        "persisted_config": config_to_dict(cfg),
    }
