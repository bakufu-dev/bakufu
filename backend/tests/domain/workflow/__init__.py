"""Workflow 集約のテスト。機能面ごとに分割している（Norman §file-split rule）。

テストは Test* クラスのトポロジでグループ化し、失敗が振る舞い単位で
集約されるようにしている:

* :mod:`test_construction` — 最小 Workflow + name 正規化
* :mod:`test_dag_invariants` — REQ-WF-005（エントリ、到達可能性、シンク、
  決定性、参照整合性、EXTERNAL_REVIEW 通知、required_role）
* :mod:`test_mutators` — add_stage / add_transition / remove_stage + pre-validate ロールバック
* :mod:`test_from_dict` — 一括インポート（REQ-WF-006）。T1 攻撃面を含む
* :mod:`test_frozen_extra` — frozen=True / extra='forbid' の不変条件
* :mod:`test_notify_channel_ssrf` — Confirmation G G1〜G10
* :mod:`test_notify_channel_kind` — MVP `kind='discord'` 制約
* :mod:`test_notify_channel_masking` — シリアライズ経路全般でのトークン秘匿
* :mod:`test_helpers_independence` — Confirmation F 双子防御の直接呼び出し
* :mod:`test_integration` — V モデルプリセット + ライフサイクルラウンドトリップ
* :mod:`test_value_objects` — CompletionPolicy / NotifyChannel / Transition VO 単体
"""
