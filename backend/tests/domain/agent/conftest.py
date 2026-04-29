"""Agent 集約のテスト全体で共有する pytest フィクスチャ。

``BAKUFU_DATA_DIR`` 環境変数は ``SkillRef.path`` の H10 チェック
（:func:`bakufu.domain.agent.path_validators._h10_check_base_escape`）に必須である。
本番環境ではランチャが設定するが、単体テストでは autouse フィクスチャで
固定のダミーディレクトリ文字列を設定し、実ファイルシステムに依存せずに
SkillRef の構築で H10 を完遂できるようにする（``Path.resolve(strict=False)``
は存在しないパスでも字句解決された形式を返すだけである）。
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _bakufu_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    """全 agent テストの実行中、``BAKUFU_DATA_DIR`` を設定する。

    autouse フィクスチャ — pytest が依存性注入で呼び出すため、pyright からは
    未使用に見える。下の pragma がそれを抑止する。
    """
    monkeypatch.setenv("BAKUFU_DATA_DIR", "/tmp/bakufu-test-root")
