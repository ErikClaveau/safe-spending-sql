from pydantic import BaseModel, ConfigDict


class ScenarioRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario_id: str
    user_id: int
    type: str
    params: str
    description: str
