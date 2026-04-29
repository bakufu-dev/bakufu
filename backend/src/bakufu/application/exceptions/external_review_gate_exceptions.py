"""ExternalReviewGate application-layer exceptions."""

from __future__ import annotations

from bakufu.domain.value_objects import GateId, OwnerId, ReviewDecision


class ExternalReviewGateNotFoundError(Exception):
    """ExternalReviewGate が見つからない場合。"""

    def __init__(self, gate_id: GateId | str) -> None:
        super().__init__(f"External review gate not found: {gate_id}")
        self.gate_id = str(gate_id)


class ExternalReviewGateAuthorizationError(Exception):
    """認証済み subject が Gate reviewer と一致しない場合。"""

    def __init__(self, gate_id: GateId | str, owner_id: OwnerId | str) -> None:
        super().__init__("Reviewer is not authorized for this gate.")
        self.gate_id = str(gate_id)
        self.owner_id = str(owner_id)


class ExternalReviewGateDecisionConflictError(Exception):
    """既決 Gate に再判断を要求した場合。"""

    def __init__(
        self,
        gate_id: GateId | str,
        current_decision: ReviewDecision | str,
        action: str,
    ) -> None:
        super().__init__("External review gate has already been decided.")
        self.gate_id = str(gate_id)
        self.current_decision = str(current_decision)
        self.action = action


__all__ = [
    "ExternalReviewGateAuthorizationError",
    "ExternalReviewGateDecisionConflictError",
    "ExternalReviewGateNotFoundError",
]
