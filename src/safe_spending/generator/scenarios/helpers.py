"""Small pieces shared by the injectors."""

from datetime import date

from pydantic import BaseModel

from safe_spending.generator.enums import ScenarioType, TxCode
from safe_spending.generator.events import Event
from safe_spending.generator.money import to_cents
from safe_spending.generator.scenarios.context import ScenarioContext
from safe_spending.generator.schemas import ScenarioRow


def scenario_id(
        user_id: int,
        scenario_type: ScenarioType
) -> str:
    return f"{user_id:03d}-{scenario_type}"


def build_row(
        ctx: ScenarioContext,
        scenario_type: ScenarioType,
        params: BaseModel,
        description: str
) -> ScenarioRow:
    """`params` carries the ground truth by construction, as JSON with sorted, stable fields."""
    return ScenarioRow(
        scenario_id=ctx.scenario_id,
        user_id=ctx.profile.user_id,
        type=scenario_type,
        params=params.model_dump_json(),
        description=description,
    )


def card_purchase(
        ctx: ScenarioContext,
        day: date,
        merchant,
        amount_cents: int
) -> Event:
    """A scenario-tagged card purchase booked the same day it was made."""
    return Event(
        booking_date=day,
        value_date=day,
        tx_code=TxCode.CARD_PURCHASE,
        amount_cents=-amount_cents,
        category_id=ctx.catalog.category(merchant.category).category_id,
        merchant=merchant,
        scenario_id=ctx.scenario_id,
    )


def subscription_price_cents(merchant) -> int:
    return to_cents(euros=merchant.price_eur)
