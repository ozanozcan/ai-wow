"""Event envelope schema: what replay is willing to recognise.

Every event is one JSON line `{"v": 1, "type": "<entity>.<verb>", "id": N,
"ts": "<utc iso>", ...payload}`. Replay is fail-closed on purpose (plan d-p1):
board and code travel in the same git tree, so an old reader meeting a newer
board must stop loudly — an unknown entity, unknown verb, missing `v`, or
`v` above SUPPORTED_VERSION is a refusal, never a silent skip.

The constant tuples below are COPIED verbatim from models.py, not imported:
models.py dies with the database in wave 2, and this package imports nothing
outside the standard library by contract.
"""

SUPPORTED_VERSION = 1

# Board entities (plan d-p6, d-p8). No `project` (the board dir is the
# project) and no `tag` (tags are plain string arrays in fields).
ENTITIES = ("task", "feature", "pbi", "requirement", "decision", "capture", "session")

_BASE_VERBS = ("add", "set", "link", "unlink")

# entity -> allowed verbs. `claim`/`release` are task-only (the CAS);
# session's creation verb is `record`, by name, per d-p8 — the store never
# writes a `session.add`, so replay does not accept one.
VERBS = {
    "task": _BASE_VERBS + ("claim", "release"),
    "feature": _BASE_VERBS,
    "pbi": _BASE_VERBS,
    "requirement": _BASE_VERBS,
    "decision": _BASE_VERBS,
    "capture": _BASE_VERBS,
    "session": ("record", "set", "link", "unlink"),
}

# Creation verb per entity: what `store.add` emits and what replay treats as
# "materialize this id".
CREATE_VERBS = {entity: ("record" if entity == "session" else "add") for entity in ENTITIES}

# Fields no `set` event may carry: ids are never reassigned (d-p4) and
# claimed_by changes only via claim/release (the CAS), never via `set`.
PROTECTED_FIELDS = ("id", "claimed_by")

# Relations grown/shrunk by `<entity>.link` / `<entity>.unlink`.
# "many": a list of target ids; "one": a single nullable target id.
RELATIONS = {
    "task": {"blocked_by": "many"},
    "capture": {"task_id": "one"},
    "decision": {"task_id": "one"},
}

# ---- constant tuples copied verbatim from models.py (which wave 2 deletes) ----

# Kanban columns — shared by Feature / PBI / Task.
# "disabled" = retired from consideration until explicitly revisited — excluded from
# `board`'s default view (unlike the others) but still a valid, settable status.
STATUSES = ("backlog", "todo", "in_progress", "blocked", "done", "disabled")
CAPTURE_KINDS = ("qa", "grill", "plan")

# Strategic lens carried over from the legacy web-app CSV board.
# priority: planning importance, ordered keystone(0) → low(3). On PBI + Task.
PRIORITIES = ("keystone", "high", "med", "low")
# lane: the "for whom" strategic tie-break. On Feature (groups a whole feature).
LANES = ("product", "platform", "workforce")
# surface: which agent/RAG surface the work builds. On Feature; blank = none.
SURFACES = ("end-user", "prod-internal", "workforce")

# Requirement lifecycle: active = current truth, removed = superseded/retired
# (kept for history rather than hard-deleted).
REQUIREMENT_STATUSES = ("active", "removed")


def _plain_int(value) -> bool:
    """True for a real integer — bool is an int subclass and is refused
    (True hashes to 1, so a boolean id/target would silently alias id 1)."""
    return isinstance(value, int) and not isinstance(value, bool)


# verb -> required payload keys: (key, description, predicate). Table-driven so
# a new verb's payload contract is one row here, not another scattered `if`.
_VERB_PAYLOADS = {
    "link": (("relation", "string", lambda v: isinstance(v, str)),
             ("target", "integer", _plain_int)),
    "unlink": (("relation", "string", lambda v: isinstance(v, str)),
               ("target", "integer", _plain_int)),
    "claim": (("agent", "string", lambda v: isinstance(v, str)),),
}


def validate_event(event: dict) -> None:
    """Raise ValueError unless `event` is an envelope this reader recognises."""
    if not isinstance(event, dict):
        raise ValueError(f"event is not an object: {event!r}")
    v = event.get("v")
    if v is None:
        raise ValueError("event has no 'v' key")
    if not _plain_int(v) or not 1 <= v <= SUPPORTED_VERSION:
        raise ValueError(f"unsupported event version {v!r} (this reader supports <= {SUPPORTED_VERSION})")
    kind = event.get("type")
    if not isinstance(kind, str) or "." not in kind:
        raise ValueError(f"malformed event type {kind!r}")
    entity, verb = kind.split(".", 1)
    if entity not in ENTITIES:
        raise ValueError(f"unknown entity {entity!r} in event type {kind!r}")
    if verb not in VERBS[entity]:
        raise ValueError(f"unknown verb {verb!r} for entity {entity!r}")
    if not _plain_int(event.get("id")):
        raise ValueError(f"event has no integer 'id': {event.get('id')!r}")
    for key, kind, valid in _VERB_PAYLOADS.get(verb, ()):
        if not valid(event.get(key)):
            raise ValueError(f"{verb!r} event needs a {kind} {key!r}: {event.get(key)!r}")
    relations = RELATIONS.get(entity, {})
    if verb == "set":
        fields = event.get("fields")
        if not isinstance(fields, dict):
            raise ValueError(f"'set' event carries no fields object: {fields!r}")
        for field in PROTECTED_FIELDS:
            if field in fields:
                raise ValueError(
                    f"'set' may not carry protected field {field!r}"
                    " (claimed_by changes only via claim/release; ids are never reassigned)")
        for field in relations:
            if field in fields:
                raise ValueError(f"'set' may not carry relation field {field!r}"
                                 " (relations change only via link/unlink)")
    elif verb == CREATE_VERBS[entity]:
        # An add may carry initial relation fields (the migration exporter
        # does), but only in the shape link/unlink would have produced —
        # anything else would raise on every future replay, bricking the board.
        fields = event.get("fields")
        if fields is not None and not isinstance(fields, dict):
            raise ValueError(f"create event fields is not an object: {fields!r}")
        if "id" in (fields or {}):
            raise ValueError(
                "create event may not carry 'id' inside fields"
                " (the id lives in the envelope; a fields id desyncs the board)")
        for field, shape in relations.items():
            if field not in (fields or {}):
                continue
            value = fields[field]
            if shape == "many":
                if not isinstance(value, list) or not all(_plain_int(t) for t in value):
                    raise ValueError(
                        f"relation field {field!r} must be a list of integer ids: {value!r}")
            elif value is not None and not _plain_int(value):  # "one"
                raise ValueError(
                    f"relation field {field!r} must be an integer id or null: {value!r}")
