"""room / http-api 結合テスト (TC-IT-RM-HTTP-001~020).

Per ``docs/features/room/http-api/test-design.md`` §結合テストケース.

Covers:
  TC-IT-RM-HTTP-001  POST /api/empires/{empire_id}/rooms → 201 RoomResponse
  TC-IT-RM-HTTP-002  POST 重複 name → 409 conflict (MSG-RM-HTTP-001)
  TC-IT-RM-HTTP-003  POST Empire 不在 → 404 not_found
  TC-IT-RM-HTTP-004  GET /api/empires/{empire_id}/rooms → 200 (空 / 2件)
  TC-IT-RM-HTTP-005  GET /api/rooms/{room_id} → 200 RoomResponse
  TC-IT-RM-HTTP-006  GET Room 不在 → 404 not_found (MSG-RM-HTTP-002)
  TC-IT-RM-HTTP-007  PATCH /api/rooms/{room_id} → 200 更新済み
  TC-IT-RM-HTTP-008  PATCH アーカイブ済み → 409 conflict (MSG-RM-HTTP-003)
  TC-IT-RM-HTTP-009  DELETE /api/rooms/{room_id} → 204 + archived=true
  TC-IT-RM-HTTP-010  POST /api/rooms/{room_id}/agents → 201 (assign_agent)
  TC-IT-RM-HTTP-011  POST assign_agent アーカイブ済み → 409 conflict
  TC-IT-RM-HTTP-012  DELETE .../agents/{agent_id}/roles/{role} → 204 (unassign_agent)
  TC-IT-RM-HTTP-013  不正 UUID パスパラメータ → 422 (R1-10, BUG-EM-SEC-001 準拠)
  TC-IT-RM-HTTP-014  POST Workflow 不在 → 404 not_found (MSG-RM-HTTP-006)
  TC-IT-RM-HTTP-015  POST assign_agent Agent 不在 → 404 not_found (MSG-RM-HTTP-004)
  TC-IT-RM-HTTP-016  DELETE unassign_agent membership 不在 → 404 (MSG-RM-HTTP-005)
  TC-IT-RM-HTTP-017  GET list Empire 不在 → 404 not_found
  TC-IT-RM-HTTP-018  PATCH Room 不在 → 404 not_found
  TC-IT-RM-HTTP-019  DELETE Room 不在 → 404 not_found
  TC-IT-RM-HTTP-020  DELETE unassign_agent アーカイブ済み → 409 conflict

Issue: #57
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixture: RoomTestCtx — AsyncClient + session_factory for direct DB seeding
# ---------------------------------------------------------------------------


@dataclass
class RoomTestCtx:
    """Room 結合テスト用コンテキスト.

    ``client``: HTTP リクエスト送信 (FastAPI ASGI)
    ``session_factory``: Workflow / Agent の直接 DB シード用セッションファクトリ
    """

    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]


@pytest_asyncio.fixture
async def room_ctx(tmp_path: Path) -> AsyncIterator[RoomTestCtx]:
    """Room テスト用 AsyncClient + session_factory.

    ``empire_app_client`` と同一パターン + session_factory を追加公開。
    Workflow / Agent は HTTP API が本 PR のスコープ外のため、direct DB seeding
    (assumed mock 禁止原則準拠 — characterization fixture 確認済み) を使う。
    """
    from bakufu.interfaces.http.app import create_app

    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory

    app = create_app()
    engine = make_test_engine(tmp_path / "room_test.db")
    await create_all_tables(engine)
    session_factory = make_test_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield RoomTestCtx(client=client, session_factory=session_factory)

    await engine.dispose()


# ---------------------------------------------------------------------------
# Seeding / helper functions
# ---------------------------------------------------------------------------


async def _create_empire(client: AsyncClient, name: str = "テスト幕府") -> dict[str, object]:
    """POST /api/empires → assert 201 → return parsed JSON."""
    resp = await client.post("/api/empires", json={"name": name})
    assert resp.status_code == 201, f"Empire creation failed: {resp.text}"
    return resp.json()  # type: ignore[return-value]


async def _seed_workflow(
    session_factory: async_sessionmaker[AsyncSession],
    workflow_id: UUID | None = None,
) -> object:
    """Workflow を tempdb に直接 INSERT して返す (assumed mock 禁止)."""
    from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
        SqliteWorkflowRepository,
    )

    from tests.factories.workflow import make_workflow

    wf = make_workflow(workflow_id=workflow_id)
    async with session_factory() as session:
        async with session.begin():
            repo = SqliteWorkflowRepository(session)
            await repo.save(wf)
    return wf


async def _seed_agent(
    session_factory: async_sessionmaker[AsyncSession],
    empire_id: UUID,
    agent_id: UUID | None = None,
) -> object:
    """Agent を tempdb に直接 INSERT して返す (assumed mock 禁止)."""
    from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
        SqliteAgentRepository,
    )

    from tests.factories.agent import make_agent

    agent = make_agent(empire_id=empire_id, agent_id=agent_id)
    async with session_factory() as session:
        async with session.begin():
            repo = SqliteAgentRepository(session)
            await repo.save(agent)
    return agent


async def _create_room(
    client: AsyncClient,
    empire_id: str,
    workflow_id: str,
    name: str = "Vモデル開発室",
    description: str = "",
    prompt_kit_prefix_markdown: str = "",
) -> dict[str, object]:
    """POST /api/empires/{empire_id}/rooms → assert 201 → return parsed JSON."""
    resp = await client.post(
        f"/api/empires/{empire_id}/rooms",
        json={
            "name": name,
            "workflow_id": workflow_id,
            "description": description,
            "prompt_kit_prefix_markdown": prompt_kit_prefix_markdown,
        },
    )
    assert resp.status_code == 201, f"Room creation failed: {resp.text}"
    return resp.json()  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-001: POST /api/empires/{empire_id}/rooms → 201 RoomResponse
# ---------------------------------------------------------------------------


class TestCreateRoom:
    """TC-IT-RM-HTTP-001: POST /api/empires/{empire_id}/rooms → 201 (REQ-RM-HTTP-001)."""

    async def test_create_returns_201(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.status_code == 201

    async def test_create_response_id_is_str(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert isinstance(resp.json()["id"], str)

    async def test_create_response_name_matches(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["name"] == "Vモデル開発室"

    async def test_create_response_workflow_id_matches(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        wf_id_str = str(wf.id)  # type: ignore[attr-defined]
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": wf_id_str,
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["workflow_id"] == wf_id_str

    async def test_create_response_members_is_empty(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["members"] == []

    async def test_create_response_archived_is_false(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["archived"] is False

    async def test_create_response_prompt_kit_prefix_markdown_empty(
        self, room_ctx: RoomTestCtx
    ) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["prompt_kit_prefix_markdown"] == ""

    async def test_csrf_evil_origin_returns_403(self, room_ctx: RoomTestCtx) -> None:
        """T1 CSRF: POST with evil Origin → 403 (room router に CSRF ミドルウェアが適用される)."""
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "CSRF室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
            headers={"Origin": "http://evil.example.com"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-002: POST 重複 name → 409 (MSG-RM-HTTP-001)
# ---------------------------------------------------------------------------


class TestCreateRoomNameConflict:
    """TC-IT-RM-HTTP-002: POST 同名 Room → 409 conflict (REQ-RM-HTTP-001 / MSG-RM-HTTP-001)."""

    async def test_duplicate_name_returns_409(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.status_code == 409

    async def test_duplicate_name_error_code_is_conflict(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["error"]["code"] == "conflict"

    async def test_duplicate_name_error_message(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "Vモデル開発室",
                "workflow_id": str(wf.id),  # type: ignore[attr-defined]
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["error"]["message"] == "Room name already exists in this empire."


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-003: POST Empire 不在 → 404 (empire_not_found_handler 既存)
# ---------------------------------------------------------------------------


class TestCreateRoomEmpireNotFound:
    """TC-IT-RM-HTTP-003: POST に存在しない empire_id → 404 (EmpireNotFoundError)."""

    async def test_empire_not_found_returns_404(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.post(
            f"/api/empires/{uuid4()}/rooms",
            json={
                "name": "X",
                "workflow_id": str(uuid4()),
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.status_code == 404

    async def test_empire_not_found_error_code(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.post(
            f"/api/empires/{uuid4()}/rooms",
            json={
                "name": "X",
                "workflow_id": str(uuid4()),
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["error"]["code"] == "not_found"

    async def test_empire_not_found_error_message(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.post(
            f"/api/empires/{uuid4()}/rooms",
            json={
                "name": "X",
                "workflow_id": str(uuid4()),
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["error"]["message"] == "Empire not found."


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-004: GET /api/empires/{empire_id}/rooms → 200
# ---------------------------------------------------------------------------


class TestListRooms:
    """TC-IT-RM-HTTP-004: GET list → 200 (空 / 2件) (REQ-RM-HTTP-002)."""

    async def test_empty_list_returns_200(self, room_ctx: RoomTestCtx) -> None:
        """(a) Empire 存在 / Room 0件 → 200, items=[], total=0."""
        empire = await _create_empire(room_ctx.client)
        resp = await room_ctx.client.get(f"/api/empires/{empire['id']}/rooms")
        assert resp.status_code == 200

    async def test_empty_list_items_is_empty(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        resp = await room_ctx.client.get(f"/api/empires/{empire['id']}/rooms")
        assert resp.json()["items"] == []

    async def test_empty_list_total_is_zero(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        resp = await room_ctx.client.get(f"/api/empires/{empire['id']}/rooms")
        assert resp.json()["total"] == 0

    async def test_two_rooms_returns_200(self, room_ctx: RoomTestCtx) -> None:
        """(b) Empire 存在 / Room 2件 → 200, items=[2 rooms], total=2."""
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        await _create_room(room_ctx.client, str(empire["id"]), str(wf.id), name="部屋A")  # type: ignore[attr-defined]
        await _create_room(room_ctx.client, str(empire["id"]), str(wf.id), name="部屋B")  # type: ignore[attr-defined]
        resp = await room_ctx.client.get(f"/api/empires/{empire['id']}/rooms")
        assert resp.status_code == 200

    async def test_two_rooms_total_is_two(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        await _create_room(room_ctx.client, str(empire["id"]), str(wf.id), name="部屋A")  # type: ignore[attr-defined]
        await _create_room(room_ctx.client, str(empire["id"]), str(wf.id), name="部屋B")  # type: ignore[attr-defined]
        resp = await room_ctx.client.get(f"/api/empires/{empire['id']}/rooms")
        assert resp.json()["total"] == 2

    async def test_two_rooms_items_contains_names(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        await _create_room(room_ctx.client, str(empire["id"]), str(wf.id), name="部屋A")  # type: ignore[attr-defined]
        await _create_room(room_ctx.client, str(empire["id"]), str(wf.id), name="部屋B")  # type: ignore[attr-defined]
        resp = await room_ctx.client.get(f"/api/empires/{empire['id']}/rooms")
        names = {item["name"] for item in resp.json()["items"]}
        assert names == {"部屋A", "部屋B"}


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-005: GET /api/rooms/{room_id} → 200 RoomResponse
# ---------------------------------------------------------------------------


class TestGetRoom:
    """TC-IT-RM-HTTP-005: GET /api/rooms/{room_id} → 200 (REQ-RM-HTTP-003)."""

    async def test_get_room_returns_200(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.get(f"/api/rooms/{room['id']}")
        assert resp.status_code == 200

    async def test_get_room_name_matches(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.get(f"/api/rooms/{room['id']}")
        assert resp.json()["name"] == "Vモデル開発室"

    async def test_get_room_archived_is_false(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.get(f"/api/rooms/{room['id']}")
        assert resp.json()["archived"] is False


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-006: GET Room 不在 → 404 (MSG-RM-HTTP-002)
# ---------------------------------------------------------------------------


class TestGetRoomNotFound:
    """TC-IT-RM-HTTP-006: GET /api/rooms/{random_uuid} → 404 (RoomNotFoundError)."""

    async def test_room_not_found_returns_404(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.get(f"/api/rooms/{uuid4()}")
        assert resp.status_code == 404

    async def test_room_not_found_error_code(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.get(f"/api/rooms/{uuid4()}")
        assert resp.json()["error"]["code"] == "not_found"

    async def test_room_not_found_error_message(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.get(f"/api/rooms/{uuid4()}")
        assert resp.json()["error"]["message"] == "Room not found."


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-007: PATCH /api/rooms/{room_id} → 200 (REQ-RM-HTTP-004)
# ---------------------------------------------------------------------------


class TestUpdateRoom:
    """TC-IT-RM-HTTP-007: PATCH /api/rooms/{room_id} → 200 更新済み (REQ-RM-HTTP-004)."""

    async def test_patch_returns_200(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.patch(
            f"/api/rooms/{room['id']}", json={"name": "新Vモデル開発室"}
        )
        assert resp.status_code == 200

    async def test_patch_name_updated(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.patch(
            f"/api/rooms/{room['id']}", json={"name": "新Vモデル開発室"}
        )
        assert resp.json()["name"] == "新Vモデル開発室"

    async def test_patch_id_unchanged(self, room_ctx: RoomTestCtx) -> None:
        """PATCH 後も room_id は変わらない."""
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.patch(
            f"/api/rooms/{room['id']}", json={"name": "新Vモデル開発室"}
        )
        assert resp.json()["id"] == room["id"]


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-008: PATCH archived → 409 (MSG-RM-HTTP-003)
# ---------------------------------------------------------------------------


class TestUpdateArchivedRoom:
    """TC-IT-RM-HTTP-008: PATCH archived Room → 409 conflict (RoomArchivedError)."""

    async def test_patch_archived_returns_409(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        # archive the room
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.patch(
            f"/api/rooms/{room['id']}", json={"name": "変更試み"}
        )
        assert resp.status_code == 409

    async def test_patch_archived_error_code(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.patch(
            f"/api/rooms/{room['id']}", json={"name": "変更試み"}
        )
        assert resp.json()["error"]["code"] == "conflict"

    async def test_patch_archived_error_message(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.patch(
            f"/api/rooms/{room['id']}", json={"name": "変更試み"}
        )
        assert resp.json()["error"]["message"] == "Room is archived and cannot be modified."


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-009: DELETE /api/rooms/{room_id} → 204 + archived=true
# ---------------------------------------------------------------------------


class TestArchiveRoom:
    """TC-IT-RM-HTTP-009: DELETE → 204 論理削除; GET → archived=true (REQ-RM-HTTP-005)."""

    async def test_archive_returns_204(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        assert resp.status_code == 204

    async def test_archive_response_has_no_body(self, room_ctx: RoomTestCtx) -> None:
        """204 No Content は body を持たない (物理保証)."""
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        assert resp.content == b""

    async def test_after_archive_get_shows_archived_true(self, room_ctx: RoomTestCtx) -> None:
        """論理削除後 GET → archived=true (物理保証)."""
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.get(f"/api/rooms/{room['id']}")
        assert resp.json()["archived"] is True


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-010: POST /api/rooms/{room_id}/agents → 201 (assign_agent)
# ---------------------------------------------------------------------------


class TestAssignAgent:
    """TC-IT-RM-HTTP-010: POST /rooms/{room_id}/agents → 201 (REQ-RM-HTTP-006)."""

    async def test_assign_returns_201(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        empire_id = UUID(str(empire["id"]))
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        agent = await _seed_agent(room_ctx.session_factory, empire_id)
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(agent.id), "role": "LEADER"},  # type: ignore[attr-defined]
        )
        assert resp.status_code == 201

    async def test_assign_response_contains_member(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        empire_id = UUID(str(empire["id"]))
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        agent = await _seed_agent(room_ctx.session_factory, empire_id)
        agent_id_str = str(agent.id)  # type: ignore[attr-defined]
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": agent_id_str, "role": "LEADER"},
        )
        members = resp.json()["members"]
        assert len(members) == 1
        assert members[0]["agent_id"] == agent_id_str

    async def test_assign_response_role_matches(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        empire_id = UUID(str(empire["id"]))
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        agent = await _seed_agent(room_ctx.session_factory, empire_id)
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(agent.id), "role": "LEADER"},  # type: ignore[attr-defined]
        )
        assert resp.json()["members"][0]["role"] == "LEADER"

    async def test_assign_response_joined_at_is_iso8601(self, room_ctx: RoomTestCtx) -> None:
        """joined_at は ISO 8601 str (MemberResponse._coerce_joined_at 検証)."""
        empire = await _create_empire(room_ctx.client)
        empire_id = UUID(str(empire["id"]))
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        agent = await _seed_agent(room_ctx.session_factory, empire_id)
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(agent.id), "role": "LEADER"},  # type: ignore[attr-defined]
        )
        joined_at = resp.json()["members"][0]["joined_at"]
        # ISO 8601 contains "T" separator
        assert "T" in joined_at


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-011: POST assign_agent archived → 409 (RoomArchivedError)
# ---------------------------------------------------------------------------


class TestAssignAgentArchivedRoom:
    """TC-IT-RM-HTTP-011: POST agents on archived Room → 409 (REQ-RM-HTTP-006)."""

    async def test_assign_archived_returns_409(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(uuid4()), "role": "LEADER"},
        )
        assert resp.status_code == 409

    async def test_assign_archived_error_code(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(uuid4()), "role": "LEADER"},
        )
        assert resp.json()["error"]["code"] == "conflict"

    async def test_assign_archived_error_message(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(uuid4()), "role": "LEADER"},
        )
        assert resp.json()["error"]["message"] == "Room is archived and cannot be modified."


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-012: DELETE .../agents/{agent_id}/roles/{role} → 204
# ---------------------------------------------------------------------------


class TestUnassignAgent:
    """TC-IT-RM-HTTP-012: DELETE unassign_agent → 204; GET members empty (REQ-RM-HTTP-007)."""

    async def test_unassign_returns_204(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        empire_id = UUID(str(empire["id"]))
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        agent = await _seed_agent(room_ctx.session_factory, empire_id)
        agent_id_str = str(agent.id)  # type: ignore[attr-defined]
        await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": agent_id_str, "role": "LEADER"},
        )
        resp = await room_ctx.client.delete(
            f"/api/rooms/{room['id']}/agents/{agent_id_str}/roles/LEADER"
        )
        assert resp.status_code == 204

    async def test_unassign_response_has_no_body(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        empire_id = UUID(str(empire["id"]))
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        agent = await _seed_agent(room_ctx.session_factory, empire_id)
        agent_id_str = str(agent.id)  # type: ignore[attr-defined]
        await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": agent_id_str, "role": "LEADER"},
        )
        resp = await room_ctx.client.delete(
            f"/api/rooms/{room['id']}/agents/{agent_id_str}/roles/LEADER"
        )
        assert resp.content == b""

    async def test_after_unassign_get_shows_empty_members(self, room_ctx: RoomTestCtx) -> None:
        """unassign 後 GET → members=[] (membership 削除確認)."""
        empire = await _create_empire(room_ctx.client)
        empire_id = UUID(str(empire["id"]))
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        agent = await _seed_agent(room_ctx.session_factory, empire_id)
        agent_id_str = str(agent.id)  # type: ignore[attr-defined]
        await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": agent_id_str, "role": "LEADER"},
        )
        await room_ctx.client.delete(
            f"/api/rooms/{room['id']}/agents/{agent_id_str}/roles/LEADER"
        )
        get_resp = await room_ctx.client.get(f"/api/rooms/{room['id']}")
        assert get_resp.json()["members"] == []


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-013: 不正 UUID パスパラメータ → 422 (R1-10 / BUG-EM-SEC-001)
# ---------------------------------------------------------------------------


class TestInvalidUuidPath:
    """TC-IT-RM-HTTP-013: 不正 UUID → 422 (FastAPI UUID path validation / R1-10)."""

    async def test_get_room_invalid_uuid_returns_422(self, room_ctx: RoomTestCtx) -> None:
        """(a) GET /api/rooms/not-a-uuid → 422 (500 でないことを確認)."""
        resp = await room_ctx.client.get("/api/rooms/not-a-uuid")
        assert resp.status_code == 422

    async def test_patch_room_invalid_uuid_returns_422(self, room_ctx: RoomTestCtx) -> None:
        """(b) PATCH /api/rooms/not-a-uuid → 422."""
        resp = await room_ctx.client.patch("/api/rooms/not-a-uuid", json={"name": "x"})
        assert resp.status_code == 422

    async def test_delete_room_invalid_uuid_returns_422(self, room_ctx: RoomTestCtx) -> None:
        """(c) DELETE /api/rooms/not-a-uuid → 422."""
        resp = await room_ctx.client.delete("/api/rooms/not-a-uuid")
        assert resp.status_code == 422

    async def test_get_list_invalid_empire_uuid_returns_422(self, room_ctx: RoomTestCtx) -> None:
        """(d) GET /api/empires/not-a-uuid/rooms → 422."""
        resp = await room_ctx.client.get("/api/empires/not-a-uuid/rooms")
        assert resp.status_code == 422

    async def test_post_room_invalid_empire_uuid_returns_422(self, room_ctx: RoomTestCtx) -> None:
        """(e) POST /api/empires/not-a-uuid/rooms → 422."""
        resp = await room_ctx.client.post(
            "/api/empires/not-a-uuid/rooms",
            json={
                "name": "X",
                "workflow_id": str(uuid4()),
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.status_code == 422

    async def test_delete_agent_invalid_agent_uuid_returns_422(
        self, room_ctx: RoomTestCtx
    ) -> None:
        """(f) DELETE .../agents/not-a-uuid/roles/LEADER → 422 (agent_id が invalid UUID)."""
        # room_id は有効 UUID 形式で存在不問 (FastAPI は UUID format を path で検証)
        resp = await room_ctx.client.delete(
            f"/api/rooms/{uuid4()}/agents/not-a-uuid/roles/LEADER"
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-014: POST Workflow 不在 → 404 (MSG-RM-HTTP-006)
# ---------------------------------------------------------------------------


class TestCreateRoomWorkflowNotFound:
    """TC-IT-RM-HTTP-014: POST Workflow 不在 → 404 (WorkflowNotFoundError)."""

    async def test_workflow_not_found_returns_404(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "X",
                "workflow_id": str(uuid4()),
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.status_code == 404

    async def test_workflow_not_found_error_code(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "X",
                "workflow_id": str(uuid4()),
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["error"]["code"] == "not_found"

    async def test_workflow_not_found_error_message(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        resp = await room_ctx.client.post(
            f"/api/empires/{empire['id']}/rooms",
            json={
                "name": "X",
                "workflow_id": str(uuid4()),
                "description": "",
                "prompt_kit_prefix_markdown": "",
            },
        )
        assert resp.json()["error"]["message"] == "Workflow not found."


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-015: POST assign_agent Agent 不在 → 404 (MSG-RM-HTTP-004)
# ---------------------------------------------------------------------------


class TestAssignAgentNotFound:
    """TC-IT-RM-HTTP-015: POST agents Agent 不在 → 404 (AgentNotFoundError)."""

    async def test_agent_not_found_returns_404(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(uuid4()), "role": "REVIEWER"},
        )
        assert resp.status_code == 404

    async def test_agent_not_found_error_code(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(uuid4()), "role": "REVIEWER"},
        )
        assert resp.json()["error"]["code"] == "not_found"

    async def test_agent_not_found_error_message(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.post(
            f"/api/rooms/{room['id']}/agents",
            json={"agent_id": str(uuid4()), "role": "REVIEWER"},
        )
        assert resp.json()["error"]["message"] == "Agent not found."


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-016: DELETE unassign_agent membership 不在 → 404 (MSG-RM-HTTP-005)
# ---------------------------------------------------------------------------


class TestUnassignAgentMembershipNotFound:
    """TC-IT-RM-HTTP-016: unassign 未割り当て membership → 404 (RoomInvariantViolation kind=member_not_found)."""

    async def test_membership_not_found_returns_404(self, room_ctx: RoomTestCtx) -> None:
        """有効 role、未割り当て agent_id → 404."""
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.delete(
            f"/api/rooms/{room['id']}/agents/{uuid4()}/roles/LEADER"
        )
        assert resp.status_code == 404

    async def test_membership_not_found_error_code(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.delete(
            f"/api/rooms/{room['id']}/agents/{uuid4()}/roles/LEADER"
        )
        assert resp.json()["error"]["code"] == "not_found"

    async def test_membership_not_found_error_message(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.delete(
            f"/api/rooms/{room['id']}/agents/{uuid4()}/roles/LEADER"
        )
        assert resp.json()["error"]["message"] == "Agent membership not found in this room."

    async def test_invalid_role_string_returns_404(self, room_ctx: RoomTestCtx) -> None:
        """無効 role 文字列 (not_a_role) → service が ValueError→RoomInvariantViolation(kind=member_not_found) に変換 → 404.

        Jensen 確認要件: unassign_agent 無効 role → 404.
        """
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        resp = await room_ctx.client.delete(
            f"/api/rooms/{room['id']}/agents/{uuid4()}/roles/not_a_role"
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-017: GET list Empire 不在 → 404
# ---------------------------------------------------------------------------


class TestListRoomsEmpireNotFound:
    """TC-IT-RM-HTTP-017: GET list Empire 不在 → 404 (EmpireNotFoundError)."""

    async def test_empire_not_found_returns_404(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.get(f"/api/empires/{uuid4()}/rooms")
        assert resp.status_code == 404

    async def test_empire_not_found_error_code(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.get(f"/api/empires/{uuid4()}/rooms")
        assert resp.json()["error"]["code"] == "not_found"

    async def test_empire_not_found_error_message(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.get(f"/api/empires/{uuid4()}/rooms")
        assert resp.json()["error"]["message"] == "Empire not found."


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-018: PATCH Room 不在 → 404
# ---------------------------------------------------------------------------


class TestUpdateRoomNotFound:
    """TC-IT-RM-HTTP-018: PATCH Room 不在 → 404 (RoomNotFoundError)."""

    async def test_room_not_found_returns_404(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.patch(
            f"/api/rooms/{uuid4()}", json={"name": "変更試み"}
        )
        assert resp.status_code == 404

    async def test_room_not_found_error_code(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.patch(
            f"/api/rooms/{uuid4()}", json={"name": "変更試み"}
        )
        assert resp.json()["error"]["code"] == "not_found"

    async def test_room_not_found_error_message(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.patch(
            f"/api/rooms/{uuid4()}", json={"name": "変更試み"}
        )
        assert resp.json()["error"]["message"] == "Room not found."


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-019: DELETE Room 不在 → 404
# ---------------------------------------------------------------------------


class TestArchiveRoomNotFound:
    """TC-IT-RM-HTTP-019: DELETE Room 不在 → 404 (RoomNotFoundError)."""

    async def test_room_not_found_returns_404(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.delete(f"/api/rooms/{uuid4()}")
        assert resp.status_code == 404

    async def test_room_not_found_error_code(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.delete(f"/api/rooms/{uuid4()}")
        assert resp.json()["error"]["code"] == "not_found"

    async def test_room_not_found_error_message(self, room_ctx: RoomTestCtx) -> None:
        resp = await room_ctx.client.delete(f"/api/rooms/{uuid4()}")
        assert resp.json()["error"]["message"] == "Room not found."


# ---------------------------------------------------------------------------
# TC-IT-RM-HTTP-020: DELETE unassign_agent archived Room → 409
# ---------------------------------------------------------------------------


class TestUnassignAgentArchivedRoom:
    """TC-IT-RM-HTTP-020: unassign_agent on archived Room → 409 (RoomArchivedError)."""

    async def test_unassign_archived_returns_409(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.delete(
            f"/api/rooms/{room['id']}/agents/{uuid4()}/roles/LEADER"
        )
        assert resp.status_code == 409

    async def test_unassign_archived_error_code(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.delete(
            f"/api/rooms/{room['id']}/agents/{uuid4()}/roles/LEADER"
        )
        assert resp.json()["error"]["code"] == "conflict"

    async def test_unassign_archived_error_message(self, room_ctx: RoomTestCtx) -> None:
        empire = await _create_empire(room_ctx.client)
        wf = await _seed_workflow(room_ctx.session_factory)
        room = await _create_room(room_ctx.client, str(empire["id"]), str(wf.id))  # type: ignore[attr-defined]
        await room_ctx.client.delete(f"/api/rooms/{room['id']}")
        resp = await room_ctx.client.delete(
            f"/api/rooms/{room['id']}/agents/{uuid4()}/roles/LEADER"
        )
        assert resp.json()["error"]["message"] == "Room is archived and cannot be modified."
