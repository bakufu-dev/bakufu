"""NotifyChannel MVP kind constraint (TC-UT-WF-055 / 056).

MVP only accepts ``kind='discord'``. The Literal alias rejects ``'slack'`` /
``'email'`` at construction so unimplemented Adapter kinds cannot enter the
domain layer (Confirmation G + I).
"""

from __future__ import annotations

import pytest
from bakufu.domain.value_objects import NotifyChannel
from pydantic import ValidationError

from tests.factories.workflow import DEFAULT_DISCORD_WEBHOOK


class TestNotifyChannelKindMVP:
    """TC-UT-WF-055 / 056 — MVP only accepts kind='discord'."""

    @pytest.mark.parametrize("bad_kind", ["slack", "email"])
    def test_non_discord_kind_rejected(self, bad_kind: str) -> None:
        """TC-UT-WF-055/056: kind='slack' or 'email' raises ValidationError."""
        with pytest.raises(ValidationError):
            NotifyChannel.model_validate(
                {"kind": bad_kind, "target": DEFAULT_DISCORD_WEBHOOK},
            )
