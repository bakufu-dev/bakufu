"""empire / http-api 結合テスト (TC-IT-EM-HTTP-001〜009).

Per ``docs/features/empire/http-api/test-design.md`` §結合テストケース.

Covers:
  TC-IT-EM-HTTP-001  POST /api/empires → 201 EmpireResponse (REQ-EM-HTTP-001)
  TC-IT-EM-HTTP-002  POST 重複 → 409 conflict (MSG-EM-HTTP-001, R1-5)
  TC-IT-EM-HTTP-003  GET /api/empires → 200 EmpireListResponse (REQ-EM-HTTP-002)
  TC-IT-EM-HTTP-004  GET /api/empires/{id} → 200 EmpireResponse (REQ-EM-HTTP-003)
  TC-IT-EM-HTTP-005  GET 不在 → 404 not_found (MSG-EM-HTTP-002)
  TC-IT-EM-HTTP-006  PATCH /api/empires/{id} → 200 更新済み (REQ-EM-HTTP-004)
  TC-IT-EM-HTTP-007  PATCH アーカイブ済み → 409 conflict (MSG-EM-HTTP-003, R1-8)
  TC-IT-EM-HTTP-008  DELETE /api/empires/{id} → 204 + archived=true (REQ-EM-HTTP-005)
  TC-IT-EM-HTTP-009  DELETE 不在 → 404 not_found (MSG-EM-HTTP-002)
  T1 CSRF           POST + evil Origin → 403 forbidden

Issue: #56
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EMPIRE_NAME = "山田の幕府"


async def _create_empire(client: AsyncClient, name: str = _EMPIRE_NAME) -> dict[str, object]:
    """POST /api/empires and return parsed JSON body (assert 201 internally)."""
    resp = await client.post("/api/empires", json={"name": name})
    assert resp.status_code == 201, f"Empire creation failed: {resp.text}"
    return resp.json()  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# TC-IT-EM-HTTP-001: POST /api/empires → 201 EmpireResponse
# ---------------------------------------------------------------------------
class TestCreateEmpire:
    """TC-IT-EM-HTTP-001: POST /api/empires creates new Empire (REQ-EM-HTTP-001)."""

    async def test_create_returns_201(self, empire_app_client: AsyncClient) -> None:
        resp = await empire_app_client.post("/api/empires", json={"name": _EMPIRE_NAME})
        assert resp.status_code == 201

    async def test_create_response_has_id(self, empire_app_client: AsyncClient) -> None:
        resp = await empire_app_client.post("/api/empires", json={"name": _EMPIRE_NAME})
        assert isinstance(resp.json()["id"], str)

    async def test_create_response_name_matches(self, empire_app_client: AsyncClient) -> None:
        resp = await empire_app_client.post("/api/empires", json={"name": _EMPIRE_NAME})
        assert resp.json()["name"] == _EMPIRE_NAME

    async def test_create_response_archived_is_false(self, empire_app_client: AsyncClient) -> None:
        resp = await empire_app_client.post("/api/empires", json={"name": _EMPIRE_NAME})
        assert resp.json()["archived"] is False

    async def test_create_response_rooms_is_empty_list(self, empire_app_client: AsyncClient) -> None:
        resp = await empire_app_client.post("/api/empires", json={"name": _EMPIRE_NAME})
        assert resp.json()["rooms"] == []

    async def test_create_response_agents_is_empty_list(self, empire_app_client: AsyncClient) -> None:
        resp = await empire_app_client.post("/api/empires", json={"name": _EMPIRE_NAME})
        assert resp.json()["agents"] == []


# ---------------------------------------------------------------------------
# TC-IT-EM-HTTP-002: POST 重複 → 409 conflict (MSG-EM-HTTP-001, R1-5)
# ---------------------------------------------------------------------------
class TestCreateEmpireConflict:
    """TC-IT-EM-HTTP-002: second POST → 409 conflict (EmpireAlreadyExistsError, R1-5)."""

    async def test_duplicate_returns_409(self, empire_app_client: AsyncClient) -> None:
        await _create_empire(empire_app_client)
        resp = await empire_app_client.post("/api/empires", json={"name": "2つ目の幕府"})
        assert resp.status_code == 409

    async def test_duplicate_error_code_is_conflict(self, empire_app_client: AsyncClient) -> None:
        await _create_empire(empire_app_client)
        resp = await empire_app_client.post("/api/empires", json={"name": "2つ目の幕府"})
        assert resp.json()["error"]["code"] == "conflict"

    async def test_duplicate_error_message(self, empire_app_client: AsyncClient) -> None:
        """MSG-EM-HTTP-001: "Empire already exists." (静的照合)."""
        await _create_empire(empire_app_client)
        resp = await empire_app_client.post("/api/empires", json={"name": "2つ目の幕府"})
        assert resp.json()["error"]["message"] == "Empire already exists."

    async def test_duplicate_response_has_error_envelope(self, empire_app_client: AsyncClient) -> None:
        await _create_empire(empire_app_client)
        resp = await empire_app_client.post("/api/empires", json={"name": "2つ目の幕府"})
        body = resp.json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]

    async def test_csrf_evil_origin_returns_403(self, empire_app_client: AsyncClient) -> None:
        """T1: POST /api/empires + evil Origin → 403 (CSRF ミドルウェアが適用されることの物理保証)."""
        resp = await empire_app_client.post(
            "/api/empires",
            headers={"Origin": "http://evil.example.com"},
            json={"name": _EMPIRE_NAME},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "forbidden"


# ---------------------------------------------------------------------------
# TC-IT-EM-HTTP-003: GET /api/empires → 200 EmpireListResponse
# ---------------------------------------------------------------------------
class TestListEmpires:
    """TC-IT-EM-HTTP-003: GET /api/empires (REQ-EM-HTTP-002)."""

    async def test_list_empty_returns_200(self, empire_app_client: AsyncClient) -> None:
        resp = await empire_app_client.get("/api/empires")
        assert resp.status_code == 200

    async def test_list_empty_body(self, empire_app_client: AsyncClient) -> None:
        resp = await empire_app_client.get("/api/empires")
        assert resp.json() == {"items": [], "total": 0}

    async def test_list_with_empire_total_is_1(self, empire_app_client: AsyncClient) -> None:
        await _create_empire(empire_app_client)
        resp = await empire_app_client.get("/api/empires")
        assert resp.json()["total"] == 1

    async def test_list_with_empire_items_has_one_entry(self, empire_app_client: AsyncClient) -> None:
        await _create_empire(empire_app_client)
        resp = await empire_app_client.get("/api/empires")
        assert len(resp.json()["items"]) == 1

    async def test_list_item_name_matches(self, empire_app_client: AsyncClient) -> None:
        await _create_empire(empire_app_client)
        resp = await empire_app_client.get("/api/empires")
        assert resp.json()["items"][0]["name"] == _EMPIRE_NAME


# ---------------------------------------------------------------------------
# TC-IT-EM-HTTP-004: GET /api/empires/{id} → 200 EmpireResponse
# ---------------------------------------------------------------------------
class TestGetEmpire:
    """TC-IT-EM-HTTP-004: GET /api/empires/{id} (REQ-EM-HTTP-003)."""

    async def test_get_returns_200(self, empire_app_client: AsyncClient) -> None:
        body = await _create_empire(empire_app_client)
        resp = await empire_app_client.get(f"/api/empires/{body['id']}")
        assert resp.status_code == 200

    async def test_get_response_name_matches(self, empire_app_client: AsyncClient) -> None:
        body = await _create_empire(empire_app_client)
        resp = await empire_app_client.get(f"/api/empires/{body['id']}")
        assert resp.json()["name"] == _EMPIRE_NAME

    async def test_get_response_archived_is_false(self, empire_app_client: AsyncClient) -> None:
        body = await _create_empire(empire_app_client)
        resp = await empire_app_client.get(f"/api/empires/{body['id']}")
        assert resp.json()["archived"] is False

    async def test_get_response_id_matches(self, empire_app_client: AsyncClient) -> None:
        body = await _create_empire(empire_app_client)
        resp = await empire_app_client.get(f"/api/empires/{body['id']}")
        assert resp.json()["id"] == body["id"]


# ---------------------------------------------------------------------------
# TC-IT-EM-HTTP-005: GET 不在 → 404 not_found (MSG-EM-HTTP-002)
# ---------------------------------------------------------------------------
class TestGetEmpireNotFound:
    """TC-IT-EM-HTTP-005: GET /api/empires/{unknown-id} → 404 (EmpireNotFoundError)."""

    async def test_not_found_returns_404(self, empire_app_client: AsyncClient) -> None:
        resp = await empire_app_client.get(f"/api/empires/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_not_found_error_code(self, empire_app_client: AsyncClient) -> None:
        resp = await empire_app_client.get(f"/api/empires/{uuid.uuid4()}")
        assert resp.json()["error"]["code"] == "not_found"

    async def test_not_found_error_message(self, empire_app_client: AsyncClient) -> None:
        """MSG-EM-HTTP-002: "Empire not found." (静的照合)."""
        resp = await empire_app_client.get(f"/api/empires/{uuid.uuid4()}")
        assert resp.json()["error"]["message"] == "Empire not found."


# ---------------------------------------------------------------------------
# TC-IT-EM-HTTP-006: PATCH /api/empires/{id} → 200 更新済み (REQ-EM-HTTP-004)
# ---------------------------------------------------------------------------
class TestUpdateEmpire:
    """TC-IT-EM-HTTP-006: PATCH /api/empires/{id} updates empire name (REQ-EM-HTTP-004)."""

    async def test_patch_returns_200(self, empire_app_client: AsyncClient) -> None:
        body = await _create_empire(empire_app_client)
        resp = await empire_app_client.patch(
            f"/api/empires/{body['id']}", json={"name": "新山田の幕府"}
        )
        assert resp.status_code == 200

    async def test_patch_response_name_updated(self, empire_app_client: AsyncClient) -> None:
        body = await _create_empire(empire_app_client)
        resp = await empire_app_client.patch(
            f"/api/empires/{body['id']}", json={"name": "新山田の幕府"}
        )
        assert resp.json()["name"] == "新山田の幕府"

    async def test_patch_archived_remains_false(self, empire_app_client: AsyncClient) -> None:
        body = await _create_empire(empire_app_client)
        resp = await empire_app_client.patch(
            f"/api/empires/{body['id']}", json={"name": "新山田の幕府"}
        )
        assert resp.json()["archived"] is False

    async def test_patch_update_is_persisted(self, empire_app_client: AsyncClient) -> None:
        """ラウンドトリップ: PATCH 後 GET で更新が永続化されていることを確認."""
        body = await _create_empire(empire_app_client)
        await empire_app_client.patch(
            f"/api/empires/{body['id']}", json={"name": "永続化確認の幕府"}
        )
        get_resp = await empire_app_client.get(f"/api/empires/{body['id']}")
        assert get_resp.json()["name"] == "永続化確認の幕府"


# ---------------------------------------------------------------------------
# TC-IT-EM-HTTP-007: PATCH アーカイブ済み → 409 conflict (MSG-EM-HTTP-003, R1-8)
# ---------------------------------------------------------------------------
class TestUpdateArchivedEmpire:
    """TC-IT-EM-HTTP-007: PATCH on archived Empire → 409 conflict (EmpireArchivedError, R1-8)."""

    async def test_patch_archived_returns_409(self, empire_app_client: AsyncClient) -> None:
        body = await _create_empire(empire_app_client)
        await empire_app_client.delete(f"/api/empires/{body['id']}")
        resp = await empire_app_client.patch(
            f"/api/empires/{body['id']}", json={"name": "変更試み"}
        )
        assert resp.status_code == 409

    async def test_patch_archived_error_code_is_conflict(self, empire_app_client: AsyncClient) -> None:
        body = await _create_empire(empire_app_client)
        await empire_app_client.delete(f"/api/empires/{body['id']}")
        resp = await empire_app_client.patch(
            f"/api/empires/{body['id']}", json={"name": "変更試み"}
        )
        assert resp.json()["error"]["code"] == "conflict"

    async def test_patch_archived_error_message(self, empire_app_client: AsyncClient) -> None:
        """MSG-EM-HTTP-003: "Empire is archived and cannot be modified." (静的照合)."""
        body = await _create_empire(empire_app_client)
        await empire_app_client.delete(f"/api/empires/{body['id']}")
        resp = await empire_app_client.patch(
            f"/api/empires/{body['id']}", json={"name": "変更試み"}
        )
        assert resp.json()["error"]["message"] == "Empire is archived and cannot be modified."


# ---------------------------------------------------------------------------
# TC-IT-EM-HTTP-008: DELETE /api/empires/{id} → 204 + archived=true
# ---------------------------------------------------------------------------
class TestDeleteEmpire:
    """TC-IT-EM-HTTP-008: DELETE /api/empires/{id} → 204 + GET shows archived=true (REQ-EM-HTTP-005)."""

    async def test_delete_returns_204(self, empire_app_client: AsyncClient) -> None:
        body = await _create_empire(empire_app_client)
        resp = await empire_app_client.delete(f"/api/empires/{body['id']}")
        assert resp.status_code == 204

    async def test_delete_body_is_empty(self, empire_app_client: AsyncClient) -> None:
        body = await _create_empire(empire_app_client)
        resp = await empire_app_client.delete(f"/api/empires/{body['id']}")
        assert resp.content == b""

    async def test_delete_sets_archived_true(self, empire_app_client: AsyncClient) -> None:
        """ラウンドトリップ: DELETE 後 GET で archived=true を確認 (論理削除)."""
        body = await _create_empire(empire_app_client)
        await empire_app_client.delete(f"/api/empires/{body['id']}")
        get_resp = await empire_app_client.get(f"/api/empires/{body['id']}")
        assert get_resp.json()["archived"] is True

    async def test_delete_empire_still_retrievable_after_archive(self, empire_app_client: AsyncClient) -> None:
        """論理削除後も GET で取得可能（物理削除ではない）."""
        body = await _create_empire(empire_app_client)
        await empire_app_client.delete(f"/api/empires/{body['id']}")
        get_resp = await empire_app_client.get(f"/api/empires/{body['id']}")
        assert get_resp.status_code == 200


# ---------------------------------------------------------------------------
# TC-IT-EM-HTTP-009: DELETE 不在 → 404 not_found (MSG-EM-HTTP-002)
# ---------------------------------------------------------------------------
class TestDeleteEmpireNotFound:
    """TC-IT-EM-HTTP-009: DELETE /api/empires/{unknown-id} → 404 (EmpireNotFoundError)."""

    async def test_delete_not_found_returns_404(self, empire_app_client: AsyncClient) -> None:
        resp = await empire_app_client.delete(f"/api/empires/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_delete_not_found_error_code(self, empire_app_client: AsyncClient) -> None:
        resp = await empire_app_client.delete(f"/api/empires/{uuid.uuid4()}")
        assert resp.json()["error"]["code"] == "not_found"

    async def test_delete_not_found_error_message(self, empire_app_client: AsyncClient) -> None:
        """MSG-EM-HTTP-002: "Empire not found." (静的照合)."""
        resp = await empire_app_client.delete(f"/api/empires/{uuid.uuid4()}")
        assert resp.json()["error"]["message"] == "Empire not found."
