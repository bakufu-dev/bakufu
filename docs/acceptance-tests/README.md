# `acceptance-tests/` — bakufu 全体の受入テスト戦略

bakufu 全体の **業務シナリオを End-to-End で検証する受入テスト** を凍結するディレクトリ。Vモデル工程の最上位（要求分析 ↔ 受入テスト）に対応する。

## 本書の役割

各 feature 配下の `system-test-design.md` は **feature 業務概念に閉じた E2E**（Vモデル位置付けではシステムテスト相当）を担当する。本ディレクトリは **複数 feature を跨ぐ業務シナリオ** を担当する。

```
Vモデル対応:

要求分析 ── docs/analysis/ + docs/requirements/                ↔ 受入テスト   : docs/acceptance-tests/scenarios/
要件定義 ── feature/<name>/feature-spec.md            ↔ システムテスト相当: feature/<name>/system-test-design.md
基本設計 ── feature/<name>/<sub>/requirements.md, basic-design ↔ 結合テスト   : feature/<name>/<sub>/test-design.md §結合
詳細設計 ── feature/<name>/<sub>/detailed-design.md            ↔ ユニットテスト  : feature/<name>/<sub>/test-design.md §UT
```

## 真実源

| フェーズ | 受入基準の真実源 | 担当シナリオ命名 |
|---|---|---|
| MVP（v0.1.0） | [`docs/requirements/acceptance-criteria.md`](../requirements/acceptance-criteria.md) #1〜#16 | `scenarios/SC-MVP-NNN-*.md` |
| Phase 2 以降 | （ロードマップ確定時に対応文書を新設） | `scenarios/SC-P2-NNN-*.md`（将来） |

`docs/requirements/`（旧 mvp-scope.md / context.md から分散）は初期開発の目標指針であり、bakufu 全体の最終ビジョンではない。Phase 2 以降の受入基準は将来のロードマップ文書で別途凍結し、本ディレクトリにシナリオを追加する。

## 用語

業界的に呼称がばらついているため、本ディレクトリでは以下を採用する:

| 本書の呼称 | 同義の業界用語 | 対象 |
|---|---|---|
| **受入テスト**（Acceptance Test） | シナリオテスト / 総合テスト / システムテスト（広義）| ペルソナの業務シナリオを End-to-End で検証 |
| **シナリオ**（Scenario） | テストケース / E2E テスト / ジャーニーテスト | 受入テストの 1 単位（ペルソナの 1 業務行為の連続） |

各 feature 配下の `system-test-design.md` は呼称上「E2E テスト」だが、Vモデル位置付けでは「システムテスト」相当（feature 業務概念に閉じる）。これと「受入テスト（feature 跨ぎ）」を分離するために、本ディレクトリの命名で区別する。

## ディレクトリ構造

```
acceptance-tests/
├── README.md                       # 本ファイル（戦略 + シナリオ一覧 + 起票計画）
└── scenarios/
    ├── SC-MVP-001-vmodel-fullflow.md   # コアフロー: Vモデル開発室で Task 完走
    ├── SC-MVP-002-rejection-loop.md    # 差し戻しと再ラウンド
    ├── SC-MVP-003-restart.md           # 再起動跨ぎでの全状態復元
    ├── SC-MVP-004-blocked.md           # BLOCKED Task の検出と admin 救済
    ├── SC-MVP-005-dead-letter.md       # dead-letter event の検出と admin 救済
    ├── SC-MVP-006-security.md          # secret マスキング / TLS / 添付安全性
    ├── SC-MVP-007-audit-log.md         # Admin CLI 操作の audit_log 記録
    └── SC-MVP-008-dev-workflow.md      # `just check-all` 緑（開発フロー）
```

## シナリオ一覧と起票計画

### MVP 範囲（v0.1.0）

| シナリオ ID | 業務シナリオ | カバーする mvp-scope §受入基準 | 関連 feature | 起票タイミング |
|---|---|---|---|---|
| SC-MVP-001 | Vモデル開発室でディレクティブから Task 完走（内部レビュー含む） | #1, #2, #3, #4, #5, #7, #9, #17, #18 | empire / room / workflow / agent / task / **internal-review-gate** / external-review-gate / discord-notifier / claude-code-adapter | M7 |
| SC-MVP-002 | 差し戻しの複数ラウンドと履歴保持 | #6 | external-review-gate / task | M7 |
| SC-MVP-003 | 再起動跨ぎでの全状態復元 | #8 | persistence-foundation + 各 Aggregate Repository | M7 |
| SC-MVP-004 | BLOCKED Task の検出と admin 救済 | #11 | task / admin-cli | M7 |
| SC-MVP-005 | dead-letter event の検出と admin 救済 | #12 | notifier / admin-cli / outbox | M7 |
| SC-MVP-006 | secret マスキング・TLS・添付安全性 | #14, #15, #16 | persistence-foundation / attachment-delivery / network | M6 |
| SC-MVP-007 | Admin CLI 操作の audit_log 記録 | #13 | admin-cli / audit-log | M6 |
| SC-MVP-008 | `just check-all` 緑（開発フロー） | #10 | dev-workflow | M1（既起票済み） |

詳細シナリオは各 SC ファイルを参照。本 PR では **SC-MVP-001 のみフル展開** してテンプレートとして凍結し、残り 7 件は M6/M7 で起票する。

### Phase 2 以降

未起票。ロードマップ確定時に追加。Phase 2 で見込まれるシナリオ候補（参考、未確定）:

- `SC-P2-NNN`: 雑談 Room / アシスタント Room / ブログ編集部 Room の業務シナリオ（ai-team から移植）
- `SC-P2-NNN`: マルチプロバイダ（Codex / Gemini）でのフォールバック動作
- `SC-P2-NNN`: ピクセルアート UI の操作可能性（Playwright）

## シナリオの書き方

各シナリオファイルは以下の構造を持つ:

1. **ペルソナと前提**: シナリオを実行する観察主体（CEO / Owner Reviewer / etc.）と起動状態
2. **業務シナリオ**: ペルソナの業務行為の連続（番号付きステップ）
3. **観察可能事象**: 各ステップで観察される事象（UI / CLI / DB / 外部 API）
4. **カバーする受入基準**: `mvp-scope.md §受入基準` への紐付け
5. **関連 feature**: 各ステップで動く feature の `system-test-design.md` への参照
6. **検証手段**: 自動テスト（pytest / Playwright）か手動オペレーションか
7. **想定実装ファイル**: M7 起票時の実装パス
8. **カバレッジ基準と未決課題**

詳細は [`scenarios/SC-MVP-001-vmodel-fullflow.md`](scenarios/SC-MVP-001-vmodel-fullflow.md) をテンプレートとする。

## 起票タイミング規律

- 受入テストは **MVP M6 / M7** で実装される（M6: 横断機能、M7: Vモデル E2E フロー）
- 設計文書（本ディレクトリ）は **M1 段階で先に凍結** し、各 feature が「うちの feature の責務外」として越権する経路を断つ
- シナリオの新規起票・修正は CODEOWNERS（`@kkm-horikawa`）レビュー必須

## 受入基準カバレッジ表

`mvp-scope.md §受入基準 #1〜#16` がすべて少なくとも 1 シナリオでカバーされていることを担保する:

| #  | 受入基準（要旨） | カバーシナリオ |
|----|----------------|------------|
| 1  | UI から Empire / Room / Agent / Workflow を CRUD | SC-MVP-001 |
| 2  | プリセットから Vモデル開発室を 1 クリック作成 | SC-MVP-001 |
| 3  | `$` directive で Task 起票 | SC-MVP-001 |
| 4  | Stage 遷移時に Agent が deliverable 生成 | SC-MVP-001 |
| 5  | EXTERNAL_REVIEW で Discord 通知 + UI 承認 | SC-MVP-001 |
| 6  | 差し戻しで前段 Stage に戻り、複数ラウンド履歴保持 | SC-MVP-002 |
| 7  | 全 Stage APPROVED で Task DONE | SC-MVP-001 |
| 8  | 再起動後も全状態が SQLite から復元 | SC-MVP-003 |
| 9  | WebSocket でリアルタイム更新 | SC-MVP-001 |
| 10 | `just check-all` がローカル / CI 双方で緑 | SC-MVP-008 |
| 11 | LLM Adapter 復旧不能エラー → BLOCKED → admin 救済 | SC-MVP-004 |
| 12 | Notifier 失敗 → dead-letter → admin 救済 | SC-MVP-005 |
| 13 | Admin CLI 操作が audit_log に記録、DELETE 拒否 | SC-MVP-007 |
| 14 | 添付の filename / MIME / サイズ拒否 | SC-MVP-006 |
| 15 | LLM stdout / stderr の secret 伏字化 | SC-MVP-006 |
| 16 | `127.0.0.1:8000` のみバインド、reverse proxy 制御 | SC-MVP-006 |
| 17 | 内部レビュー全 GateRole APPROVED で外部レビュー到達 | SC-MVP-001（Step 3.5） |
| 18 | 内部レビュー REJECTED で前段差し戻し | SC-MVP-001（Step 3.5） |

孤児受入基準（カバーシナリオなし）はゼロ。

## 関連設計書

- [`docs/requirements/acceptance-criteria.md`](../requirements/acceptance-criteria.md) — MVP 受入基準の真実源
- [`docs/requirements/use-cases.md`](../requirements/use-cases.md) — 主要ユースケースのシーケンス図（SC-MVP-001 の根拠）
- [`docs/design/threat-model.md`](../design/threat-model.md) — セキュリティ受入基準（SC-MVP-006 の根拠）
- [`docs/features/`](../features/) — 各 feature の Vモデル設計書（feature 業務概念単位の system-test-design.md を持つ）
