"""application 層 masking ユーティリティ（§確定 I）。

``infrastructure.security.masking.mask`` を application 層から再エクスポートする
薄いアダプタ。masking ロジックの実体は ``infrastructure/security/masking.py`` が
唯一の真実源として保持する（DRY 原則）。

依存方向:
    interfaces → application（許容）/ application → infrastructure（許容）
    interfaces → infrastructure の直接依存なし（TC-UT-AGH-009 制約を維持）

冪等性:
    ``mask()`` は冪等。``<REDACTED:*>`` を入力しても同一の ``<REDACTED:*>`` を返す。
    GET パス field_serializer の二重 masking が副作用を持たないことを保証する。
"""

from __future__ import annotations

from bakufu.infrastructure.security.masking import mask as mask

__all__ = ["mask"]
