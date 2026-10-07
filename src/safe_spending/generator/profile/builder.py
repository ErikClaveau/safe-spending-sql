"""User profiles: who the user is and what they earn, pay and habitually buy (design 5.1).

Everything here draws from the user's `profile` stream.
"""

import numpy as np
from faker import Faker

from safe_spending.generator import iban as iban_module
from safe_spending.generator.config import Catalog, GeneratorConfig, Merchant
from safe_spending.generator.money import to_cents
from safe_spending.generator.profile.profile import Profile
from safe_spending.generator.profile.subscription import Subscription
from safe_spending.generator.profile.utility import Utility
from safe_spending.generator.rng import stream

# Share of a category's purchases going to the user's 1st, 2nd and 3rd habitual merchant.
HABITUAL_SHARES = (0.6, 0.3, 0.1)


def _weighted_pick(
        rng: np.random.Generator,
        merchants: list[Merchant],
        k: int
) -> list[Merchant]:
    weights = np.array(
        [m.weight for m in merchants],
        dtype=float
    )
    indexes = rng.choice(len(merchants), size=min(k, len(merchants)), replace=False, p=weights / weights.sum())

    return [merchants[int(i)] for i in indexes]


def build_profile(
        config: GeneratorConfig,
        catalog: Catalog,
        user_id: int
) -> Profile:
    rng = stream(config.seed, user_id, "profile")
    fake = Faker("es_ES")
    fake.seed_instance(int(rng.integers(0, 2**31 - 1)))

    names = sorted(config.archetypes)
    weights = np.array([config.archetypes[n].weight for n in names], dtype=float)
    archetype = config.archetypes[names[int(rng.choice(len(names), p=weights / weights.sum()))]]

    cities = sorted(config.cities)
    city_weights = np.array([config.cities[c] for c in cities], dtype=float)
    city = cities[int(rng.choice(len(cities), p=city_weights / city_weights.sum()))]

    name, landlord, employer = fake.name(), fake.name(), fake.company()

    low, high = archetype.annual_net_income_eur
    annual_net_cents = to_cents(round(float(rng.uniform(low, high)), -2))
    monthly_income_cents = annual_net_cents // 12

    rent_share = float(rng.uniform(*archetype.rent_share))
    rent_cents = to_cents(round(rent_share * monthly_income_cents / 100 / 5) * 5)

    pay_day = int(rng.integers(archetype.pay_day[0], archetype.pay_day[1] + 1))
    rent_day = int(rng.integers(archetype.rent_day[0], archetype.rent_day[1] + 1))

    def merchants_of(channel: str, kind: str | None = None) -> list[Merchant]:
        return [m for m in catalog.merchants if m.channel == channel and (kind is None or m.kind == kind)]

    utilities = []
    for kind in ("electricity", "internet"):
        merchant = _weighted_pick(rng, merchants_of("direct_debit", kind), 1)[0]
        utilities.append(Utility(merchant=merchant, day=int(rng.integers(1, 29)), base_cents=to_cents(float(rng.uniform(*merchant.monthly_eur)))))
    if rng.random() < 0.6:
        merchant = _weighted_pick(rng, merchants_of("direct_debit", "mobile"), 1)[0]
        utilities.append(Utility(merchant=merchant, day=int(rng.integers(1, 29)), base_cents=to_cents(float(rng.uniform(*merchant.monthly_eur)))))

    n_subscriptions = int(rng.integers(archetype.subscriptions[0], archetype.subscriptions[1] + 1))
    subscriptions = tuple(
        Subscription(merchant=m, day=int(rng.integers(1, 29))) for m in _weighted_pick(rng, merchants_of("subscription"), n_subscriptions)
    )

    habitual = {}
    for category in sorted(archetype.category_budget_share):
        available = [m for m in catalog.merchants_in(category) if m.channel in ("card_present", "card_online")]
        picked = _weighted_pick(rng, available, len(HABITUAL_SHARES))
        shares = np.array(HABITUAL_SHARES[: len(picked)], dtype=float)
        habitual[category] = tuple(zip(picked, (shares / shares.sum()).tolist()))

    return Profile(
        user_id=user_id,
        archetype=archetype.name,
        name=name,
        city=city,
        employer=employer,
        landlord=landlord,
        iban=iban_module.generate(rng),
        card_prefix=f"{int(rng.choice([4, 5]))}{int(rng.integers(0, 1000)):03d}",
        annual_net_cents=annual_net_cents,
        monthly_income_cents=monthly_income_cents,
        pay_day=pay_day,
        rent_cents=rent_cents,
        rent_day=rent_day,
        utilities=tuple(utilities),
        subscriptions=subscriptions,
        habitual=habitual,
        budget_noise=float(np.exp(rng.normal(0, 0.2))),
    )
