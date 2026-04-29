"""Outbox ディスパッチャ + ハンドラ レジストリ スケルトン。

ディスパッチャは ``domain_event_outbox`` をポーリングし、行を ``DISPATCHING`` に
マークし、行の ``event_kind`` に対応するハンドラを :mod:`...handler_registry` で
ルックアップし、ハンドラを await して、行を ``DISPATCHED``（成功）/
``attempt_count`` をインクリメントした ``PENDING``（失敗）/ ``DEAD_LETTER``
（5 回失敗後）に更新する。

Schneier 中等 3（Confirmation K）に従い、本 PR は **ゼロ個** のハンドラを登録する。
すべての Outbox 行は後続の ``feature/{event-kind}-handler`` PR が投入されるまで
``PENDING`` のままとなる。ディスパッチャは起動時、およびレジストリが空のまま
pending 行を見つけたポーリング サイクルごとに WARN を発火するため、オペレータは
配線が部分的であることに気付ける。
"""

from __future__ import annotations

from bakufu.infrastructure.persistence.sqlite.outbox import (
    dispatcher,
    handler_registry,
)

__all__ = ["dispatcher", "handler_registry"]
