"""Synthetic daily exchange rates (design 5.3).

One series per currency, drawn once for everybody from the global random stream, so two users
who pay in pounds on the same day get the same rate. Each series is a mean-reverting random walk
around a realistic base value. A rate is units of the currency per 1 EUR.
"""

import math
from datetime import date
from decimal import Decimal

from safe_spending.generator.config import CurrencyRate, GeneratorConfig
from safe_spending.generator.dates import daterange
from safe_spending.generator.fx.fx_series import FxSeries
from safe_spending.generator.rng import GLOBAL, Stage, stream

RATE_DECIMALS = 6  # the NUMERIC(12,6) of transactions.exchange_rate


def build_fx_series(
        config: GeneratorConfig,
        end: date
) -> FxSeries:
    """A daily rate for every currency of the config, from the period start to `end`."""
    days = daterange(config.period_start, end)

    # One stream per currency, keyed by its code: a series depends neither on the other
    # currencies nor on where the run ends, so a shorter run is a prefix of a longer one.
    return FxSeries(rates={
        currency: dict(zip(days, _walk(
            spec=spec,
            shocks=stream(
                seed=config.seed,
                user_id=GLOBAL,
                stage=Stage.FX,
                extra=_code(currency)
            ).standard_normal(len(days))
        )))
        for currency, spec in sorted(config.fx.currencies.items())
    })


def _code(currency: str) -> int:
    """A stable integer for a currency code ('GBP' -> 4670544), unique per code."""
    return int.from_bytes(currency.encode("ascii"), "big")


def _walk(
        spec: CurrencyRate,
        shocks
) -> list[Decimal]:
    log_base = math.log(spec.base)
    level = log_base
    rates = []

    for shock in shocks:
        level += spec.reversion * (log_base - level) + spec.daily_sigma * float(shock)
        rates.append(Decimal(f"{math.exp(level):.{RATE_DECIMALS}f}"))

    return rates
