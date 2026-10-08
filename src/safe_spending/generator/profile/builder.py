"""User profiles: who the user is and what they earn, pay and habitually buy (design 5.1).

Everything here draws from the user's `profile` stream.
"""

import numpy as np
from faker import Faker

from safe_spending.generator import iban as iban_module
from safe_spending.generator.config import Archetype, Catalog, GeneratorConfig, Merchant
from safe_spending.generator.dates import MONTHS_PER_YEAR
from safe_spending.generator.enums import Channel, UtilityKind
from safe_spending.generator.money import CENTS_PER_EUR, to_cents
from safe_spending.generator.profile.profile import Profile
from safe_spending.generator.profile.subscription import Subscription
from safe_spending.generator.profile.utility import Utility
from safe_spending.generator.rng import Stage, stream

# Share of a category's purchases going to the user's 1st, 2nd and 3rd habitual merchant.
HABITUAL_SHARES = (0.6, 0.3, 0.1)
# Channels a habitual (random-purchase) merchant can have.
HABITUAL_CHANNELS = (Channel.CARD_PRESENT, Channel.CARD_ONLINE)

FAKER_LOCALE = "es_ES"
FAKER_SEED_BOUND = 2**31 - 1

INCOME_ROUNDING_DIGITS = -2  # annual net income is rounded to hundreds of euros
RENT_ROUNDING_EUR = 5  # rent is rounded to multiples of 5 euros
BUDGET_NOISE_SIGMA = 0.2  # lognormal sigma of the per-user spending multiplier

# Billing days stop at 28 so every month has them (day_in_month clamps anyway).
FIRST_BILLING_DAY = 1
LAST_BILLING_DAY = 28

# Every user has electricity and internet; mobile is added with this probability.
MANDATORY_UTILITIES = (UtilityKind.ELECTRICITY, UtilityKind.INTERNET)
MOBILE_PROBABILITY = 0.6

CARD_NETWORK_FIRST_DIGITS = (4, 5)  # Visa, Mastercard
CARD_PREFIX_SUFFIX_LIMIT = 1000  # the other three digits of the 4-digit card prefix


def build_profile(
        config: GeneratorConfig,
        catalog: Catalog,
        user_id: int
) -> Profile:
    rng = stream(
        seed=config.seed,
        user_id=user_id,
        stage=Stage.PROFILE
    )
    fake = Faker(FAKER_LOCALE)
    fake.seed_instance(int(rng.integers(
        low=0,
        high=FAKER_SEED_BOUND))
    )

    archetype = _get_archetype(
        rng=rng,
        archetypes=config.archetypes
    )
    name, landlord, employer = fake.name(), fake.name(), fake.company()

    low, high = archetype.annual_net_income_eur
    annual_net_cents = to_cents(round(float(rng.uniform(low, high)), INCOME_ROUNDING_DIGITS))
    monthly_income_cents = annual_net_cents // MONTHS_PER_YEAR

    rent_share = float(rng.uniform(*archetype.rent_share))
    rent_cents = to_cents(round(rent_share * monthly_income_cents / CENTS_PER_EUR / RENT_ROUNDING_EUR) * RENT_ROUNDING_EUR)

    pay_day = int(rng.integers(archetype.pay_day[0], archetype.pay_day[1] + 1))
    rent_day = int(rng.integers(archetype.rent_day[0], archetype.rent_day[1] + 1))

    return Profile(
        user_id=user_id,
        archetype=archetype.name,
        name=name,
        city=_get_city(
            rng=rng,
            city_options=config.cities
        ),
        employer=employer,
        landlord=landlord,
        iban=iban_module.generate(rng),
        card_prefix=f"{int(rng.choice(CARD_NETWORK_FIRST_DIGITS))}{int(rng.integers(0, CARD_PREFIX_SUFFIX_LIMIT)):03d}",
        annual_net_cents=annual_net_cents,
        monthly_income_cents=monthly_income_cents,
        pay_day=pay_day,
        rent_cents=rent_cents,
        rent_day=rent_day,
        utilities=tuple(_get_utilities(
            rng=rng,
            merchants=catalog.merchants
        )),
        subscriptions=_get_subscriptions(
            rng=rng,
            archetype=archetype,
            merchants=catalog.merchants,
            channel=Channel.SUBSCRIPTION
        ),
        habitual=_get_habitual(
            rng=rng,
            category_budget_share=archetype.category_budget_share,
            catalog=catalog
        ),
        budget_noise=float(np.exp(rng.normal(0, BUDGET_NOISE_SIGMA))),
    )


def _get_habitual(
        rng: np.random.Generator,
        category_budget_share: dict[str, float],
        catalog: Catalog
) -> dict[str, tuple[tuple[Merchant, float], ...]]:
    habitual = {}

    for category in sorted(category_budget_share):
        available = [
            m
            for m in catalog.merchants_in(category)
            if m.channel in HABITUAL_CHANNELS
        ]
        picked = _weighted_pick(
            rng=rng,
            merchants=available,
            k=len(HABITUAL_SHARES)
        )
        shares = np.array(HABITUAL_SHARES[: len(picked)], dtype=float)
        habitual[category] = tuple(zip(picked, (shares / shares.sum()).tolist()))

    return habitual


def _get_subscriptions(
        rng: np.random.Generator,
        archetype: Archetype,
        merchants: tuple[Merchant, ...],
        channel: Channel
) -> tuple[Subscription, ...]:
    n_subscriptions = int(rng.integers(archetype.subscriptions[0], archetype.subscriptions[1] + 1))
    subscriptions = tuple(
        Subscription(
            merchant=m,
            day=int(rng.integers(
                low=FIRST_BILLING_DAY,
                high=LAST_BILLING_DAY + 1)
            )
        ) for m in _weighted_pick(
            rng=rng,
            merchants=_merchants_of(
                merchants=merchants,
                channel=channel
            ),
            k=n_subscriptions
        )
    )

    return subscriptions


def _get_city(
        rng: np.random.Generator,
        city_options: dict[str, float]
) -> str:
    cities = sorted(city_options)
    city_weights = np.array(
        object=[city_options[c] for c in cities],
        dtype=float
    )
    city = cities[int(rng.choice(
        len(cities),
        p=city_weights / city_weights.sum()
    ))]

    return city


def _get_archetype(
        rng: np.random.Generator,
        archetypes: dict[str, Archetype]
) -> Archetype:
    names = sorted(archetypes)
    weights = np.array(
        object=[archetypes[n].weight for n in names],
        dtype=float
    )
    archetype = archetypes[names[int(rng.choice(
        len(names),
        p=weights / weights.sum()
    ))]]

    return archetype


def _weighted_pick(
        rng: np.random.Generator,
        merchants: list[Merchant],
        k: int
) -> list[Merchant]:
    weights = np.array(
        [m.weight for m in merchants],
        dtype=float
    )
    indexes = rng.choice(
        len(merchants),
        size=min(k, len(merchants)),
        replace=False,
        p=weights / weights.sum()
    )

    return [merchants[int(i)] for i in indexes]


def _merchants_of(
        merchants: tuple[Merchant, ...],
        channel: Channel,
        kind: UtilityKind | None = None
) -> list[Merchant]:
    return [
        m
        for m in merchants
        if m.channel == channel and (kind is None or m.kind == kind)
    ]


def _get_utility(
        rng: np.random.Generator,
        merchants: tuple[Merchant, ...],
        channel: Channel,
        kind: UtilityKind
) -> Utility:
    merchant = _weighted_pick(
        rng=rng,
        merchants=_merchants_of(
            merchants=merchants,
            channel=channel,
            kind=kind
        ),
        k=1
    )[0]

    return Utility(
        merchant=merchant,
        day=int(rng.integers(
            low=FIRST_BILLING_DAY,
            high=LAST_BILLING_DAY + 1
        )),
        base_cents=to_cents(float(rng.uniform(*merchant.monthly_eur)))
    )


def _get_utilities(
        rng: np.random.Generator,
        merchants: tuple[Merchant, ...],
) -> list[Utility]:
    utilities = []

    for kind in MANDATORY_UTILITIES:
        utility = _get_utility(
            rng=rng,
            merchants=merchants,
            channel=Channel.DIRECT_DEBIT,
            kind=kind
        )

        utilities.append(utility)
    if rng.random() < MOBILE_PROBABILITY:
        utility = _get_utility(
            rng=rng,
            merchants=merchants,
            channel=Channel.DIRECT_DEBIT,
            kind=UtilityKind.MOBILE
        )

        utilities.append(utility)

    return utilities
