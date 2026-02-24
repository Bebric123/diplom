# backend/src/db/models.py
from sqlalchemy import Column, UUID, String, Boolean, DateTime, JSON, ForeignKey, Text, Integer, ARRAY, UniqueConstraint, Float
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.sql import func
from .database import Base
import uuid

# --- Основные таблицы ---
class Project(Base):
    __tablename__ = "projects"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
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

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    external_id = Column(String, nullable=False)
    email_hash = Column(String)
    ip_address = Column(INET)
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), onupdate=func.now())
    __table_args__ = (UniqueConstraint('project_id', 'external_id'),)

# --- Справочники ---
class Platform(Base):
    __tablename__ = "platforms"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)

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

# --- Основное событие ---
class Event(Base):
    __tablename__ = "events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    error_group_id = Column(UUID(as_uuid=True), ForeignKey("error_groups.id"))
    action = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    metadata_ = Column("metadata", JSONB, default=dict)
    is_classified = Column(Boolean, default=False)
    is_notified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# --- 4НФ: вынесенные группы ---
class EventContext(Base):
    __tablename__ = "event_contexts"
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    platform_id = Column(UUID(as_uuid=True), ForeignKey("platforms.id"), nullable=False)
    language = Column(String)
    os_family = Column(String)
    browser_family = Column(String)
    browser_version = Column(String)

class EventUrl(Base):
    __tablename__ = "event_urls"
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    page_url = Column(String)
    page_path = Column(String)
    domain = Column(String)

class EventError(Base):
    __tablename__ = "event_errors"
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    error_message = Column(Text)
    error_stack = Column(Text)
    error_line = Column(Integer)
    error_column = Column(Integer)
    error_file = Column(String)

# --- Группы ошибок ---
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
    __table_args__ = (UniqueConstraint('project_id', 'group_hash'),)

# --- Уведомления и аудит ---
class Notification(Base):
    __tablename__ = "notifications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    error_group_id = Column(UUID(as_uuid=True), ForeignKey("error_groups.id"))
    channel = Column(String, nullable=False)
    status = Column(String, nullable=False)
    recipient = Column(String)
    content = Column(Text)
    external_id = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id"))
    action = Column(String, nullable=False)
    entity_type = Column(String)
    entity_id = Column(UUID(as_uuid=True))
    ip_address = Column(INET)
    details = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ClassificationCache(Base):
    __tablename__ = "classification_cache"
    error_signature = Column(String, primary_key=True)
    result = Column(JSONB, nullable=False)
    confidence = Column(Float)
    used_count = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())