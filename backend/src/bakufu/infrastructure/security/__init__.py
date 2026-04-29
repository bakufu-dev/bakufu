"""シークレット マスキング ゲートウェイ。

あらゆる永続化境界（SQLite 行、構造化ログファイル、監査ログ）にシークレット
が到達する *前* に、それらを伏字化する単一の信頼できる出所（SSOT）。
利用者向けに 2 つの API を提供する:

* :func:`bakufu.infrastructure.security.masking.mask` — 単一文字列の
  伏字化。
* :func:`bakufu.infrastructure.security.masking.mask_in` — ``dict`` /
  ``list`` / ``tuple`` ペイロードを再帰的に走査するウォーカ。

配線契約（Confirmation B）は ``infrastructure/persistence/sqlite/tables/``
のテーブルモジュールに記述される。シークレットを保持するカラムを持つ各
テーブルは、それらのカラムを :class:`MaskedJSONEncoded` /
:class:`MaskedText` TypeDecorator（:mod:`bakufu.infrastructure.persistence.sqlite.base`
で定義）で宣言し、Core / ORM のバインドのたびに ``process_bind_param`` が
本ゲートウェイを経由するようにする。イベントリスナがリバース棄却された
理由（BUG-PF-001）は ``docs/features/persistence-foundation/requirements-analysis.md``
§確定 R1-D を参照。
"""
