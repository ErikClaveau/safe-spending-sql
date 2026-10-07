from functools import cached_property

from pydantic import BaseModel, ConfigDict

from safe_spending.generator.config.category import Category
from safe_spending.generator.config.merchant import Merchant


class Catalog(BaseModel):
    model_config = ConfigDict(frozen=True)

    categories: tuple[Category, ...]
    merchants: tuple[Merchant, ...]

    @cached_property
    def _categories_by_name(self) -> dict[str, Category]:
        return {c.name: c for c in self.categories}

    @cached_property
    def _merchants_by_category(self) -> dict[str, list[Merchant]]:
        grouped: dict[str, list[Merchant]] = {}
        for merchant in self.merchants:
            grouped.setdefault(merchant.category, []).append(merchant)
        return grouped

    def category(self, name: str) -> Category:
        return self._categories_by_name[name]

    def merchants_in(self, category: str) -> list[Merchant]:
        return self._merchants_by_category.get(category, [])
