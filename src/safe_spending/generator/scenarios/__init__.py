"""Scripted scenarios (design 5.5): injectors that add or change a user's movements.

Each injector receives the user's baseline events and its own random stream, and returns the new
event list plus a `scenarios` row whose `params` hold the ground truth by construction.
"""

from safe_spending.generator.scenarios.scenario_application import ScenarioApplication
from safe_spending.generator.scenarios.scenario_outcome import ScenarioOutcome
from safe_spending.generator.scenarios.registry import apply_scenarios

__all__ = ["ScenarioApplication", "ScenarioOutcome", "apply_scenarios"]
