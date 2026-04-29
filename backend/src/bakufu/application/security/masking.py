"""application 層 masking ユーティリティ（§確定 I）。

``MaskingGateway`` を application 層から呼ぶ薄いアダプタ。masking ロジックの実体は
``infrastructure/security/masking.py`` が唯一の真実源として保持する（DRY 原則）。

依存方向:
    interfaces → application（許容）/ application → infrastructure（許容）
    interfaces → infrastructure の直接依存なし（TC-UT-AGH-009 制約を維持）

冪等性:
    ``ApplicationMasking.mask()`` は冪等。``<REDACTED:*>`` を入力しても同一の
    ``<REDACTED:*>`` を返す。
    GET パス field_serializer の二重 masking が副作用を持たないことを保証する。
"""

from __future__ import annotations

from bakufu.infrastructure.security.masking import MaskingGateway


class ApplicationMasking:
    """application 層から使う伏字化入口。"""

    @classmethod
    def mask(cls, value: object) -> str:
        return MaskingGateway.mask(value)


__all__ = ["ApplicationMasking"]
