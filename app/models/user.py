from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    username = Column(String(150), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="Interviewer")

    jobs = relationship("Job", back_populates="hiring_manager", lazy="selectin")
    interview_assignments = relationship("InterviewAssignment", back_populates="interviewer", lazy="selectin")
    audit_logs = relationship("AuditLog", back_populates="actor", lazy="selectin")