# external-review-gate — feature README

> 業務仕様: [feature-spec.md](feature-spec.md)
> システムテスト戦略: [system-test-design.md](system-test-design.md)
> 関連 Issue: [#38 feat(external-review-gate): ExternalReviewGate Aggregate Root (M1)](https://github.com/bakufu-dev/bakufu/issues/38) / [#36 feat(external-review-gate-repository): ExternalReviewGate SQLite Repository (M2)](https://github.com/bakufu-dev/bakufu/issues/36) / [#61 feat(external-review-gate): reviewer HTTP API (M3)](https://github.com/bakufu-dev/bakufu/issues/61)

## ディレクトリ構造

```
docs/features/external-review-gate/
  README.md                          ← 本ファイル
  feature-spec.md                    ← 業務仕様書（階層 2：全 sub-feature 共通）
  system-test-design.md              ← システムテスト戦略（E2E）
  domain/                            ← sub-feature: ExternalReviewGate Aggregate + VO
    basic-design.md
    detailed-design.md
    test-design.md
  repository/                        ← sub-feature: SQLite 永続化（3 テーブル）
    basic-design.md
    detailed-design.md
    test-design.md
  http-api/                          ← reviewer HTTP API（一覧 / 履歴 / 詳細 / approve / reject / cancel）
    basic-design.md
    detailed-design.md
    test-design.md
  (Phase 2 候補) ui/                 ← CEO レビュー操作 UI
```

## sub-feature マイルストーン

| sub-feature | Issue | 状態 | 設計書 |
|---|---|---|---|
| domain | [#38](https://github.com/bakufu-dev/bakufu/issues/38) | 実装済み（PR #46） | [domain/](domain/) |
| repository | [#36](https://github.com/bakufu-dev/bakufu/issues/36) | 実装済み（PR #53） | [repository/](repository/) |
| http-api | [#61](https://github.com/bakufu-dev/bakufu/issues/61) | 実装対象（PR #112） | [http-api/](http-api/) |
| ui | 該当なし（Phase 2 候補） | 未着手 | — |

## 着手順序

1. **domain** (#38) — ExternalReviewGate Aggregate Root + AuditEntry VO + ReviewDecision / AuditAction enum
2. **repository** (#36) — SQLite 永続化（`external_review_gates` / `external_review_gate_attachments` / `external_review_audit_entries` 3 テーブル + Alembic 0008）
3. **http-api** (#61) — reviewer 向け 6 API（一覧 / 履歴 / 詳細 / approve / reject / cancel）と GateService application 層
4. **ui**（Phase 2 候補） — CEO が Deliverable を確認して approve / reject するレビュー画面
