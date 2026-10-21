from pydantic import BaseModel, ConfigDict, Field


class ScenarioRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario_id: str = Field(description="Scenario identifier; tx_labels.scenario_id points to it.")
    user_id: int = Field(description="User the scenario was applied to.")
    type: str = Field(description="Scenario type.")
    params: str = Field(description="JSON with the ground truth of the scenario, by construction.")
    description: str = Field(description="Human-readable description of the scenario.")
