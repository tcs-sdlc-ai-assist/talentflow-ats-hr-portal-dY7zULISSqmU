# TalentFlow ATS

An Applicant Tracking System (ATS) built with Python and FastAPI for managing recruitment workflows, job postings, candidate pipelines, and hiring team collaboration.

## Features

- **Job Management** — Create, update, and archive job postings with detailed descriptions, requirements, and metadata
- **Candidate Pipeline** — Track candidates through configurable hiring stages (Applied → Screening → Interview → Offer → Hired/Rejected)
- **Application Tracking** — Manage applications with status updates, notes, and document attachments
- **Interview Scheduling** — Schedule and manage interviews with calendar integration and feedback collection
- **Team Collaboration** — Role-based access for recruiters, hiring managers, and interviewers with activity feeds
- **Analytics Dashboard** — Hiring metrics, pipeline reports, time-to-hire tracking, and source effectiveness
- **Search & Filtering** — Full-text search across candidates, jobs, and applications with advanced filters
- **Audit Logging** — Complete audit trail of all actions for compliance and accountability
- **Email Notifications** — Automated notifications for application updates, interview reminders, and team assignments

## Tech Stack

- **Backend:** Python 3.11+, FastAPI
- **Database:** SQLAlchemy 2.0 (async) with SQLite (development) / PostgreSQL (production)
- **Authentication:** JWT tokens via python-jose, password hashing via bcrypt
- **Validation:** Pydantic v2
- **Templating:** Jinja2 with Tailwind CSS
- **Testing:** pytest, pytest-asyncio, httpx
- **Server:** Uvicorn (ASGI)

## Folder Structure

```
talentflow-ats/
├── main.py                  # FastAPI application entry point with lifespan handler
├── database.py              # Async SQLAlchemy engine, session factory, Base
├── config.py                # Pydantic Settings for environment configuration
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (not committed)
├── models/
│   ├── __init__.py          # Re-exports all models
│   ├── user.py              # User model (recruiters, hiring managers, interviewers, admins)
│   ├── job.py               # Job posting model
│   ├── candidate.py         # Candidate profile model
│   ├── application.py       # Application model linking candidates to jobs
│   ├── interview.py         # Interview scheduling model
│   ├── feedback.py          # Interview feedback model
│   ├── note.py              # Notes/comments model
│   ├── department.py        # Department model
│   └── audit_log.py         # Audit log model
├── schemas/
│   ├── __init__.py
│   ├── user.py              # User request/response schemas
│   ├── job.py               # Job schemas
│   ├── candidate.py         # Candidate schemas
│   ├── application.py       # Application schemas
│   ├── interview.py         # Interview schemas
│   ├── feedback.py          # Feedback schemas
│   └── auth.py              # Auth token schemas
├── routes/
│   ├── __init__.py
│   ├── auth.py              # Login, register, token refresh
│   ├── users.py             # User CRUD and role management
│   ├── jobs.py              # Job posting CRUD
│   ├── candidates.py        # Candidate CRUD and search
│   ├── applications.py      # Application management and pipeline
│   ├── interviews.py        # Interview scheduling
│   ├── feedback.py          # Interview feedback
│   ├── dashboard.py         # Analytics and reporting endpoints
│   └── departments.py       # Department management
├── dependencies/
│   ├── __init__.py
│   ├── auth.py              # JWT token verification, get_current_user
│   └── database.py          # get_db session dependency
├── services/
│   ├── __init__.py
│   ├── auth_service.py      # Authentication logic
│   ├── job_service.py       # Job business logic
│   ├── candidate_service.py # Candidate business logic
│   ├── application_service.py # Application pipeline logic
│   └── email_service.py     # Email notification service
├── templates/
│   ├── base.html            # Base layout with Tailwind CSS
│   ├── dashboard/
│   ├── jobs/
│   ├── candidates/
│   ├── applications/
│   └── auth/
├── static/
│   └── css/
├── tests/
│   ├── conftest.py          # Shared fixtures (async client, test DB, auth helpers)
│   ├── test_auth.py         # Authentication endpoint tests
│   ├── test_jobs.py         # Job CRUD tests
│   ├── test_candidates.py   # Candidate tests
│   ├── test_applications.py # Application pipeline tests
│   └── test_interviews.py   # Interview scheduling tests
└── alembic/                 # Database migrations (optional)
    ├── alembic.ini
    └── versions/
```

## Setup Instructions

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd talentflow-ats
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Application
APP_NAME=TalentFlow ATS
DEBUG=true

# Database
DATABASE_URL=sqlite+aiosqlite:///./talentflow.db

# Authentication
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Email (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=noreply@talentflow.com

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
```

### 5. Run the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at:
- **API:** http://localhost:8000
- **Interactive Docs (Swagger):** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Usage Guide by Role

### Super Admin
- Manage all users, departments, and system settings
- View system-wide analytics and audit logs
- Create and assign roles to team members

### Recruiter
- Create and publish job postings
- Source and add candidates to the system
- Move candidates through pipeline stages
- Schedule interviews and coordinate with hiring managers
- Generate hiring reports

### Hiring Manager
- Review candidates assigned to their open positions
- Provide interview feedback and hiring decisions
- View pipeline analytics for their department's roles

### Interviewer
- View scheduled interviews and candidate profiles
- Submit structured interview feedback and scorecards
- Access interview guides and evaluation criteria

### Viewer (Read-Only)
- Browse open positions and candidate pipelines
- View reports and dashboards without edit permissions

## API Routes Summary

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register a new user |
| POST | `/api/auth/login` | Login and receive JWT tokens |
| POST | `/api/auth/refresh` | Refresh access token |
| POST | `/api/auth/logout` | Logout and invalidate token |

### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users` | List all users (admin) |
| GET | `/api/users/{id}` | Get user details |
| PUT | `/api/users/{id}` | Update user profile |
| DELETE | `/api/users/{id}` | Deactivate user (admin) |

### Jobs
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/jobs` | List jobs with filters |
| POST | `/api/jobs` | Create a new job posting |
| GET | `/api/jobs/{id}` | Get job details |
| PUT | `/api/jobs/{id}` | Update job posting |
| DELETE | `/api/jobs/{id}` | Archive job posting |

### Candidates
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/candidates` | List/search candidates |
| POST | `/api/candidates` | Add a new candidate |
| GET | `/api/candidates/{id}` | Get candidate profile |
| PUT | `/api/candidates/{id}` | Update candidate info |
| DELETE | `/api/candidates/{id}` | Remove candidate |

### Applications
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/applications` | List applications with filters |
| POST | `/api/applications` | Create application |
| GET | `/api/applications/{id}` | Get application details |
| PUT | `/api/applications/{id}` | Update application |
| PATCH | `/api/applications/{id}/stage` | Move to next pipeline stage |
| PATCH | `/api/applications/{id}/reject` | Reject application |

### Interviews
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/interviews` | List scheduled interviews |
| POST | `/api/interviews` | Schedule an interview |
| GET | `/api/interviews/{id}` | Get interview details |
| PUT | `/api/interviews/{id}` | Update interview |
| DELETE | `/api/interviews/{id}` | Cancel interview |

### Feedback
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/feedback` | Submit interview feedback |
| GET | `/api/feedback/{interview_id}` | Get feedback for interview |
| PUT | `/api/feedback/{id}` | Update feedback |

### Departments
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/departments` | List departments |
| POST | `/api/departments` | Create department |
| PUT | `/api/departments/{id}` | Update department |

### Dashboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/stats` | Overall hiring statistics |
| GET | `/api/dashboard/pipeline` | Pipeline stage breakdown |
| GET | `/api/dashboard/time-to-hire` | Time-to-hire metrics |

## Testing

### Run All Tests

```bash
pytest
```

### Run with Verbose Output

```bash
pytest -v
```

### Run Specific Test File

```bash
pytest tests/test_auth.py -v
```

### Run with Coverage Report

```bash
pip install pytest-cov
pytest --cov=. --cov-report=html
```

### Run Async Tests Only

```bash
pytest -m asyncio -v
```

## Deployment

### Vercel Deployment

1. Install the Vercel CLI:
   ```bash
   npm install -g vercel
   ```

2. Create a `vercel.json` in the project root:
   ```json
   {
     "builds": [
       {
         "src": "main.py",
         "use": "@vercel/python"
       }
     ],
     "routes": [
       {
         "src": "/(.*)",
         "dest": "main.py"
       }
     ]
   }
   ```

3. Set environment variables in the Vercel dashboard (Settings → Environment Variables). Use a PostgreSQL connection string for `DATABASE_URL` in production:
   ```
   DATABASE_URL=postgresql+asyncpg://user:password@host:5432/talentflow
   ```

4. Deploy:
   ```bash
   vercel --prod
   ```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t talentflow-ats .
docker run -p 8000:8000 --env-file .env talentflow-ats
```

### Production Considerations

- Set `DEBUG=false` in environment variables
- Use PostgreSQL with `asyncpg` driver instead of SQLite
- Set a strong, unique `SECRET_KEY`
- Configure proper `ALLOWED_ORIGINS` for CORS
- Enable HTTPS via reverse proxy (nginx, Caddy)
- Set up database backups and monitoring
- Use a process manager (systemd, supervisor) or container orchestration (Docker Compose, Kubernetes)

## License

Private — All rights reserved.