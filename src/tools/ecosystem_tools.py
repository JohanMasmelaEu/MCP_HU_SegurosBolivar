"""Tool implementations: init_ecosystem, register_app, list_ecosystem, get_cross_app_context, sync_ecosystem."""

import logging

from src.engine.ecosystem import get_ecosystem
from src.engine.ecosystem_manager import get_ecosystem_manager
from src.engine.memory import get_memory
from src.models.ecosystem import AppRegistration, ContractDefinition, EntityDefinition

logger = logging.getLogger("mcp_hu.tools.ecosystem")


def handle_init_ecosystem(config_dict: dict) -> dict:
    """Inicializa un nuevo ecosistema de apps.

    Usa el EcosystemManager para crear ecosistemas aislados. Cada ecosistema
    tiene su propio .hu-ecosystem/ independiente.

    Args:
        config_dict: Dict con ecosystem_id, name, description.

    Returns:
        Status de la operacion.
    """
    ecosystem_id = config_dict.get("ecosystem_id")
    name = config_dict.get("name")
    description = config_dict.get("description", "")

    if not ecosystem_id or not name:
        return {
            "status": "error",
            "message": "Se requiere 'ecosystem_id' y 'name' en la configuracion.",
        }

    manager = get_ecosystem_manager()

    if not manager:
        return {"status": "error", "message": "EcosystemManager no disponible. El servidor no se inicializó correctamente."}

    try:
        engine = manager.create_ecosystem(ecosystem_id, name, description)
        return {
            "status": "success",
            "ecosystem_id": ecosystem_id,
            "name": name,
            "path": str(engine.ecosystem_path),
            "message": (
                f"Ecosistema '{name}' inicializado y activado. "
                f"Registra apps con register_app para comenzar a mapear dependencias."
            ),
        }
    except ValueError as e:
        # Ecosistema ya existe — ofrecer alternativas
        return {
            "status": "error",
            "message": str(e),
            "hint": (
                "Opciones disponibles:\n"
                "- switch_ecosystem: Activar el ecosistema existente.\n"
                "- reset_ecosystem: Eliminar y volver a crear.\n"
                "- list_ecosystems: Ver todos los ecosistemas disponibles."
            ),
        }
    except Exception as e:
        logger.exception("Error inicializando ecosistema")
        return {"status": "error", "message": f"Error: {e}"}


def handle_register_app(app_dict: dict) -> dict:
    """Registra una app en el ecosistema.

    Args:
        app_dict: Dict con app_id, name, memory_path, coupling_type, etc.

    Returns:
        Status con snapshot de la app registrada.
    """
    ecosystem = get_ecosystem()

    if not ecosystem.is_initialized:
        return {
            "status": "error",
            "message": "Ecosistema no inicializado. Usar init_ecosystem primero.",
        }

    required_fields = ["app_id", "name", "memory_path", "coupling_type"]
    missing = [f for f in required_fields if not app_dict.get(f)]
    if missing:
        return {
            "status": "error",
            "message": f"Campos requeridos faltantes: {', '.join(missing)}",
        }

    coupling = app_dict.get("coupling_type", "decoupled")
    if coupling not in ("cohesive", "decoupled"):
        return {
            "status": "error",
            "message": "coupling_type debe ser 'cohesive' o 'decoupled'.",
        }

    try:
        app = AppRegistration(**app_dict)
    except Exception as e:
        return {"status": "error", "message": f"Datos de app invalidos: {e}"}

    # Registrar contratos si vienen en el dict
    contracts = app_dict.get("contracts", [])

    try:
        ecosystem.register_app(app)

        # Registrar contratos asociados
        for contract_data in contracts:
            # Normalizar: aceptar 'consumers' como alias de 'consumer_apps'
            if "consumers" in contract_data and "consumer_apps" not in contract_data:
                contract_data["consumer_apps"] = contract_data.pop("consumers")
            # Normalizar: aceptar 'consumer_app' (singular) como alias
            if "consumer_app" in contract_data and "consumer_apps" not in contract_data:
                consumer = contract_data.pop("consumer_app")
                contract_data["consumer_apps"] = [consumer] if consumer else []
            # Normalizar: aceptar 'entities' como alias de 'entities_involved'
            if "entities" in contract_data and "entities_involved" not in contract_data:
                raw_entities = contract_data.pop("entities")
                # Soporte para entidades como objetos con category
                if raw_entities and isinstance(raw_entities[0], dict):
                    contract_data["entities_grouped"] = [
                        EntityDefinition(**e) if isinstance(e, dict) else EntityDefinition(name=e)
                        for e in raw_entities
                    ]
                    contract_data["entities_involved"] = [
                        e["name"] if isinstance(e, dict) else e for e in raw_entities
                    ]
                else:
                    contract_data["entities_involved"] = raw_entities
            # Normalizar: soporte directo para entities_grouped como lista de objetos
            if "entities_grouped" in contract_data and isinstance(contract_data["entities_grouped"], list):
                grouped = contract_data["entities_grouped"]
                if grouped and isinstance(grouped[0], dict):
                    contract_data["entities_grouped"] = [
                        EntityDefinition(**e) for e in grouped
                    ]

            # Si el contrato tiene role="consumer", buscar el contrato provider
            # existente y agregar esta app como consumidor en vez de crear uno nuevo.
            role = contract_data.pop("role", None)
            if role == "consumer":
                provider_app_id = contract_data.get("provider_app", "")
                contract_id = contract_data.get("contract_id", "")
                existing_contracts = ecosystem.get_contracts()

                # Buscar contrato provider existente por contract_id o por provider_app
                target_contract = None
                if contract_id:
                    target_contract = next(
                        (c for c in existing_contracts if c.contract_id == contract_id),
                        None,
                    )
                if not target_contract and provider_app_id:
                    target_contract = next(
                        (c for c in existing_contracts if c.provider_app == provider_app_id),
                        None,
                    )

                if target_contract:
                    # Agregar la app actual como consumidor del contrato existente
                    if app.app_id not in target_contract.consumer_apps:
                        target_contract.consumer_apps.append(app.app_id)
                    # Persistir el contrato actualizado
                    ecosystem.add_contract(target_contract)
                    # Registrar en la app que consume este contrato
                    if target_contract.contract_id not in app.consumes_contracts:
                        app.consumes_contracts.append(target_contract.contract_id)
                    # Persistir la app actualizada con consumes_contracts
                    ecosystem.register_app(app)
                    continue

                # Si no existe contrato provider, crear uno normal con consumer_apps
                if "consumer_apps" not in contract_data:
                    contract_data["consumer_apps"] = [app.app_id]
                elif app.app_id not in contract_data["consumer_apps"]:
                    contract_data["consumer_apps"].append(app.app_id)

            contract = ContractDefinition(**contract_data)
            ecosystem.add_contract(contract)

        # Obtener resultado post-registro
        registered = ecosystem.get_app(app.app_id)
        shared = ecosystem.get_shared_entities()

        return {
            "status": "success",
            "app_id": app.app_id,
            "name": app.name,
            "coupling_type": app.coupling_type,
            "entities_indexed": registered.entities_snapshot if registered else [],
            "flows_indexed": registered.flows_snapshot if registered else [],
            "story_count": registered.story_count if registered else 0,
            "shared_entities_detected": [
                {"entity": s.entity_name, "apps": s.defined_in_apps}
                for s in shared
                if app.app_id in s.defined_in_apps
            ],
            "contracts_registered": len(contracts),
            "message": (
                f"App '{app.name}' registrada en el ecosistema. "
                f"Entidades: {len(registered.entities_snapshot) if registered else 0}, "
                f"Flujos: {len(registered.flows_snapshot) if registered else 0}."
            ),
        }
    except Exception as e:
        logger.exception("Error registrando app")
        return {"status": "error", "message": f"Error: {e}"}


def handle_list_ecosystem() -> dict:
    """Devuelve el estado completo del ecosistema.

    Returns:
        Apps, contratos, entidades compartidas y dependencias.
    """
    ecosystem = get_ecosystem()

    if not ecosystem.is_initialized:
        return {
            "status": "error",
            "message": "Ecosistema no inicializado. Usar init_ecosystem primero.",
        }

    registry = ecosystem.registry
    if not registry:
        return {"status": "error", "message": "No se pudo leer el registro del ecosistema."}

    apps = ecosystem.get_all_apps()
    contracts = ecosystem.get_contracts()
    shared = ecosystem.get_shared_entities()

    # Calcular dependencias por app
    app_dependencies = {}
    for app in apps:
        deps = ecosystem.get_app_dependencies(app.app_id)
        app_dependencies[app.app_id] = deps

    return {
        "status": "success",
        "ecosystem_id": registry.ecosystem_id,
        "ecosystem_name": registry.name,
        "description": registry.description,
        "statistics": {
            "total_apps": len(apps),
            "total_contracts": len(contracts),
            "shared_entities": len(shared),
            "cohesive_apps": len([a for a in apps if a.coupling_type == "cohesive"]),
            "decoupled_apps": len([a for a in apps if a.coupling_type == "decoupled"]),
        },
        "apps": [
            {
                "app_id": a.app_id,
                "name": a.name,
                "coupling_type": a.coupling_type,
                "team": a.team,
                "entities_count": len(a.entities_snapshot),
                "flows_count": len(a.flows_snapshot),
                "story_count": a.story_count,
                "exposes": a.exposes_contracts,
                "consumes": a.consumes_contracts,
                "depends_on": app_dependencies.get(a.app_id, {}).get("depends_on", []),
                "depended_by": app_dependencies.get(a.app_id, {}).get("depended_by", []),
            }
            for a in apps
        ],
        "contracts": [
            {
                "contract_id": c.contract_id,
                "name": c.name,
                "type": c.type,
                "provider": c.provider_app,
                "consumers": c.consumer_apps,
                "entities": c.entities_involved,
                "version": c.version,
            }
            for c in contracts
        ],
        "shared_entities": [
            {
                "entity": s.entity_name,
                "apps": s.defined_in_apps,
                "is_consistent": s.is_consistent,
                "divergence": s.divergence_notes if not s.is_consistent else "",
            }
            for s in shared
        ],
    }


def handle_get_cross_app_context(story_id: str) -> dict:
    """Obtiene contexto transversal de otras apps relevante para una HU.

    Lee la HU del proyecto actual y busca en el ecosistema
    entidades/contratos/apps que se relacionan.

    Args:
        story_id: ID de la HU en el proyecto actual.

    Returns:
        Contexto cross-app filtrado por relevancia.
    """
    memory = get_memory()
    ecosystem = get_ecosystem()

    if not memory.is_initialized:
        return {"status": "error", "message": "Proyecto no inicializado."}

    if not ecosystem.is_initialized:
        return {
            "status": "success",
            "cross_app_available": False,
            "message": "No hay ecosistema configurado. El proyecto opera en modo standalone.",
        }

    story = memory.get_story(story_id)
    if not story:
        return {"status": "error", "message": f"HU '{story_id}' no encontrada."}

    # Obtener app_id del proyecto actual
    current_app_id = None
    if memory.index and memory.index.config.app_id:
        current_app_id = memory.index.config.app_id

    # Consultar contexto cross-app
    context = ecosystem.get_cross_app_context(
        entity_names=story.entities_detected,
        flow_names=story.flows_detected,
        current_app_id=current_app_id,
    )

    if not context.get("available"):
        return {
            "status": "success",
            "cross_app_available": False,
            "message": "Ecosistema no disponible.",
        }

    return {
        "status": "success",
        "cross_app_available": True,
        "story_id": story_id,
        "story_entities": story.entities_detected,
        "story_flows": story.flows_detected,
        "current_app": current_app_id or "unknown",
        "ecosystem": context["ecosystem"],
        "shared_entities_relevant": context["shared_entities_relevant"],
        "contracts_relevant": context["contracts_relevant"],
        "other_apps_context": context["other_apps_context"],
        "instructions_for_llm": (
            "Usa el contexto cross-app para enriquecer el analisis de la HU. "
            "Si hay entidades compartidas divergentes, senalalo como riesgo. "
            "Si hay contratos relevantes, verifica que la HU los considere. "
            "Si otras apps tocan las mismas entidades, menciona posibles impactos."
        ),
    }


def handle_sync_ecosystem(app_id: str = "") -> dict:
    """Re-sincroniza las apps del ecosistema desde sus .hu-memory/.

    Args:
        app_id: ID de app especifica, o vacio para sincronizar todas.

    Returns:
        Resultado de la sincronizacion.
    """
    ecosystem = get_ecosystem()

    if not ecosystem.is_initialized:
        return {
            "status": "error",
            "message": "Ecosistema no inicializado.",
        }

    try:
        if app_id:
            result = ecosystem.sync_app(app_id)
            if not result:
                return {
                    "status": "error",
                    "message": f"App '{app_id}' no encontrada en el ecosistema.",
                }
            return {
                "status": "success",
                "synced_app": app_id,
                "entities": result.entities_snapshot,
                "flows": result.flows_snapshot,
                "story_count": result.story_count,
                "shared_entities": [
                    s.entity_name
                    for s in ecosystem.get_shared_entities()
                    if app_id in s.defined_in_apps
                ],
                "message": f"App '{app_id}' sincronizada exitosamente.",
            }
        else:
            synced_count = ecosystem.sync_all_apps()
            shared = ecosystem.get_shared_entities()
            return {
                "status": "success",
                "apps_synced": synced_count,
                "total_apps": len(ecosystem.get_all_apps()),
                "shared_entities_total": len(shared),
                "message": f"{synced_count} apps sincronizadas. {len(shared)} entidades compartidas detectadas.",
            }
    except Exception as e:
        logger.exception("Error sincronizando ecosistema")
        return {"status": "error", "message": f"Error: {e}"}
