"""Applies the scenarios assigned to a user, in the order they appear in the config."""

from collections.abc import Callable
from datetime import date

from safe_spending.generator.config import Catalog, GeneratorConfig
from safe_spending.generator.enums import ScenarioType
from safe_spending.generator.events import Event
from safe_spending.generator.profile import Profile
from safe_spending.generator.rng import Stage, stream
from safe_spending.generator.scenarios import (
    anomalous_month,
    job_change,
    recent_signup,
    subscription_changes,
    zero_category,
)
from safe_spending.generator.scenarios.context import ScenarioContext
from safe_spending.generator.scenarios.helpers import scenario_id
from safe_spending.generator.scenarios.scenario_application import ScenarioApplication
from safe_spending.generator.scenarios.scenario_outcome import ScenarioOutcome

Injector = Callable[[ScenarioContext], ScenarioOutcome]

INJECTORS: dict[ScenarioType, Injector] = {
    ScenarioType.SUBSCRIPTION_CHANGES: subscription_changes.inject,
    ScenarioType.JOB_CHANGE: job_change.inject,
    ScenarioType.RECENT_SIGNUP: recent_signup.inject,
    ScenarioType.ZERO_CATEGORY: zero_category.inject,
    ScenarioType.ANOMALOUS_MONTH: anomalous_month.inject,
}


def apply_scenarios(
        config: GeneratorConfig,
        catalog: Catalog,
        profile: Profile,
        events: list[Event],
        end: date
) -> ScenarioApplication:
    """Runs every scenario of the user over the baseline events. A user without one is unchanged."""
    rng = stream(
        seed=config.seed,
        user_id=profile.user_id,
        stage=Stage.SCENARIOS
    )
    current = tuple(events)
    rows = []
    signup_date = None

    for assignment in config.scenarios_of(profile.user_id):
        outcome = INJECTORS[assignment.type](
            ScenarioContext(
                config=config,
                catalog=catalog,
                profile=profile,
                events=current,
                rng=rng,
                end=end,
                scenario_id=scenario_id(profile.user_id, assignment.type),
            )
        )
        current = outcome.events
        rows.append(outcome.row)
        signup_date = outcome.signup_date or signup_date

    return ScenarioApplication(
        events=current,
        rows=tuple(rows),
        signup_date=signup_date
    )
