# `_template/` — Vモデル 5 設計書のひな形

bakufu の新 feature を起こす際に、本ディレクトリ全体を **コピー先 `docs/features/<feature-name>/` として複製**して使う。

## 使い方

```bash
# 新 feature の設計開始時
NAME=empire-aggregate
cp -r docs/features/_template docs/features/$NAME
```

その後、5 ファイルを **順に** 書く（V モデルの上から下へ）：

| 順 | ファイル | 役割 | 着手タイミング |
|----|----|----|----|
| 1 | `requirements-analysis.md` | 人間の要求 → 痛点 → 議論結果 → ペルソナ → 機能一覧 → 受入基準 | feature 起票直後 |
| 2 | `requirements.md` | REQ-XX-NNN を入力/処理/出力/エラー時で詳細化 + MSG-XX-NNN 一覧 | requirements-analysis.md がオーナー承認後 |
| 3 | `basic-design.md` | モジュール構成 + クラス概要 + 処理フロー + シーケンス + 脅威モデル | requirements.md がオーナー承認後 |
| 4 | `detailed-design.md` | 構造契約詳細 + MSG 確定文言 + キー構造 + API 詳細 | basic-design.md がオーナー承認後 |
| 5 | `test-design.md` | テストマトリクス + E2E / 結合 / ユニットテストケース | detailed-design.md と並行作成可 |

## ファイル単位の規律

- **基本設計と詳細設計は別ファイル**。統合禁止
- **疑似コード・サンプル実装（言語コードブロック）を設計書に書くな**。ソースと二重管理になる
- 図は **mermaid** に統一（classDiagram / sequenceDiagram / erDiagram / flowchart）
- 設計書の更新は別 PR（`feature/<name>-design`）→ 実装 PR（`feature/<name>`）の二段で

## ID 命名規則

| プレフィックス | 用途 |
|----|----|
| `REQ-XX-NNN` | 機能要件（XX は feature 略号 2 文字、NNN は 3 桁連番） |
| `MSG-XX-NNN` | ユーザー向けメッセージ |
| `TC-UT-NNN` | ユニットテストケース |
| `TC-IT-NNN` | 結合テストケース |
| `TC-E2E-NNN` | E2E テストケース |
| `TBD-N` | 要起票 characterization task |

feature 略号の例: `EM`（Empire）/ `RM`（Room）/ `WF`（Workflow）/ `AG`（Agent）/ `TS`（Task）/ `RV`（External Review）/ `DW`（Dev Workflow）

## 既存サンプル

完成形の参考: [`docs/features/dev-workflow/`](../dev-workflow/) — bakufu 自身の開発フロー機能の Vモデル 5 ファイル。
