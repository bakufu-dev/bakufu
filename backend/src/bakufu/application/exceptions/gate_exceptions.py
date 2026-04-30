"""Gate application-layer exceptions (P-1: REQ-ERG-HTTP-001〜006)."""

from __future__ import annotations

from bakufu.domain.value_objects import GateId, OwnerId, ReviewDecision


class GateNotFoundError(Exception):
    """Gate が見つからない場合（MSG-ERG-HTTP-001）。"""

    def __init__(self, gate_id: GateId | str) -> None:
        super().__init__(f"Gate not found: {gate_id}")
        self.gate_id = str(gate_id)


class GateAlreadyDecidedError(Exception):
    """既に判断済みの Gate に approve / reject / cancel を試みた場合（MSG-ERG-HTTP-002）。

    domain の ``ExternalReviewGateInvariantViolation(kind='decision_already_decided')``
    を Service 層で wrap する。
    """

    def __init__(self, gate_id: GateId | str, current_decision: ReviewDecision | str) -> None:
        super().__init__(
            f"Gate decision is already finalized: gate_id={gate_id}, "
            f"current_decision={current_decision}"
        )
        self.gate_id = str(gate_id)
        self.current_decision = str(current_decision)


class GateAuthorizationError(Exception):
    """Bearer トークンの OwnerId が gate.reviewer_id と一致しない場合（MSG-ERG-HTTP-003）。"""

    def __init__(
        self,
        gate_id: GateId | str,
        reviewer_id: OwnerId | str,
        expected_reviewer_id: OwnerId | str,
    ) -> None:
        super().__init__(
            f"Not authorized to decide on gate: gate_id={gate_id}, "
            f"reviewer_id={reviewer_id}, expected={expected_reviewer_id}"
        )
        self.gate_id = str(gate_id)
        self.reviewer_id = str(reviewer_id)
        self.expected_reviewer_id = str(expected_reviewer_id)


__all__ = [
    "GateAlreadyDecidedError",
    "GateAuthorizationError",
    "GateNotFoundError",
]
