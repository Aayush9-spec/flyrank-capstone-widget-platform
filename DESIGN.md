# Embeddable Widget & Lead-Capture Platform — System Design

## 1. Project Overview

A multi-tenant embeddable widget and lead-capture platform that allows customers to create configurable lead forms, embed them on external websites using a single JavaScript snippet, securely collect visitor submissions, and monitor leads through an owner dashboard.

## 2. Technology Stack

- Backend: Python, FastAPI
- Database: PostgreSQL
- ORM: SQLAlchemy
- Migrations: Alembic
- Validation: Pydantic
- Rate Limiting: SlowAPI or equivalent
- Widget: Vanilla JavaScript, HTML, CSS
- Testing: Pytest
- Infrastructure: Docker and Docker Compose
- Email testing: Console backend or Mailpit

## 3. Architecture

The application follows a layered architecture:

1. API Layer — HTTP endpoints, authentication, CORS, and request handling.
2. Service Layer — Business logic, tenant authorization, submission processing, enrichment, and notifications.
3. Data Layer — SQLAlchemy models, database queries, migrations, and indexes.
4. Delivery Layer — Public widget configuration and versioned JavaScript bundle.
5. Frontend Layer — Owner dashboard and embeddable visitor-facing widget.
6. Background Jobs — Retryable email/webhook delivery and failure reporting.

## 4. Database Design

### Tenant
- id: UUID, primary key
- name: String
- created_at: Timestamp

### User
- id: UUID, primary key
- tenant_id: UUID, foreign key
- email: String, unique
- password_hash: String
- created_at: Timestamp

### Widget
- id: UUID, primary key
- tenant_id: UUID, foreign key
- name: String
- configuration: JSON
- allowed_origins: JSON
- version: Integer
- is_active: Boolean
- created_at: Timestamp
- updated_at: Timestamp

### Submission
- id: UUID, primary key
- tenant_id: UUID, foreign key
- widget_id: UUID, foreign key
- visitor_data: JSON
- ip_address: String
- country: String, nullable
- city: String, nullable
- idempotency_key: String, nullable
- created_at: Timestamp

### NotificationJob
- id: UUID, primary key
- submission_id: UUID, foreign key
- status: String
- attempts: Integer
- last_error: Text, nullable
- next_retry_at: Timestamp, nullable
- created_at: Timestamp

### Database Constraints and Indexes

- Enforce tenant ownership with foreign keys and tenant-scoped queries.
- Add indexes on Widget (tenant_id), Submission (tenant_id, widget_id, created_at), and NotificationJob (status, next_retry_at).
- Enforce idempotency uniqueness using a unique constraint on (widget_id, idempotency_key) when the key is present.
- Use database constraints to prevent invalid widget versions and notification statuses.
- User email addresses are globally unique in the initial version.
- Store IP addresses only when required for security or enrichment, and avoid exposing them in dashboard responses.

## 5. Tenant Isolation and Security

- Every customer-owned resource is associated with a tenant.
- Authenticated requests derive tenant identity from the authenticated user, never from an untrusted client-supplied tenant ID.
- Every widget and submission query must enforce tenant ownership.
- Public submission endpoints must verify the widget, its active status, and permitted origin.
- Validate request fields and enforce payload size limits.
- Use rate limiting and a honeypot field to reduce spam.
- Store secrets in environment variables, never in source control.
- Use parameterized database operations through SQLAlchemy.
- Public widget identifiers are not authentication credentials.
- Validate the request Origin against the widget's exact allowed-origin list. Reject unauthorized origins.
- CORS is a browser security mechanism, not a replacement for tenant authorization.
- Trust forwarded IP headers only from explicitly trusted proxies.
- Never log passwords, authentication tokens, or visitor submission contents.

## 6. End-to-End Widget Flow

1. Owner signs in and creates a widget.
2. Backend stores widget configuration and generates a public embed identifier.
3. Owner copies a JavaScript embed snippet.
4. External website loads the widget script.
5. Script fetches the public widget configuration.
6. Widget renders the configured form.
7. Visitor submits the form.
8. Backend validates origin, payload, honeypot, and rate limits.
9. Submission is stored with an idempotency key where supplied.
10. Geo-enrichment is attempted using provider A, with provider B as fallback.
11. Notification work is queued separately and retried on failure.
12. Owner views submissions and analytics in the dashboard.


## 7. API Contracts

### Authentication
- POST /api/auth/register
- POST /api/auth/login

### Widget Management (Authenticated)
- POST /api/widgets
- GET /api/widgets
- GET /api/widgets/{widget_id}
- PATCH /api/widgets/{widget_id}
- DELETE /api/widgets/{widget_id}

### Public Widget Delivery
- GET /api/public/widgets/{public_id}/config
- GET /widget/v1/widget.js

### Public Lead Submission
- OPTIONS /api/public/widgets/{public_id}/submissions
- POST /api/public/widgets/{public_id}/submissions

### Owner Dashboard (Authenticated)
- GET /api/dashboard/submissions
- GET /api/dashboard/stats

### Health
- GET /
- GET /health


## 8. Reliability and Performance

- Add database migrations and indexes for tenant_id, widget_id, and created_at.
- Use idempotency to prevent duplicate submissions.
- Apply appropriate cache headers to public configuration and JavaScript assets.
- Return clean 4xx JSON responses for invalid requests.
- Rate-limit abusive submission traffic without taking down the API.
- Geo-enrichment failures must not prevent submission storage.
- Email and webhook failures must not change a successful submission response.
- Background notification jobs must support retries and failure alerts.
- Notification jobs use bounded retries with exponential backoff.
- Permanently failed jobs are marked as failed and trigger an operational alert.
- Job processing must be safe against duplicate execution.
- Submission storage is completed independently of optional geo-enrichment and notification delivery.
- Public configuration responses use version-aware caching and appropriate cache invalidation.
- The initial implementation does not use AI; AI cost tracking is therefore outside the initial scope.

## 9. Testing and Evidence

Tests will cover:

- Valid cross-origin submission and database persistence.
- Invalid and oversized payload handling.
- Rate limiting and HTTP 429 responses.
- Honeypot spam rejection.
- Tenant A isolation from Tenant B.
- Geo-provider fallback and total provider failure.
- Email and webhook failure isolation.
- Idempotent submission behavior.
- Widget and configuration cache headers.
- Widget rendering on a separate website origin.

## 10. Explicit Non-Goal

The initial version will not include a visual drag-and-drop form builder. Widget configuration will use predefined supported fields and settings.

## 11. Delivery Milestones

- Phase 1: System design, data model, API contracts, and architecture.
- Phase 2: Secure submission API, validation, CORS, rate limiting, spam protection, enrichment, and notification reliability.
- Phase 3: Embeddable JavaScript widget, public delivery, dashboard analytics, cross-origin demo, and final evidence.
