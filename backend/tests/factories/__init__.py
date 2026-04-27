"""Test factories for the bakufu domain layer.

Per ``docs/features/empire/test-design.md`` factories use a module-scope
``WeakValueDictionary`` registry to mark synthetic instances without ever
mutating the frozen Pydantic models themselves. ``is_synthetic(instance)``
queries the registry by ``id(instance)`` and returns ``True`` when the value
was produced via this package.

Test code MUST use these factories rather than constructing aggregates with
inline literals — this keeps the synthetic-vs-real boundary auditable and
ensures invariants are exercised through the same construction path that
production code follows.
"""
