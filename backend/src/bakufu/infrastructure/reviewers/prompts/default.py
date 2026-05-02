"""汎用 GateRole プロンプトテンプレート（§確定 E）。

InternalReviewGateExecutor._build_prompt() が使用するデフォルトテンプレート。
role 別カスタムテンプレートが存在しない場合に使用される。
現時点では全 GateRole がこのテンプレートを使用する（YAGNI: 将来 role 別テンプレートを追加可能）。

設計書: docs/features/internal-review-gate/application/detailed-design.md §確定 E
"""

from __future__ import annotations


def build(role: str, deliverable_summary: str) -> str:
    """§確定 E のプロンプト構造に従いシステムプロンプトを構築する。

    Args:
        role: GateRole slug（例: "reviewer" / "security"）。
        deliverable_summary: task.current_deliverable.content（審査対象成果物テキスト）。

    Returns:
        LLMProviderPort.chat_with_tools() の system 引数に渡す文字列。
    """
    return (
        f"あなたは {role} の専門家として、以下の成果物をレビューしてください。\n\n"
        f"## 審査対象成果物\n\n"
        f"{deliverable_summary}\n\n"
        f"## 審査指示\n\n"
        f"レビュー完了後、**必ず** `submit_verdict` ツールを呼び出して判定を登録してください。"
        f"テキストのみの返答は無効として再指示されます。\n\n"
        f"## 判定基準\n\n"
        f"`decision` は `APPROVED` または `REJECTED` の 2 値のみ。"
        f"条件付き承認・曖昧な判定は `REJECTED` として登録してください。\n\n"
        f"## フィードバック指示\n\n"
        f"`reason` に審査根拠とフィードバックを 500 文字以内で記述してください。"
    )


__all__ = ["build"]
