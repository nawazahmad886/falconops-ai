from .base import Adapter, MongoSeededAdapter
from .elk import ELKAdapter
from .appdynamics import AppDynamicsAdapter
from .solarwinds import SolarWindsAdapter
from .mq import MQAdapter
from .db import DBAdapter
from .cmdb import CMDBAdapter
from .changes import ChangesAdapter
from .oneagent_live import OneAgentLiveAdapter
from .llm_observability_live import LLMObservabilityLiveAdapter

ADAPTERS: dict[str, Adapter] = {
    "elk": ELKAdapter(),
    "appdynamics": AppDynamicsAdapter(),
    "solarwinds": SolarWindsAdapter(),
    "mq": MQAdapter(),
    "db": DBAdapter(),
    "cmdb": CMDBAdapter(),
    "changes": ChangesAdapter(),
    "oneagent_live": OneAgentLiveAdapter(),
    "llm_live": LLMObservabilityLiveAdapter(),
}

__all__ = [
    "Adapter",
    "MongoSeededAdapter",
    "ELKAdapter",
    "AppDynamicsAdapter",
    "SolarWindsAdapter",
    "MQAdapter",
    "DBAdapter",
    "CMDBAdapter",
    "ChangesAdapter",
    "OneAgentLiveAdapter",
    "LLMObservabilityLiveAdapter",
    "ADAPTERS",
]
