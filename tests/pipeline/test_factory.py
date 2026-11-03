from datetime import date
from pathlib import Path

import pytest

from safe_spending.pipeline.factory import build_assistant


def test_tracing_needs_both_a_directory_and_a_context():
    with pytest.raises(ValueError, match="go together"):
        build_assistant(
            model="any",
            prompt_version="v1",
            max_corrections=1,
            reference_date=date(2026, 9, 15),
            trace_dir=Path("logs/traces"),
        )
