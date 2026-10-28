from pathlib import Path

import yaml

from safe_spending.evals.adversarial.isolation_set import ADVERSARIAL_DIR
from safe_spending.evals.adversarial.schemas import InjectionSet

INJECTION_FILE = ADVERSARIAL_DIR / "injection_v0.yaml"


def load_injection_set(path: Path = INJECTION_FILE) -> InjectionSet:
    return InjectionSet.model_validate(obj=yaml.safe_load(path.read_text(encoding="utf-8")))
