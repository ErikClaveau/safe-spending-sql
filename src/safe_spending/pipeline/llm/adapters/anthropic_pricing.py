"""Anthropic list prices, USD per million tokens, as of 2026-10-06.

A model missing here has no cost in the trace rather than a wrong one. Add Haiku 5.5 when the
week-5 comparison needs it, after checking its cache prices.
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
}
