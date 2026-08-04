from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String

from app.db.base import Base
from app.models.base import new_id


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=new_id)

    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="viewer")
    is_active = Column(Boolean, nullable=False, default=True)

    api_key_hash = Column(String(255), unique=True, nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
