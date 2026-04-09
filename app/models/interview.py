import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.models.base import Base


class InterviewAssignment(Base):
    __tablename__ = "interview_assignments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), nullable=False)
    application_id = Column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    interviewer_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    scheduled_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    application = relationship("Application", back_populates="interview_assignments", lazy="selectin")
    interviewer = relationship("User", back_populates="interview_assignments", lazy="selectin")
    feedback = relationship("InterviewFeedback", back_populates="assignment", lazy="selectin", cascade="all, delete-orphan")


class InterviewFeedback(Base):
    __tablename__ = "interview_feedback"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), nullable=False)
    assignment_id = Column(String(36), ForeignKey("interview_assignments.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)
    notes = Column(Text, nullable=False)
    submitted_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    assignment = relationship("InterviewAssignment", back_populates="feedback", lazy="selectin")
    submitter = relationship("User", back_populates="interview_feedbacks", lazy="selectin")
```

Wait, I need to check — I'm missing the `relationship` import. Let me produce the correct final file:

```python
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


class InterviewAssignment(Base):
    __tablename__ = "interview_assignments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), nullable=False)
    application_id = Column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    interviewer_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    scheduled_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    application = relationship("Application", back_populates="interview_assignments", lazy="selectin")
    interviewer = relationship("User", back_populates="interview_assignments", lazy="selectin")
    feedback = relationship("InterviewFeedback", back_populates="assignment", lazy="selectin", cascade="all, delete-orphan")


class InterviewFeedback(Base):
    __tablename__ = "interview_feedback"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), nullable=False)
    assignment_id = Column(String(36), ForeignKey("interview_assignments.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)
    notes = Column(Text, nullable=False)
    submitted_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    assignment = relationship("InterviewAssignment", back_populates="feedback", lazy="selectin")
    submitter = relationship("User", back_populates="interview_feedbacks", lazy="selectin")