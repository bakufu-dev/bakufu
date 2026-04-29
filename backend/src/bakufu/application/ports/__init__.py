"""Repository ports（Aggregate ごとに 1 Protocol）。

各 Aggregate は本パッケージ配下に専用の :class:`typing.Protocol` ファイルを保有する。
これにより:

1. ある Aggregate の契約面を単独で検索できる。
2. 新しい Aggregate に対する Repository の追加が単一ファイルの差分で済む。
3. ports は infrastructure の import から完全に分離される —
   参照するドメイン型は Aggregate Root が用いる VO と同一。

配置ルールは ``docs/features/empire-repository/detailed-design.md`` §確定 A
（イーロン承認済み「Repository ポート配置 — Aggregate 別ファイル分離」）を参照。
後続の ``feature/{aggregate}-repository`` PR は同じパターンに従って自身のファイルを
追加する。
"""
