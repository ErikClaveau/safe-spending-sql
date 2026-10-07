"""Loaders for the generator configuration and catalogs, read from YAML in resources/."""

import hashlib
from pathlib import Path

import yaml

from safe_spending.generator.config.archetype import Archetype
from safe_spending.generator.config.catalog import Catalog
from safe_spending.generator.config.category import Category
from safe_spending.generator.config.generator_config import GeneratorConfig
from safe_spending.generator.config.merchant import Merchant

RESOURCES = Path(__file__).parents[1] / "resources"
CONFIG_FILE = RESOURCES / "config.yaml"
CATALOG_FILES = ("categories.yaml", "merchants.yaml")


def load_config(path: Path = CONFIG_FILE) -> GeneratorConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    archetypes = {name: Archetype(name=name, **a) for name, a in raw["archetypes"].items()}
    return GeneratorConfig(**{**raw, "archetypes": archetypes})


def load_catalog(resources: Path = RESOURCES) -> Catalog:
    categories = []
    for group in yaml.safe_load((resources / "categories.yaml").read_text(encoding="utf-8"))["groups"]:
        for name in group["categories"]:
            categories.append(Category(category_id=len(categories) + 1, name=name, group_name=group["name"]))
    names = {c.name for c in categories}
    if len(names) != len(categories):
        raise ValueError("duplicate category names in categories.yaml")

    merchants = []
    raw = yaml.safe_load((resources / "merchants.yaml").read_text(encoding="utf-8"))["merchants"]
    for entry in raw:
        if entry["category"] not in names:
            raise ValueError(f"merchant {entry['name']} has unknown category {entry['category']}")
        merchants.append(
            Merchant(
                **{**entry, "variants": entry.get("variants", [entry["name"]])},
                merchant_id=len(merchants) + 1,
            )
        )
    if len({m.name for m in merchants}) != len(merchants):
        raise ValueError("duplicate merchant names in merchants.yaml")
    return Catalog(categories=tuple(categories), merchants=tuple(merchants))


def configuration_hash(config_path: Path = CONFIG_FILE, resources: Path = RESOURCES) -> str:
    """SHA-256 over the config and both catalogs, in a fixed order (manifest.json)."""
    digest = hashlib.sha256()
    for path in (config_path, *(resources / name for name in CATALOG_FILES)):
        digest.update(path.read_bytes())
    return digest.hexdigest()
