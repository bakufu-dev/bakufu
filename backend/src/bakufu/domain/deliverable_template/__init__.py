"""DeliverableTemplate ドメイン機能の公開 API。

このパッケージは以下の集約ルートと VO を re-export する:

- :class:`DeliverableTemplate` — 成果物テンプレート集約ルート
- :class:`RoleProfile` — ロール別テンプレート参照コレクション集約ルート
- :class:`DeliverableTemplateInvariantViolation` — DeliverableTemplate 不変条件例外
- :class:`RoleProfileInvariantViolation` — RoleProfile 不変条件例外
- :class:`TemplateType` — テンプレート種別 enum
- :class:`SemVer` — セマンティック バージョン VO
- :class:`DeliverableTemplateRef` — テンプレート参照 VO
- :class:`AcceptanceCriterion` — 受け入れ基準 VO
"""

from __future__ import annotations

from bakufu.domain.deliverable_template.deliverable_template import DeliverableTemplate
from bakufu.domain.deliverable_template.role_profile import RoleProfile
from bakufu.domain.exceptions import (
    DeliverableTemplateInvariantViolation,
    RoleProfileInvariantViolation,
)
from bakufu.domain.value_objects.enums import TemplateType
from bakufu.domain.value_objects.template_vos import (
    AcceptanceCriterion,
    DeliverableTemplateRef,
    SemVer,
)

__all__ = [
    "AcceptanceCriterion",
    "DeliverableTemplate",
    "DeliverableTemplateInvariantViolation",
    "DeliverableTemplateRef",
    "RoleProfile",
    "RoleProfileInvariantViolation",
    "SemVer",
    "TemplateType",
]
