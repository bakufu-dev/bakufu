# 詳細設計補章: Schneier 申し送り取り込み + 依存方向の物理保証

> 親: [`../detailed-design.md`](../detailed-design.md)。本書は Schneier 申し送り 6 項目の実装ステータス（確定 H）と domain → infrastructure 依存方向の物理保証（確定 I）を凍結する。

## 確定 H: Schneier 申し送り 6 項目の実装ステータス

| # | 項目 | 本 PR | 後続 PR |
|---|---|---|---|
| 1 | `BAKUFU_DATA_DIR` 絶対パス | ✓ `data_dir.py` で実装 + 結合テスト | — |
| 2 | H10 TOCTOU | ✗ | `feature/skill-loader` で skill 読み込み直前再検証 |
| 3 | `Persona.prompt_body` Repository マスキング | △ TypeDecorator (`MaskedText`) hook 構造のみ提供 | `feature/agent-repository` で `agents.prompt_body` カラムに `mapped_column(MaskedText, ...)` で宣言 |
| 4 | `audit_log` DELETE 拒否 | ✓ Alembic 初回 revision でトリガ作成 + 結合テスト（[`triggers.md`](triggers.md) §確定 C） | — |
| 5 | `bakufu_pid_registry` 0600 | ✓ テーブル + GC スケルトン + パーミッション強制（[`bootstrap.md`](bootstrap.md) §確定 E） | LLM Adapter 側で実 spawn / kill 配線（`feature/llm-adapter`） |
| 6 | Outbox `payload_json` / `last_error` マスキング | ✓ TypeDecorator (`MaskedJSONEncoded` / `MaskedText`) の `process_bind_param` で Core / ORM 両経路強制ゲートウェイ化 + 結合テスト TC-IT-PF-020 PASSED（[`triggers.md`](triggers.md) §確定 B + [`masking.md`](masking.md) §確定 F） | — |

「△」項目は hook を提供するに留まり、実適用は対応 Aggregate Repository PR の責務。本 Issue の設計書に「申し送りを継承」と明記する。

## 確定 I: 依存方向の物理保証

domain 層から infrastructure 層への import が 0 件であることを以下で保証:

1. CI script: `grep -rn 'from bakufu.infrastructure' backend/src/bakufu/domain/` の結果が空であること
2. テスト: `tests/architecture/test_dependency_direction.py` が `bakufu.domain.*` の全モジュールを import し、`bakufu.infrastructure.*` の名前が module 属性に含まれないことを検証

これにより、後続 Repository PR で誰かが `domain/` 内に infrastructure 参照を持ち込んでも CI で落ちる。
