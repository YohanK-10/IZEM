# IZEM

AI-assisted feedback and live support queues, built with **Vue 3, TypeScript, FastAPI, and SQLAlchemy**.

IZEM connects participants requesting help with reviewers who can approve or edit AI-generated feedback. It combines role-based access, asynchronous AI jobs, real-time queue updates, and operational analytics in a single application.

This portfolio edition presents a collaboratively developed full-stack application. The team worked together across the frontend, backend, AI integration, and testing.

## Preview

![Live support queue with fictional participants](docs/screenshots/live-queue.png)

[Feedback review](docs/screenshots/feedback-review.png) · [Analytics dashboard](docs/screenshots/analytics.png)

## Product walkthrough

1. A participant submits a question with text or an image and joins a support queue.
2. A background job generates feedback while the interface reports progress.
3. A reviewer claims the request and approves, edits, or replaces the feedback.
4. The participant receives updates and can track the request through resolution.
5. An instructor manages sessions and views queue activity and feedback analytics.

## Engineering highlights

- Vue Composition API, Pinia stores, typed API clients, and role-aware routing.
- FastAPI endpoints with resource access checks and SQLAlchemy persistence.
- Background AI job processing with progress reporting and configurable models.
- WebSocket updates, reviewer coordination, and request lifecycle tracking.
- Text and image submissions, notifications, CSV analytics, and feedback exports.
- Optional Canvas API integration; the local demo uses no external service.
- Backend and frontend tests for authentication, permissions, queues, stores, and views.

## Run the local demo

Requires Python 3.11+ and Node.js 22+.

```sh
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.demo.example` to `.env`, then create the fictional dataset:

```sh
python scripts/seed_demo.py
cd frontend
npm ci --legacy-peer-deps
npm run build
cd ..
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://localhost:8000. Select a demo account on the login page and submit the form:

| Account | Experience |
| --- | --- |
| `teacher@example.com` | Session configuration and analytics |
| `ta@example.com` | Live queue and feedback review |
| `student@example.com` | Request submission and progress |

Demo mode bypasses email verification for fictional accounts and uses mock AI feedback. Use it locally. For normal configuration, start from `.env.example`; configure email and model credentials privately. This repository is a portfolio demonstration, not a production deployment guide.

For frontend development, run `npm run dev` in `frontend` and `uvicorn app.main:app --reload` in the repository root.

## Validation

```sh
pip install -r requirements-dev.txt
python -m pytest unit-tests -q
cd frontend
npm run type-check
npm test
npm run build
```

## Architecture

See [the architecture overview](docs/architecture.md) for the request flow and component responsibilities.

## Portfolio context

This edition uses neutral branding and a newly authored fictional workshop dataset. It contains no imported user records, submitted documents, original database files, or inherited commit history. The original domain terms (courses, students, teachers, and teaching assistants) remain in the data model and UI roles.
