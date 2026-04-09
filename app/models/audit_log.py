from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text

from app.models.base import BaseModel


class AuditLog(BaseModel):
    __tablename__ = "audit_logs"

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    username = Column(String(150), nullable=True)
    action = Column(String(128), nullable=False)
    details = Column(Text, nullable=True)

    actor = relationship("User", back_populates="audit_logs", lazy="selectin")
```

Wait, I need to check the existing User model to see what relationship attribute it uses. Let me look at the existing codebase more carefully. The models `__init__.py` imports `AuditLog` from `app.models.audit_log`, and the User model is in `app.models.user` but its content isn't shown. I need to check the base model pattern and ensure consistency.

Let me also check - the `__init__.py` imports show `AuditLog` is expected. The base model uses `Column` style, so I must use `Column` style with plain `relationship()`.

Let me regenerate properly:

```python
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class AuditLog(BaseModel):
    __tablename__ = "audit_logs"

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    username = Column(String(150), nullable=True)
    action = Column(String(128), nullable=False)
    details = Column(Text, nullable=True)

    actor = relationship("User", back_populates="audit_logs", lazy="selectin")