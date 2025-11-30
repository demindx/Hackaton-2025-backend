from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


class User(Base):
  __tablename__ = "users"

  id = Column(Integer, primary_key=True, index=True)
  email = Column(String, unique=True, index=True, nullable=False)
  hashed_password = Column(String, nullable=False)

  requests = relationship("RequestHistory", back_populates="user")


class RequestHistory(Base):
  __tablename__ = "request_history"

  id = Column(Integer, primary_key=True, index=True)
  user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
  prompt = Column(Text, nullable=False)
  pdf_path = Column(String, nullable=False)
  created_at = Column(DateTime, default=datetime.utcnow)

  user = relationship("User", back_populates="requests")
