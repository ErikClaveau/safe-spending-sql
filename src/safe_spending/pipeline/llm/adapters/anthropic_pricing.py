"""Anthropic list prices, USD per million tokens, as of 2026-10-06.

A model missing here has no cost in the trace rather than a wrong one. Haiku 5.5 prices are for prompts
up to 100K tokens; its cache prices are not verified (the usual 0.1x read and 1.25x write), but nothing
is cached today, so they do not affect the cost.
"""

from decimal import Decimal

from safe_spending.pipeline.llm.schemas import ModelPricing

ANTHROPIC_PRICING = {
    "claude-sonnet-5-5": ModelPricing(
        input=Decimal("2.00"),
        output=Decimal("10.00"),
        cache_read=Decimal("0.20"),
        cache_write=Decimal("2.50"),
    ),
    "claude-opus-5-5": ModelPricing(
        input=Decimal("4.00"),
        output=Decimal("20.00"),
        cache_read=Decimal("0.20"),
        cache_write=Decimal("5.00"),
    ),
    "claude-haiku-5-5": ModelPricing(
        input=Decimal("0.10"),
        output=Decimal("0.50"),
        cache_read=Decimal("0.01"),
        cache_write=Decimal("0.125"),
    ),
}
