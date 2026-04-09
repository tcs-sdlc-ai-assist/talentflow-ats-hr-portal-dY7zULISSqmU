# Changelog

All notable changes to the TalentFlow ATS project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-01

### Added

#### Authentication & Session Management
- Cookie-based session authentication with secure HTTP-only cookies
- User registration and login with email and password
- Password hashing using bcrypt for secure credential storage
- Session expiration and automatic logout on inactivity
- CSRF protection for all state-changing operations

#### Role-Based Access Control (RBAC)
- Four distinct user roles: **Admin**, **Hiring Manager**, **Recruiter**, and **Interviewer**
- Role-based route protection with middleware enforcement
- Granular permission checks on all API endpoints
- Admin-only user management and role assignment capabilities

#### Job Requisition Management
- Full CRUD operations for job requisitions (create, read, update, delete)
- Job status lifecycle: Draft → Open → On Hold → Closed → Cancelled
- Support for job details including title, department, location, employment type, and salary range
- Rich text job descriptions and requirements fields
- Filtering and searching across all job requisitions
- Role-based visibility and editing permissions for requisitions

#### Candidate Database
- Centralized candidate profiles with contact information and professional details
- Skill tags system for categorizing and filtering candidates
- Resume and document attachment support
- Candidate search with filters by skills, experience, and availability
- Candidate source tracking (referral, job board, direct application, agency)
- Duplicate candidate detection based on email

#### Application Pipeline with Kanban View
- Visual Kanban board for tracking application stages
- Configurable pipeline stages: Applied → Screening → Interview → Offer → Hired → Rejected
- Drag-and-drop stage transitions with automatic timestamp logging
- Application status history with full audit trail
- Bulk actions for moving multiple applications between stages
- Per-requisition pipeline views with candidate cards

#### Interview Scheduling & Feedback
- Interview scheduling with date, time, and location (in-person or virtual)
- Interviewer assignment with calendar availability awareness
- Structured interview feedback forms with rating scales
- Multi-round interview support with stage-specific question sets
- Interview status tracking: Scheduled → Completed → Cancelled → No Show
- Consolidated feedback summaries per candidate across all interview rounds

#### Role-Based Dashboards
- **Admin Dashboard**: System-wide metrics, user management, and audit log access
- **Hiring Manager Dashboard**: Requisition overview, pipeline health, and time-to-fill analytics
- **Recruiter Dashboard**: Active candidates, upcoming interviews, and application funnel metrics
- **Interviewer Dashboard**: Assigned interviews, pending feedback submissions, and schedule view
- Real-time statistics and summary cards on all dashboards

#### Audit Trail Logging
- Comprehensive audit log for all create, update, and delete operations
- Logged fields: actor, action type, entity type, entity ID, timestamp, and change details
- Admin-accessible audit log viewer with filtering by user, action, entity, and date range
- Immutable audit records for compliance and accountability
- Automatic capture of IP address and user agent for each logged action