"""Panel de Expertos: 10 expertos con reglas de clasificacion y prompts de analisis.

Cada experto define:
- keywords: palabras que activan al experto cuando se detectan en la HU
- analysis_prompt: contexto especializado que Kiro usa para analizar desde esa perspectiva
- questions_template: preguntas que el experto siempre hace sobre una HU
"""

import logging
import re
from dataclasses import dataclass, field

from src.models.story import ExpertType

logger = logging.getLogger("mcp_hu.engine.experts")


@dataclass
class ExpertProfile:
    """Perfil de un experto con reglas de activacion y prompts."""

    expert_type: ExpertType
    name: str
    description: str
    keywords: list[str] = field(default_factory=list)
    always_active: bool = False
    analysis_focus: list[str] = field(default_factory=list)
    standard_questions: list[str] = field(default_factory=list)


# ─── DEFINICION DE LOS 10 EXPERTOS ──────────────────────────────────────────────

EXPERT_PROFILES: dict[ExpertType, ExpertProfile] = {
    ExpertType.NEGOCIO: ExpertProfile(
        expert_type=ExpertType.NEGOCIO,
        name="Negocio/Dominio",
        description="Analiza reglas de negocio, edge cases, flujos alternativos y excepciones funcionales.",
        keywords=[],
        always_active=True,
        analysis_focus=[
            "Reglas de negocio explicitas e implicitas",
            "Precondiciones y postcondiciones",
            "Flujos alternativos y de excepcion",
            "Edge cases y boundary conditions",
            "Consistencia con el dominio del proyecto",
        ],
        standard_questions=[
            "Que precondiciones deben cumplirse para ejecutar esta accion?",
            "Que pasa si la operacion falla a mitad del proceso?",
            "Existe algun limite de negocio (cantidad, tiempo, monto)?",
            "Puede este flujo ejecutarse mas de una vez para el mismo caso?",
            "Que roles o permisos se requieren?",
        ],
    ),
    ExpertType.UX: ExpertProfile(
        expert_type=ExpertType.UX,
        name="UX/UI",
        description="Analiza flujos de usuario, estados de pantalla, accesibilidad y feedback visual.",
        keywords=[
            "pantalla", "interfaz", "formulario", "boton", "modal", "navegacion",
            "usuario ve", "usuario hace", "mostrar", "visualizar", "seleccionar",
            "click", "tap", "scroll", "menu", "dashboard", "listado", "detalle",
            "filtro", "busqueda", "app", "web", "movil", "responsive",
        ],
        analysis_focus=[
            "Flujo paso a paso del usuario (happy path)",
            "Estados de la UI (loading, vacio, error, exito, offline)",
            "Validaciones del lado del cliente",
            "Feedback visual en cada accion",
            "Accesibilidad (WCAG basico)",
            "Comportamiento responsive/mobile",
        ],
        standard_questions=[
            "Cuantos pasos tiene el flujo para el usuario?",
            "Que ve el usuario si no hay datos (empty state)?",
            "Que feedback recibe al completar la accion?",
            "Funciona offline o requiere conexion?",
            "Hay confirmacion antes de acciones destructivas?",
        ],
    ),
    ExpertType.BACKEND: ExpertProfile(
        expert_type=ExpertType.BACKEND,
        name="Backend/API",
        description="Analiza contratos de endpoints, validaciones server-side, idempotencia y performance.",
        keywords=[
            "endpoint", "api", "servicio", "request", "response", "consulta",
            "operacion", "crear", "actualizar", "eliminar", "listar", "obtener",
            "paginado", "filtro", "ordenar", "validar", "procesar", "calcular",
            "asincrono", "batch", "cola", "webhook",
        ],
        analysis_focus=[
            "Endpoints REST necesarios (metodo, path, body, response)",
            "Validaciones del lado del servidor",
            "Manejo de errores y codigos HTTP",
            "Idempotencia de operaciones",
            "Performance y timeouts",
            "Paginacion y limites",
        ],
        standard_questions=[
            "La operacion es sincrona o asincrona?",
            "Que validaciones se aplican en el servidor?",
            "Que codigo HTTP corresponde a cada caso (exito, error, not found)?",
            "Es idempotente (se puede reintentar sin duplicar)?",
            "Hay limites de tamano o rate limiting?",
        ],
    ),
    ExpertType.DATOS: ExpertProfile(
        expert_type=ExpertType.DATOS,
        name="Datos/Persistencia",
        description="Analiza modelo de datos, relaciones, migraciones y consistencia.",
        keywords=[
            "almacenar", "guardar", "registrar", "base de datos", "tabla",
            "consultar", "historico", "reporte", "registro", "auditoria",
            "relacion", "indice", "migrar", "campo", "columna", "schema",
        ],
        analysis_focus=[
            "Entidades y atributos necesarios",
            "Relaciones entre entidades (1:1, 1:N, N:M)",
            "Indices y consultas frecuentes",
            "Auditoria (quien, cuando, que cambio)",
            "Migraciones necesarias",
            "Consistencia y transaccionalidad",
        ],
        standard_questions=[
            "Que entidades se crean o modifican?",
            "Que relaciones existen entre ellas?",
            "Se necesita auditoria de cambios?",
            "Hay datos que deben ser unicos o inmutables?",
            "Cual es la retencion de datos esperada?",
        ],
    ),
    ExpertType.SEGURIDAD: ExpertProfile(
        expert_type=ExpertType.SEGURIDAD,
        name="Seguridad",
        description="Analiza autenticacion, autorizacion, PII, compliance y OWASP.",
        keywords=[
            "login", "autenticar", "permiso", "rol", "acceso", "token",
            "cifrar", "encriptar", "dato sensible", "pii", "contrasena",
            "sesion", "auditoria", "consentimiento", "privacidad",
        ],
        analysis_focus=[
            "Autenticacion requerida",
            "Autorizacion (que roles pueden ejecutar)",
            "Datos sensibles (PII) involucrados",
            "Validacion de propiedad del recurso (BOLA/IDOR)",
            "Registro de auditoria de acciones",
            "Compliance regulatorio",
        ],
        standard_questions=[
            "Que nivel de autenticacion se requiere?",
            "Que roles pueden ejecutar esta accion?",
            "Se manejan datos personales sensibles?",
            "Se valida que el usuario es dueno del recurso?",
            "Se registra quien ejecuto la accion (auditoria)?",
        ],
    ),
    ExpertType.QA: ExpertProfile(
        expert_type=ExpertType.QA,
        name="QA/Testing",
        description="Genera criterios de aceptacion, escenarios negativos y datos de prueba.",
        keywords=[],
        always_active=True,
        analysis_focus=[
            "Criterios de aceptacion en formato Given/When/Then",
            "Escenarios negativos (que NO debe pasar)",
            "Boundary values (limites exactos)",
            "Datos de prueba necesarios",
            "Regresion: que podria romperse",
        ],
        standard_questions=[
            "Cuales son los criterios de aceptacion minimos?",
            "Que escenarios de error se deben validar?",
            "Que datos de prueba se necesitan?",
            "Que funcionalidad existente podria afectarse?",
        ],
    ),
    ExpertType.INTEGRACION: ExpertProfile(
        expert_type=ExpertType.INTEGRACION,
        name="Integracion",
        description="Analiza contratos con sistemas externos, timeouts, retry y fallback.",
        keywords=[
            "sistema externo", "api tercero", "servicio externo", "notificar",
            "enviar a", "consumir", "integrar", "webhook", "callback",
            "proveedor", "gateway", "soap", "rest externo",
        ],
        analysis_focus=[
            "Sistemas externos involucrados",
            "Contrato de la integracion (request/response)",
            "Manejo de timeouts y errores del externo",
            "Estrategia de retry y circuit breaker",
            "Fallback si el externo no responde",
            "Transformacion de datos entre sistemas",
        ],
        standard_questions=[
            "Que sistema externo se consume?",
            "Cual es el SLA del sistema externo?",
            "Que pasa si el externo no responde?",
            "Se necesita retry automatico?",
            "Los datos se transforman entre formatos?",
        ],
    ),
    ExpertType.OBSERVABILIDAD: ExpertProfile(
        expert_type=ExpertType.OBSERVABILIDAD,
        name="Observabilidad",
        description="Analiza metricas, alertas, logs y trazabilidad en flujos criticos.",
        keywords=[
            "transaccion critica", "pago", "financiero", "proceso asincrono",
            "monitorear", "alerta", "metrica", "traza", "log",
            "rendimiento", "latencia", "error rate",
        ],
        analysis_focus=[
            "Metricas clave del flujo (latencia, error rate, throughput)",
            "Alertas necesarias",
            "Logs estructurados para debugging",
            "Trazabilidad end-to-end (correlation-id)",
            "SLOs del flujo",
        ],
        standard_questions=[
            "Es un flujo critico que requiere monitoreo?",
            "Que metricas miden el exito de esta operacion?",
            "Que alertas se disparan si falla?",
            "Se necesita trazabilidad distribuida?",
        ],
    ),
    ExpertType.DEVOPS: ExpertProfile(
        expert_type=ExpertType.DEVOPS,
        name="DevOps/Infra",
        description="Analiza escalabilidad, despliegue, feature flags y jobs batch.",
        keywords=[
            "programado", "batch", "cron", "masivo", "despliegue",
            "configuracion por ambiente", "feature flag", "escalar",
            "contenedor", "lambda", "serverless", "job",
        ],
        analysis_focus=[
            "Necesidad de feature flags",
            "Configuracion por ambiente",
            "Escalabilidad (carga esperada)",
            "Jobs programados o batch",
            "Impacto en despliegue (migracion, downtime)",
        ],
        standard_questions=[
            "Se necesita feature flag para despliegue gradual?",
            "Hay configuracion que varia por ambiente?",
            "Cual es la carga esperada (requests/seg, volumen)?",
            "Requiere ejecucion programada?",
            "El despliegue requiere migracion de datos?",
        ],
    ),
    ExpertType.LEGAL: ExpertProfile(
        expert_type=ExpertType.LEGAL,
        name="Legal/Compliance",
        description="Analiza retencion de datos, consentimiento, habeas data y regulacion.",
        keywords=[
            "datos personales", "consentimiento", "regulacion", "sfc",
            "poliza", "contrato", "legal", "habeas data", "retencion",
            "normativa", "ley", "proteccion de datos", "gdpr",
        ],
        analysis_focus=[
            "Datos personales involucrados y su tratamiento",
            "Consentimiento necesario del usuario",
            "Retencion de datos (plazo legal)",
            "Regulacion sectorial aplicable (SFC, habeas data)",
            "Terminos y condiciones impactados",
        ],
        standard_questions=[
            "Se recopilan datos personales nuevos?",
            "Se requiere consentimiento explicito del usuario?",
            "Cual es el plazo de retencion de estos datos?",
            "Hay regulacion sectorial que aplique?",
            "Se impactan terminos y condiciones existentes?",
        ],
    ),
}


class ExpertClassifier:
    """Clasifica que expertos se activan para una HU dada."""

    def classify(self, text: str) -> list[ExpertType]:
        """Determina que expertos participan en el analisis de una HU.

        Args:
            text: Texto completo de la HU (cualquier formato).

        Returns:
            Lista de ExpertTypes activados (siempre incluye NEGOCIO y QA).
        """
        text_lower = text.lower()
        activated: list[ExpertType] = []

        for expert_type, profile in EXPERT_PROFILES.items():
            if profile.always_active:
                activated.append(expert_type)
                continue

            for keyword in profile.keywords:
                if keyword in text_lower:
                    activated.append(expert_type)
                    break

        # Deduplicar preservando orden
        seen = set()
        unique = []
        for e in activated:
            if e not in seen:
                seen.add(e)
                unique.append(e)

        logger.debug("Expertos activados para HU: %s", [e.value for e in unique])
        return unique

    def get_profile(self, expert_type: ExpertType) -> ExpertProfile:
        """Obtiene el perfil completo de un experto.

        Args:
            expert_type: Tipo de experto.

        Returns:
            ExpertProfile con toda la configuracion.
        """
        return EXPERT_PROFILES[expert_type]

    def get_analysis_context(self, expert_type: ExpertType) -> str:
        """Genera el prompt de contexto que Kiro usa para analizar desde esta perspectiva.

        Args:
            expert_type: Tipo de experto.

        Returns:
            Texto con el foco de analisis y preguntas del experto.
        """
        profile = EXPERT_PROFILES[expert_type]
        lines = [
            f"## Perspectiva: {profile.name}",
            f"_{profile.description}_",
            "",
            "### Foco de analisis:",
        ]
        for focus in profile.analysis_focus:
            lines.append(f"- {focus}")
        lines.append("")
        lines.append("### Preguntas que debe responder:")
        for q in profile.standard_questions:
            lines.append(f"- {q}")
        return "\n".join(lines)

    def get_all_profiles(self) -> list[ExpertProfile]:
        """Retorna todos los perfiles de expertos.

        Returns:
            Lista de ExpertProfile.
        """
        return list(EXPERT_PROFILES.values())
