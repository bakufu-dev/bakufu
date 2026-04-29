"""AgentService — Agent Aggregate 操作の application 層サービス（§確定 G）。"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.application.exceptions.agent_exceptions import (
    AgentArchivedError,
    AgentNameAlreadyExistsError,
    AgentNotFoundError,
)
from bakufu.application.exceptions.empire_exceptions import EmpireNotFoundError
from bakufu.application.ports.agent_repository import AgentRepository
from bakufu.application.ports.empire_repository import EmpireRepository
from bakufu.domain.agent import Agent
from bakufu.domain.value_objects import AgentId, EmpireId


class AgentService:
    """Agent Aggregate 操作の application 層サービス（§確定 G）。"""

    def __init__(
        self,
        agent_repo: AgentRepository,
        empire_repo: EmpireRepository,
        session: AsyncSession,
    ) -> None:
        self._agent_repo = agent_repo
        self._empire_repo = empire_repo
        self._session = session

    async def hire(
        self,
        empire_id: EmpireId,
        name: str,
        persona: dict[str, Any],
        role: str,
        providers: list[dict[str, Any]],
        skills: list[dict[str, Any]],
    ) -> Agent:
        """Agent を採用して永続化する（REQ-AG-HTTP-001）。

        Agent 構築（純粋 domain 処理）→ UoW: Empire 存在確認 + 名前重複確認 + 保存
        の順で実行する。BUG-EM-001 パターン準拠: Empire 存在確認を begin() の外で
        実行すると autobegin が起動し、後続の ``async with session.begin():`` が
        ``InvalidRequestError: A transaction is already begun`` で失敗するため、
        全 DB アクセスを単一の ``async with session.begin():`` 内に収める。
        """
        # 1. Agent 構築（純粋なドメイン処理 — DB アクセスなし）
        # AgentInvariantViolation は早期送出（begin() の外で失敗できる）
        agent = self._build_agent(
            empire_id=empire_id,
            name=name,
            persona=persona,
            role=role,
            providers=providers,
            skills=skills,
        )

        # 2. UoW: Empire 存在確認 + 名前重複確認 + 保存
        # BUG-EM-001: Empire check を begin() 内に移動して autobegin 競合を回避
        async with self._session.begin():
            empire = await self._empire_repo.find_by_id(empire_id)
            if empire is None:
                raise EmpireNotFoundError(str(empire_id))
            existing = await self._agent_repo.find_by_name(empire_id, name)
            if existing is not None:
                raise AgentNameAlreadyExistsError(str(empire_id), name)
            await self._agent_repo.save(agent)

        return agent

    async def find_by_empire(self, empire_id: EmpireId) -> list[Agent]:
        """Empire 内の全 Agent を返す（REQ-AG-HTTP-002）。"""
        empire = await self._empire_repo.find_by_id(empire_id)
        if empire is None:
            raise EmpireNotFoundError(str(empire_id))
        return await self._agent_repo.find_all_by_empire(empire_id)

    async def find_by_id(self, agent_id: AgentId) -> Agent:
        """Agent を返す。存在しない場合は AgentNotFoundError（REQ-AG-HTTP-003）。"""
        agent = await self._agent_repo.find_by_id(agent_id)
        if agent is None:
            raise AgentNotFoundError(str(agent_id))
        return agent

    async def update(
        self,
        agent_id: AgentId,
        name: str | None,
        persona: dict[str, Any] | None,
        role: str | None,
        providers: list[dict[str, Any]] | None,
        skills: list[dict[str, Any]] | None,
    ) -> Agent:
        """Agent を部分更新する（REQ-AG-HTTP-004）。

        autobegin 競合を避けるため、read も含めて単一の ``async with session.begin():``
        ブロック内で完結させる（workflow_service.py BUG-EM-001 凍結と同様）。
        """
        async with self._session.begin():
            agent = await self._agent_repo.find_by_id(agent_id)
            if agent is None:
                raise AgentNotFoundError(str(agent_id))
            if agent.archived:
                raise AgentArchivedError(str(agent_id))

            # name 変更時の重複チェック
            if name is not None and name != agent.name:
                existing = await self._agent_repo.find_by_name(agent.empire_id, name)
                if existing is not None:
                    raise AgentNameAlreadyExistsError(str(agent.empire_id), name)

            # 部分更新: 変更フィールドのみ差し替えた dict で model_validate 再構築
            state = agent.model_dump()

            if name is not None:
                state["name"] = name

            if persona is not None:
                # PersonaUpdate: 各フィールドで非 None のもののみ差し替え
                existing_persona: dict[str, Any] = dict(state["persona"])
                if persona.get("display_name") is not None:
                    existing_persona["display_name"] = persona["display_name"]
                if persona.get("archetype") is not None:
                    existing_persona["archetype"] = persona["archetype"]
                if persona.get("prompt_body") is not None:
                    existing_persona["prompt_body"] = persona["prompt_body"]
                state["persona"] = existing_persona

            if role is not None:
                state["role"] = role

            if providers is not None:
                state["providers"] = self._prepare_provider_dicts(providers)

            if skills is not None:
                state["skills"] = self._prepare_skill_dicts(skills)

            updated = Agent.model_validate(state)
            await self._agent_repo.save(updated)

        return updated

    async def archive(self, agent_id: AgentId) -> None:
        """Agent を論理削除する（archived=True）（REQ-AG-HTTP-005）。

        冪等: 2 回目の DELETE も 204 を返す（archive() は冪等）。
        read も含めて単一の ``async with session.begin():`` ブロック内で完結させる。
        """
        async with self._session.begin():
            agent = await self._agent_repo.find_by_id(agent_id)
            if agent is None:
                raise AgentNotFoundError(str(agent_id))
            archived_agent = agent.archive()
            await self._agent_repo.save(archived_agent)

    # ---- private helpers ------------------------------------------------

    def _build_agent(
        self,
        empire_id: EmpireId,
        name: str,
        persona: dict[str, Any],
        role: str,
        providers: list[dict[str, Any]],
        skills: list[dict[str, Any]],
    ) -> Agent:
        """dict 定義から Agent を構築する（AgentInvariantViolation は早期送出）。"""
        return Agent.model_validate(
            {
                "id": uuid4(),
                "empire_id": empire_id,
                "name": name,
                "persona": self._prepare_persona_dict(persona),
                "role": role,
                "providers": self._prepare_provider_dicts(providers),
                "skills": self._prepare_skill_dicts(skills),
            }
        )

    @staticmethod
    def _prepare_persona_dict(persona: dict[str, Any]) -> dict[str, Any]:
        """PersonaCreate.model_dump() 形式を domain Persona 互換形式に変換する。"""
        p = dict(persona)
        if p.get("archetype") is None:
            p["archetype"] = ""
        if p.get("prompt_body") is None:
            p["prompt_body"] = ""
        return p

    @staticmethod
    def _prepare_provider_dicts(providers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """ProviderConfigCreate.model_dump() 形式を domain ProviderConfig 互換形式に変換する。"""
        return [dict(p) for p in providers]

    @staticmethod
    def _prepare_skill_dicts(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """SkillRefCreate.model_dump() 形式を domain SkillRef 互換形式に変換する。"""
        return [dict(s) for s in skills]


__all__ = ["AgentService"]
