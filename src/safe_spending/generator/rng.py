"""Independent random streams (generator design, section 6.1).

Each (user, stage) pair gets its own stream derived from the global seed, so adding,
removing or changing a user, or changing one stage's draws, never alters any other
user's data or any other stage of the same user. User id 0 is the global stream for
shared elements.
"""

from enum import StrEnum

import numpy as np


class Stage(StrEnum):
    # Order matters: the index is part of the stream key. Append new stages, never reorder.
    PROFILE = "profile"
    RECURRING = "recurring"
    PURCHASES = "purchases"
    SPECIAL = "special"
    SCENARIOS = "scenarios"
    TRAPS = "traps"
    TEXT = "text"


STAGES = tuple(Stage)
GLOBAL = 0


def stream(
        seed: int,
        user_id: int,
        stage: Stage
) -> np.random.Generator:
    key = (user_id, STAGES.index(stage))

    return np.random.default_rng(
        seed=np.random.SeedSequence(
            entropy=seed,
            spawn_key=key
        )
    )
