from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from app.models.base import BaseModel
from app.models.candidate import candidate_skills


class Skill(BaseModel):
    __tablename__ = "skills"

    name = Column(String(100), unique=True, nullable=False)

    candidates = relationship(
        "Candidate",
        secondary=candidate_skills,
        back_populates="skills",
        lazy="selectin",
    )