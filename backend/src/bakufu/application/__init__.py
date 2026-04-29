"""Application 層。

:mod:`bakufu.domain`（純粋な DDD Aggregate）と :mod:`bakufu.infrastructure`
（SQLite / FS / プロセス I/O）の中間に位置する。本層が保有するのは:

* **Ports**（:mod:`bakufu.application.ports`） — infrastructure 層が満たすべき
  :class:`typing.Protocol` 契約。Hexagonal Architecture の "ports and adapters"
  パターン。
* **Services**（後続 PR） — オーケストレーション、Unit-of-Work の協調、
  Aggregate 横断 Tx 境界。

依存方向は **厳格に** ``domain ← application ← infrastructure``。本パッケージは
``domain`` を import してよいが ``infrastructure`` を import してはならない。
``infrastructure`` はここで定義した ports を import して adapter クラスを宣言する。
"""
