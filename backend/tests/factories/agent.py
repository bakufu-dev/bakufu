"""Agent アグリゲートとそのエンティティ、VO のファクトリ群.

``docs/features/agent/test-design.md`` 準拠。empire / workflow と同パターン:
各ファクトリは本番コンストラクタ経由で *妥当* なデフォルトインスタンスを返し、
キーワード上書きを許可し、結果を :class:`WeakValueDictionary` に登録する。
これにより :func:`is_synthetic` が後から、frozen Pydantic モデルを変更せずに
テスト由来オブジェクトをフラグ付けできる。

``DEFAULT_SKILL_PATH`` と ``BAKUFU_DATA_DIR`` 環境変数 (``conftest.py`` で設定)
の組み合わせで、デフォルト ``SkillRef`` が H1〜H10 を全てパスするようになる ──
Agent 挙動に注力したテストはセットアップでパスペイロードを伝搬させる必要が無くなる。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from bakufu.domain.agent import (
    Agent,
    Persona,
    ProviderConfig,
    SkillRef,
)
from bakufu.domain.value_objects import ProviderKind, Role
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Sequence

# モジュールスコープのレジストリ。値は弱参照で GC 圧は中立に保つ。
_SYNTHETIC_REGISTRY: WeakValueDictionary[int, BaseModel] = WeakValueDictionary()

# ``BAKUFU_DATA_DIR`` 設定下で H1〜H10 を満たすデフォルト SkillRef.path。
DEFAULT_SKILL_PATH: str = "bakufu-data/skills/sample-skill.md"


def is_synthetic(instance: BaseModel) -> bool:
    """``instance`` が本モジュールのファクトリで生成されたものなら ``True`` を返す。"""
    cached = _SYNTHETIC_REGISTRY.get(id(instance))
    return cached is instance


def _register(instance: BaseModel) -> None:
    """``instance`` を合成レジストリに記録する。"""
    _SYNTHETIC_REGISTRY[id(instance)] = instance


# ---------------------------------------------------------------------------
# Persona
# ---------------------------------------------------------------------------
def make_persona(
    *,
    display_name: str = "テストペルソナ",
    archetype: str = "review-focused",
    prompt_body: str = "You are a thorough reviewer.",
) -> Persona:
    """妥当な :class:`Persona` を構築する。"""
    persona = Persona(
        display_name=display_name,
        archetype=archetype,
        prompt_body=prompt_body,
    )
    _register(persona)
    return persona


# ---------------------------------------------------------------------------
# ProviderConfig
# ---------------------------------------------------------------------------
def make_provider_config(
    *,
    provider_kind: ProviderKind = ProviderKind.CLAUDE_CODE,
    model: str = "sonnet-4.5",
    is_default: bool = True,
) -> ProviderConfig:
    """妥当な :class:`ProviderConfig` を構築する。デフォルトは ``is_default=True``。"""
    config = ProviderConfig(
        provider_kind=provider_kind,
        model=model,
        is_default=is_default,
    )
    _register(config)
    return config


# ---------------------------------------------------------------------------
# SkillRef
# ---------------------------------------------------------------------------
def make_skill_ref(
    *,
    skill_id: UUID | None = None,
    name: str = "sample-skill",
    path: str = DEFAULT_SKILL_PATH,
) -> SkillRef:
    """妥当な :class:`SkillRef` を構築する。``BAKUFU_DATA_DIR`` 環境変数を要する (H10)。"""
    ref = SkillRef(
        skill_id=skill_id if skill_id is not None else uuid4(),
        name=name,
        path=path,
    )
    _register(ref)
    return ref


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
def make_agent(
    *,
    agent_id: UUID | None = None,
    empire_id: UUID | None = None,
    name: str = "テストエージェント",
    persona: Persona | None = None,
    role: Role = Role.DEVELOPER,
    providers: Sequence[ProviderConfig] | None = None,
    skills: Sequence[SkillRef] | None = None,
    archived: bool = False,
) -> Agent:
    """妥当な :class:`Agent` を構築する。

    上書きなしの場合、最小妥当な Agent を返す: 新規 ``empire_id``、
    ``is_default=True`` の ProviderConfig 1 件、skill なし、``archived=False``。
    agent-repository の ``find_by_name`` スコープや Empire レベルの
    membership 不変条件を検証するテストは ``empire_id`` を上書きすること ──
    ファクトリが新規生成するデフォルトがテスト側のセットアップと衝突しないように。
    """
    if persona is None:
        persona = make_persona()
    if providers is None:
        providers = [make_provider_config()]
    if skills is None:
        skills = []
    agent = Agent(
        id=agent_id if agent_id is not None else uuid4(),
        empire_id=empire_id if empire_id is not None else uuid4(),
        name=name,
        persona=persona,
        role=role,
        providers=list(providers),
        skills=list(skills),
        archived=archived,
    )
    _register(agent)
    return agent


def make_archived_agent(**overrides: object) -> Agent:
    """冪等性テスト用に ``archived=True`` の Agent を構築する。"""
    return make_agent(archived=True, **overrides)  # pyright: ignore[reportArgumentType]


__all__ = [
    "DEFAULT_SKILL_PATH",
    "is_synthetic",
    "make_agent",
    "make_archived_agent",
    "make_persona",
    "make_provider_config",
    "make_skill_ref",
]
