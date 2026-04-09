from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Application(BaseModel):
    __tablename__ = "applications"

    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=False)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)
    status = Column(String(50), nullable=False, default="Applied")
    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_application_candidate_job"),
    )

    candidate = relationship("Candidate", back_populates="applications", lazy="selectin")
    job = relationship("Job", back_populates="applications", lazy="selectin")
    interview_assignments = relationship(
        "InterviewAssignment",
        back_populates="application",
        lazy="selectin",
        cascade="all, delete-orphan",
    )