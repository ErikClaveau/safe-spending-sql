from safe_spending.generator.config import FxSettings
from safe_spending.generator.money import CENTS_PER_EUR


def exchange_fee_cents(
        settings: FxSettings,
        eur_cents: int
) -> int:
    """The bank's fee for a foreign-currency card payment of `eur_cents` (sign ignored), in cents."""
    minimum = round(settings.fee_min_eur * CENTS_PER_EUR)

    return max(minimum, round(abs(eur_cents) * settings.fee_rate))
