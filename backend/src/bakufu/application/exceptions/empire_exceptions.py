"""Empire アプリケーション層の例外（確定 F）。

これらは、ドメイン層の ``EmpireInvariantViolation`` とは独立したアプリケーション層
レベルの例外である。interfaces 層の例外ハンドラがこれらを捕捉し、HTTP レスポンス
へ変換する。

* :class:`EmpireNotFoundError` — 対象の Empire が存在しない（404）
* :class:`EmpireAlreadyExistsError` — Empire が既に存在する（409, R1-5）
* :class:`EmpireArchivedError` — アーカイブ済み Empire への更新試行（409, R1-8）
"""

from __future__ import annotations


class EmpireNotFoundError(Exception):
    """要求された Empire が存在しないときに送出される。

    ``EmpireService.find_by_id`` がリポジトリから ``None`` を受け取った場合、および
    ``EmpireService.archive`` で同条件のときに送出される。interfaces 層では
    HTTP 404 / ``not_found``（MSG-EM-HTTP-002）に変換される。
    """

    def __init__(self, empire_id: str) -> None:
        super().__init__(f"Empire not found: {empire_id}")
        self.empire_id = empire_id


class EmpireAlreadyExistsError(Exception):
    """``EmpireService.create`` が既存の Empire を検出したときに送出される（R1-5）。

    bakufu の Empire はシングルトンであり、``EmpireRepository.count() > 0`` で
    本例外がトリガされる。interfaces 層では HTTP 409 / ``conflict``
    （MSG-EM-HTTP-001）に変換される。
    """

    def __init__(self) -> None:
        super().__init__("Empire already exists.")


class EmpireArchivedError(Exception):
    """アーカイブ済み Empire に対して更新が試みられたときに送出される（R1-8）。

    ``EmpireService.update`` 内で、フィールド変更を適用する前にチェックされる。
    interfaces 層では HTTP 409 / ``conflict``（MSG-EM-HTTP-003）に変換される。
    """

    def __init__(self, empire_id: str) -> None:
        super().__init__(f"Empire is archived and cannot be modified: {empire_id}")
        self.empire_id = empire_id


__all__ = [
    "EmpireAlreadyExistsError",
    "EmpireArchivedError",
    "EmpireNotFoundError",
]
