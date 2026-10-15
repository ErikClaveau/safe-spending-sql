from datetime import date

from safe_spending.generator.config import Catalog, GeneratorConfig
from safe_spending.generator.events import Event
from safe_spending.generator.profile import Profile
from safe_spending.generator.enums import Stage
from safe_spending.generator.rng import stream
from safe_spending.generator.savings.plan import build_savings_plan
from safe_spending.generator.savings.savings_result import Savings
from safe_spending.generator.savings.transfers import savings_events


def build_savings(
        config: GeneratorConfig,
        catalog: Catalog,
        profile: Profile,
        events: list[Event],
        end: date
) -> Savings:
    rng = stream(
        seed=config.seed,
        user_id=profile.user_id,
        stage=Stage.SAVINGS
    )
    plan = build_savings_plan(config, profile, rng)

    if plan is None:
        return Savings(plan=None)

    return Savings(
        plan=plan,
        events=tuple(savings_events(config, catalog, plan, events, rng, end))
    )
