"""eventlog — a dbless task board: events appended to a JSONL log, state by
replay, mutations serialized through an O_EXCL lockfile.

Every board entity (task, feature, pbi, requirement, decision, capture,
session) lives in the one log behind a versioned, fail-closed envelope
(schema.py) with per-entity id counters. Standard library only, by contract;
the CLI port onto this store lands in wave 2.
"""
