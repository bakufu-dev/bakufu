"""``deliverable_templates`` テーブル — DeliverableTemplate Aggregate ルート行。

DeliverableTemplate は acceptance_criteria / composition を JSON カラムに集約する
（子テーブルなし、YAGNI — MVP は Aggregate 単位の永続化のみを要件とする）。

カラム別 masking ハンドリング（feature-spec §13 業務判断「機密レベル低」）:

* `acceptance_criteria_json` は :class:`JSONEncoded` カラム。AcceptanceCriterion は
  description（自然言語テキスト）/ id（UUID）/ required（bool）のみを保持し、
  Schneier §6 秘密情報 6 カテゴリに該当しない。
* `composition_json` は :class:`JSONEncoded` カラム。DeliverableTemplateRef は
  template_id（UUID）と minimum_version（SemVer）のみを保持し、同上非該当。
* `schema` は :class:`Text` カラム。JSON_SCHEMA / OPENAPI 型は json.dumps 済み dict
  を格納するが、バリデーション定義でありシークレット値を含まない。
* 残りのカラムは UUIDStr / String を保持し、masking カテゴリには該当しない。

CI 三層防衛（REQ-DTR-006）: Layer 1 grep guard + Layer 2 arch test が本テーブルに
``Masked*`` TypeDecorator が存在しないことを物理保証する。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, JSONEncoded, UUIDStr


class DeliverableTemplateRow(Base):
    """``deliverable_templates`` テーブルの ORM マッピング。"""

    __tablename__ = "deliverable_templates"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # TemplateType enum 値: "MARKDOWN" / "JSON_SCHEMA" / "OPENAPI" /
    # "CODE_SKELETON" / "PROMPT"（§確定 D の type 判別キー）。
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    # SemVer TEXT 形式 "major.minor.patch"（例: "1.2.3"）— §確定 E。
    # String(20) は "999.999.999" まで収容可能。
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    # §確定 D: JSON_SCHEMA / OPENAPI 型は json.dumps(dict) を格納、
    # それ以外は plain text をそのまま格納。復元時は type カラムを判別キーに使用。
    schema: Mapped[str] = mapped_column(Text, nullable=False)
    # §確定 F: list[AcceptanceCriterion] の JSON シリアライズ。
    # DEFAULT '[]' は 0012_deliverable_template_aggregate.py の server_default で強制。
    acceptance_criteria_json: Mapped[Any] = mapped_column(JSONEncoded, nullable=False)
    # §確定 F: list[DeliverableTemplateRef] の JSON シリアライズ。
    # DEFAULT '[]' は同 migration の server_default で強制。
    composition_json: Mapped[Any] = mapped_column(JSONEncoded, nullable=False)


__all__ = ["DeliverableTemplateRow"]
