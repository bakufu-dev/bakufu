# 業務仕様書（feature-spec）— Empire

> feature: `empire`（業務概念単位）
> sub-features: [`domain/`](domain/) | [`repository/`](repository/) | [`http-api/`](http-api/) | ui（将来）
> 関連 Issue: [#8 feat(empire): Empire Aggregate Root (M1)](https://github.com/bakufu-dev/bakufu/issues/8) / [#25 feat(empire-repository): Empire SQLite Repository (M2)](https://github.com/bakufu-dev/bakufu/issues/25) / [#56 feat(empire-http-api): Empire HTTP API (M3-B)](https://github.com/bakufu-dev/bakufu/issues/56)
> 凍結済み設計: [`docs/design/domain-model/aggregates.md`](../../design/domain-model/aggregates.md) §Empire

## 本書の役割

本書は **Empire という業務概念全体の業務仕様** を凍結する。bakufu 全体の要求分析（[`docs/analysis/`](../../analysis/)）を Empire という業務概念で具体化し、ペルソナ（個人開発者 CEO）から見て **観察可能な業務ふるまい** を実装レイヤー（domain / repository / http-api / ui）に依存せず定義する。Vモデル正規工程では **要件定義（業務）** 相当（システムテスト ↔ [`system-test-design.md`](system-test-design.md)）。

各 sub-feature（[`domain/`](domain/) / [`repository/`](repository/) / 将来の http-api / ui）は本書を **業務根拠の真実源** として参照する。各 sub-feature は本書の業務ルール R1-X を実装方針 §確定 A〜Z として展開し、本書には逆流させない（本書の更新は別 PR で先行する）。

**書くこと**:
- ペルソナ（CEO）が Empire という業務概念で達成できるようになる行為（ユースケース）
- 業務ルール（重複拒否・容量上限・履歴保持・永続性 等、すべての sub-feature を貫く凍結）
- E2E で観察可能な事象としての受入基準（業務概念全体）
- sub-feature 間の責務分離マップ（実装レイヤー対応）

**書かないこと**（sub-feature の設計書へ追い出す）:
- 採用技術スタック（Pydantic / SQLAlchemy / FastAPI 等） → sub-feature の `basic-design.md`
- 実装方式の比較・選定議論（pre-validate / delete-then-insert / TypeDecorator 等） → sub-feature の `detailed-design.md`
- 内部 API 形・メソッド名・属性名・型 → sub-feature の `basic-design.md` / `detailed-design.md`
- sub-feature 内のテスト戦略（IT / UT） → sub-feature の `test-design.md`（E2E のみ親 [`system-test-design.md`](system-test-design.md) で扱う）

## 1. この feature の位置付け

bakufu インスタンスの最上位コンテナ「Empire」を、ペルソナ（個人開発者 CEO）が組織として運用できる業務概念として定義する。Empire は CEO が建てる **唯一の組織コンテナ** であり、Agent（役割）と Room（部署）の編成所在を保持する。

Empire の業務的なライフサイクルは複数の実装レイヤーを跨ぐ:

| レイヤー | sub-feature | 業務観点での役割 |
|---|---|---|
| domain | [`domain/`](domain/) | 組織の構造的整合性（重複なし、命名ルール、容量）を Aggregate 内で保証 |
| repository | [`repository/`](repository/) | 組織の状態を再起動跨ぎで保持（永続化）、CEO は永続化を意識せず観察可能 |
| http-api | [`http-api/`](http-api/) | CEO が HTTP 経由で Empire を CRUD・アーカイブする経路（UC-EM-001, 008〜010）|
| ui | (将来) | CEO が組織を直感的に編成する画面 |

本書はこれら全レイヤーを貫く **業務概念単位の凍結文書** であり、各 sub-feature は本書を引用して実装契約を凍結する。

## 2. 人間の要求

> Issue #8（M1 domain）:
>
> bakufu MVP（v0.1.0）M1「ドメイン骨格」の一環として **Empire Aggregate Root** を実装する。Empire は bakufu インスタンスの最上位ドメインオブジェクトで、Room / Agent の編成所在を保持するシングルトン Aggregate。

> Issue #25（M2 repository）:
>
> bakufu MVP（v0.1.0）M2「SQLite 永続化」の **最初の Aggregate Repository PR** として **Empire Repository** を実装する。再起動後も Empire / Room / Agent / Task / Gate の状態が SQLite から復元される受入基準を満たす経路を確立する。

## 3. 背景・痛点

### 現状の痛点

1. CEO が「組織を建てる」最初の一歩を表現する業務オブジェクトが存在しない。後続 feature（Room / Agent / Task）が編成所在を参照できない
2. CEO がアプリを再起動するたびに組織状態が消える経路では、業務として成立しない（組織は持続的な概念）
3. 「組織の整合性違反（重複・容量超過・命名違反）」を CEO がアプリ再起動後に発見する運用は許容できない（domain 層と永続化層で整合性が分離して観察される事象になる）

### 解決されれば変わること

- CEO が組織を 1 つ建てて、そこに役割（Agent）と部署（Room）を編成できるようになる
- 編成した組織状態がアプリ再起動を跨いで保持される（CEO は永続化を意識しない）
- 組織の整合性違反は **業務エラーとして即時に拒否される**（domain 層 → 永続化層の経路全体で一貫した観察）

### ビジネス価値

- bakufu MVP の最初のユースケース（CEO 組織構築）を実現する基盤
- 再起動跨ぎでの組織状態保持により、bakufu が「使い捨てツール」ではなく「継続的な組織運営ツール」として成立

## 4. ペルソナ

| ペルソナ名 | 役割 | 観察主体 | 達成したいゴール |
|-----------|------|---------|---------------|
| 個人開発者 CEO | bakufu インスタンスのオーナー | 直接（将来の UI 経由） / 間接（domain・repository sub-feature では application 層経由） | 組織を 1 つ建て、Agent 採用 / Room 設立を直感的に編成し、再起動跨ぎで状態が保持される |

bakufu システム全体ペルソナは [`docs/analysis/personas.md`](../../analysis/personas.md) を参照。

各 sub-feature の観察主体は本ペルソナの行為が実装レイヤーで観察される形であり、sub-feature 側で観察主体の屈折説明（"CEO は domain 層を直接操作しないが application 層経由で観察する"）を繰り返す必要はない。

## 5. ユースケース

| UC ID | ペルソナ | ユーザーストーリー | 優先度 | 主担当 sub-feature |
|-------|---------|-----------------|-------|------|
| UC-EM-001 | CEO | 新しい組織コンテナ（Empire）を 1 つ建てられる | 必須 | domain |
| UC-EM-002 | CEO | 組織に役割（Agent）を採用できる、同じ役割は二重に採用されない | 必須 | domain |
| UC-EM-003 | CEO | 組織に部署（Room）を設立できる、同じ部署は二重に設立されない | 必須 | domain |
| UC-EM-004 | CEO | 部署をアーカイブできる、アーカイブ済みでも履歴は残る（監査可能性） | 必須 | domain |
| UC-EM-005 | CEO | 業務ルール違反（重複・容量・名前範囲）の操作が拒否され、組織状態は変化しない | 必須 | domain |
| UC-EM-006 | CEO | 編成した組織状態がアプリ再起動を跨いで保持される（永続化を意識しない） | 必須 | repository |
| UC-EM-007 | CEO | 同 bakufu インスタンスに Empire は 1 つしか存在しない（複数組織は業務モデル外） | 必須 | repository（count 提供）+ 将来 application/empire-service（強制） |
| UC-EM-008 | CEO | HTTP 経由で Empire の現在状態（name / rooms / agents / archived）を取得したい | 必須 | http-api |
| UC-EM-009 | CEO | HTTP 経由で Empire の名前を更新したい | 必須 | http-api |
| UC-EM-010 | CEO | HTTP 経由で Empire を論理削除（アーカイブ）したい | 必須 | http-api |

## 6. スコープ

### In Scope

- Empire 業務概念全体で観察可能な業務ふるまい（UC-EM-001〜010）
- ふるまいの呼び出し失敗時に観察される拒否シグナル（業務ルール違反）
- 業務概念単位の E2E 検証戦略 → [`system-test-design.md`](system-test-design.md)
- HTTP 経由での Empire CRUD・アーカイブ操作（UC-EM-001 HTTP 経路 / UC-EM-008〜010）→ [`http-api/`](http-api/)

### Out of Scope（参照）

- Empire の管理 UI → 将来の `empire/ui/` sub-feature
- Empire の管理 CLI → 別 feature `feature/admin-cli`（横断的）
- Room / Agent / Task の実体 → `feature/room` / `feature/agent` / `feature/task`（業務概念として独立）
- 永続化基盤の汎用責務（WAL / マイグレーション / masking gateway） → [`feature/persistence-foundation`](../persistence-foundation/)（横断的）
- 「Empire は 1 つ」の application 層強制 → 将来の `feature/empire-service`（domain と repository の合間に位置）

## 7. 業務ルールの確定（要求としての凍結）

### 確定 R1-1: 組織名は 1〜80 文字、空白のみは無効

**理由**: CEO が認識可能な表示名であること、UI 上の表示破綻を起こさないこと。bakufu の UI 設計（将来の `empire/ui/`）における名前カラムの想定幅 80 文字に合わせる。

文字数の正規化規約（NFC / strip / Unicode コードポイント数）の詳細は [`domain/detailed-design.md §確定 B`](domain/detailed-design.md) で実装方針として展開する。

### 確定 R1-2: 同じ役割（Agent）は二重に採用されない

**理由**: CEO が「役割の重複」に気付かず編成すると、業務上の責任分担が曖昧になり、後段の監査ログで「どの Agent が出した directive か」を追跡できなくなる。重複は業務エラーとして即時に拒否する。

### 確定 R1-3: 同じ部署（Room）は二重に設立されない

**理由**: 同上。部署名の重複は監査ログで「どの部署に発生した出来事か」を追跡できなくなる。

### 確定 R1-4: アーカイブされた部署は物理削除しない

**理由**: 監査可能性。過去に存在した部署の履歴を `audit_log`（後段 feature）から参照する際、物理削除すると `room_id` が解決できなくなる。アーカイブは「論理削除フラグ + 履歴保持」とする。

復元 UI は将来の `empire/ui/` Phase 2 で扱う。

### 確定 R1-5: bakufu インスタンスにつき Empire は 1 つ

**理由**: bakufu の起動モデル（個人 = 1 インスタンス = 1 組織）。複数 Empire は本 MVP の業務モデル外。

実装責務分離: Aggregate 内（domain）では「Empire 自身は他の Empire を知らない」、Repository（repository）が `count()` を提供、最終的な強制は将来の `feature/empire-service`（application 層）。詳細は [`domain/detailed-design.md §確定事項`](domain/detailed-design.md) / [`repository/detailed-design.md §確定 R1-D`](repository/detailed-design.md) を参照。

### 確定 R1-6: 役割数 / 部署数の容量上限

**理由**: 個人 CEO の運用想定規模（同時編成 100 件）を超える編成は「業務的に妥当でない」と判定し、業務エラーとして即時に拒否する。後段の運用実績を見て調整可能。

具体的な上限値（100）の凍結は [`domain/detailed-design.md §確定 C`](domain/detailed-design.md)。

### 確定 R1-7: 組織状態は再起動跨ぎで保持される

**理由**: 組織は持続的な業務概念であり、アプリ再起動による状態消失は業務として許容できない。永続化は CEO から意識されない透明な責務。

実装方針（SQLite 永続化、delete-then-insert 戦略、Alembic マイグレーション）は [`repository/detailed-design.md §確定 R1-A〜F`](repository/detailed-design.md) で展開する。

### 確定 R1-8: Empire の論理削除は `archived = True` フラグで管理する

**理由**: 業務ルール R1-4（Room は物理削除しない）と一貫した監査可能性の確保。Empire 消滅後も `audit_log`（将来 feature）から Empire への参照が解決できる必要がある。アーカイブ済み Empire への PATCH 操作は業務エラーとして 409 Conflict で拒否する（中途半端な変更履歴を作らない）。

## 8. 制約・前提

| 区分 | 内容 |
|-----|------|
| 既存運用規約 | GitFlow / Conventional Commits（[`CONTRIBUTING.md`](../../../CONTRIBUTING.md)） |
| ライセンス | MIT |
| 対象 OS | Windows 10 21H2+ / macOS 12+ / Linux glibc 2.35+ |
| ネットワーク | 該当なし — Empire 業務概念は外部通信を持たない（永続化はローカル SQLite） |
| 依存 feature | M1 開始時点: chore #7 マージ済み / M2 開始時点: M1 `empire/domain` + [`feature/persistence-foundation`](../persistence-foundation/) マージ済み |

実装技術スタック（Python 3.12 / Pydantic v2 / SQLAlchemy 2.x async / Alembic / pyright strict / pytest）は各 sub-feature の `basic-design.md §依存関係` に集約する。

## 9. 受入基準（観察可能な事象）

| # | 基準 | 紐付く UC | 検証方法 |
|---|------|---------|---------|
| 1 | 新しい Empire が valid な状態で構築でき、その後の操作（採用 / 設立 / アーカイブ）の出発点になる | UC-EM-001 | TC-IT-EM-domain-001 |
| 2 | 名前が業務ルール R1-1（1〜80 文字、空白のみ無効）に違反する Empire は構築できない | UC-EM-005 | TC-UT-EM-domain-002, 003 |
| 3 | Agent を採用すると、それ以降「採用済み」として観察できる | UC-EM-002 | TC-UT-EM-domain-004, 005 |
| 4 | 既に採用済みの Agent を再採用すると、業務ルール R1-2 違反として拒否され、既存編成は変化しない | UC-EM-002 | TC-UT-EM-domain-006, 014 |
| 5 | Room を設立すると、それ以降「設立済み」として観察できる | UC-EM-003 | TC-UT-EM-domain-008 |
| 6 | 既に設立済みの Room を再設立すると、業務ルール R1-3 違反として拒否され、既存編成は変化しない | UC-EM-003 | TC-UT-EM-domain-009, 015 |
| 7 | アーカイブ済みの Room は archived フラグが立つが、編成リストから消えない（業務ルール R1-4） | UC-EM-004 | TC-UT-EM-domain-011, 013 |
| 8 | 存在しない Room をアーカイブしようとすると拒否され、既存編成は変化しない | UC-EM-004 | TC-UT-EM-domain-012, 016 |
| 9 | 役割数 / 部署数が業務ルール R1-6 の上限（100）を超える編成は拒否され、既存編成は変化しない | UC-EM-005 | TC-UT-EM-domain-007, 010 |
| 10 | 編成した組織状態がアプリ再起動跨ぎで保持される（業務ルール R1-7、構造的等価で復元） | UC-EM-006 | TC-E2E-EM-001（[`system-test-design.md`](system-test-design.md)） |
| 11 | 同 bakufu インスタンスで Empire を 2 つ目を建てようとすると、業務ルール R1-5 違反として拒否される | UC-EM-007 | TC-E2E-EM-002（強制責務は将来 `feature/empire-service`、暫定は repository.count() で観察） |
| 12 | `POST /api/empires` が HTTP 201 と `EmpireResponse` を返す | UC-EM-001（HTTP 経路）| TC-IT-EM-HTTP-001 |
| 13 | `POST /api/empires` で Empire が既に存在する場合 HTTP 409 と `{"error": {"code": "conflict", ...}}` を返す | UC-EM-007 | TC-IT-EM-HTTP-002 |
| 14 | `GET /api/empires` が HTTP 200 と `EmpireListResponse` を返す（0 件 / 1 件）| UC-EM-008 | TC-IT-EM-HTTP-003 |
| 15 | `GET /api/empires/{id}` が HTTP 200 と `EmpireResponse` を返す | UC-EM-008 | TC-IT-EM-HTTP-004 |
| 16 | `GET /api/empires/{存在しない id}` が HTTP 404 と `{"error": {"code": "not_found", ...}}` を返す | UC-EM-008 | TC-IT-EM-HTTP-005 |
| 17 | `PATCH /api/empires/{id}` が HTTP 200 と更新済み `EmpireResponse` を返す | UC-EM-009 | TC-IT-EM-HTTP-006 |
| 18 | アーカイブ済み Empire への `PATCH` が HTTP 409 と `{"error": {"code": "conflict", ...}}` を返す（業務ルール R1-8）| UC-EM-009 | TC-IT-EM-HTTP-007 |
| 19 | `DELETE /api/empires/{id}` が HTTP 204 を返し、以降の GET で `archived = true` が観察できる | UC-EM-010 | TC-IT-EM-HTTP-008 |
| 20 | `DELETE /api/empires/{存在しない id}` が HTTP 404 と `{"error": {"code": "not_found", ...}}` を返す | UC-EM-010 | TC-IT-EM-HTTP-009 |

E2E（受入基準 10, 11）は [`system-test-design.md`](system-test-design.md) で詳細凍結。受入基準 1〜9 は domain sub-feature の IT / UT で検証（[`domain/test-design.md`](domain/test-design.md)）。受入基準 12〜20 は http-api sub-feature の結合テスト（[`http-api/test-design.md`](http-api/test-design.md)）で検証。

## 10. 開発者品質基準（CI 担保、業務要求ではない）

各 sub-feature の `basic-design.md §モジュール契約` / `test-design.md §カバレッジ基準` で個別に管理する。本書では業務要求のみ凍結。

参考: domain は `domain/empire.py` カバレッジ 95% 以上、repository は実装ファイル群で 90% 以上を目標としているが、これは sub-feature 側の凍結事項。

## 11. 開放論点 (Open Questions)

凍結時点で未確定の論点はなし — R1 レビューで全件凍結済み。確定 R1-1〜7 として §7 に集約。

## 12. sub-feature 一覧とマイルストーン整理

[`README.md`](README.md) を参照。

## 13. 扱うデータと機密レベル

| 区分 | 内容 | 機密レベル |
|-----|------|----------|
| Empire.name | bakufu インスタンスの表示名（例: "山田の幕府"） | 低（CEO 任意の文字列、機密性なし） |
| RoomRef / AgentRef | Room / Agent の参照（id + 表示用 name） | 低 |
| 永続化テーブル群（empires / empire_room_refs / empire_agent_refs） | 上記の永続化先、masking 対象なし | 低 |

## 14. 非機能要求

| 区分 | 要求 |
|-----|------|
| パフォーマンス | 業務ふるまい呼び出しの応答が CEO 視点で「即時」（数 ms 以内）と感じられること。MVP 想定規模（容量上限 100）で domain 層 1ms 未満、永続化層 50ms 未満を目標 |
| 可用性 | 永続化層の WAL モード + crash safety（[`feature/persistence-foundation`](../persistence-foundation/) 担保）により、書き込み中のクラッシュでも組織状態が破損しない |
| 可搬性 | 純 Python のみ。OS / ファイルシステム依存なし（SQLite はクロスプラットフォーム） |
| セキュリティ | 業務ルール違反は早期に拒否される（Fail Fast）。中途半端な状態は持ち越されない（変更失敗時、組織状態は呼び出し前と同一）。Empire 関連カラムは masking 対象なし（[`feature/persistence-foundation`](../persistence-foundation/) §逆引き表） |
