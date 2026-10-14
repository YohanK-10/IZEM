import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import update

from app.models.db import HelpRequest, RequestStatus, SessionLocal

logger = logging.getLogger(__name__)


AI_QUEUE_WORKERS = max(1, int(os.getenv("AI_QUEUE_WORKERS", "1")))
AI_QUEUE_POLL_INTERVAL_SECONDS = max(0.2, float(os.getenv("AI_QUEUE_POLL_INTERVAL_SECONDS", "1.0")))
AI_QUEUE_STALE_SECONDS = max(30, int(os.getenv("AI_QUEUE_STALE_SECONDS", "180")))


class AIJobQueue:
    def __init__(self) -> None:
        self._started = False
        self._stop_event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        if self._started:
            return

        self._started = True
        self._stop_event.clear()
        self._requeue_stale_jobs()

        for index in range(AI_QUEUE_WORKERS):
            task = asyncio.create_task(self._worker_loop(index + 1))
            self._tasks.append(task)

        logger.info("Started AI job queue with %s worker(s)", AI_QUEUE_WORKERS)

    async def stop(self) -> None:
        if not self._started:
            return

        self._stop_event.set()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self._started = False
        logger.info("Stopped AI job queue")

    def enqueue_request(self, request_id: int) -> bool:
        db = SessionLocal()
        try:
            request = db.query(HelpRequest).filter(HelpRequest.id == request_id).first()
            if not request:
                return False
            if request.status != RequestStatus.PENDING:
                logger.info("Skipping AI enqueue for request %s because it is %s", request_id, request.status.value)
                return False
            if request.ai_queue_state in {"queued", "processing"}:
                return True

            now = datetime.utcnow()
            request.ai_queue_state = "queued"
            request.ai_queue_enqueued_at = now
            request.ai_queue_started_at = None
            request.ai_queue_error = None
            request.ai_progress_status = "queued"
            request.last_progress_update = now
            db.commit()
            return True
        finally:
            db.close()

    def _requeue_stale_jobs(self) -> None:
        db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(seconds=AI_QUEUE_STALE_SECONDS)
            stale_jobs = db.query(HelpRequest).filter(
                HelpRequest.status == RequestStatus.PENDING,
                HelpRequest.ai_queue_state == "processing",
                HelpRequest.ai_queue_started_at.is_not(None),
                HelpRequest.ai_queue_started_at < cutoff,
            ).all()

            if not stale_jobs:
                return

            now = datetime.utcnow()
            for request in stale_jobs:
                request.ai_queue_state = "queued"
                request.ai_queue_enqueued_at = now
                request.ai_queue_started_at = None
                request.ai_queue_error = None
                request.ai_progress_status = "queued"
                request.last_progress_update = now

            db.commit()
            logger.warning("Re-queued %s stale AI job(s)", len(stale_jobs))
        finally:
            db.close()

    async def _worker_loop(self, worker_id: int) -> None:
        from app.services.openai_feedback import feedback_generator

        while not self._stop_event.is_set():
            request_id = await self._claim_next_request()
            if request_id is None:
                await asyncio.sleep(AI_QUEUE_POLL_INTERVAL_SECONDS)
                continue

            try:
                await asyncio.to_thread(feedback_generator.generate_feedback_background, request_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("AI worker %s crashed while processing request %s", worker_id, request_id)

    async def _claim_next_request(self) -> Optional[int]:
        while True:
            db = SessionLocal()
            try:
                request = db.query(HelpRequest).filter(
                    HelpRequest.status == RequestStatus.PENDING,
                    HelpRequest.ai_queue_state == "queued",
                ).order_by(
                    HelpRequest.ai_queue_enqueued_at.asc(),
                    HelpRequest.id.asc(),
                ).first()

                if not request:
                    return None

                request_id = request.id
                now = datetime.utcnow()
                claimed = db.execute(
                    update(HelpRequest)
                    .where(
                        HelpRequest.id == request_id,
                        HelpRequest.status == RequestStatus.PENDING,
                        HelpRequest.ai_queue_state == "queued",
                    )
                    .values(
                        ai_queue_state="processing",
                        ai_queue_started_at=now,
                        ai_queue_error=None,
                        ai_progress_status="processing",
                        last_progress_update=now,
                    )
                )
                db.commit()

                if claimed.rowcount:
                    return request_id
            finally:
                db.close()


ai_job_queue = AIJobQueue()
