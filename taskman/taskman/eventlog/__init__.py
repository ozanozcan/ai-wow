"""eventlog — a dbless task board: events appended to a JSONL log, state by
replay, mutations serialized through an O_EXCL lockfile.

Standard library only, by contract. Spike for the taskman-no-db plan; the CLI
port onto this store is deliberately not wired here.
"""
