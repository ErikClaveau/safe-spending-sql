"""Category at zero (design 5.5): a user who never spends in one category.

It tells "0 EUR" apart from "no data". The category is one the user would otherwise buy in,
and every purchase in it is removed, so the ground truth is exactly zero.
"""

from safe_spending.generator.enums import ScenarioType
from safe_spending.generator.scenarios.context import ScenarioContext
from safe_spending.generator.scenarios.helpers import build_row
from safe_spending.generator.scenarios.scenario_outcome import ScenarioOutcome
from safe_spending.generator.scenarios.zero_category_params import ZeroCategoryParams

# Discretionary categories where spending nothing is plausible.
CANDIDATE_CATEGORIES = (
    "Comida a domicilio",
    "Taxi y VTC",
    "Ropa y calzado",
    "Electrónica",
    "Hogar y bricolaje",
    "Cuidado personal",
)


def inject(ctx: ScenarioContext) -> ScenarioOutcome:
    candidates = [c for c in CANDIDATE_CATEGORIES if c in ctx.profile.habitual]
    name = candidates[int(ctx.rng.integers(len(candidates)))]
    category = ctx.catalog.category(name)

    kept = tuple(e for e in ctx.events if e.category_id != category.category_id)

    return ScenarioOutcome(
        events=kept,
        row=build_row(
            ctx=ctx,
            scenario_type=ScenarioType.ZERO_CATEGORY,
            params=ZeroCategoryParams(
                category=category.name,
                group=category.group_name,
                purchases_removed=len(ctx.events) - len(kept),
            ),
            description=f"The user never spends in {category.name}.",
        ),
    )
