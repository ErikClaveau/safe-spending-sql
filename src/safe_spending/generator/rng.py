"""Independent random streams (generator design, section 6.1).

Each (user, stage) pair gets its own stream derived from the global seed, so adding,
removing or changing a user, or changing one stage's draws, never alters any other
user's data or any other stage of the same user. User id 0 is the global stream for
shared elements.
"""

import numpy as np

from safe_spending.generator.enums import Stage

STAGES = tuple(Stage)
GLOBAL = 0


def stream(
        seed: int,
        user_id: int,
        stage: Stage,
        extra: int | None = None
) -> np.random.Generator:
    """The stream of a (user, stage) pair. `extra` splits it further (for example per currency)
    without changing the key, hence the draws, of any stream that does not use it."""
    key = (user_id, STAGES.index(stage)) if extra is None else (user_id, STAGES.index(stage), extra)

    return np.random.default_rng(
        seed=np.random.SeedSequence(
            entropy=seed,
            spawn_key=key
        )
    )
