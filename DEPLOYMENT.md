# TalentFlow ATS — Deployment Guide

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Environment Variables](#environment-variables)
- [Vercel Deployment](#vercel-deployment)
- [vercel.json Configuration](#verceljson-configuration)
- [Build Command](#build-command)
- [Database Considerations for Serverless](#database-considerations-for-serverless)
- [CI/CD with GitHub Actions](#cicd-with-github-actions)
- [Backup Procedures](#backup-procedures)
- [Troubleshooting](#troubleshooting)

---

## Overview

TalentFlow ATS is a Python FastAPI application designed to be deployed on Vercel as a serverless function. This guide covers the full deployment lifecycle including environment configuration, database strategy, CI/CD pipelines, and operational procedures.

---

## Prerequisites

- Python 3.11+
- A [Vercel](https://vercel.com) account linked to your GitHub repository
- A persistent database provider (see [Database Considerations](#database-considerations-for-serverless))
- Git installed locally
- Node.js 18+ (required by Vercel CLI)

Install the Vercel CLI globally:

```bash
npm install -g vercel
```

---

## Environment Variables

All configuration is managed through environment variables using Pydantic Settings (`BaseSettings` with `SettingsConfigDict`). The application reads from a `.env` file locally and from Vercel's environment variable dashboard in production.

### Required Variables

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | Database connection string | `postgresql+asyncpg://user:pass@host:5432/talentflow` |
| `SECRET_KEY` | JWT signing key (min 32 chars) | `a-very-long-random-secret-key-here-min-32` |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token TTL in minutes | `30` |

### Optional Variables

| Variable | Description | Default |
|---|---|---|
| `ENVIRONMENT` | Runtime environment | `production` |
| `DEBUG` | Enable debug mode | `false` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `*` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Setting Variables on Vercel

Via the Vercel dashboard:

1. Navigate to your project → **Settings** → **Environment Variables**
2. Add each variable for the appropriate scope (Production, Preview, Development)
3. Redeploy after adding or changing variables

Via the Vercel CLI:

```bash
vercel env add DATABASE_URL production
vercel env add SECRET_KEY production
vercel env add ALGORITHM production
vercel env add ACCESS_TOKEN_EXPIRE_MINUTES production
```

> **Security Note:** Never commit `.env` files to version control. Ensure `.env` is listed in `.gitignore`.

---

## Vercel Deployment

### Initial Setup

1. Push your repository to GitHub.
2. Import the project in the Vercel dashboard: **New Project** → select your repo.
3. Vercel auto-detects the `vercel.json` configuration.
4. Set all required environment variables before the first deployment.
5. Click **Deploy**.

### Manual Deployment via CLI

```bash
# Login to Vercel
vercel login

# Deploy to preview
vercel

# Deploy to production
vercel --prod
```

---

## vercel.json Configuration

Create a `vercel.json` file in the project root:

```json
{
  "version": 2,
  "builds": [
    {
      "src": "main.py",
      "use": "@vercel/python",
      "config": {
        "maxLambdaSize": "50mb",
        "runtime": "python3.11"
      }
    }
  ],
  "routes": [
    {
      "src": "/static/(.*)",
      "dest": "/static/$1"
    },
    {
      "src": "/(.*)",
      "dest": "main.py"
    }
  ],
  "env": {
    "ENVIRONMENT": "production"
  }
}
```

### Key Configuration Notes

- **`src: "main.py"`** — Vercel expects the FastAPI `app` object to be importable from the entry point file. Ensure `main.py` exposes `app = FastAPI(...)` at module level.
- **`maxLambdaSize: "50mb"`** — Increase if your dependencies are large (e.g., ML libraries).
- **Static files** — The first route rule serves static assets directly without hitting the Python function.
- **Catch-all route** — All other requests are routed to the FastAPI application.

---

## Build Command

Vercel automatically installs dependencies from `requirements.txt` during the build phase. No custom build command is needed for a standard FastAPI project.

If you need a custom build step (e.g., running database migrations or compiling assets):

```json
{
  "builds": [
    {
      "src": "main.py",
      "use": "@vercel/python",
      "config": {
        "runtime": "python3.11"
      }
    }
  ],
  "buildCommand": "pip install -r requirements.txt"
}
```

### Local Build Verification

Always verify the build locally before deploying:

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Run the application
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Run tests
pytest tests/ -v
```

---

## Database Considerations for Serverless

### SQLite Limitations on Vercel

**SQLite cannot be used in production on Vercel.** Vercel serverless functions run in ephemeral, read-only file systems. This means:

- SQLite database files are **not persisted** between invocations
- Each cold start creates a fresh, empty database
- Concurrent function instances **cannot share** a SQLite file
- Write operations to the filesystem will fail or be lost

SQLite is acceptable **only** for:
- Local development
- Running tests in CI/CD

### Recommended Production Databases

| Provider | Connection String Format | Free Tier |
|---|---|---|
| **Neon** (PostgreSQL) | `postgresql+asyncpg://user:pass@ep-xxx.us-east-2.aws.neon.tech/dbname?sslmode=require` | Yes |
| **Supabase** (PostgreSQL) | `postgresql+asyncpg://postgres:pass@db.xxx.supabase.co:5432/postgres` | Yes |
| **PlanetScale** (MySQL) | `mysql+aiomysql://user:pass@aws.connect.psdb.cloud/dbname?ssl=true` | Yes |
| **Railway** (PostgreSQL) | `postgresql+asyncpg://postgres:pass@xxx.railway.app:5432/railway` | Yes |
| **AWS RDS** (PostgreSQL) | `postgresql+asyncpg://user:pass@xxx.rds.amazonaws.com:5432/dbname` | No |

### Migration Strategy

For production deployments, run migrations **before** deploying:

```bash
# Generate a migration (development)
alembic revision --autogenerate -m "description of changes"

# Apply migrations to production database
DATABASE_URL="postgresql+asyncpg://..." alembic upgrade head
```

> **Important:** Never run `Base.metadata.create_all()` in production. Use Alembic for all schema changes.

### Connection Pooling for Serverless

Serverless functions open and close database connections frequently. Use connection pooling to avoid exhausting database connections:

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=300,  # Recycle connections every 5 minutes
    pool_pre_ping=True,  # Verify connections before use
)
```

For Neon or Supabase, consider using their built-in connection poolers (PgBouncer) and set:

```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=1,       # Minimal pool for serverless
    max_overflow=2,
    pool_pre_ping=True,
)
```

---

## CI/CD with GitHub Actions

Create `.github/workflows/ci.yml`:

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: "3.11"

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: "pip"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run linting
        run: |
          pip install ruff
          ruff check .

      - name: Run tests
        env:
          DATABASE_URL: "sqlite+aiosqlite:///./test.db"
          SECRET_KEY: "test-secret-key-minimum-32-characters-long"
          ALGORITHM: "HS256"
          ACCESS_TOKEN_EXPIRE_MINUTES: "30"
          ENVIRONMENT: "testing"
        run: |
          pytest tests/ -v --tb=short --strict-markers

      - name: Check test coverage
        env:
          DATABASE_URL: "sqlite+aiosqlite:///./test.db"
          SECRET_KEY: "test-secret-key-minimum-32-characters-long"
          ALGORITHM: "HS256"
          ACCESS_TOKEN_EXPIRE_MINUTES: "30"
          ENVIRONMENT: "testing"
        run: |
          pip install pytest-cov
          pytest tests/ --cov=. --cov-report=term-missing --cov-fail-under=70

  deploy-preview:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Deploy to Vercel Preview
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}

  deploy-production:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Deploy to Vercel Production
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          vercel-args: "--prod"
```

### Required GitHub Secrets

Add these secrets in your GitHub repository under **Settings** → **Secrets and variables** → **Actions**:

| Secret | Description | How to Obtain |
|---|---|---|
| `VERCEL_TOKEN` | Vercel API token | Vercel Dashboard → Settings → Tokens |
| `VERCEL_ORG_ID` | Vercel organization/team ID | Run `vercel link` locally, check `.vercel/project.json` |
| `VERCEL_PROJECT_ID` | Vercel project ID | Run `vercel link` locally, check `.vercel/project.json` |

---

## Backup Procedures

### Database Backups

#### Automated Backups with pg_dump (PostgreSQL)

Create a backup script `scripts/backup_db.sh`:

```bash
#!/bin/bash
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups"
BACKUP_FILE="${BACKUP_DIR}/talentflow_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "Starting database backup..."
pg_dump "${DATABASE_URL}" | gzip > "${BACKUP_FILE}"
echo "Backup saved to ${BACKUP_FILE}"

# Remove backups older than 30 days
find "${BACKUP_DIR}" -name "*.sql.gz" -mtime +30 -delete
echo "Old backups cleaned up."
```

#### Scheduled Backups with GitHub Actions

Add to `.github/workflows/backup.yml`:

```yaml
name: Database Backup

on:
  schedule:
    - cron: "0 2 * * *"  # Daily at 2:00 AM UTC
  workflow_dispatch:  # Allow manual trigger

jobs:
  backup:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Install PostgreSQL client
        run: sudo apt-get install -y postgresql-client

      - name: Create backup
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          TIMESTAMP=$(date +%Y%m%d_%H%M%S)
          pg_dump "${DATABASE_URL}" | gzip > "backup_${TIMESTAMP}.sql.gz"

      - name: Upload backup artifact
        uses: actions/upload-artifact@v4
        with:
          name: db-backup-${{ github.run_id }}
          path: "*.sql.gz"
          retention-days: 30
```

#### Managed Database Backups

Most managed database providers include automatic backups:

- **Neon:** Point-in-time recovery included on all plans
- **Supabase:** Daily backups on Pro plan; manual backups via dashboard
- **Railway:** Automatic daily backups
- **AWS RDS:** Automated backups with configurable retention (up to 35 days)

### Application Data Backups

For uploaded files or documents stored outside the database:

1. Use cloud object storage (AWS S3, Cloudflare R2, Vercel Blob) instead of local filesystem
2. Enable versioning on the storage bucket
3. Configure lifecycle rules for automatic archival

---

## Troubleshooting

### Common Deployment Issues

#### 1. `ModuleNotFoundError: No module named 'xyz'`

**Cause:** Missing dependency in `requirements.txt`.

**Fix:** Ensure all dependencies are listed:

```bash
pip freeze > requirements.txt
```

Or verify the specific package is included:

```bash
grep "xyz" requirements.txt
```

#### 2. `Internal Server Error (500)` on Cold Start

**Cause:** Application fails during initialization — usually a missing environment variable or database connection failure.

**Fix:**
- Check Vercel function logs: **Project** → **Deployments** → select deployment → **Functions** tab
- Verify all required environment variables are set
- Test the database connection string locally:

```bash
python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine('YOUR_DATABASE_URL')
async def test():
    async with engine.connect() as conn:
        result = await conn.execute(text('SELECT 1'))
        print('Connection successful:', result.scalar())
asyncio.run(test())
"
```

#### 3. `Function Size Exceeds Limit`

**Cause:** Lambda package exceeds Vercel's size limit (50MB default, 250MB max).

**Fix:**
- Increase `maxLambdaSize` in `vercel.json` (up to `"250mb"`)
- Remove unnecessary dependencies from `requirements.txt`
- Use lighter alternatives (e.g., `orjson` instead of heavy JSON libraries)

#### 4. `CORS Error` in Browser Console

**Cause:** Frontend origin not in the allowed CORS origins list.

**Fix:** Update the `CORS_ORIGINS` environment variable to include your frontend domain:

```
CORS_ORIGINS=https://your-frontend.vercel.app,https://your-domain.com
```

#### 5. `MissingGreenlet: greenlet_spawn has not been called`

**Cause:** Lazy loading a SQLAlchemy relationship in an async context.

**Fix:** Add `lazy="selectin"` to ALL `relationship()` declarations, or use `selectinload()` in queries:

```python
from sqlalchemy.orm import selectinload

result = await db.execute(
    select(Candidate).options(selectinload(Candidate.applications))
)
```

#### 6. `Connection Refused` or `Too Many Connections`

**Cause:** Serverless functions opening too many database connections.

**Fix:**
- Use a connection pooler (PgBouncer, Neon pooler, Supabase pooler)
- Reduce `pool_size` to 1-2 for serverless
- Enable `pool_pre_ping=True` to handle stale connections
- Use the pooler endpoint URL instead of the direct database URL

#### 7. `sqlite3.OperationalError: attempt to write a readonly database`

**Cause:** Using SQLite on Vercel's read-only filesystem.

**Fix:** Switch to a managed PostgreSQL database. See [Database Considerations](#database-considerations-for-serverless).

#### 8. `ValidationError: Extra inputs are not permitted`

**Cause:** Vercel injects extra environment variables that Pydantic Settings rejects.

**Fix:** Ensure your Settings class includes `extra="ignore"`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    # ... fields
```

#### 9. Deployment Succeeds but Pages Return `404`

**Cause:** Routes not matching the `vercel.json` catch-all, or router prefixes doubled.

**Fix:**
- Verify the catch-all route `"src": "/(.*)"` is the **last** entry in `routes`
- Check that router prefixes are defined in only one place (either `APIRouter(prefix=...)` or `app.include_router(..., prefix=...)`, not both)

#### 10. Slow Cold Starts

**Cause:** Large dependency tree or heavy initialization logic.

**Fix:**
- Minimize top-level imports; use lazy imports for heavy modules
- Reduce `requirements.txt` to only necessary packages
- Pre-warm functions with a health check endpoint:

```python
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

Set up an external cron (e.g., UptimeRobot, GitHub Actions schedule) to ping `/health` every 5 minutes.

### Viewing Logs

- **Vercel Dashboard:** Project → Deployments → select deployment → **Runtime Logs**
- **Vercel CLI:** `vercel logs your-project-url`
- **Real-time streaming:** `vercel logs your-project-url --follow`

### Rolling Back a Deployment

If a deployment introduces issues:

1. Go to **Project** → **Deployments** in the Vercel dashboard
2. Find the last known good deployment
3. Click the three-dot menu → **Promote to Production**

Or via CLI:

```bash
vercel rollback
```

---

## Security Checklist

Before deploying to production, verify:

- [ ] `SECRET_KEY` is a cryptographically random string (min 32 characters)
- [ ] `DEBUG` is set to `false`
- [ ] `CORS_ORIGINS` lists only trusted domains (not `*`)
- [ ] Database credentials use a dedicated application user (not superuser)
- [ ] `.env` file is in `.gitignore`
- [ ] All passwords are hashed with bcrypt (never stored in plain text)
- [ ] HTTPS is enforced (Vercel handles this automatically)
- [ ] Rate limiting is configured for authentication endpoints
- [ ] SQL injection is prevented by using parameterized queries (SQLAlchemy ORM)
- [ ] Sensitive data is not logged (passwords, tokens, PII)