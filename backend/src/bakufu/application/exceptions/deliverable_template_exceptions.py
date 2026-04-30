"""DeliverableTemplate / RoleProfile アプリケーション層の例外。

これらは、ドメイン層の不変条件違反とは独立したアプリケーション層
レベルの例外である。interfaces 層の例外ハンドラがこれらを捕捉し、HTTP レスポンス
へ変換する。

* :class:`DeliverableTemplateNotFoundError` — DeliverableTemplate が存在しない
* :class:`RoleProfileNotFoundError` — RoleProfile が存在しない（404）
* :class:`CompositionCycleError` — DAG 走査で循環または上限超過を検出（422）
* :class:`DeliverableTemplateVersionDowngradeError` — PUT で version 降格を検出（422）
"""

from __future__ import annotations

from typing import Literal


class DeliverableTemplateNotFoundError(Exception):
    """要求された DeliverableTemplate が存在しないときに送出される。

    ``kind`` 属性により HTTP ステータスが決定される:

    * ``"primary"``: 直接 ``find_by_id`` で不在 → HTTP 404 / ``not_found``
      （MSG-DT-HTTP-001）
    * ``"composition_ref"``: composition ref 確認時に不在 → HTTP 422 /
      ``ref_not_found``（MSG-DT-HTTP-002）
    * ``"role_profile_ref"``: RoleProfile ref 確認時に不在 → HTTP 422 /
      ``ref_not_found``（MSG-RP-HTTP-002）

    Attributes:
        message: 人間可読なエラー文字列。
        template_id: 対象 DeliverableTemplate の UUID 文字列（省略可能）。
        kind: ``"primary"`` / ``"composition_ref"`` / ``"role_profile_ref"``
            のいずれか。error_handlers.py が参照して HTTP ステータスを決定する。
    """

    def __init__(
        self,
        template_id: str | None = None,
        *,
        kind: Literal["primary", "composition_ref", "role_profile_ref"] = "primary",
    ) -> None:
        super().__init__(f"DeliverableTemplate not found: {template_id}")
        self.message: str = f"DeliverableTemplate not found: {template_id}"
        self.template_id: str | None = template_id
        self.kind: Literal["primary", "composition_ref", "role_profile_ref"] = kind


class RoleProfileNotFoundError(Exception):
    """要求された RoleProfile が存在しないときに送出される。

    ``RoleProfileService.find_by_empire_and_role`` がリポジトリから ``None`` を
    受け取った場合に送出される。interfaces 層では HTTP 404 / ``not_found``
    （MSG-RP-HTTP-001）に変換される。

    Attributes:
        empire_id: 対象 Empire の UUID 文字列。
        role: 対象 Role 文字列（例: ``"LEADER"``）。
    """

    def __init__(self, empire_id: str, role: str) -> None:
        super().__init__(f"RoleProfile not found: empire={empire_id}, role={role}")
        self.empire_id: str = empire_id
        self.role: str = role


class CompositionCycleError(Exception):
    """DAG 走査（``_check_dag``）で循環参照または上限超過を検出したときに送出される。

    ``reason`` 属性により具体的な原因を識別できる:

    * ``"transitive_cycle"``: 推移的循環参照を検出（MSG-DT-HTTP-003a）
    * ``"depth_limit"``: 参照深度が上限（10）を超過（MSG-DT-HTTP-003b）
    * ``"node_limit"``: 参照ノード数が上限（100）を超過（MSG-DT-HTTP-003c）

    Attributes:
        reason: 原因の識別子。
        cycle_path: ``reason="transitive_cycle"`` のときの UUID 文字列の列。
            ``reason="depth_limit"`` / ``"node_limit"`` のときは空リスト ``[]``。
    """

    def __init__(
        self,
        reason: Literal["transitive_cycle", "depth_limit", "node_limit"],
        *,
        cycle_path: list[str] | None = None,
    ) -> None:
        super().__init__(f"Composition cycle detected: {reason}")
        self.reason: Literal["transitive_cycle", "depth_limit", "node_limit"] = reason
        self.cycle_path: list[str] = cycle_path if cycle_path is not None else []


class DeliverableTemplateVersionDowngradeError(Exception):
    """PUT で提供された version が現在の version より小さいときに送出される。

    interfaces 層では HTTP 422 / ``version_downgrade``（MSG-DT-HTTP-004）に変換される。

    Attributes:
        current_version: 現在保存されている SemVer 文字列（例: ``"1.2.3"``）。
        provided_version: PUT リクエストで提供された SemVer 文字列。
    """

    def __init__(self, current_version: str, provided_version: str) -> None:
        super().__init__(
            f"Version downgrade detected: provided={provided_version} < current={current_version}"
        )
        self.current_version: str = current_version
        self.provided_version: str = provided_version


__all__ = [
    "CompositionCycleError",
    "DeliverableTemplateNotFoundError",
    "DeliverableTemplateVersionDowngradeError",
    "RoleProfileNotFoundError",
]
