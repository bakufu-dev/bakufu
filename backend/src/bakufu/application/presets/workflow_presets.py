"""Workflow preset definitions (V-model / Agile)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WorkflowPresetDefinition:
    """Workflow プリセット定義。"""

    preset_name: str
    display_name: str
    description: str
    name: str
    stages: list[dict] = field(default_factory=list)
    transitions: list[dict] = field(default_factory=list)
    entry_stage_id: str = ""

    @property
    def stage_count(self) -> int:
        """ステージ数。"""
        return len(self.stages)

    @property
    def transition_count(self) -> int:
        """トランジション数。"""
        return len(self.transitions)


# ---------------------------------------------------------------------------
# V-model preset (13 stages, 15 transitions)
# Stage IDs: "00000001-0000-4000-8000-{i:012d}"
# Transition IDs: "00000001-0001-4000-8000-{i:012d}"
# ---------------------------------------------------------------------------
_VMODEL_STAGES: list[dict] = [
    {
        "id": "00000001-0000-4000-8000-000000000001",
        "name": "要件定義",
        "kind": "WORK",
        "required_role": ["LEADER"],
        "completion_policy": {"kind": "manual", "description": ""},
        "notify_channels": [],
        "deliverable_template": "",
    },
    {
        "id": "00000001-0000-4000-8000-000000000002",
        "name": "要件レビュー",
        "kind": "INTERNAL_REVIEW",
        "required_role": ["REVIEWER"],
        "completion_policy": {"kind": "manual", "description": ""},
        "notify_channels": [],
        "deliverable_template": "",
    },
    {
        "id": "00000001-0000-4000-8000-000000000003",
        "name": "基本設計",
        "kind": "WORK",
        "required_role": ["DEVELOPER"],
        "completion_policy": {"kind": "manual", "description": ""},
        "notify_channels": [],
        "deliverable_template": "",
    },
    {
        "id": "00000001-0000-4000-8000-000000000004",
        "name": "基本設計レビュー",
        "kind": "INTERNAL_REVIEW",
        "required_role": ["REVIEWER"],
        "completion_policy": {"kind": "manual", "description": ""},
        "notify_channels": [],
        "deliverable_template": "",
    },
    {
        "id": "00000001-0000-4000-8000-000000000005",
        "name": "詳細設計",
        "kind": "WORK",
        "required_role": ["DEVELOPER"],
        "completion_policy": {"kind": "manual", "description": ""},
        "notify_channels": [],
        "deliverable_template": "",
    },
    {
        "id": "00000001-0000-4000-8000-000000000006",
        "name": "詳細設計レビュー",
        "kind": "INTERNAL_REVIEW",
        "required_role": ["REVIEWER"],
        "completion_policy": {"kind": "manual", "description": ""},
        "notify_channels": [],
        "deliverable_template": "",
    },
    {
        "id": "00000001-0000-4000-8000-000000000007",
        "name": "コーディング",
        "kind": "WORK",
        "required_role": ["DEVELOPER"],
        "completion_policy": {"kind": "manual", "description": ""},
        "notify_channels": [],
        "deliverable_template": "",
    },
    {
        "id": "00000001-0000-4000-8000-000000000008",
        "name": "単体テスト",
        "kind": "WORK",
        "required_role": ["TESTER"],
        "completion_policy": {"kind": "manual", "description": ""},
        "notify_channels": [],
        "deliverable_template": "",
    },
    {
        "id": "00000001-0000-4000-8000-000000000009",
        "name": "単体テストレビュー",
        "kind": "INTERNAL_REVIEW",
        "required_role": ["REVIEWER"],
        "completion_policy": {"kind": "manual", "description": ""},
        "notify_channels": [],
        "deliverable_template": "",
    },
    {
        "id": "00000001-0000-4000-8000-000000000010",
        "name": "結合テスト",
        "kind": "WORK",
        "required_role": ["TESTER"],
        "completion_policy": {"kind": "manual", "description": ""},
        "notify_channels": [],
        "deliverable_template": "",
    },
    {
        "id": "00000001-0000-4000-8000-000000000011",
        "name": "システムテスト",
        "kind": "WORK",
        "required_role": ["TESTER"],
        "completion_policy": {"kind": "manual", "description": ""},
        "notify_channels": [],
        "deliverable_template": "",
    },
    {
        "id": "00000001-0000-4000-8000-000000000012",
        "name": "システムテストレビュー",
        "kind": "INTERNAL_REVIEW",
        "required_role": ["REVIEWER"],
        "completion_policy": {"kind": "manual", "description": ""},
        "notify_channels": [],
        "deliverable_template": "",
    },
    {
        "id": "00000001-0000-4000-8000-000000000013",
        "name": "リリース承認",
        "kind": "INTERNAL_REVIEW",
        "required_role": ["LEADER"],
        "completion_policy": {"kind": "manual", "description": ""},
        "notify_channels": [],
        "deliverable_template": "",
    },
]

# Forward APPROVED transitions (12): stage 1→2, 2→3, 3→4, 4→5, 5→6, 6→7,
#   7→8, 8→9, 9→10, 10→11, 11→12, 12→13
# Backward REJECTED transitions (3): 2→1, 4→3, 6→5
_VMODEL_TRANSITIONS: list[dict] = [
    # Forward transitions (APPROVED)
    {
        "id": "00000001-0001-4000-8000-000000000001",
        "from_stage_id": "00000001-0000-4000-8000-000000000001",
        "to_stage_id": "00000001-0000-4000-8000-000000000002",
        "condition": "APPROVED",
        "label": "",
    },
    {
        "id": "00000001-0001-4000-8000-000000000002",
        "from_stage_id": "00000001-0000-4000-8000-000000000002",
        "to_stage_id": "00000001-0000-4000-8000-000000000003",
        "condition": "APPROVED",
        "label": "",
    },
    {
        "id": "00000001-0001-4000-8000-000000000003",
        "from_stage_id": "00000001-0000-4000-8000-000000000003",
        "to_stage_id": "00000001-0000-4000-8000-000000000004",
        "condition": "APPROVED",
        "label": "",
    },
    {
        "id": "00000001-0001-4000-8000-000000000004",
        "from_stage_id": "00000001-0000-4000-8000-000000000004",
        "to_stage_id": "00000001-0000-4000-8000-000000000005",
        "condition": "APPROVED",
        "label": "",
    },
    {
        "id": "00000001-0001-4000-8000-000000000005",
        "from_stage_id": "00000001-0000-4000-8000-000000000005",
        "to_stage_id": "00000001-0000-4000-8000-000000000006",
        "condition": "APPROVED",
        "label": "",
    },
    {
        "id": "00000001-0001-4000-8000-000000000006",
        "from_stage_id": "00000001-0000-4000-8000-000000000006",
        "to_stage_id": "00000001-0000-4000-8000-000000000007",
        "condition": "APPROVED",
        "label": "",
    },
    {
        "id": "00000001-0001-4000-8000-000000000007",
        "from_stage_id": "00000001-0000-4000-8000-000000000007",
        "to_stage_id": "00000001-0000-4000-8000-000000000008",
        "condition": "APPROVED",
        "label": "",
    },
    {
        "id": "00000001-0001-4000-8000-000000000008",
        "from_stage_id": "00000001-0000-4000-8000-000000000008",
        "to_stage_id": "00000001-0000-4000-8000-000000000009",
        "condition": "APPROVED",
        "label": "",
    },
    {
        "id": "00000001-0001-4000-8000-000000000009",
        "from_stage_id": "00000001-0000-4000-8000-000000000009",
        "to_stage_id": "00000001-0000-4000-8000-000000000010",
        "condition": "APPROVED",
        "label": "",
    },
    {
        "id": "00000001-0001-4000-8000-000000000010",
        "from_stage_id": "00000001-0000-4000-8000-000000000010",
        "to_stage_id": "00000001-0000-4000-8000-000000000011",
        "condition": "APPROVED",
        "label": "",
    },
    {
        "id": "00000001-0001-4000-8000-000000000011",
        "from_stage_id": "00000001-0000-4000-8000-000000000011",
        "to_stage_id": "00000001-0000-4000-8000-000000000012",
        "condition": "APPROVED",
        "label": "",
    },
    {
        "id": "00000001-0001-4000-8000-000000000012",
        "from_stage_id": "00000001-0000-4000-8000-000000000012",
        "to_stage_id": "00000001-0000-4000-8000-000000000013",
        "condition": "APPROVED",
        "label": "",
    },
    # Backward transitions (REJECTED): 要件レビュー→要件定義, 基本設計レビュー→基本設計,
    #   詳細設計レビュー→詳細設計
    {
        "id": "00000001-0001-4000-8000-000000000013",
        "from_stage_id": "00000001-0000-4000-8000-000000000002",
        "to_stage_id": "00000001-0000-4000-8000-000000000001",
        "condition": "REJECTED",
        "label": "",
    },
    {
        "id": "00000001-0001-4000-8000-000000000014",
        "from_stage_id": "00000001-0000-4000-8000-000000000004",
        "to_stage_id": "00000001-0000-4000-8000-000000000003",
        "condition": "REJECTED",
        "label": "",
    },
    {
        "id": "00000001-0001-4000-8000-000000000015",
        "from_stage_id": "00000001-0000-4000-8000-000000000006",
        "to_stage_id": "00000001-0000-4000-8000-000000000005",
        "condition": "REJECTED",
        "label": "",
    },
]

# ---------------------------------------------------------------------------
# Agile preset (6 stages, 8 transitions)
# Stage IDs: "00000002-0000-4000-8000-{i:012d}"
# Transition IDs: "00000002-0001-4000-8000-{i:012d}"
# ---------------------------------------------------------------------------
_AGILE_STAGES: list[dict] = [
    {
        "id": "00000002-0000-4000-8000-000000000001",
        "name": "バックログ精査",
        "kind": "WORK",
        "required_role": ["LEADER"],
        "completion_policy": {"kind": "manual", "description": ""},
        "notify_channels": [],
        "deliverable_template": "",
    },
    {
        "id": "00000002-0000-4000-8000-000000000002",
        "name": "スプリント計画",
        "kind": "WORK",
        "required_role": ["DEVELOPER"],
        "completion_policy": {"kind": "manual", "description": ""},
        "notify_channels": [],
        "deliverable_template": "",
    },
    {
        "id": "00000002-0000-4000-8000-000000000003",
        "name": "開発",
        "kind": "WORK",
        "required_role": ["DEVELOPER"],
        "completion_policy": {"kind": "manual", "description": ""},
        "notify_channels": [],
        "deliverable_template": "",
    },
    {
        "id": "00000002-0000-4000-8000-000000000004",
        "name": "スプリントレビュー",
        "kind": "INTERNAL_REVIEW",
        "required_role": ["REVIEWER"],
        "completion_policy": {"kind": "manual", "description": ""},
        "notify_channels": [],
        "deliverable_template": "",
    },
    {
        "id": "00000002-0000-4000-8000-000000000005",
        "name": "バグ修正",
        "kind": "WORK",
        "required_role": ["TESTER"],
        "completion_policy": {"kind": "manual", "description": ""},
        "notify_channels": [],
        "deliverable_template": "",
    },
    {
        "id": "00000002-0000-4000-8000-000000000006",
        "name": "リリース",
        "kind": "WORK",
        "required_role": ["LEADER"],
        "completion_policy": {"kind": "manual", "description": ""},
        "notify_channels": [],
        "deliverable_template": "",
    },
]

_AGILE_TRANSITIONS: list[dict] = [
    # バックログ精査→スプリント計画(APPROVED)
    {
        "id": "00000002-0001-4000-8000-000000000001",
        "from_stage_id": "00000002-0000-4000-8000-000000000001",
        "to_stage_id": "00000002-0000-4000-8000-000000000002",
        "condition": "APPROVED",
        "label": "",
    },
    # スプリント計画→開発(APPROVED)
    {
        "id": "00000002-0001-4000-8000-000000000002",
        "from_stage_id": "00000002-0000-4000-8000-000000000002",
        "to_stage_id": "00000002-0000-4000-8000-000000000003",
        "condition": "APPROVED",
        "label": "",
    },
    # 開発→スプリントレビュー(APPROVED)
    {
        "id": "00000002-0001-4000-8000-000000000003",
        "from_stage_id": "00000002-0000-4000-8000-000000000003",
        "to_stage_id": "00000002-0000-4000-8000-000000000004",
        "condition": "APPROVED",
        "label": "",
    },
    # スプリントレビュー→バグ修正(REJECTED)
    {
        "id": "00000002-0001-4000-8000-000000000004",
        "from_stage_id": "00000002-0000-4000-8000-000000000004",
        "to_stage_id": "00000002-0000-4000-8000-000000000005",
        "condition": "REJECTED",
        "label": "",
    },
    # スプリントレビュー→リリース(APPROVED)
    {
        "id": "00000002-0001-4000-8000-000000000005",
        "from_stage_id": "00000002-0000-4000-8000-000000000004",
        "to_stage_id": "00000002-0000-4000-8000-000000000006",
        "condition": "APPROVED",
        "label": "",
    },
    # バグ修正→スプリントレビュー(APPROVED)
    {
        "id": "00000002-0001-4000-8000-000000000006",
        "from_stage_id": "00000002-0000-4000-8000-000000000005",
        "to_stage_id": "00000002-0000-4000-8000-000000000004",
        "condition": "APPROVED",
        "label": "",
    },
    # スプリント計画→バックログ精査(REJECTED)
    {
        "id": "00000002-0001-4000-8000-000000000007",
        "from_stage_id": "00000002-0000-4000-8000-000000000002",
        "to_stage_id": "00000002-0000-4000-8000-000000000001",
        "condition": "REJECTED",
        "label": "",
    },
    # バグ修正→バックログ精査(CONDITIONAL)
    {
        "id": "00000002-0001-4000-8000-000000000008",
        "from_stage_id": "00000002-0000-4000-8000-000000000005",
        "to_stage_id": "00000002-0000-4000-8000-000000000001",
        "condition": "CONDITIONAL",
        "label": "",
    },
]

WORKFLOW_PRESETS: dict[str, WorkflowPresetDefinition] = {
    "v-model": WorkflowPresetDefinition(
        preset_name="v-model",
        display_name="V モデル",
        description="要件定義からリリース承認まで V 字型プロセスを辿る 13 ステージのワークフロー。",
        name="V モデル開発プロセス",
        stages=_VMODEL_STAGES,
        transitions=_VMODEL_TRANSITIONS,
        entry_stage_id="00000001-0000-4000-8000-000000000001",
    ),
    "agile": WorkflowPresetDefinition(
        preset_name="agile",
        display_name="アジャイル",
        description="バックログ精査からリリースまでのアジャイル開発プロセス 6 ステージ。",
        name="アジャイル開発プロセス",
        stages=_AGILE_STAGES,
        transitions=_AGILE_TRANSITIONS,
        entry_stage_id="00000002-0000-4000-8000-000000000001",
    ),
}

__all__ = [
    "WORKFLOW_PRESETS",
    "WorkflowPresetDefinition",
]
