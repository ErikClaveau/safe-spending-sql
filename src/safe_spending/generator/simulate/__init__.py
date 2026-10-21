"""Orchestration: config + seed + clock -> in-memory dataset."""

from safe_spending.generator.simulate.dataset import Dataset
from safe_spending.generator.simulate.pipeline import (
    ACCOUNTS_PER_USER_STRIDE,
    TX_ID_STRIDE,
    describe,
    generate,
    simulate_user,
)

__all__ = ["ACCOUNTS_PER_USER_STRIDE", "TX_ID_STRIDE", "Dataset", "describe", "generate", "simulate_user"]
