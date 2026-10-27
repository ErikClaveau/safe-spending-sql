from pathlib import Path

import yaml

from safe_spending.evals.adversarial.schemas import IsolationSet

ADVERSARIAL_DIR = Path(__file__).parents[4] / "evals" / "adversarial"
ISOLATION_FILE = ADVERSARIAL_DIR / "isolation_v0.yaml"
EXPECTED_FILE = ADVERSARIAL_DIR / "expected_isolation_v0.json"


def load_isolation_set(path: Path = ISOLATION_FILE) -> IsolationSet:
    return IsolationSet.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
