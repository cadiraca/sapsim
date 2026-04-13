"""
SAP SIM — Database Package
Phase: 7.1
Purpose: SQLite-backed async persistence layer using aiosqlite.
         Replaces the file-based JSON/JSONL persistence from Phase 1.5.

Public API:
    from db import init_db
    from db.schema import init_db, TABLE_DEFINITIONS
"""

from db.schema import init_db

__all__ = ["init_db"]
