"""Who has a savings account and how much goes into it each month (design 5.1).

A user gets one only if they can afford to save, judged top-down like the rest of the generator:
what they can save is the income minus rent, bills, subscriptions and the spending budget. The
monthly transfer is a share of that, so it stays inside what the user really keeps.
"""

import numpy as np

from safe_spending.generator import iban as iban_module
from safe_spending.generator.config import GeneratorConfig
from safe_spending.generator.money import CENTS_PER_EUR, to_cents
from safe_spending.generator.profile import Profile
from safe_spending.generator.savings.savings_plan import SavingsPlan


def savings_capacity_cents(
        config: GeneratorConfig,
        profile: Profile
) -> int:
    """What the user is expected to be able to save in a month: income minus everything budgeted."""
    archetype = config.archetypes[profile.archetype]
    budget = sum(archetype.category_budget_share.values()) * profile.monthly_income_cents * profile.budget_noise
    fixed = (
        profile.rent_cents
        + sum(u.base_cents for u in profile.utilities)
        + sum(to_cents(s.merchant.price_eur) for s in profile.subscriptions)
    )

    return profile.monthly_income_cents - round(budget) - fixed


def build_savings_plan(
        config: GeneratorConfig,
        profile: Profile,
        rng: np.random.Generator
) -> SavingsPlan | None:
    """The user's savings plan, or None if they have no savings account."""
    settings = config.savings
    # Drawn whatever the outcome, so who can save never shifts the draws that follow.
    wants_account = float(rng.random()) < settings.account_probability
    share = float(rng.uniform(*settings.share_of_capacity))
    delay_days = int(rng.integers(settings.delay_days[0], settings.delay_days[1] + 1))
    capacity = savings_capacity_cents(config, profile)

    if not wants_account or capacity < round(settings.min_capacity_eur * CENTS_PER_EUR):
        return None

    step = settings.rounding_eur * CENTS_PER_EUR
    monthly = max(settings.min_transfer_eur * CENTS_PER_EUR, round(capacity * share / step) * step)

    return SavingsPlan(
        iban=iban_module.generate(rng),
        monthly_cents=monthly,
        delay_days=delay_days
    )
