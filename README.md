
# FlyRank — Embeddable Widget & Lead-Capture Platform

A multi-tenant platform for creating embeddable lead forms, collecting visitor submissions from external websites, and managing leads through secure APIs.

## Features

- JWT-based authentication and Argon2 password hashing
- Tenant-isolated widget CRUD operations
- Configurable widget fields and allowed origins
- Lightweight JavaScript embed widget using Shadow DOM
- Cross-origin lead submission with origin validation
- Pydantic request validation and payload-size protection
- IP-based rate limiting and honeypot spam protection
- Idempotent lead submissions
- Geo-enrichment with provider fallback
- Owner dashboard APIs for leads and statistics
- PostgreSQL persistence and Alembic migrations
- Background webhook/email notification worker
- Notification retries, exponential backoff, and terminal failure alerts
- Versioned JavaScript asset caching

## Technology Stack

- Python, FastAPI
- PostgreSQL, SQLAlchemy
- Alembic, Pydantic
- SlowAPI
- Vanilla JavaScript
- Docker Compose
- Pytest

## Architecture

```text
External Website
      |
      v
Embeddable JavaScript Widget
      |
      +----> Public Widget Configuration API
      |
      +----> Public Submission API
                    |
                    v
             Validation & Security
                    |
                    v
                PostgreSQL
                    |
          +---------+---------+
          |                   |
          v                   v
     Dashboard API      Notification Jobs
                              |
                              v
                      Background Worker
                              |
                       Webhook / Email
```

## Prerequisites

- Python 3.11 or later
- Docker and Docker Compose
- Node.js (for JavaScript syntax checking)
- Git

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/Aayush9-spec/flyrank-capstone-widget-platform.git
cd flyrank-capstone-widget-platform
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Update `.env` with a strong random `SECRET_KEY` and your local configuration.

Never commit `.env` or share its credentials.

### 5. Start PostgreSQL

```bash
docker compose up -d db
```

The default development database is exposed on port `5433`.

### 6. Apply database migrations

```bash
alembic upgrade head
```

### 7. Start the API

```bash
uvicorn app.main:app --reload --port 8000
```

API documentation:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health: http://localhost:8000/health

## Running the Notification Worker

Open a second terminal, activate the virtual environment, and run:

```bash
python -m app.workers.notifications
```

The worker polls pending notification jobs, delivers configured notifications, retries failures with exponential backoff, and alerts on terminal failures.

Configure webhook and/or SMTP settings in `.env`.

## Running the Demo Website

In another terminal:

```bash
python -m http.server 5500 --directory demo
```

Open:

http://localhost:5500

The demo website is served from a separate origin from the API, allowing cross-origin widget behavior to be tested locally.

## Embedding a Widget

After registering, logging in, and creating a widget through the API, copy its public ID.

Add the following snippet to the external website. Replace the public ID with the ID returned by the widget creation endpoint.

```html
<script
  src="http://localhost:8000/widget/v1/widget.js"
  data-widget-id="YOUR_PUBLIC_WIDGET_ID"
  async>
</script>
```

The widget retrieves its public configuration and renders the configured form.

For production, replace the local API URL with your deployed HTTPS API URL and configure the widget's allowed origins.

## API Reference

### Health

| Method | Endpoint |
|---|---|
| GET | `/` |
| GET | `/health` |

### Authentication

| Method | Endpoint |
|---|---|
| POST | `/api/auth/register` |
| POST | `/api/auth/login` |

### Widget Management

Requires authentication.

| Method | Endpoint |
|---|---|
| POST | `/api/widgets` |
| GET | `/api/widgets` |
| GET | `/api/widgets/{widget_id}` |
| PATCH | `/api/widgets/{widget_id}` |
| DELETE | `/api/widgets/{widget_id}` |

### Public Widget Delivery

| Method | Endpoint |
|---|---|
| GET | `/api/public/widgets/{public_id}/config` |
| GET | `/widget/v1/widget.js` |

### Lead Submission

| Method | Endpoint |
|---|---|
| OPTIONS | `/api/public/widgets/{public_id}/submissions` |
| POST | `/api/public/widgets/{public_id}/submissions` |

The submission endpoint supports an `Idempotency-Key` header.

### Owner Dashboard

Requires authentication.

| Method | Endpoint |
|---|---|
| GET | `/api/dashboard/submissions` |
| GET | `/api/dashboard/stats` |

## Security and Reliability

- Tenant ownership is derived from the authenticated user.
- Widget and dashboard queries are tenant-scoped.
- Public submissions validate widget status and allowed origin.
- Request bodies are limited to 64 KB.
- Submission rate limits are enforced using SlowAPI.
- Honeypot validation helps reject automated spam.
- Database uniqueness constraints protect idempotency.
- Geo-enrichment failures do not prevent lead storage.
- Notification delivery is processed separately from submission requests.
- Notification jobs support bounded retries and terminal failure reporting.
- Secrets are loaded from environment variables.

CORS is not used as a substitute for authentication or tenant authorization.

## Tests and Verification

Run the automated tests:

```bash
python -m pytest -v
```

Additional checks:

```bash
python -m compileall -q app migrations tests
node --check widget/widget.js
alembic check
```

The current automated suite includes notification success/skip, retry, permanent failure alert, and expired-job recovery tests.

See [EVIDENCE.md](EVIDENCE.md) for implementation verification details and manual integration checks.

## Project Design

See [DESIGN.md](DESIGN.md) for the system architecture, data model, API contracts, security decisions, and delivery milestones.

## Current Scope

The initial implementation provides API-driven widget configuration. A visual drag-and-drop form builder and a dedicated graphical owner dashboard are not included in this version.

## License

See [LICENSE](LICENSE).
