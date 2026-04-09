from sqlalchemy import Column, DateTime, String, Table, ForeignKey, Text
from datetime import datetime
import uuid

from app.models.base import Base, BaseModel


candidate_skills = Table(
    "candidate_skills",
    Base.metadata,
    Column("candidate_id", String(36), ForeignKey("candidates.id"), primary_key=True),
    Column("skill_id", String(36), ForeignKey("skills.id"), primary_key=True),
)


class Candidate(BaseModel):
    __tablename__ = "candidates"

    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    resume_text = Column(Text, nullable=True)
    linkedin_url = Column(String(500), nullable=True)

    from sqlalchemy.orm import relationship

    skills = relationship(
        "Skill",
        secondary=candidate_skills,
        back_populates="candidates",
        lazy="selectin",
    )
    applications = relationship(
        "Application",
        back_populates="candidate",
        lazy="selectin",
    )