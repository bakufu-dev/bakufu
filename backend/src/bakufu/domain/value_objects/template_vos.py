"""DeliverableTemplate 機能のための Value Object。

このモジュールは以下の VO を定義する:

- :class:`SemVer` — セマンティック バージョン（major.minor.patch）
- :class:`DeliverableTemplateRef` — テンプレートへの参照（id + 最低バージョン）
- :class:`AcceptanceCriterion` — 受け入れ基準の 1 項目
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from bakufu.domain.value_objects.identifiers import DeliverableTemplateId


class SemVer(BaseModel):
    """セマンティック バージョン（major.minor.patch）。

    全フィールドは非負整数。frozen かつ extra='forbid' により
    不変 VO としての契約を保証する。
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=False)

    major: int = Field(ge=0)
    minor: int = Field(ge=0)
    patch: int = Field(ge=0)

    def is_compatible_with(self, other: SemVer) -> bool:
        """メジャー バージョンが同一であれば互換とみなす（semver 互換性）。"""
        return self.major == other.major

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @classmethod
    def from_str(cls, s: str) -> SemVer:
        """``'1.2.3'`` 形式の文字列から :class:`SemVer` を生成する。

        Raises:
            ValueError: 文字列が ``'MAJOR.MINOR.PATCH'`` 形式でない場合、
                または各部分が非負整数でない場合。
        """
        parts = s.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid SemVer string: {s!r}. Expected 'MAJOR.MINOR.PATCH' format.")
        try:
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError as exc:
            raise ValueError(
                f"Invalid SemVer string: {s!r}. Each part must be a non-negative integer."
            ) from exc
        return cls(major=major, minor=minor, patch=patch)


class DeliverableTemplateRef(BaseModel):
    """DeliverableTemplate Aggregate への参照（id + 最低バージョン）。

    RoleProfile と DeliverableTemplate の合成で使用する。
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=False)

    template_id: DeliverableTemplateId
    minimum_version: SemVer


class AcceptanceCriterion(BaseModel):
    """DeliverableTemplate に紐づく受け入れ基準の 1 項目。

    ``id`` は UUID、``description`` は 1〜500 文字の非空文字列、
    ``required`` はデフォルト True。
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=False)

    id: UUID
    description: str = Field(min_length=1, max_length=500)
    required: bool = True


__all__ = [
    "AcceptanceCriterion",
    "DeliverableTemplateRef",
    "SemVer",
]
