"""Recent sign-up (design 5.5): the user has only a few months of history.

Events before the sign-up date are dropped and the user's `signup_date` moves forward, so the
"no data" questions have a clean ground truth: nothing exists before that date.
"""

from datetime import timedelta

from safe_spending.generator.enums import ScenarioType
from safe_spending.generator.scenarios.context import ScenarioContext
from safe_spending.generator.scenarios.helpers import build_row
from safe_spending.generator.scenarios.recent_signup_params import RecentSignupParams
from safe_spending.generator.scenarios.scenario_outcome import ScenarioOutcome

HISTORY_DAYS = (60, 100)  # inclusive range of days between sign-up and the reference date


def inject(ctx: ScenarioContext) -> ScenarioOutcome:
    history_days = int(ctx.rng.integers(
        low=HISTORY_DAYS[0],
        high=HISTORY_DAYS[1] + 1
    ))
    signup_date = ctx.end - timedelta(days=history_days)

    return ScenarioOutcome(
        events=tuple(
            e
            for e in ctx.events
            if e.booking_date >= signup_date
        ),
        signup_date=signup_date,
        row=build_row(
            ctx=ctx,
            scenario_type=ScenarioType.RECENT_SIGNUP,
            params=RecentSignupParams(
                signup_date=signup_date,
                history_days=history_days
            ),
            description="The user signed up a few months before the reference date.",
        ),
    )
