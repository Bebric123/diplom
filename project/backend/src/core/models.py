from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    UUID,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base
import uuid


class Project(Base):
    __tablename__ = "projects"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    telegram_chat_id = Column(String(64), nullable=True)
    tech_stack = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ApiKey(Base):
    __tablename__ = "api_keys"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    hashed_key = Column(String, unique=True, nullable=False)
    scope = Column(ARRAY(String), default=[])
    is_revoked = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Platform(Base):
    __tablename__ = "platforms"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    contexts = relationship("EventContext", back_populates="platform")


class SeverityLevel(Base):
    __tablename__ = "severity_levels"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    level = Column(Integer, unique=True, nullable=False)


class CriticalityLevel(Base):
    __tablename__ = "criticality_levels"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    level = Column(Integer, unique=True, nullable=False)


class Event(Base):
    __tablename__ = "events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id"))
    error_group_id = Column(UUID(as_uuid=True), ForeignKey("error_groups.id"))
    action = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    metadata_ = Column("metadata", JSONB, default=dict)
    is_classified = Column(Boolean, default=False)
    is_notified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    context = relationship("EventContext", back_populates="event", uselist=False, cascade="all, delete-orphan")
    url = relationship("EventUrl", back_populates="event", uselist=False, cascade="all, delete-orphan")
    error = relationship("EventError", back_populates="event", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_events_project_created", "project_id", "created_at"),
        Index("ix_events_created_at", "created_at"),
        Index(
            "ix_events_error_group_id",
            "error_group_id",
            postgresql_where=text("error_group_id IS NOT NULL"),
        ),
    )


class EventContext(Base):
    __tablename__ = "event_contexts"
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    platform_id = Column(UUID(as_uuid=True), ForeignKey("platforms.id"), nullable=False)
    language = Column(String)
    os_family = Column(String)
    browser_family = Column(String)
    browser_version = Column(String)
    event = relationship("Event", back_populates="context")
    platform = relationship("Platform")


class EventUrl(Base):
    __tablename__ = "event_urls"
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    page_url = Column(String)
    page_path = Column(String)
    domain = Column(String)
    event = relationship("Event", back_populates="url")


class EventError(Base):
    __tablename__ = "event_errors"
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    error_message = Column(Text)
    error_stack = Column(Text)
    error_line = Column(Integer)
    error_column = Column(Integer)
    error_file = Column(String)
    event = relationship("Event", back_populates="error")


class ErrorGroup(Base):
    __tablename__ = "error_groups"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    group_hash = Column(String, nullable=False)
    title = Column(String, nullable=False)
    platform_id = Column(UUID(as_uuid=True), ForeignKey("platforms.id"), nullable=False)
    occurrence_count = Column(Integer, default=1)
    affected_users_count = Column(Integer, default=1)
    severity_id = Column(UUID(as_uuid=True), ForeignKey("severity_levels.id"))
    criticality_id = Column(UUID(as_uuid=True), ForeignKey("criticality_levels.id"))
    recommendation = Column(Text)
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True))
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), onupdate=func.now())
    alert_last_sent_at = Column(DateTime(timezone=True), nullable=True)
    alert_last_severity = Column(String, nullable=True)
    __table_args__ = (
        UniqueConstraint("project_id", "group_hash"),
        Index("ix_error_groups_project_id", "project_id"),
    )


class ErrorTask(Base):
    __tablename__ = "error_tasks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    error_group_id = Column(UUID(as_uuid=True), ForeignKey("error_groups.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    is_acknowledged = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)
    acknowledged_by_telegram_user_id = Column(BigInteger, nullable=True)
    acknowledged_by_label = Column(String(255), nullable=True)
    resolved_by_telegram_user_id = Column(BigInteger, nullable=True)
    resolved_by_label = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    last_notification_sent_at = Column(DateTime(timezone=True), nullable=True)
    notification_count = Column(Integer, default=0)
    last_severity = Column(String, nullable=True)
    telegram_message_id = Column(Integer, nullable=True)
    telegram_chat_id = Column(String, nullable=True)
    event = relationship("Event", backref="tasks")
    error_group = relationship("ErrorGroup", backref="tasks")
    project = relationship("Project", backref="tasks")

    __table_args__ = (
        Index("ix_error_tasks_error_group_id", "error_group_id"),
        Index("ix_error_tasks_project_created", "project_id", "created_at"),
    )


class LogFile(Base):
    __tablename__ = "log_files"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    error_group_id = Column(UUID(as_uuid=True), ForeignKey("error_groups.id", ondelete="CASCADE"), nullable=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    lines_sent = Column(Integer, nullable=False)
    total_lines = Column(Integer, nullable=True)
    content = Column(Text, nullable=False)
    server_name = Column(String, nullable=True)
    service_name = Column(String, nullable=True)
    environment = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    project = relationship("Project", backref="log_files")
    error_group = relationship("ErrorGroup", backref="log_files")

    __table_args__ = (Index("ix_log_files_project_created", "project_id", "created_at"),)
