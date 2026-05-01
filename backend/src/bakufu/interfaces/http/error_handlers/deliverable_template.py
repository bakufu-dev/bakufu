"""DeliverableTemplate / RoleProfile 専用ハンドラ群。

MSG 確定文言は detailed-design.md §MSG 確定文言表 で凍結されている。
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from bakufu.interfaces.http.error_handlers._common import (
    NOT_FOUND,
    VALIDATION_ERROR,
    clean_domain_message,
    error_response,
)
from bakufu.interfaces.http.schemas.common import ErrorDetail, ErrorResponse

# ── DeliverableTemplate ───────────────────────────────────────────────────────


async def deliverable_template_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """``DeliverableTemplateNotFoundError`` → HTTP 404 / not_found または 422 / ref_not_found。

    ``kind`` に応じて HTTP ステータスとコードを決定する:

    * ``"primary"`` → 404 / ``not_found`` （MSG-DT-HTTP-001）
    * ``"composition_ref"`` → 422 / ``ref_not_found`` （MSG-DT-HTTP-002）
    * ``"role_profile_ref"`` → 422 / ``ref_not_found`` （MSG-RP-HTTP-002）
    """
    from bakufu.application.exceptions.deliverable_template_exceptions import (
        DeliverableTemplateNotFoundError,
    )

    if not isinstance(exc, DeliverableTemplateNotFoundError):
        raise TypeError(f"Expected DeliverableTemplateNotFoundError, got {type(exc).__name__}")

    if exc.kind == "primary":
        return error_response(
            NOT_FOUND,
            "[FAIL] DeliverableTemplate が見つかりません。\n"
            "Next: template_id を確認し、存在するテンプレートを指定してください。",
            404,
        )

    # composition_ref / role_profile_ref → 422 / ref_not_found
    if exc.kind == "composition_ref":
        message = (
            f"[FAIL] composition に指定された DeliverableTemplate が存在しません"
            f"（id: {exc.template_id}）。\n"
            "Next: 存在するテンプレートの id を指定してください。"
        )
    else:  # role_profile_ref
        message = (
            f"[FAIL] deliverable_template_refs に指定された DeliverableTemplate が"
            f"存在しません（id: {exc.template_id}）。\n"
            "Next: 存在するテンプレートの id を指定してください。"
        )

    body = ErrorResponse(
        error=ErrorDetail(
            code="ref_not_found",
            message=message,
            detail={"template_id": exc.template_id},
        )
    )
    return JSONResponse(content=body.model_dump(), status_code=422)


async def composition_cycle_handler(request: Request, exc: Exception) -> JSONResponse:
    """``CompositionCycleError`` → HTTP 422 / composition_cycle (MSG-DT-HTTP-003a/b/c)。

    cycle_path はクライアントが提出していない内部ノードの UUID を含む可能性があるため
    レスポンスから除外する（最小情報開示原則 / Tabriz 指摘対応）。
    """
    from bakufu.application.exceptions.deliverable_template_exceptions import (
        CompositionCycleError,
    )

    if not isinstance(exc, CompositionCycleError):
        raise TypeError(f"Expected CompositionCycleError, got {type(exc).__name__}")

    if exc.reason == "transitive_cycle":
        message = (
            "[FAIL] composition に推移的な循環参照が検出されました。\n"
            "Next: 循環を引き起こす DeliverableTemplateRef を composition から除去してください。"
        )
    elif exc.reason == "depth_limit":
        message = (
            "[FAIL] composition の参照深度が上限（10）を超えました。\n"
            "Next: composition の参照ネストを減らしてください（上限: depth 10）。"
        )
    else:  # node_limit
        message = (
            "[FAIL] composition の参照ノード数が上限（100）を超えました。\n"
            "Next: composition に含まれるテンプレート数を減らしてください（上限: 100 ノード）。"
        )

    body = ErrorResponse(
        error=ErrorDetail(
            code="composition_cycle",
            message=message,
            # cycle_path は内部 UUID を含む可能性があるため除外（最小情報開示原則）
            detail={"reason": exc.reason},
        )
    )
    return JSONResponse(content=body.model_dump(), status_code=422)


async def deliverable_template_version_downgrade_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """``DeliverableTemplateVersionDowngradeError`` → 422 / version_downgrade (MSG-DT-HTTP-004)。"""
    from bakufu.application.exceptions.deliverable_template_exceptions import (
        DeliverableTemplateVersionDowngradeError,
    )

    if not isinstance(exc, DeliverableTemplateVersionDowngradeError):
        raise TypeError(
            f"Expected DeliverableTemplateVersionDowngradeError, got {type(exc).__name__}"
        )
    body = ErrorResponse(
        error=ErrorDetail(
            code="version_downgrade",
            message=(
                f"[FAIL] 提供 version（{exc.provided_version}）が現在の version"
                f"（{exc.current_version}）より小さいです。\n"
                "Next: 現在の version 以上の SemVer を指定してください。"
            ),
            detail={
                "current_version": exc.current_version,
                "provided_version": exc.provided_version,
            },
        )
    )
    return JSONResponse(content=body.model_dump(), status_code=422)


async def deliverable_template_invariant_violation_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """``DeliverableTemplateInvariantViolation`` → HTTP 422 / validation_error。"""
    from bakufu.domain.exceptions import DeliverableTemplateInvariantViolation

    if not isinstance(exc, DeliverableTemplateInvariantViolation):
        raise TypeError(f"Expected DeliverableTemplateInvariantViolation, got {type(exc).__name__}")
    return error_response(VALIDATION_ERROR, clean_domain_message(str(exc)), 422)


# ── RoleProfile ───────────────────────────────────────────────────────────────


async def role_profile_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """``RoleProfileNotFoundError`` → HTTP 404 / not_found (MSG-RP-HTTP-001)。"""
    from bakufu.application.exceptions.deliverable_template_exceptions import (
        RoleProfileNotFoundError,
    )

    if not isinstance(exc, RoleProfileNotFoundError):
        raise TypeError(f"Expected RoleProfileNotFoundError, got {type(exc).__name__}")
    return error_response(
        NOT_FOUND,
        f"[FAIL] RoleProfile が見つかりません（empire: {exc.empire_id}, role: {exc.role}）。\n"
        f"Next: PUT /api/empires/{exc.empire_id}/role-profiles/{exc.role} で先に作成してください。",
        404,
    )


async def role_profile_invariant_violation_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """``RoleProfileInvariantViolation`` → HTTP 422 / validation_error。"""
    from bakufu.domain.exceptions import RoleProfileInvariantViolation

    if not isinstance(exc, RoleProfileInvariantViolation):
        raise TypeError(f"Expected RoleProfileInvariantViolation, got {type(exc).__name__}")
    return error_response(VALIDATION_ERROR, clean_domain_message(str(exc)), 422)


async def invalid_role_handler(request: Request, exc: Exception) -> JSONResponse:
    """``InvalidRoleError`` → HTTP 422 / validation_error。

    ``role`` パスパラメータに不正な文字列が渡された際に
    ``RoleProfileService._parse_role`` が送出する ``InvalidRoleError`` を
    422 に変換する。グローバルな ``ValueError`` ハンドラを設置せずに済む設計
    （Tabriz / ヘルスバーグ指摘対応）。
    """
    from bakufu.application.exceptions.deliverable_template_exceptions import InvalidRoleError

    if not isinstance(exc, InvalidRoleError):
        raise TypeError(f"Expected InvalidRoleError, got {type(exc).__name__}")
    return error_response(
        VALIDATION_ERROR,
        f"Invalid role value: {exc.value!r}. Must be one of the valid Role enum values.",
        422,
    )
