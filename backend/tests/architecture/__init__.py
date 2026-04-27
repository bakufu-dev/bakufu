"""Architecture-invariant tests.

These tests guard cross-cutting structural rules that simple grep
checks cannot cover (dynamic metadata, runtime registration, type
hierarchies). They run with the regular ``pytest backend/`` invocation.
"""
