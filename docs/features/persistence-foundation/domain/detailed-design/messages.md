# 詳細設計補章: ユーザー向けメッセージ確定文言

> 親: [`../detailed-design.md`](../detailed-design.md)。本書は MSG-PF-001〜008 の確定文言を凍結する真実源。[`../feature-spec.md`](../feature-spec.md) §ユーザー向けメッセージ一覧 とのマッピング元。

## プレフィックス統一

| プレフィックス | 意味 |
|--------------|-----|
| `[FAIL]` | 処理中止を伴う失敗（startup 段階） |
| `[WARN]` | 警告（処理は継続） |
| `[INFO]` | 情報提供（処理は継続） |

## MSG 確定文言表

| ID | 出力先 | 文言 |
|----|------|----|
| MSG-PF-001 | stderr / startup ログ | `[FAIL] BAKUFU_DATA_DIR must be an absolute path (got: {value})` — `{value}` はホームパス置換適用後 |
| MSG-PF-002 | stderr / startup ログ | `[FAIL] SQLite engine initialization failed: {reason}` |
| MSG-PF-003 | stderr / startup ログ | `[FAIL] Attachment FS root initialization failed at {path}: {reason}` |
| MSG-PF-004 | stderr / startup ログ | `[FAIL] Alembic migration failed: {reason}` |
| MSG-PF-005 | SQLite トリガ raise message | `audit_log is append-only` / `audit_log result is immutable once set` |
| MSG-PF-006 | WARN ログ | `[WARN] Masking gateway fallback applied: {kind}` — `{kind}` は [`masking.md`](masking.md) §確定 F の Fail-Secure 3 種に同期: `mask_error` / `listener_error` / `mask_overflow`（必要に応じ `mask_oversize_dict` 等のサブ識別子） |
| MSG-PF-007 | WARN ログ | `[WARN] pid_registry GC: psutil.AccessDenied for pid={pid}, retry next cycle` |
| MSG-PF-008 | stderr / startup ログ | `[FAIL] Masking environment dictionary load failed: {reason}.` / `Next: Cannot start with partial masking layer. Investigate env access permissions and OS-level masking config; restart bakufu after fix.` — [`masking.md`](masking.md) §確定 F の Fail Fast 契約（masking layer 1 が無効化された状態での起動を許容しない）|

メッセージは ASCII 範囲。日本語化は UI 側 i18n（Phase 2、UI に届くメッセージのみ）。MSG-PF-008 は 2 行構造（`[FAIL] ...` + `Next: ...`）で運用者に復旧経路を提示する（Norman R5「フィードバック原則」と整合）。
