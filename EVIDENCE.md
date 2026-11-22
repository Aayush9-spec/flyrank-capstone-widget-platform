
# Implementation Evidence — FlyRank Widget Platform

## 1. Verification Summary

| Verification | Result |
|---|---|
| Python compilation (`compileall`) | Passed |
| JavaScript syntax (`node --check`) | Passed |
| Automated pytest suite | 4 passed |
| Alembic migration consistency | Passed |
| Git whitespace validation | Passed |
| PostgreSQL connection and migrations | Verified |
| Cross-origin widget loading | Verified |
| Cross-origin form submission | Verified |
| Lead persistence in PostgreSQL | Verified |
| Widget JavaScript cache headers | Verified |
| Public configuration ETag / 304 behavior | Verified |
| Rate-limit response | HTTP 429 verified |
| Oversized request rejection | HTTP 413 verified |
| Geo-provider failure isolation | Verified |
| Notification webhook delivery | 13 jobs delivered successfully |

## 2. Cross-Origin Widget Integration

A separate demo website was served at:

`http://localhost:5500`

The API was served at:

`http://localhost:8000`

The demo website loaded the widget JavaScript from the API using a script tag.

Observed browser network results:

| Request | Result |
|---|---|
| Widget JavaScript | HTTP 200 |
| Public widget configuration | HTTP 200 |
| Cross-origin preflight | HTTP 204 |
| Lead submission | HTTP 201 |

A test lead was submitted successfully and verified in PostgreSQL.

Example test submission:

- Name: Widget Demo Test
- Email: widget-demo@example.com
- Message: Testing cross-origin lead capture

The submission was stored with the expected visitor data.

## 3. Security and Validation Checks

### Rate Limiting

A burst of requests exceeded the configured per-widget/IP limit.

The API returned HTTP 429 for the rate-limited request while remaining available.

### Payload Size

A request larger than the configured 64 KB body limit was rejected with HTTP 413.

### Geo-Enrichment Failure

Geo-provider failure did not prevent lead persistence. The submission was stored with nullable location fields when enrichment was unavailable.

### Tenant Isolation

Dashboard queries and widget-management queries include the authenticated user's tenant ID in their database filters.

Tenant isolation was manually checked during implementation.

### Idempotency

The submission implementation uses a database uniqueness constraint on widget ID and idempotency key, with duplicate-key handling in the API.

## 4. Notification Worker

The worker supports:

- Webhook delivery
- Optional SMTP email delivery
- Idempotency header on webhook requests
- Retry with exponential backoff
- Maximum attempt limits
- Expired processing-job recovery
- Terminal failure alerts

A webhook endpoint was configured locally for integration testing.

Thirteen queued notification jobs were processed. All thirteen returned successful webhook responses and were marked `sent` in PostgreSQL.

No private webhook URL, password, or token is included in this repository.

## 5. Automated Test Results

Command:

```bash
python -m pytest -v
```

Tests:

| Test | Result |
|---|---|
| `test_successful_delivery` | Passed |
| `test_retry_after_delivery_failure` | Passed |
| `test_permanent_failure_alert` | Passed |
| `test_recover_expired_processing_job` | Passed |

Total: 4 passed.

## 6. Database and Migration Verification

PostgreSQL was run using Docker Compose.

The initial Alembic migration was applied successfully.

Command:

```bash
alembic check
```

Result:

`No new upgrade operations detected.`

The database includes tenant, user, widget, submission, and notification job tables with relevant indexes and uniqueness constraints.

## 7. Cache Verification

The versioned widget JavaScript asset returned:

- HTTP 200
- JavaScript content type
- `Cache-Control: public, max-age=31536000, immutable`

The public widget configuration endpoint supports ETag-based conditional requests and HTTP 304 responses.

## 8. Known Limitations and Future Improvements

- The automated test suite currently focuses on notification-worker behavior; broader API integration tests should be added.
- Tenant isolation, rate limiting, payload-size handling, and cross-origin behavior have also been manually verified.
- SMTP delivery requires external SMTP configuration and has not been established as a production email service.
- The owner interface currently exposes dashboard APIs rather than a complete graphical dashboard.
- The widget configuration is API-driven; a visual form builder is not included.
- Geo-enrichment depends on external providers and may return null location information.
- Production deployment still requires HTTPS, production secrets, trusted proxy configuration, and deployment-specific CORS settings.

## 9. Reproducibility

Use the setup and execution instructions in [README.md](README.md).

All local secrets and environment-specific configuration belong in `.env`, which is excluded from version control.
