"""Template Library 定数モジュール — WELL_KNOWN_TEMPLATES / PRESET_ROLE_TEMPLATE_MAP。

副作用のない純粋なデータ定数モジュール。import しても DB 接続や I/O は発生しない。
DeliverableTemplate.model_validate() で構築済みの Aggregate インスタンスを保持する。

設計書: docs/features/deliverable-template/template-library/detailed-design.md §確定A〜C
"""

from __future__ import annotations

from uuid import UUID, uuid5

from bakufu.domain.deliverable_template.deliverable_template import DeliverableTemplate
from bakufu.domain.value_objects.enums import Role, TemplateType
from bakufu.domain.value_objects.template_vos import DeliverableTemplateRef, SemVer

# ---------------------------------------------------------------------------
# §確定 C: 変更禁止の固定 UUID 名前空間
# ---------------------------------------------------------------------------
# BAKUFU_TEMPLATE_NS: 全 well-known テンプレートの UUID5 算出に使う名前空間。
# 変更禁止 — 変更すると全テンプレートの UUID が変わり既存 DB レコードと乖離する。
BAKUFU_TEMPLATE_NS: UUID = UUID("ba4a2f00-cafe-1234-dead-beefcafe0001")

# BAKUFU_ROLE_NS: Empire-scope RoleProfile の UUID5 算出に使う名前空間。
# UUID5(BAKUFU_ROLE_NS, f"{empire_id}:{role.value}") で RoleProfile id を生成する。
BAKUFU_ROLE_NS: UUID = UUID("ba4a2f00-cafe-1234-dead-beefcafe0002")

# ---------------------------------------------------------------------------
# 内部: テンプレート構築ヘルパー
# ---------------------------------------------------------------------------
_V100 = {"major": 1, "minor": 0, "patch": 0}


def _build_template(
    slug: str,
    name: str,
    description: str,
    schema: str,
) -> DeliverableTemplate:
    """固定 UUID5 を持つ DeliverableTemplate を構築する（Fail Fast at import）。

    definitions.py の定数が不正な場合は import 時に
    DeliverableTemplateInvariantViolation が発生しプロセスが落ちる。
    """
    return DeliverableTemplate.model_validate(
        {
            "id": uuid5(BAKUFU_TEMPLATE_NS, slug),
            "name": name,
            "description": description,
            "type": TemplateType.MARKDOWN,
            "schema": schema,
            "acceptance_criteria": [],
            "version": _V100,
            "composition": [],
        }
    )


# ---------------------------------------------------------------------------
# §確定 A: WELL_KNOWN_TEMPLATES — 12 件の確定定義（凍結）
# ---------------------------------------------------------------------------
# 全件 MARKDOWN / version 1.0.0 / acceptance_criteria=() / composition=()
# id = UUID5(BAKUFU_TEMPLATE_NS, slug)
# ---------------------------------------------------------------------------
WELL_KNOWN_TEMPLATES: tuple[DeliverableTemplate, ...] = (
    # LEADER (3件)
    _build_template(
        slug="leader-plan",
        name="計画書",
        description="タスクの背景・目標・スコープ・マイルストーンを記述する計画文書。",
        schema=(
            "## 計画書テンプレート\n\n"
            "### 背景\n（タスクが発生した背景・課題を記述）\n\n"
            "### 目標\n（達成すべき成果を明確に記述）\n\n"
            "### スコープ\n（対象範囲と対象外範囲を明記）\n\n"
            "### マイルストーン\n（主要な中間成果物と期日）\n\n"
            "### リスク\n（想定リスクと対応方針）"
        ),
    ),
    _build_template(
        slug="leader-priority",
        name="優先度判定レポート",
        description="複数候補の優先順位を比較根拠とともに記述するレポート。",
        schema=(
            "## 優先度判定レポートテンプレート\n\n"
            "### 評価対象一覧\n（比較する候補を列挙）\n\n"
            "### 評価基準\n（判断に使う基準と重み付け）\n\n"
            "### 比較分析\n（各候補の基準ごとの評価）\n\n"
            "### 判定結果\n（優先順位と根拠の明示）\n\n"
            "### 次のアクション\n（判定を受けた具体的な行動計画）"
        ),
    ),
    _build_template(
        slug="leader-stakeholder",
        name="ステークホルダ報告",
        description="進捗・リスク・決定事項を人間向けに要約する報告文書。",
        schema=(
            "## ステークホルダ報告テンプレート\n\n"
            "### 進捗サマリ\n（全体の進捗状況を一言で）\n\n"
            "### 完了した成果\n（前回報告からの完了事項）\n\n"
            "### リスク・課題\n（現在の懸念点と対応策）\n\n"
            "### 決定事項\n（今期の重要な決定とその根拠）\n\n"
            "### 次期予定\n（次回報告までの計画）"
        ),
    ),
    # DEVELOPER (5件)
    _build_template(
        slug="dev-design",
        name="設計書",
        description="システム設計・データモデル・コンポーネント構成を記述する設計文書。",
        schema=(
            "## 設計書テンプレート\n\n"
            "### 概要\n（変更・追加する機能の概要）\n\n"
            "### アーキテクチャ\n（システム構成・依存関係・レイヤー構造）\n\n"
            "### データモデル\n（主要なクラス・エンティティと関係）\n\n"
            "### 処理フロー\n（主要ユースケースのシーケンス）\n\n"
            "### エラーハンドリング\n（異常系の処理方針）\n\n"
            "### セキュリティ考慮\n（信頼境界・入力検証・認可要件）"
        ),
    ),
    _build_template(
        slug="dev-adr",
        name="ADR",
        description=("Architecture Decision Record — 決定の背景・選択肢・根拠を記録する文書。"),
        schema=(
            "## ADR テンプレート\n\n"
            "### ステータス\n（提案 / 承認 / 廃止 / 置換）\n\n"
            "### コンテキスト\n（この決定が必要になった背景と制約）\n\n"
            "### 検討した選択肢\n（候補として評価した代替案）\n\n"
            "### 決定\n（採用した選択肢と根拠）\n\n"
            "### 影響\n（この決定がもたらすポジティブ・ネガティブな影響）"
        ),
    ),
    _build_template(
        slug="dev-acceptance",
        name="受入条件",
        description="機能の受入基準（Given / When / Then 形式推奨）を記述する文書。",
        schema=(
            "## 受入条件テンプレート\n\n"
            "### 機能概要\n（対象機能の一言説明）\n\n"
            "### 受入基準\n"
            "各基準を以下の形式で記述する:\n\n"
            "- **Given**: （前提条件）\n"
            "  **When**: （操作・イベント）\n"
            "  **Then**: （期待される結果）\n\n"
            "### 対象外\n（スコープに含めない事項を明記）"
        ),
    ),
    _build_template(
        slug="dev-impl-pr",
        name="実装 PR",
        description=("Pull Request の概要・変更点・テスト方法・レビュー観点を記述する文書。"),
        schema=(
            "## 実装 PR テンプレート\n\n"
            "### 変更の概要\n（このPRで何をしたか一言で）\n\n"
            "### 変更内容\n（主要な変更点をリスト形式で）\n\n"
            "### テスト方法\n（変更を手動・自動で確認する手順）\n\n"
            "### レビュー観点\n（レビュアーに特に確認してほしい箇所）\n\n"
            "### 関連 Issue\n（対応する Issue 番号）"
        ),
    ),
    _build_template(
        slug="dev-lib-readme",
        name="ライブラリ README",
        description=("ライブラリの目的・インストール・使用例・API リファレンスを記述する文書。"),
        schema=(
            "## ライブラリ README テンプレート\n\n"
            "### 概要\n（このライブラリが何をするか・なぜ存在するか）\n\n"
            "### インストール\n（パッケージマネージャを使ったインストール手順）\n\n"
            "### クイックスタート\n（最小限の使用例）\n\n"
            "### API リファレンス\n（主要クラス・関数の説明）\n\n"
            "### 設定\n（設定オプションと環境変数）\n\n"
            "### ライセンス\n（ライセンス種別）"
        ),
    ),
    # TESTER (3件)
    _build_template(
        slug="tester-testdesign",
        name="テスト設計書",
        description="テスト戦略・テストケース（TC-XX-NNN）・カバレッジ方針を記述する文書。",
        schema=(
            "## テスト設計書テンプレート\n\n"
            "### テスト戦略\n（テストレベル・テスト方針・リスクベーステスト）\n\n"
            "### テストケース一覧\n"
            "| TC-ID | テスト内容 | 前提条件 | 期待結果 | 優先度 |\n"
            "|-------|----------|---------|---------|--------|\n\n"
            "### カバレッジ基準\n（目標カバレッジ率・計測方法）\n\n"
            "### 除外事項\n（テスト対象外の範囲と理由）"
        ),
    ),
    _build_template(
        slug="tester-report",
        name="テスト結果報告書",
        description=("テスト実施結果・バグ件数・品質メトリクス・品質評価を記述する報告文書。"),
        schema=(
            "## テスト結果報告書テンプレート\n\n"
            "### 実施概要\n（テスト期間・対象バージョン・テスト環境）\n\n"
            "### 結果サマリ\n（総テストケース数・合格・不合格・保留）\n\n"
            "### 品質メトリクス\n（コードカバレッジ・バグ密度・欠陥除去効率）\n\n"
            "### 検出バグ一覧\n（バグID・重要度・ステータス）\n\n"
            "### 品質評価\n（リリース可否の判断と根拠）\n\n"
            "### 残課題\n（未解決事項と次ステップ）"
        ),
    ),
    _build_template(
        slug="tester-regression",
        name="回帰スイート定義",
        description="回帰テスト対象範囲・実行条件・合否基準を記述する文書。",
        schema=(
            "## 回帰スイート定義テンプレート\n\n"
            "### 目的\n（この回帰スイートが守る品質領域）\n\n"
            "### 実行条件\n（トリガー：PR マージ前 / リリース前 / 定期など）\n\n"
            "### 対象スコープ\n（テスト対象のモジュール・機能範囲）\n\n"
            "### テストケース一覧\n（含める TC-ID と除外するケースの理由）\n\n"
            "### 合否基準\n（スイート全体の PASS/FAIL 判定条件）\n\n"
            "### メンテナンス方針\n（新機能追加時のスイート更新ルール）"
        ),
    ),
    # REVIEWER (1件)
    _build_template(
        slug="reviewer-review",
        name="コードレビュー報告",
        description=("コード品質・設計上の問題・改善提案を構造化して記述するレビュー報告文書。"),
        schema=(
            "## コードレビュー報告テンプレート\n\n"
            "### レビュー対象\n（PR / コミット範囲・対象ファイル）\n\n"
            "### 判定\n（合格 / 条件付き合格 / 却下）\n\n"
            "### 重大な指摘\n（ブロッカー：修正必須の問題点）\n\n"
            "### 改善提案\n（推奨される改善点とその根拠）\n\n"
            "### 良かった点\n（認めるべき設計・実装の優れた箇所）\n\n"
            "### 確認事項\n（追加で確認が必要な点）"
        ),
    ),
)

# ---------------------------------------------------------------------------
# §確定 B: PRESET_ROLE_TEMPLATE_MAP — 4 件の確定定義（凍結）
# ---------------------------------------------------------------------------
# Role → DeliverableTemplateRef リスト。minimum_version は全件 1.0.0。
# LEADER / DEVELOPER / TESTER / REVIEWER の 4 Role が対象。
# ---------------------------------------------------------------------------
_REFS: dict[str, DeliverableTemplateRef] = {
    t.id: DeliverableTemplateRef(
        template_id=t.id,
        minimum_version=SemVer(major=1, minor=0, patch=0),
    )
    for t in WELL_KNOWN_TEMPLATES
}

# slug → id のマッピングを構築して参照しやすくする
_SLUG_TO_ID: dict[str, object] = {
    slug: uuid5(BAKUFU_TEMPLATE_NS, slug)
    for slug in (
        "leader-plan",
        "leader-priority",
        "leader-stakeholder",
        "dev-design",
        "dev-adr",
        "dev-acceptance",
        "dev-impl-pr",
        "dev-lib-readme",
        "tester-testdesign",
        "tester-report",
        "tester-regression",
        "reviewer-review",
    )
}


def _ref(slug: str) -> DeliverableTemplateRef:
    return DeliverableTemplateRef(
        template_id=_SLUG_TO_ID[slug],  # type: ignore[arg-type]
        minimum_version=SemVer(major=1, minor=0, patch=0),
    )


PRESET_ROLE_TEMPLATE_MAP: dict[Role, list[DeliverableTemplateRef]] = {
    Role.LEADER: [
        _ref("leader-plan"),
        _ref("leader-priority"),
        _ref("leader-stakeholder"),
    ],
    Role.DEVELOPER: [
        _ref("dev-design"),
        _ref("dev-adr"),
        _ref("dev-acceptance"),
        _ref("dev-impl-pr"),
        _ref("dev-lib-readme"),
    ],
    Role.TESTER: [
        _ref("tester-testdesign"),
        _ref("tester-report"),
        _ref("tester-regression"),
    ],
    Role.REVIEWER: [
        _ref("reviewer-review"),
    ],
}

__all__ = [
    "BAKUFU_ROLE_NS",
    "BAKUFU_TEMPLATE_NS",
    "PRESET_ROLE_TEMPLATE_MAP",
    "WELL_KNOWN_TEMPLATES",
]
