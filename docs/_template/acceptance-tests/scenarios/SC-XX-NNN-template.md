# SC-XX-NNN: \<シナリオ名: 業務シナリオの簡潔な記述\>

> シナリオ ID: `SC-XX-NNN`
> マイルストーン: \<例: MVP M7 / Phase 2 等\>
> カバーする受入基準: [`acceptance-criteria.md`](../../requirements/acceptance-criteria.md) #N, #M, ...
> 戦略: [`../README.md`](../README.md)
> ステータス: \<設計済 / 実装中 / 完了\>

## 1. ペルソナと前提

| 区分 | 内容 |
|---|---|
| ペルソナ | \<例: プライマリペルソナ\>（[`personas.md §A`](../../analysis/personas.md)） |
| 観察主体 | \<例: ペルソナ自身（直接観察）+ ...\> |
| 環境 | \<起動済みシステム / 認証済み外部 API / 等\> |
| 起動状態 | \<初期データ状態\> |

## 2. 業務シナリオ

### Step 1: \<ステップ名\>

**観察主体の操作**:
1. \<UI 操作 / CLI 入力 / API 呼び出し\>
2. \<次の操作\>

**観察可能事象**:
- \<UI 表示 / DB 状態 / 外部 API レスポンス\>
- \<WebSocket イベント / Discord 通知 等\>

**カバー受入基準**: #N, #M

### Step 2: \<次のステップ名\>

**観察主体の操作**:
1. ...

**観察可能事象**:
- ...

**カバー受入基準**: #N

### Step 3: \<さらに次のステップ\>

...

## 3. 関連 feature の system-test-design.md

各 feature の `system-test-design.md` は本シナリオで観察される事象のうち feature 内に閉じる部分を担保する。本シナリオは feature 跨ぎの統合観察を担当する。

| Step | 関連 feature | 関連 system-test-design |
|---|---|---|
| Step 1 | \<feature-name 1\> | `features/<feature-name-1>/system-test-design.md` |
| Step 2 | \<feature-name 2\> | `features/<feature-name-2>/system-test-design.md` |
| Step 3 | \<feature-name 3\> | `features/<feature-name-3>/system-test-design.md` |

## 4. 検証手段

| 観点 | 採用方法 |
|---|---|
| UI 操作 | \<Playwright / Selenium / 手動\> |
| Backend API | \<pytest + httpx / curl / 等\> |
| 外部 API | \<Mock サーバ / fake adapter / 専用テスト環境\> |
| 永続化 | \<実 DB（テスト用 tempfile）/ 等\> |

## 5. 想定実装ファイル

```
backend/tests/acceptance/
└── test_sc_xx_nnn_<scenario_slug>.py     # 本シナリオの自動化
frontend/tests/e2e/
└── sc-xx-nnn-<scenario-slug>.spec.ts     # UI 部分（Playwright 等）
```

実装方針:
- \<バックエンド経由の駆動方法\>
- \<UI 操作の検証方法\>
- \<外部 API の Mock 戦略\>

## 6. カバレッジ基準

- 本シナリオの全ステップが自動テストでカバーされる
- `acceptance-criteria.md` の受入基準 #N, #M, ... の各々がシナリオ内で観察される
- 本シナリオで観察できない受入基準は別シナリオ（SC-XX-NNN-...）で担保

## 7. 未決課題（実装時に解決）

- \<未決課題 1: 例 - 外部 API のテストモード実装\>
- \<未決課題 2: 例 - UI と Backend テストの統合\>
- \<未決課題 3\>

## 8. 関連設計書

- [`../../requirements/acceptance-criteria.md`](../../requirements/acceptance-criteria.md) §受入基準
- [`../../requirements/use-cases.md`](../../requirements/use-cases.md) — 主要ユースケース
- [`../README.md`](../README.md) — 受入テスト戦略
