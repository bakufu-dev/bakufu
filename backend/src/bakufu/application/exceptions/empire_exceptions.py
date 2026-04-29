"""Empire application-layer exceptions (確定 F).

These are application-level exceptions, independent of domain-layer
``EmpireInvariantViolation``. The interfaces layer's exception handlers
catch these and convert them to HTTP responses.

* :class:`EmpireNotFoundError` — target Empire not found (404)
* :class:`EmpireAlreadyExistsError` — Empire already exists (409, R1-5)
* :class:`EmpireArchivedError` — update attempted on archived Empire (409, R1-8)
"""

from __future__ import annotations


class EmpireNotFoundError(Exception):
    """Raised when the requested Empire does not exist.

    Raised by ``EmpireService.find_by_id`` when the repository returns
    ``None``, and by ``EmpireService.archive`` on the same condition.
    The interfaces layer converts this to HTTP 404 / ``not_found``
    (MSG-EM-HTTP-002).
    """

    def __init__(self, empire_id: str) -> None:
        super().__init__(f"Empire not found: {empire_id}")
        self.empire_id = empire_id


class EmpireAlreadyExistsError(Exception):
    """Raised when ``EmpireService.create`` detects an existing Empire (R1-5).

    Bakufu's Empire is a singleton; ``EmpireRepository.count() > 0``
    triggers this. The interfaces layer converts it to HTTP 409 /
    ``conflict`` (MSG-EM-HTTP-001).
    """

    def __init__(self) -> None:
        super().__init__("Empire already exists.")


class EmpireArchivedError(Exception):
    """Raised when an update is attempted on an archived Empire (R1-8).

    Checked in ``EmpireService.update`` before applying any field change.
    The interfaces layer converts this to HTTP 409 / ``conflict``
    (MSG-EM-HTTP-003).
    """

    def __init__(self, empire_id: str) -> None:
        super().__init__(f"Empire is archived and cannot be modified: {empire_id}")
        self.empire_id = empire_id


__all__ = [
    "EmpireAlreadyExistsError",
    "EmpireArchivedError",
    "EmpireNotFoundError",
]
