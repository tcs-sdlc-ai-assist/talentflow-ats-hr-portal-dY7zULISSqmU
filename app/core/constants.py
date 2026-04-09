class UserRole:
    SYSTEM_ADMIN = "System Admin"
    HR_RECRUITER = "HR Recruiter"
    HIRING_MANAGER = "Hiring Manager"
    INTERVIEWER = "Interviewer"

    ALL = [SYSTEM_ADMIN, HR_RECRUITER, HIRING_MANAGER, INTERVIEWER]


class JobStatus:
    DRAFT = "Draft"
    PUBLISHED = "Published"
    CLOSED = "Closed"

    ALL = [DRAFT, PUBLISHED, CLOSED]


class ApplicationStage:
    APPLIED = "Applied"
    SCREENING = "Screening"
    INTERVIEWING = "Interviewing"
    OFFERED = "Offered"
    HIRED = "Hired"
    REJECTED = "Rejected"

    ALL = [APPLIED, SCREENING, INTERVIEWING, OFFERED, HIRED, REJECTED]

    ACTIVE_STAGES = [APPLIED, SCREENING, INTERVIEWING, OFFERED]
    TERMINAL_STAGES = [HIRED, REJECTED]


class InterviewStatus:
    SCHEDULED = "Scheduled"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"

    ALL = [SCHEDULED, COMPLETED, CANCELLED]


class OfferStatus:
    PENDING = "Pending"
    ACCEPTED = "Accepted"
    DECLINED = "Declined"
    WITHDRAWN = "Withdrawn"

    ALL = [PENDING, ACCEPTED, DECLINED, WITHDRAWN]


# Pagination defaults
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Token expiration (minutes)
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7