from datetime import datetime
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.database import Base
from app.embeddings import EMBEDDING_DIMENSIONS


def new_id():
    return str(uuid4())


class Service(Base):
    __tablename__ = "services"

    id = Column(String(36), primary_key=True, default=new_id)
    name = Column(String(120), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    owner_team = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    incidents = relationship("Incident", back_populates="service")
    logs = relationship("LogEntry", back_populates="service")
    deployments = relationship("Deployment", back_populates="service")


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String(36), primary_key=True, default=new_id)
    title = Column(String(200), nullable=False)
    severity = Column(String(50), default="medium", nullable=False)
    status = Column(String(50), default="open", index=True, nullable=False)
    description = Column(Text, nullable=True)

    service_id = Column(String(36), ForeignKey("services.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    service = relationship("Service", back_populates="incidents")
    logs = relationship("LogEntry", back_populates="incident")
    analysis_runs = relationship("AnalysisRun", back_populates="incident")


class LogEntry(Base):
    __tablename__ = "logs"

    id = Column(String(36), primary_key=True, default=new_id)

    service_id = Column(String(36), ForeignKey("services.id"), nullable=False)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    level = Column(String(30), index=True, nullable=False)
    message = Column(Text, nullable=False)
    source = Column(String(120), nullable=True)
    context = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    service = relationship("Service", back_populates="logs")
    incident = relationship("Incident", back_populates="logs")


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(String(36), primary_key=True, default=new_id)

    service_id = Column(String(36), ForeignKey("services.id"), nullable=False)

    version = Column(String(80), nullable=False)
    environment = Column(String(80), default="production", nullable=False)
    commit_sha = Column(String(120), nullable=True)
    deployed_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    service = relationship("Service", back_populates="deployments")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=new_id)

    title = Column(String(200), nullable=False)
    filename = Column(String(255), nullable=True)
    content_type = Column(String(120), nullable=True)
    content = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=new_id)

    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)

    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIMENSIONS), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="chunks")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(String(36), primary_key=True, default=new_id)

    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False)

    status = Column(String(50), default="pending", nullable=False)
    model_name = Column(String(120), nullable=True)
    summary = Column(Text, nullable=True)

    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    incident = relationship("Incident", back_populates="analysis_runs")
