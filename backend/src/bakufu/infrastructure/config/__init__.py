"""Bootstrap-stage configuration helpers (DATA_DIR resolution etc.).

These modules wire OS-level state into the rest of the infrastructure
layer. They sit *outside* the persistence package because they run
before the SQLite engine is ready (Bootstrap stage 1).
"""
