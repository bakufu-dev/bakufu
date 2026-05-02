"""Gate application-layer exceptions (P-1: REQ-ERG-HTTP-001〜006)."""

from __future__ import annotations

from bakufu.domain.value_objects import (
    AgentId,
    GateId,
    GateRole,
    InternalGateId,
    OwnerId,
    ReviewDecision,
)


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


class InternalReviewGateNotFoundError(Exception):
    """InternalReviewGate が見つからない場合（MSG-IRG-A001）。"""

    def __init__(self, gate_id: InternalGateId | str) -> None:
        super().__init__(
            f"[FAIL] InternalReviewGate {gate_id} が見つかりません。\n"
            "Next: gate_id を確認し、タスクの実行状態を"
            " 'bakufu admin list-tasks' で確認してください。"
        )
        self.gate_id = str(gate_id)


class UnauthorizedGateRoleError(Exception):
    """GateRole 権限がない場合（MSG-IRG-A002）。

    T1: GateRole詐称防止。gate.required_gate_rolesに含まれないroleからのVerdict提出を拒否する。
    """

    def __init__(self, agent_id: AgentId | str, role: GateRole | str) -> None:
        super().__init__(
            f"[FAIL] エージェント {agent_id} は GateRole '{role}' の審査権限を持っていません。\n"
            f"Next: Agent の role_profile に '{role}' が含まれているか確認し、"
            f"権限を付与してから再試行してください。"
        )
        self.agent_id = str(agent_id)
        self.role = str(role)


__all__ = [
    "GateAlreadyDecidedError",
    "GateAuthorizationError",
    "GateNotFoundError",
    "InternalReviewGateNotFoundError",
    "UnauthorizedGateRoleError",
]
