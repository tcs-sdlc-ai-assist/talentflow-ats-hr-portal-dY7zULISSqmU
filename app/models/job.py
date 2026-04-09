from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Job(BaseModel):
    __tablename__ = "jobs"

    title = Column(String(255), nullable=False)
    department = Column(String(100), nullable=False)
    location = Column(String(255), nullable=False)
    job_type = Column(String(50), nullable=False)
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    description = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="Draft")
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    owner = relationship("User", back_populates="jobs", lazy="selectin")
    applications = relationship("Application", back_populates="job", lazy="selectin", cascade="all, delete-orphan")