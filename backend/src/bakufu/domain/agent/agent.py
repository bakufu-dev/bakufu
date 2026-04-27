"""Agent Aggregate Root (REQ-AG-001〜006).

Implements per ``docs/features/agent``. The aggregate dispatches over five
helpers in :mod:`bakufu.domain.agent.aggregate_validators` and delegates
SkillRef.path traversal defense (H1〜H10) to
:mod:`bakufu.domain.agent.path_validators`.

Design contracts:

* **Pre-validate rebuild (Confirmation A)** — ``set_default_provider`` /
  ``add_skill`` / ``remove_skill`` / ``archive`` all go through
  :meth:`Agent._rebuild_with` (``model_dump → swap → model_validate``).
* **NFC pipeline (Confirmation E)** — ``Agent.name`` reuses the empire /
  workflow ``nfc_strip`` helper. Length judgement happens in the model
  validator so the resulting :class:`AgentInvariantViolation` carries
  ``kind='name_range'`` with MSG-AG-001 wording.
* **archive idempotency (Confirmation D)** — ``archive()`` always returns a
  *new* instance. Idempotency means "result state matches", not "object
  identity". Pydantic v2 frozen + ``model_validate`` rebuild guarantees this
  by construction; the docstring/tests document the contract so users do not
  rely on ``is`` comparisons.
* **provider_kind MVP gate (Confirmation I)** — *not* implemented in the
  aggregate. ``AgentService.hire()`` (a Phase-2 application service) is the
  responsibility owner; the aggregate trusts that the enum value is well
  formed and lets the service decide whether the Adapter exists.
"""

from __future__ import annotations

from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from bakufu.domain.agent.aggregate_validators import (
    _validate_default_provider_count,
    _validate_provider_capacity,
    _validate_provider_kind_unique,
    _validate_skill_capacity,
    _validate_skill_id_unique,
)
from bakufu.domain.agent.value_objects import (
    Persona,
    ProviderConfig,
    SkillRef,
)
from bakufu.domain.exceptions import AgentInvariantViolation
from bakufu.domain.value_objects import (
    AgentId,
    ProviderKind,
    Role,
    SkillId,
    nfc_strip,
)

# Confirmation E: name length bounds (1〜40 after NFC + strip).
MIN_NAME_LENGTH: int = 1
MAX_NAME_LENGTH: int = 40


class Agent(BaseModel):
    """Hireable LLM agent owned by an :class:`Empire`."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: AgentId
    name: str
    persona: Persona
    role: Role
    providers: list[ProviderConfig]
    skills: list[SkillRef] = []
    archived: bool = False

    # ---- pre-validation -------------------------------------------------
    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        return nfc_strip(value)

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        """Dispatch over the aggregate-level helpers in deterministic order.

        Order: name range → provider capacity / uniqueness / default count
        → skill capacity / uniqueness. Earlier failures hide later ones so
        error messages stay focused on the root cause.
        """
        self._check_name_range()
        _validate_provider_capacity(self.providers)
        _validate_provider_kind_unique(self.providers)
        _validate_default_provider_count(self.providers)
        _validate_skill_capacity(self.skills)
        _validate_skill_id_unique(self.skills)
        return self

    def _check_name_range(self) -> None:
        length = len(self.name)
        if not (MIN_NAME_LENGTH <= length <= MAX_NAME_LENGTH):
            raise AgentInvariantViolation(
                kind="name_range",
                message=(
                    f"[FAIL] Agent name must be "
                    f"{MIN_NAME_LENGTH}-{MAX_NAME_LENGTH} characters "
                    f"(got {length})"
                ),
                detail={"length": length},
            )

    # ---- behaviors (Tell, Don't Ask) ------------------------------------
    def set_default_provider(self, provider_kind: ProviderKind) -> Agent:
        """Switch the default provider to the entry whose ``provider_kind`` matches.

        Linear scan over ``providers`` (small N ≤ 10). Raises if the kind is
        not registered — the caller cannot mark a never-configured provider
        as default.

        Raises:
            AgentInvariantViolation: ``kind='provider_not_found'`` when no
                ``ProviderConfig`` matches ``provider_kind``.
        """
        if not any(provider.provider_kind == provider_kind for provider in self.providers):
            raise AgentInvariantViolation(
                kind="provider_not_found",
                message=f"[FAIL] provider_kind not registered: {provider_kind}",
                detail={"provider_kind": str(provider_kind)},
            )
        new_providers = [
            ProviderConfig(
                provider_kind=provider.provider_kind,
                model=provider.model,
                is_default=(provider.provider_kind == provider_kind),
            )
            for provider in self.providers
        ]
        return self._rebuild_with(providers=new_providers)

    def add_skill(self, skill_ref: SkillRef) -> Agent:
        """Append ``skill_ref`` to ``skills``; aggregate validation catches duplicates."""
        return self._rebuild_with(skills=[*self.skills, skill_ref])

    def remove_skill(self, skill_id: SkillId) -> Agent:
        """Drop the SkillRef whose ``skill_id`` matches.

        Raises:
            AgentInvariantViolation: ``kind='skill_not_found'`` (MSG-AG-008).
        """
        if not any(skill.skill_id == skill_id for skill in self.skills):
            raise AgentInvariantViolation(
                kind="skill_not_found",
                message=f"[FAIL] Skill not found in agent: skill_id={skill_id}",
                detail={"skill_id": str(skill_id)},
            )
        return self._rebuild_with(
            skills=[skill for skill in self.skills if skill.skill_id != skill_id],
        )

    def archive(self) -> Agent:
        """Return a new :class:`Agent` with ``archived=True`` (Confirmation D).

        Idempotent: calling on an already-archived Agent yields a fresh
        Agent that is **structurally equal** to the input but has a
        different ``id()``. Callers must not rely on object identity —
        always reassign the returned value (``agent = agent.archive()``).
        """
        return self._rebuild_with_state({"archived": True})

    # ---- internal: pre-validate rebuild (Confirmation A) ----------------
    def _rebuild_with(
        self,
        *,
        providers: list[ProviderConfig] | None = None,
        skills: list[SkillRef] | None = None,
    ) -> Agent:
        """Re-construct via ``model_validate`` so ``_check_invariants`` re-fires."""
        state = self.model_dump()
        if providers is not None:
            state["providers"] = [provider.model_dump() for provider in providers]
        if skills is not None:
            state["skills"] = [skill.model_dump() for skill in skills]
        return Agent.model_validate(state)

    def _rebuild_with_state(self, updates: dict[str, Any]) -> Agent:
        """Pre-validate rebuild for scalar attribute updates (e.g. ``archived``)."""
        state = self.model_dump()
        state.update(updates)
        return Agent.model_validate(state)


__all__ = [
    "MAX_NAME_LENGTH",
    "MIN_NAME_LENGTH",
    "Agent",
]
