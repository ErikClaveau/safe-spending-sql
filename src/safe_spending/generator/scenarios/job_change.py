"""Job change (design 5.5): from some month on, the salary comes from another employer and is higher.

The baseline salary events are rewritten in place (amount and employer), so the number of pays
does not change and no pay is duplicated.
"""

from faker import Faker

from safe_spending.generator.enums import ScenarioType, TxCode
from safe_spending.generator.events import Event
from safe_spending.generator.money import CENTS_PER_EUR, to_decimal
from safe_spending.generator.profile.builder import FAKER_LOCALE, FAKER_SEED_BOUND
from safe_spending.generator.scenarios.context import ScenarioContext
from safe_spending.generator.scenarios.helpers import build_row
from safe_spending.generator.scenarios.job_change_params import JobChangeParams
from safe_spending.generator.scenarios.scenario_outcome import ScenarioOutcome

CHANGE_FIRST_MONTH = 8
CHANGE_LAST_MARGIN = 6  # at least this many months of pays with the new employer
RAISE_RANGE = (1.10, 1.35)  # new instalment = old instalment * a factor in this range


def inject(ctx: ScenarioContext) -> ScenarioOutcome:
    rng = ctx.rng
    change_index = int(rng.integers(CHANGE_FIRST_MONTH, len(ctx.timeline) - CHANGE_LAST_MARGIN + 1))
    year, month = ctx.timeline[change_index]

    salaries = [e for e in ctx.events if e.tx_code == TxCode.SALARY]
    change_date = min(e.booking_date for e in salaries if (e.booking_date.year, e.booking_date.month) == (year, month))
    old_cents = salaries[0].amount_cents
    new_cents = round(old_cents * float(rng.uniform(*RAISE_RANGE)) / CENTS_PER_EUR) * CENTS_PER_EUR
    new_employer = _new_employer(ctx)

    events = tuple(
        _with_new_employer(event, new_employer, new_cents, ctx.scenario_id)
        if event.tx_code == TxCode.SALARY and event.booking_date >= change_date
        else event
        for event in ctx.events
    )

    return ScenarioOutcome(
        events=events,
        row=build_row(
            ctx=ctx,
            scenario_type=ScenarioType.JOB_CHANGE,
            params=JobChangeParams(
                change_date=change_date,
                old_employer=ctx.profile.employer,
                new_employer=new_employer,
                old_instalment_eur=to_decimal(old_cents),
                new_instalment_eur=to_decimal(new_cents),
            ),
            description="The user changes employer and the salary instalment goes up.",
        ),
    )


def _new_employer(ctx: ScenarioContext) -> str:
    fake = Faker(FAKER_LOCALE)
    fake.seed_instance(int(ctx.rng.integers(0, FAKER_SEED_BOUND)))
    employer = fake.company()

    while employer == ctx.profile.employer:
        employer = fake.company()

    return employer


def _with_new_employer(
        event: Event,
        employer: str,
        amount_cents: int,
        scenario_id: str
) -> Event:
    return event.model_copy(update={
        "counterparty": employer,
        "amount_cents": amount_cents,
        "scenario_id": scenario_id,
    })
