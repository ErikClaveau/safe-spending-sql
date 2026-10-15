"""Generator configuration and catalogs, loaded from YAML in resources/."""

from safe_spending.generator.config.archetype import Archetype
from safe_spending.generator.config.catalog import Catalog
from safe_spending.generator.config.category import Category
from safe_spending.generator.config.generator_config import ADVERSARIAL_SPLIT, GeneratorConfig
from safe_spending.generator.config.loaders import (
    CATALOG_FILES,
    CONFIG_FILE,
    RESOURCES,
    configuration_hash,
    load_catalog,
    load_config,
)
from safe_spending.generator.config.fx_settings import CurrencyRate, FxSettings
from safe_spending.generator.config.merchant import Merchant
from safe_spending.generator.config.refund_settings import RefundSettings
from safe_spending.generator.config.savings_settings import SavingsSettings
from safe_spending.generator.config.scenario_assignment import ScenarioAssignment
from safe_spending.generator.config.trap_settings import TrapSettings
from safe_spending.generator.config.trap_templates import CANARY_PLACEHOLDER, TRAP_CHANNELS, TrapTemplates

__all__ = [
    "ADVERSARIAL_SPLIT",
    "CANARY_PLACEHOLDER",
    "CATALOG_FILES",
    "CONFIG_FILE",
    "RESOURCES",
    "TRAP_CHANNELS",
    "Archetype",
    "Catalog",
    "Category",
    "CurrencyRate",
    "FxSettings",
    "GeneratorConfig",
    "Merchant",
    "RefundSettings",
    "SavingsSettings",
    "ScenarioAssignment",
    "TrapSettings",
    "TrapTemplates",
    "configuration_hash",
    "load_catalog",
    "load_config",
]
