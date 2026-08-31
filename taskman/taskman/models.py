from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Kanban columns — shared by Feature / PBI / Task.
# "disabled" = retired from consideration until explicitly revisited — excluded from
# `board`'s default view (unlike the others) but still a valid, settable status.
STATUSES = ("backlog", "todo", "in_progress", "blocked", "done", "disabled")
CAPTURE_KINDS = ("qa", "grill", "plan")

# Strategic lens carried over from the legacy web-app CSV board.
# priority: planning importance, ordered keystone(0) → low(3). On PBI + Task.
PRIORITIES = ("keystone", "high", "med", "low")
PRIORITY_ORDER = {p: i for i, p in enumerate(PRIORITIES)}
# lane: the "for whom" strategic tie-break. On Feature (groups a whole feature).
LANES = ("product", "platform", "workforce")
# surface: which agent/RAG surface the work builds. On Feature; blank = none.
SURFACES = ("end-user", "prod-internal", "workforce")

# source_ref format (locked): {relative_transcript_path}#L{line_number}

# Requirement lifecycle: active = current truth, removed = superseded/retired
# (kept for history rather than hard-deleted).
REQUIREMENT_STATUSES = ("active", "removed")


class Base(DeclarativeBase):
    pass


# self-M2M: a task is blocked_by other tasks
task_dep = Table(
    "taskman_task_dep",
    Base.metadata,
    Column("task_id", ForeignKey("taskman_task.id", ondelete="CASCADE"), primary_key=True),
    Column("blocked_by_id", ForeignKey("taskman_task.id", ondelete="CASCADE"), primary_key=True),
)

# Tag M2M for Feature/PBI only. Task keeps denormalized tags ARRAY for v1 compat
# (dual storage — Wave 6 may unify).
feature_tag = Table(
    "taskman_feature_tag",
    Base.metadata,
    Column("feature_id", ForeignKey("taskman_feature.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("taskman_tag.id", ondelete="CASCADE"), primary_key=True),
)

pbi_tag = Table(
    "taskman_pbi_tag",
    Base.metadata,
    Column("pbi_id", ForeignKey("taskman_pbi.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("taskman_tag.id", ondelete="CASCADE"), primary_key=True),
)


class Project(Base):
    __tablename__ = "taskman_project"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Tag(Base):
    __tablename__ = "taskman_tag"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_taskman_tag_project_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("taskman_project.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String)


class Feature(Base):
    __tablename__ = "taskman_feature"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("taskman_project.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="backlog", index=True)
    # Strategic lens (blank = unset). lane = for-whom; surface = which agent/RAG.
    lane: Mapped[str] = mapped_column(String, default="", index=True)
    surface: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tags: Mapped[list[Tag]] = relationship("Tag", secondary=feature_tag)
    pbis: Mapped[list["PBI"]] = relationship("PBI", back_populates="feature")


class PBI(Base):
    __tablename__ = "taskman_pbi"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("taskman_project.id", ondelete="CASCADE"), index=True
    )
    feature_id: Mapped[int] = mapped_column(
        ForeignKey("taskman_feature.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String)
    acceptance_criteria: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="backlog", index=True)
    priority: Mapped[str] = mapped_column(String, default="med", index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    feature: Mapped[Feature] = relationship("Feature", back_populates="pbis")
    tags: Mapped[list[Tag]] = relationship("Tag", secondary=pbi_tag)
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="pbi")


class Requirement(Base):
    """Living spec: current behavior for a Feature, stated as SHALL + scenarios.

    Kept separate from PBI.acceptance_criteria (which scopes one unit of work);
    a Requirement is the durable, capability-level truth a PBI's work rolls up
    into. ADDED = new row; MODIFIED = same row edited in place; REMOVED =
    status flipped rather than hard-deleted, so retired behavior stays visible.
    """

    __tablename__ = "taskman_requirement"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("taskman_project.id", ondelete="CASCADE"), index=True
    )
    feature_id: Mapped[int] = mapped_column(
        ForeignKey("taskman_feature.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String)
    # The SHALL/MUST/SHOULD/MAY statement — one observable behavior.
    statement: Mapped[str] = mapped_column(Text, default="")
    # list[{"name": str, "given": str, "when": str, "then": str}]
    scenarios: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String, default="active", index=True)
    # PBI whose work last added/modified this requirement (nullable: manual entries).
    source_pbi_id: Mapped[int | None] = mapped_column(
        ForeignKey("taskman_pbi.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    feature: Mapped[Feature] = relationship("Feature")
    source_pbi: Mapped[PBI | None] = relationship("PBI")


class Task(Base):
    __tablename__ = "taskman_task"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("taskman_project.id", ondelete="CASCADE"), index=True
    )
    # nullable: legacy flat tasks (pre-hierarchy) stay readable until manually linked
    pbi_id: Mapped[int | None] = mapped_column(
        ForeignKey("taskman_pbi.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="backlog", index=True)
    priority: Mapped[str] = mapped_column(String, default="med", index=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    # Strategic lens carried over from the legacy web-app CSV board, at Task level (blank = unset).
    # Feature has the same lane/surface pair for hierarchy-grouped work; a flat Task (no PBI)
    # needs its own copy since it may never be linked under a Feature.
    lane: Mapped[str] = mapped_column(String, default="")
    surface: Mapped[str] = mapped_column(String, default="")
    afk: Mapped[str] = mapped_column(String, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    # provenance: {relative_transcript_path}#L{line_number}
    source_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    # Dispatch-only fields for lossless brief round-trip (role, wave, files, …).
    brief: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Atomic checkout lock — set by `taskman task claim`, cleared by `task release`.
    claimed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    claimed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    pbi: Mapped[PBI | None] = relationship("PBI", back_populates="tasks")
    blocked_by: Mapped[list["Task"]] = relationship(
        "Task",
        secondary=task_dep,
        primaryjoin=id == task_dep.c.task_id,
        secondaryjoin=id == task_dep.c.blocked_by_id,
    )
    captures: Mapped[list["Capture"]] = relationship(
        "Capture",
        back_populates="task",
    )


class Decision(Base):
    __tablename__ = "taskman_decision"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("taskman_project.id", ondelete="CASCADE"), index=True
    )
    # Optional owner task (d#865) — mirrors Capture.task_id for accountability.
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("taskman_task.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String)
    why: Mapped[str] = mapped_column(Text, default="")
    alternatives: Mapped[str] = mapped_column(Text, default="")
    implications: Mapped[str] = mapped_column(Text, default="")
    # Scope tags (d#852): area / path:<glob> / feature:N — same shape as Task.tags.
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    # provenance: {relative_transcript_path}#L{line_number}
    source_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped[Task | None] = relationship("Task", foreign_keys=[task_id])


class Capture(Base):
    __tablename__ = "taskman_capture"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("taskman_project.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("taskman_task.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String, index=True)  # qa|grill|plan
    summary: Mapped[str] = mapped_column(String, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    # Scope tags (d#852): same conventions as Decision.tags / Task.tags.
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    # provenance: {relative_transcript_path}#L{line_number}
    source_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped[Task | None] = relationship("Task", back_populates="captures")


class AgentSession(Base):
    """Archived agent chat metrics. Named AgentSession to avoid clashing with sqlalchemy Session."""

    __tablename__ = "taskman_session"
    __table_args__ = (UniqueConstraint("project_id", "session_id", "transcript_path", name="uq_taskman_session_path"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("taskman_project.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[str] = mapped_column(String, index=True)
    source: Mapped[str] = mapped_column(String, default="unknown")  # claude|cursor|unknown
    transcript_path: Mapped[str] = mapped_column(String)
    tokens_status: Mapped[str] = mapped_column(String, default="unknown")  # ok|unknown
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    cache_creation_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    api_calls: Mapped[int] = mapped_column(Integer, default=0)
    models: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    effort: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    recorded_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
