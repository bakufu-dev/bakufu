# テスト設計書 — internal-review-gate / repository

> feature: `internal-review-gate` / sub-feature: `repository`
> 親業務仕様: [`../feature-spec.md`](../feature-spec.md)
> 関連: [`basic-design.md`](basic-design.md) / [`detailed-design.md`](detailed-design.md)
> 担当 Issue: [#164 feat(M5-B): InternalReviewGate infrastructure実装](https://github.com/bakufu-dev/bakufu/issues/164)

## 本書の役割

本書は **internal-review-gate / repository sub-feature の IT（結合テスト）と UT（単体テスト）** を凍結する。システムテスト（TC-ST-IRG-XXX）は [`../system-test-design.md`](../system-test-design.md) が担当する。

## テスト方針

| レベル | 対象 | 手段 |
|-------|------|------|
| IT（結合）| `SqliteInternalReviewGateRepository` ↔ 実 SQLite | `tempfile` 一時 DB + `alembic upgrade head` |
| UT（単体）| Protocol 充足確認 / `_to_rows` / `_from_rows` / masking 配線 | pytest fixture + mock session |

**実 SQLite を使う理由**: Repository の主要責務は「SQLite への正確な CRUD」であり、Mock DB では ON DELETE CASCADE / UNIQUE 制約 / MaskedText TypeDecorator の実動作を検証できない。

## 結合テスト（IT）

テストディレクトリ: `backend/tests/infrastructure/persistence/sqlite/repositories/test_internal_review_gate_repository/`

### TC-IT-IRG-R001: Gate の新規保存と復元（PENDING 初期状態、verdicts なし）

| 項目 | 内容 |
|-----|------|
| 対象 | `REQ-IRG-R002`（save + find_by_id ラウンドトリップ）|
| 前提 | alembic upgrade head 済みの一時 SQLite DB |
| 手順 | 1) `required_gate_roles={"reviewer","ux"}` で Gate を構築 → 2) `save(gate)` → 3) `find_by_id(gate.id)` → 4) 全属性比較 |
| 期待結果 | 復元 Gate の id / task_id / stage_id / required_gate_roles / verdicts / gate_decision / created_at が全て元と一致 |
| 受入基準 | #12（再起動跨ぎ保持）|

### TC-IT-IRG-R002: Verdict 追加後の再保存と復元

| 項目 | 内容 |
|-----|------|
| 対象 | `REQ-IRG-R003`（save での DELETE/INSERT semantics）|
| 手順 | 1) Gate(PENDING) を save → 2) `gate.submit_verdict(role="reviewer", APPROVED, "OK", ...)` → 3) `save(updated_gate)` → 4) `find_by_id` で復元 → 5) verdicts[0] の全属性確認 |
| 期待結果 | verdicts タプルが 1 件、role="reviewer"、decision="APPROVED"、comment が **マスク済み文字列** で保持される |
| 注記 | comment にダミー secret（webhook URL 形式の文字列）を仕込み、復元後 comment が `<REDACTED:...>` 形式であることを確認 |

### TC-IT-IRG-R003: 複数 Verdict の順序保証

| 項目 | 内容 |
|-----|------|
| 対象 | `REQ-IRG-R003`（order_index による tuple 順序保持）|
| 手順 | 1) Gate(PENDING, required_gate_roles={"reviewer","ux","security"}) を save → 2) reviewer APPROVED → save → 3) ux APPROVED → save → 4) security REJECTED → save → 5) `find_by_id` で復元 |
| 期待結果 | verdicts タプルが 3 件、順序が (reviewer, ux, security) の submit 順を保持 |

### TC-IT-IRG-R004: `find_by_task_and_stage` — PENDING Gate の取得

| 項目 | 内容 |
|-----|------|
| 対象 | `REQ-IRG-R001`（find_by_task_and_stage）|
| 手順 | 1) Gate_1(REJECTED) を save → 2) Gate_2(PENDING) を同一 (task_id, stage_id) で save → 3) `find_by_task_and_stage(task_id, stage_id)` |
| 期待結果 | Gate_2 が返る（PENDING のみを絞り込む）|

### TC-IT-IRG-R005: `find_all_by_task_id` — 複数ラウンドの全履歴取得

| 項目 | 内容 |
|-----|------|
| 対象 | `REQ-IRG-R001`（find_all_by_task_id）|
| 手順 | 1) Gate_1(REJECTED) を save → 2) Gate_2(PENDING) を save → 3) `find_all_by_task_id(task_id)` |
| 期待結果 | [Gate_1, Gate_2] が created_at 昇順で返る（全履歴）|

### TC-IT-IRG-R006: ON DELETE CASCADE — Gate 削除で verdicts が連動削除

| 項目 | 内容 |
|-----|------|
| 対象 | ER 図 FK ON DELETE CASCADE（DB 整合性）|
| 手順 | 1) Gate + verdicts 2 件を save → 2) SQL で `internal_review_gates` 行を直接 DELETE → 3) `SELECT * FROM internal_review_gate_verdicts WHERE gate_id=?` |
| 期待結果 | verdicts 行が 0 件（CASCADE 削除）|

### TC-IT-IRG-R007: UNIQUE(gate_id, role) 制約 — 同 role の重複 INSERT を物理拒否

| 項目 | 内容 |
|-----|------|
| 対象 | セキュリティ T2（Aggregate 不変条件の DB 二重防衛）|
| 手順 | 1) Gate を save（verdicts なし）→ 2) Aggregate を迂回して `internal_review_gate_verdicts` に同一 role の行を 2 件 INSERT |
| 期待結果 | `sqlalchemy.IntegrityError` が発生する |

### TC-IT-IRG-R008: `verdicts.comment` の masking 配線確認

| 項目 | 内容 |
|-----|------|
| 対象 | セキュリティ T1（MaskedText TypeDecorator 実配線）|
| 手順 | 1) comment = `"https://discord.com/api/webhooks/secret_token"` で Verdict を含む Gate を save → 2) SQLite DB ファイルを直接 `sqlite3` CLI で開いて `internal_review_gate_verdicts.comment` カラムを確認 |
| 期待結果 | DB 上の comment が `<REDACTED:DISCORD_WEBHOOK>` 形式（plain text で token が残っていない）|

## ユニットテスト（UT）

テストディレクトリ: `backend/tests/infrastructure/persistence/sqlite/repositories/test_internal_review_gate_repository/`

### TC-UT-IRG-R101: `InternalReviewGateRepositoryPort` Protocol 充足（pyright 静的保証）

| 項目 | 内容 |
|-----|------|
| 対象 | `REQ-IRG-R002`（Protocol 充足）|
| 手順 | `SqliteInternalReviewGateRepository` のインスタンスを Protocol 型にアサート（pyright strict + isinstance チェック） |
| 期待結果 | pyright 静的エラーなし / `isinstance(repo, InternalReviewGateRepositoryPort)` が True |
| 注記 | InternalReviewGateRepositoryPort は `@runtime_checkable` なしのため `isinstance` テストは pyright の型整合性確認のみ（実行時 isinstance は Protocol が runtime_checkable のときのみ動作）。pyright strict mode の型検査で充足を保証する |

### TC-UT-IRG-R102: `_to_rows()` — Aggregate → Row 変換の正確性

| 項目 | 内容 |
|-----|------|
| 対象 | `_to_rows` private method（row 変換ロジック）|
| 手順 | Gate(verdicts 2 件) を渡して `_to_rows()` を呼び、返却 tuple を検査 |
| 期待結果 | gate_row の全属性 / verdict_rows の order_index / role / decision / comment が Gate の属性と一致 |

### TC-UT-IRG-R103: `_from_rows()` — Row → Aggregate 変換の正確性

| 項目 | 内容 |
|-----|------|
| 対象 | `_from_rows` private method（Aggregate 復元ロジック）|
| 手順 | mock gate_row + verdict_rows を用意して `_from_rows()` を呼ぶ |
| 期待結果 | 復元 InternalReviewGate の全属性（required_gate_roles が frozenset / verdicts が tuple）が正しい |

### TC-UT-IRG-R104: `_from_rows()` — verdicts が order_index 昇順で復元される

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 A（tuple 順序保証）|
| 手順 | verdict_rows を order_index 逆順で渡して `_from_rows()` を呼ぶ |
| 期待結果 | 復元 verdicts タプルが order_index 昇順（0, 1, 2）で並ぶ |

### TC-UT-IRG-R105: `_from_rows()` — `required_gate_roles` の JSON 復元

| 項目 | 内容 |
|-----|------|
| 対象 | §確定 C（required_gate_roles JSON 保持）|
| 手順 | gate_row.required_gate_roles = `'["reviewer", "ux"]'` で `_from_rows()` を呼ぶ |
| 期待結果 | 復元 Gate の `required_gate_roles` が `frozenset({"reviewer", "ux"})` |

## カバレッジ基準

| 対象 | カバレッジ目標 |
|-----|------------|
| `SqliteInternalReviewGateRepository`（全 4 method + private method 2 件）| line 90% 以上 |
| IT テストで UNIQUE / CASCADE / masking の実動作を確認 | IT 全 8 件全緑 |
| pyright strict pass | 型エラーゼロ |

## テスト実行方法

```
# IT（実 SQLite）
pytest backend/tests/infrastructure/persistence/sqlite/repositories/test_internal_review_gate_repository/ -v

# UT（mock）
pytest backend/tests/infrastructure/persistence/sqlite/repositories/test_internal_review_gate_repository/test_row_conversion.py -v

# カバレッジ
pytest --cov=bakufu.infrastructure.persistence.sqlite.repositories.internal_review_gate_repository --cov-report=term-missing
```
