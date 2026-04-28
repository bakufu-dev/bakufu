# `design/` — 基本設計（Vモデル左 3、階層 1: システム全体）

「**システムをどう構成するか**」を構造契約・採用技術・脅威モデルの観点で凍結する。要件定義（[`../requirements/`](../requirements/)）を実現するためのシステム全体構造を定義する場。

## 階層的位置付け

本ディレクトリは **階層 1: システム全体の基本設計**（System-level Basic Design）。Vモデル の階層的トップダウン分解（System → Module）の上位を担当する。

各 sub-feature の [`features/<feature-name>/<sub-feature>/basic-design.md`](../features/) は、本書で凍結された全体構造を **モジュールレベルに展開した細部の基本設計**（Module-level Basic Design）。両者は Vモデル「基本設計」工程の階層的分解として併存する。命名は同じ「基本設計」だが、対象スコープ（システム全体 / モジュール）で区別される。

## 本ディレクトリの役割

**書くこと**:
- システム全体アーキテクチャ図（レイヤー構成、依存方向）
- ドメインモデル（Aggregate / Entity / VO / Domain Event の関係）
- 採用技術スタックと根拠 / 不採用ツール
- 脅威モデル（信頼境界 / 攻撃面 / OWASP Top 10 対応方針）
- DB マイグレーション計画（将来のスキーマ変更）

**書かないこと**（後段の工程ディレクトリへ追い出す）:
- 各 feature の構造契約詳細 → [`../features/<feature-name>/<sub-feature>/basic-design.md`](../features/)
- 各 feature の実装契約・MSG 確定文言 → [`../features/<feature-name>/<sub-feature>/detailed-design.md`](../features/)

## 所収ファイル

| ファイル | 役割 |
|---|---|
| [`architecture.md`](architecture.md) | システム全体構造（レイヤー / 依存方向 / 主要 Aggregate / 採用技術 / 脅威概観） |
| [`domain-model.md`](domain-model.md) | Aggregate / Entity / VO / Domain Event の関係（DDD） |
| [`tech-stack.md`](tech-stack.md) | 採用技術と根拠 / 不採用ツール |
| [`threat-model.md`](threat-model.md) | 信頼境界 / 攻撃面 / OWASP Top 10 対応方針 |
| [`migration-plan.md`](migration-plan.md) | DB マイグレーション計画（将来の DB 移行 TODO 集約） |

## 対応するテストレベル

基本設計 ↔ **結合テスト**: 各 feature の [`features/<feature-name>/<sub-feature>/test-design.md §結合`](../features/)

## 関連

- [`../requirements/`](../requirements/) — 前工程（要件定義）
- [`../features/`](../features/) — 次工程（詳細設計）
