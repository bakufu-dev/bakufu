"""Repository ports (one Protocol per Aggregate).

Each Aggregate owns its own :class:`typing.Protocol` file under this
package so:

1. The contract surface of one Aggregate is searchable in isolation.
2. Adding a new Repository for a new Aggregate is a single file diff.
3. The ports stay free of any infrastructure imports — the domain
   types they reference are the same VOs the Aggregate Roots use.

See ``docs/features/empire-repository/detailed-design.md`` §確定 A
(イーロン承認済み, "Repository ポート配置 — Aggregate 別ファイル分離")
for the placement rule. Subsequent ``feature/{aggregate}-repository``
PRs add their own files following the same pattern.
"""
