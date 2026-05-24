"""TDD seed for change #1 — these tests are expected to FAIL until the
`Skill` model is implemented in add-core-models-and-storage."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from skill_forge.models import Skill


def test_skill_model_requires_name() -> None:
    with pytest.raises(ValidationError):
        Skill()  # type: ignore[call-arg]
