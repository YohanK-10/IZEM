from datetime import datetime
import logging

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.db import (
    Assignment,
    Course,
    FeedbackHistory,
    HelpRequest,
    Notification,
    Question,
    RequestStatus,
    TAAssignment,
    User,
)
from app.services.emailer import email_service
from app.services.feedback_formatting import format_feedback_text

logger = logging.getLogger(__name__)

# Only requests in these states can be acted on by a TA.
ACTIONABLE_STATUSES = {RequestStatus.PENDING, RequestStatus.AI_GENERATED}


def _clear_ai_queue_fields(help_request: HelpRequest):
    help_request.ai_queue_state = None
    help_request.ai_queue_enqueued_at = None
    help_request.ai_queue_started_at = None
    help_request.ai_queue_error = None


def _review_conflict_message(db: Session, assigned_ta_id: int | None) -> str:
    if not assigned_ta_id:
        return "This request is already being reviewed by another TA."
    reviewer = db.query(User).filter(User.id == assigned_ta_id).first()
    if reviewer and reviewer.name:
        return f"This request is already being reviewed by {reviewer.name}."
    return "This request is already being reviewed by another TA."


def ensure_request_owned_by_reviewer(db: Session, request_id: int, reviewer_id: int) -> HelpRequest | None:
    """Ensure a request is owned by the reviewing TA before acting on it."""
    help_request = db.query(HelpRequest).filter(HelpRequest.id == request_id).first()
    if not help_request:
        return None
    if help_request.status not in ACTIONABLE_STATUSES:
        raise ValueError(f"Cannot review a request with status '{help_request.status.value}'")

    if help_request.assigned_ta_id == reviewer_id:
        if not help_request.started_helping_at:
            help_request.started_helping_at = datetime.utcnow()
            db.commit()
        return help_request

    if help_request.assigned_ta_id is not None:
        raise ValueError(_review_conflict_message(db, help_request.assigned_ta_id))

    now = datetime.utcnow()
    claimed = db.query(HelpRequest).filter(
        HelpRequest.id == request_id,
        HelpRequest.status.in_(list(ACTIONABLE_STATUSES)),
        HelpRequest.assigned_ta_id == None,
    ).update(
        {
            HelpRequest.assigned_ta_id: reviewer_id,
            HelpRequest.started_helping_at: now,
        },
        synchronize_session=False,
    )

    if claimed:
        db.commit()
        return db.query(HelpRequest).filter(HelpRequest.id == request_id).first()

    db.rollback()
    help_request = db.query(HelpRequest).filter(HelpRequest.id == request_id).first()
    if not help_request:
        return None
    if help_request.status not in ACTIONABLE_STATUSES:
        raise ValueError(f"Cannot review a request with status '{help_request.status.value}'")
    if help_request.assigned_ta_id == reviewer_id:
        return help_request
    raise ValueError(_review_conflict_message(db, help_request.assigned_ta_id))


def approve_request(db: Session, request_id: int, reviewer_id: int):
    """Approve AI feedback and return (help_request, question, assignment)."""
    help_request = ensure_request_owned_by_reviewer(db, request_id, reviewer_id)
    if not help_request:
        return None, None, None

    help_request.final_feedback = format_feedback_text(help_request.ai_feedback) or help_request.ai_feedback
    help_request.status = RequestStatus.APPROVED
    help_request.resolved_at = datetime.utcnow()
    help_request.queue_position = None
    _clear_ai_queue_fields(help_request)

    db.add(
        FeedbackHistory(
            help_request_id=request_id,
            ta_id=reviewer_id,
            action="approved",
            feedback_text=help_request.ai_feedback,
        )
    )
    db.add(
        Notification(
            user_id=help_request.student_id,
            help_request_id=request_id,
            type="feedback_ready",
            message=(
                "Your overtime feedback is ready - check your email for the full response!"
                if help_request.is_overtime
                else "Your feedback has been approved and is ready to view!"
            ),
        )
    )
    db.commit()

    question = db.query(Question).filter(Question.id == help_request.question_id).first()
    assignment = db.query(Assignment).filter(Assignment.id == question.assignment_id).first() if question else None

    if help_request.is_overtime:
        _send_overtime_email(db, help_request, question, assignment, reviewer_id)

    return help_request, question, assignment


def edit_request(db: Session, request_id: int, reviewer_id: int, feedback: str):
    """Edit and approve feedback and return (help_request, question, assignment)."""
    help_request = ensure_request_owned_by_reviewer(db, request_id, reviewer_id)
    if not help_request:
        return None, None, None

    help_request.final_feedback = feedback
    help_request.status = RequestStatus.EDITED
    help_request.resolved_at = datetime.utcnow()
    help_request.queue_position = None
    _clear_ai_queue_fields(help_request)

    db.add(
        FeedbackHistory(
            help_request_id=request_id,
            ta_id=reviewer_id,
            action="edited",
            feedback_text=feedback,
        )
    )
    db.add(
        Notification(
            user_id=help_request.student_id,
            help_request_id=request_id,
            type="feedback_ready",
            message=(
                "Your overtime feedback is ready - check your email for the full response!"
                if help_request.is_overtime
                else "Your feedback has been reviewed and is ready to view!"
            ),
        )
    )
    db.commit()

    question = db.query(Question).filter(Question.id == help_request.question_id).first()
    assignment = db.query(Assignment).filter(Assignment.id == question.assignment_id).first() if question else None

    if help_request.is_overtime:
        _send_overtime_email(db, help_request, question, assignment, reviewer_id)

    return help_request, question, assignment


def reject_request(db: Session, request_id: int, reviewer_id: int, reason: str):
    """Mark a request for in-person help and return (help_request, question, assignment)."""
    help_request = ensure_request_owned_by_reviewer(db, request_id, reviewer_id)
    if not help_request:
        return None, None, None

    help_request.status = RequestStatus.IN_PERSON
    help_request.resolved_at = datetime.utcnow()
    help_request.final_feedback = reason
    help_request.queue_position = None
    _clear_ai_queue_fields(help_request)

    db.add(
        FeedbackHistory(
            help_request_id=request_id,
            ta_id=reviewer_id,
            action="rejected",
            feedback_text=f"In-person help required: {reason}",
        )
    )
    db.add(
        Notification(
            user_id=help_request.student_id,
            help_request_id=request_id,
            type="in_person_required",
            message=f"Raise your hand! A TA is coming to help you. Note: {reason}",
        )
    )
    db.commit()

    question = db.query(Question).filter(Question.id == help_request.question_id).first()
    assignment = db.query(Assignment).filter(Assignment.id == question.assignment_id).first() if question else None
    return help_request, question, assignment


def _send_overtime_email(db: Session, help_request: HelpRequest, question, assignment, reviewer_id: int):
    """Send feedback email to student for an overtime request. Fires and forgets; errors are logged."""
    try:
        student = db.query(User).filter(User.id == help_request.student_id).first()
        reviewer = db.query(User).filter(User.id == reviewer_id).first()
        if not student or not student.email:
            return
        email_service.send_overtime_feedback_email(
            to_email=student.email,
            student_name=student.name,
            assignment_name=assignment.name if assignment else "Unknown assignment",
            question_number=question.question_number if question else 0,
            feedback_text=help_request.final_feedback or "",
            ta_name=reviewer.name if reviewer else "Your TA",
        )
    except Exception as exc:
        logger.error(f"Failed to send overtime feedback email for request {help_request.id}: {exc}")


def claim_request(db: Session, request_id: int, claimer_id: int) -> HelpRequest | None:
    """Assign a help request to a claimer and set started_helping_at."""
    return ensure_request_owned_by_reviewer(db, request_id, claimer_id)


def get_student_email_info(db: Session, help_request: HelpRequest):
    """Get the student's email info for sending notification email."""
    student = db.query(User).filter(User.id == help_request.student_id).first()
    if not student:
        return None, None
    return student.email, student.name


def notify_tas_new_request(db: Session, assignment: Assignment, help_request: HelpRequest, student_name: str):
    """Create notifications for all assigned TAs plus the teacher when a new request comes in."""
    course = db.query(Course).filter(Course.id == assignment.course_id).first()

    ta_assignments = db.query(TAAssignment).filter(
        or_(
            TAAssignment.course_id == assignment.course_id,
            TAAssignment.assignment_id == assignment.id,
        )
    ).all()

    notified_ids = set()
    for ta in ta_assignments:
        if ta.ta_id not in notified_ids:
            db.add(
                Notification(
                    user_id=ta.ta_id,
                    help_request_id=help_request.id,
                    type="new_request",
                    message=(
                        f"New help request from {student_name} for {assignment.name} "
                        f"Q{db.query(Question).filter(Question.id == help_request.question_id).first().question_number}"
                    ),
                )
            )
            notified_ids.add(ta.ta_id)

    if course and course.teacher_id and course.teacher_id not in notified_ids:
        question = db.query(Question).filter(Question.id == help_request.question_id).first()
        db.add(
            Notification(
                user_id=course.teacher_id,
                help_request_id=help_request.id,
                type="new_request",
                message=f"New help request from {student_name} for {assignment.name} Q{question.question_number}",
            )
        )
    db.commit()
