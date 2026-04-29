""":class:`Agent` のための Aggregate レベル不変条件ヘルパ。

各ヘルパは **モジュール レベルの純粋関数** であるため、テストから ``import`` して
直接呼べる — Norman / Steve が workflow パッケージの ``dag_validators.py`` で
承認したのと同じテスタビリティ パターン。:mod:`bakufu.domain.agent.agent` の
Aggregate Root はそれらの薄いディスパッチに留まり、ルール変更はヘルパのみに触れ、
オーケストレーション コードは触らない。

ヘルパ（:class:`Agent.model_validator` ではこの順で実行）:

1. :func:`_validate_provider_capacity` — ``1 ≤ len(providers) ≤ 10``
2. :func:`_validate_provider_kind_unique` — ``provider_kind`` の重複なし
3. :func:`_validate_default_provider_count` — ``is_default=True`` がちょうど 1 つ
4. :func:`_validate_skill_capacity` — ``len(skills) ≤ 20``
5. :func:`_validate_skill_id_unique` — ``skill_id`` の重複なし

命名は workflow の先例（コレクション一意性チェックには ``_validate_*_unique``）
に従う（Steve の PR #16 twin-defense 対称性ルール）。
"""

from __future__ import annotations

from bakufu.domain.agent.value_objects import ProviderConfig, SkillRef
from bakufu.domain.exceptions import AgentInvariantViolation
from bakufu.domain.value_objects import ProviderKind, SkillId

# Confirmation C: 容量境界。
MIN_PROVIDERS: int = 1
MAX_PROVIDERS: int = 10
MAX_SKILLS: int = 20


def _validate_provider_capacity(providers: list[ProviderConfig]) -> None:
    """T2-DoS ガード + REQ-AG-001 コントラクト（1 件以上、上限 10 件）。"""
    count = len(providers)
    if count < MIN_PROVIDERS:
        raise AgentInvariantViolation(
            kind="no_provider",
            message="[FAIL] Agent must have at least one provider",
            detail={"providers_count": count, "min_providers": MIN_PROVIDERS},
        )
    if count > MAX_PROVIDERS:
        raise AgentInvariantViolation(
            kind="provider_capacity_exceeded",
            message=(
                f"[FAIL] Agent invariant violation: providers capacity "
                f"{MAX_PROVIDERS} exceeded (got {count})"
            ),
            detail={"providers_count": count, "max_providers": MAX_PROVIDERS},
        )


def _validate_provider_kind_unique(providers: list[ProviderConfig]) -> None:
    """2 つの ProviderConfig が ``provider_kind`` を共有してはならない（MSG-AG-004）。"""
    seen: set[ProviderKind] = set()
    for provider in providers:
        if provider.provider_kind in seen:
            raise AgentInvariantViolation(
                kind="provider_duplicate",
                message=f"[FAIL] Duplicate provider_kind: {provider.provider_kind}",
                detail={"provider_kind": str(provider.provider_kind)},
            )
        seen.add(provider.provider_kind)


def _validate_default_provider_count(providers: list[ProviderConfig]) -> None:
    """``is_default=True`` を持つ provider はちょうど 1 つでなければならない（MSG-AG-003）。"""
    count = sum(1 for provider in providers if provider.is_default)
    if count != 1:
        raise AgentInvariantViolation(
            kind="default_not_unique",
            message=(f"[FAIL] Exactly one provider must have is_default=True (got {count})"),
            detail={"default_count": count},
        )


def _validate_skill_capacity(skills: list[SkillRef]) -> None:
    """skills を 20 で頭打ちにする（REQ-AG-001 / Confirmation C）。"""
    count = len(skills)
    if count > MAX_SKILLS:
        raise AgentInvariantViolation(
            kind="skill_capacity_exceeded",
            message=(
                f"[FAIL] Agent invariant violation: skills capacity "
                f"{MAX_SKILLS} exceeded (got {count})"
            ),
            detail={"skills_count": count, "max_skills": MAX_SKILLS},
        )


def _validate_skill_id_unique(skills: list[SkillRef]) -> None:
    """2 つの SkillRef が ``skill_id`` を共有してはならない（MSG-AG-007）。

    命名は workflow の ``_validate_stage_id_unique`` /
    ``_validate_transition_id_unique`` の対称性をミラーしている — Steve が PR #16
    で要求したルール: 「id 重複なし」を謳うすべてのコレクション コントラクトに専用
    ヘルパを設けることで、Boy Scout ルール（「最初のリークが全てを壊す」）が次の
    Aggregate で不意打ちにならないようにする。
    """
    seen: set[SkillId] = set()
    for skill in skills:
        if skill.skill_id in seen:
            raise AgentInvariantViolation(
                kind="skill_duplicate",
                message=f"[FAIL] Skill already added: skill_id={skill.skill_id}",
                detail={"skill_id": str(skill.skill_id)},
            )
        seen.add(skill.skill_id)


__all__ = [
    "MAX_PROVIDERS",
    "MAX_SKILLS",
    "MIN_PROVIDERS",
    "_validate_default_provider_count",
    "_validate_provider_capacity",
    "_validate_provider_kind_unique",
    "_validate_skill_capacity",
    "_validate_skill_id_unique",
]
