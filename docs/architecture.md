# Architecture overview

IZEM is a Vue client backed by a FastAPI application. FastAPI serves the compiled frontend and starts the background AI worker loop through its lifespan handler.

## Implementation map

| Concern | Main implementation |
| --- | --- |
| App lifecycle and frontend hosting | [app/main.py](../app/main.py) |
| Resource access checks | [app/auth/permissions.py](../app/auth/permissions.py) |
| Schema and database setup | [app/models/db.py](../app/models/db.py) |
| HTTP workflows | [app/routes/api.py](../app/routes/api.py) |
| Sign-off administration and analytics | [app/routes/admin_signoff.py](../app/routes/admin_signoff.py) |
| Database-backed AI work | [app/services/ai_job_queue.py](../app/services/ai_job_queue.py) |
| Feedback generation | [app/services/openai_feedback.py](../app/services/openai_feedback.py) |
| Reviewer ownership and actions | [app/services/help_request_service.py](../app/services/help_request_service.py) |
| Client transport | [frontend/src/app/api/client.ts](../frontend/src/app/api/client.ts) |

## Submission and AI work

Submission saves the help request and its queued AI state together. Workers poll the database for pending requests, claim them with a conditional update, and execute synchronous feedback generation in a thread. Generated feedback and failure state are persisted on the request. Startup recovery requeues processing jobs older than the configured stale threshold.

## Review and updates

Review actions validate access and establish reviewer ownership before updating a request. They save final feedback, review history, notifications, and resolution timing. The frontend polls HTTP endpoints for queue, request, and notification updates. The WebSocket manager module is currently unconnected to registered routes and client transport.

## Demo and persistence

The synthetic seed script creates fictional accounts and a workshop with active and resolved requests. Mock AI avoids model credentials. SQLite provides the default local setup, while SQLAlchemy connection configuration also supports PostgreSQL. Canvas integration is optional and defaults to a placeholder hostname.

For the diagram, API summary, setup instructions, and implementation tradeoffs, see [the README](../README.md).
