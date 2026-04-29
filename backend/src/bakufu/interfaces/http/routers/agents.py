"""Agent HTTP API エンドポイント（§確定 E）。

Router 内に try/except は書かない（http-api-foundation architecture 規律）。
全例外は error_handlers.py の専用ハンドラが処理する。
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from bakufu.interfaces.http.dependencies import AgentServiceDep
from bakufu.interfaces.http.schemas.agent import (
    AgentCreate,
    AgentListResponse,
    AgentResponse,
    AgentUpdate,
)

# Empire スコープのエンドポイント: POST / GET /api/empires/{empire_id}/agents
empire_agents_router = APIRouter(prefix="/api/empires", tags=["agent"])

# Agent スコープのエンドポイント: GET / PATCH / DELETE /api/agents/{agent_id}
agents_router = APIRouter(prefix="/api/agents", tags=["agent"])


@empire_agents_router.post(
    "/{empire_id}/agents",
    response_model=AgentResponse,
    status_code=201,
    summary="Agent 採用（REQ-AG-HTTP-001）",
)
async def hire_agent(
    empire_id: UUID,
    body: AgentCreate,
    service: AgentServiceDep,
) -> AgentResponse:
    """Empire に Agent を採用する。"""
    agent = await service.hire(
        empire_id=empire_id,
        name=body.name,
        persona=body.persona.model_dump(),
        role=body.role,
        providers=[p.model_dump() for p in body.providers],
        skills=[s.model_dump() for s in body.skills],
    )
    return AgentResponse.model_validate(agent)


@empire_agents_router.get(
    "/{empire_id}/agents",
    response_model=AgentListResponse,
    status_code=200,
    summary="Empire の Agent 一覧取得（REQ-AG-HTTP-002）",
)
async def list_agents(
    empire_id: UUID,
    service: AgentServiceDep,
) -> AgentListResponse:
    """Empire 内の全 Agent を返す（0 件も 200）。"""
    agents = await service.find_by_empire(empire_id)
    items = [AgentResponse.model_validate(a) for a in agents]
    return AgentListResponse(items=items, total=len(items))


@agents_router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    status_code=200,
    summary="Agent 単件取得（REQ-AG-HTTP-003）",
)
async def get_agent(
    agent_id: UUID,
    service: AgentServiceDep,
) -> AgentResponse:
    """Agent を 1 件返す。"""
    agent = await service.find_by_id(agent_id)
    return AgentResponse.model_validate(agent)


@agents_router.patch(
    "/{agent_id}",
    response_model=AgentResponse,
    status_code=200,
    summary="Agent 更新（REQ-AG-HTTP-004）",
)
async def update_agent(
    agent_id: UUID,
    body: AgentUpdate,
    service: AgentServiceDep,
) -> AgentResponse:
    """Agent を部分更新する。"""
    persona_dict = body.persona.model_dump() if body.persona is not None else None
    providers_list = (
        [p.model_dump() for p in body.providers] if body.providers is not None else None
    )
    skills_list = [s.model_dump() for s in body.skills] if body.skills is not None else None
    updated = await service.update(
        agent_id=agent_id,
        name=body.name,
        persona=persona_dict,
        role=body.role,
        providers=providers_list,
        skills=skills_list,
    )
    return AgentResponse.model_validate(updated)


@agents_router.delete(
    "/{agent_id}",
    status_code=204,
    summary="Agent 引退（REQ-AG-HTTP-005）",
)
async def archive_agent(
    agent_id: UUID,
    service: AgentServiceDep,
) -> None:
    """Agent を論理削除する（archived=True）。冪等: 2 回目の DELETE も 204。"""
    await service.archive(agent_id)


__all__ = ["agents_router", "empire_agents_router"]
