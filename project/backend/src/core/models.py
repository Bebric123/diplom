# backend/src/core/models.py
from sqlalchemy import Column, UUID, String, Boolean, DateTime, ForeignKey, Text, Integer, ARRAY, UniqueConstraint, Float
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.sql import func
from .database import Base
import uuid
from sqlalchemy.orm import relationship 

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

    context = relationship("EventContext", back_populates="event", uselist=False, cascade="all, delete-orphan")
    
    # Связь с URL (один-к-одному)
    url = relationship("EventUrl", back_populates="event", uselist=False, cascade="all, delete-orphan")
    
    # Связь с ошибкой (один-к-одному)
    error = relationship("EventError", back_populates="event", uselist=False, cascade="all, delete-orphan")

# --- 4НФ: вынесенные группы ---
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

class ErrorTask(Base):
    __tablename__ = "error_tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    error_group_id = Column(UUID(as_uuid=True), ForeignKey("error_groups.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    # Статусы задачи
    is_acknowledged = Column(Boolean, default=False)  # Нажата кнопка "Начать работу"
    is_resolved = Column(Boolean, default=False)      # Нажата кнопка "Решено"
    
    # Временные метки для статистики
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Троттлинг
    last_notification_sent_at = Column(DateTime(timezone=True), nullable=True)
    notification_count = Column(Integer, default=0)
    last_severity = Column(String, nullable=True) 
    
    # Метаданные для обновления сообщения в ТГ
    telegram_message_id = Column(Integer, nullable=True)
    telegram_chat_id = Column(String, nullable=True)
    
    # Связи
    event = relationship("Event", backref="tasks")
    error_group = relationship("ErrorGroup", backref="tasks")
    project = relationship("Project", backref="tasks")

class LogFile(Base):
    __tablename__ = "log_files"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    error_group_id = Column(UUID(as_uuid=True), ForeignKey("error_groups.id", ondelete="CASCADE"), nullable=True)
    
    # Информация о файле
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)  # в байтах
    lines_sent = Column(Integer, nullable=False)  # сколько строк отправили
    total_lines = Column(Integer, nullable=True)  # всего строк в файле
    
    # Содержимое (последние N строк)
    content = Column(Text, nullable=False)
    
    # Метаданные
    server_name = Column(String, nullable=True)
    service_name = Column(String, nullable=True)
    environment = Column(String, nullable=True)  # production, staging, development
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    project = relationship("Project", backref="log_files")
    error_group = relationship("ErrorGroup", backref="log_files")