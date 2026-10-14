from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime
from urllib.parse import quote_plus

from app.models.db import (
    Assignment, QueueRoom, Session as HelpSession, LLMConfig,
    HelpRequest, Question, User, RequestStatus, Notification
)

ACTIVE_QUEUE_STATUSES = [RequestStatus.PENDING, RequestStatus.AI_GENERATED]


def get_assignment_question_ids(db: Session, assignment_id: int) -> list[int]:
    return [q[0] for q in db.query(Question.id).filter(
        Question.assignment_id == assignment_id
    ).all()]


def get_next_queue_position(db: Session, assignment_id: int, room_id: int | None = None) -> int:
    """Return the next queue position within a room-specific queue."""
    question_ids = get_assignment_question_ids(db, assignment_id)
    if not question_ids:
        return 1

    query = db.query(func.max(HelpRequest.queue_position)).filter(
        HelpRequest.question_id.in_(question_ids),
        HelpRequest.status.in_(ACTIVE_QUEUE_STATUSES),
        HelpRequest.assigned_ta_id.is_(None),
    )
    if room_id is None:
        query = query.filter(HelpRequest.queue_room_id.is_(None))
    else:
        query = query.filter(HelpRequest.queue_room_id == room_id)

    max_position = query.scalar() or 0
    return max_position + 1


def collapse_queue_positions(
    db: Session,
    assignment_id: int,
    removed_position: int | None,
    room_id: int | None = None
):
    """Close a gap in queue positions after a student leaves or is called."""
    if removed_position is None:
        return

    question_ids = get_assignment_question_ids(db, assignment_id)
    if not question_ids:
        return

    query = db.query(HelpRequest).filter(
        HelpRequest.question_id.in_(question_ids),
        HelpRequest.status.in_(ACTIVE_QUEUE_STATUSES),
        HelpRequest.assigned_ta_id.is_(None),
        HelpRequest.queue_position > removed_position,
    )
    if room_id is None:
        query = query.filter(HelpRequest.queue_room_id.is_(None))
    else:
        query = query.filter(HelpRequest.queue_room_id == room_id)

    for request in query.order_by(HelpRequest.queue_position.asc()).all():
        if request.queue_position is not None:
            request.queue_position -= 1


def validate_room_names(db: Session, assignment_id: int, sanitized_names: list):
    """Validate room names: check for duplicates within submission and conflicts with open rooms.
    Returns (is_valid, error_type, conflicting_names)."""
    submitted_lower = [n.lower() for n in sanitized_names]
    if len(set(submitted_lower)) != len(submitted_lower):
        return False, "duplicate_rooms", sanitized_names

    existing_room_names = {
        r.name.strip().lower()
        for r in db.query(QueueRoom).filter(
            QueueRoom.assignment_id == assignment_id,
            QueueRoom.is_open == True
        ).all()
    }
    conflicting = [n for n in sanitized_names if n.lower() in existing_room_names]
    if conflicting:
        return False, "room_exists", conflicting

    return True, None, None


def open_queue(db: Session, assignment_id: int, room_names: list, llm_id: int, opened_by: int):
    """Open a queue: create rooms, set assignment.queue_open=True, create HelpSession.
    Returns the assignment."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        return None

    # Create rooms
    for name in room_names:
        db.add(QueueRoom(
            assignment_id=assignment.id,
            name=name,
            is_open=True,
            opened_at=datetime.utcnow(),
            opened_by=opened_by
        ))

    # Mark assignment as open
    assignment.queue_open = True
    assignment.queue_opened_at = datetime.utcnow()
    assignment.queue_opened_by = opened_by

    # Close existing active sessions for this assignment
    existing_sessions = db.query(HelpSession).filter(
        HelpSession.assignment_id == assignment.id,
        HelpSession.active == True
    ).all()
    for s in existing_sessions:
        s.active = False
        s.ended_at = datetime.utcnow()

    # Create new session
    db.add(HelpSession(
        course_id=assignment.course_id,
        assignment_id=assignment.id,
        session_name=f"{assignment.name} - Help Session",
        started_by=opened_by,
        active=True,
        active_llm_config_id=llm_id
    ))

    db.commit()
    return assignment


def close_queue(db: Session, assignment_id: int, resolve_unassigned: bool = True):
    """Close a queue: close all rooms, set assignment.queue_open=False, end active sessions.
    Optionally resolve any unclaimed active requests before closing.
    Returns the assignment."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        return None

    closed_at = datetime.utcnow()

    rooms = db.query(QueueRoom).filter(QueueRoom.assignment_id == assignment.id).all()
    for r in rooms:
        r.is_open = False
        r.closed_at = closed_at

    assignment.queue_open = False
    assignment.queue_closed_at = closed_at

    question_ids = get_assignment_question_ids(db, assignment.id)
    if resolve_unassigned and question_ids:
        abandoned_requests = db.query(HelpRequest).filter(
            HelpRequest.question_id.in_(question_ids),
            HelpRequest.status.in_(ACTIVE_QUEUE_STATUSES),
            HelpRequest.assigned_ta_id.is_(None),
        ).all()

        for request in abandoned_requests:
            request.status = RequestStatus.RESOLVED
            request.resolved_at = closed_at
            request.queue_position = None
            request.ai_feedback = None
            request.final_feedback = (
                request.final_feedback
                or "The queue was closed before a TA could pick up your request."
            )
            request.ai_progress_status = None
            request.ai_queue_state = None
            request.ai_queue_enqueued_at = None
            request.ai_queue_started_at = None
            request.ai_queue_error = None
            request.last_progress_update = closed_at

            db.add(Notification(
                user_id=request.student_id,
                help_request_id=request.id,
                type="queue_closed",
                message=f"The queue for {assignment.name} was closed before a TA could review your request.",
            ))

    sessions = db.query(HelpSession).filter(
        HelpSession.assignment_id == assignment.id,
        HelpSession.active == True
    ).all()
    for s in sessions:
        s.active = False
        s.ended_at = closed_at

    db.commit()
    return assignment


def get_queue_state(db: Session, assignment_id: int) -> dict:
    """Get the current state of the queue for an assignment."""
    question_ids = get_assignment_question_ids(db, assignment_id)

    queue_items = db.query(HelpRequest).filter(
        HelpRequest.question_id.in_(question_ids),
        HelpRequest.status.in_(ACTIVE_QUEUE_STATUSES),
        HelpRequest.assigned_ta_id.is_(None),
    ).order_by(
        HelpRequest.queue_room_id.asc(),
        HelpRequest.queue_position.asc(),
        HelpRequest.joined_queue_at.asc()
    ).all()

    queue_data = []
    for item in queue_items:
        student = db.query(User).filter(User.id == item.student_id).first()
        question = db.query(Question).filter(Question.id == item.question_id).first()
        assignment = db.query(Assignment).filter(
            Assignment.id == question.assignment_id
        ).first() if question else None

        room_name = None
        if item.queue_room_id:
            room = db.query(QueueRoom).filter(QueueRoom.id == item.queue_room_id).first()
            room_name = room.name if room else None

        queue_data.append({
            "id": item.id,
            "position": item.queue_position or 0,
            "student": {
                "id": student.id,
                "name": student.name
            },
            "assignment": assignment.name if assignment else "Unknown",
            "question": f"Q{question.question_number}" if question else "?",
            "status": item.status.value,
            "wait_time": int((datetime.utcnow() - item.joined_queue_at).total_seconds() / 60)
                if item.joined_queue_at else 0,
            "progress": item.ai_progress_status,
            "has_ai_feedback": bool(item.ai_feedback),
            "room_id": item.queue_room_id,
            "room_name": room_name,
            "student_comment": item.student_comment,
            "last_update": item.last_progress_update.isoformat() if item.last_progress_update else None
        })

    return {
        "queue": queue_data,
        "total": len(queue_data),
        "assignment_id": assignment_id
    }


def get_room_view_state(db: Session, room_id: int) -> dict:
    """Get the view-only state for a specific room, including waiting and being-helped students."""
    room = db.query(QueueRoom).filter(QueueRoom.id == room_id).first()
    if not room:
        return None

    assignment = db.query(Assignment).filter(Assignment.id == room.assignment_id).first()

    # Students waiting in queue (not yet assigned to a TA)
    waiting_items = db.query(HelpRequest).filter(
        HelpRequest.queue_room_id == room_id,
        HelpRequest.status.in_(ACTIVE_QUEUE_STATUSES),
        HelpRequest.assigned_ta_id == None
    ).order_by(HelpRequest.queue_position.asc()).all()

    # Students currently being helped (assigned to a TA but not yet resolved)
    being_helped_items = db.query(HelpRequest).filter(
        HelpRequest.queue_room_id == room_id,
        HelpRequest.status.in_(ACTIVE_QUEUE_STATUSES),
        HelpRequest.assigned_ta_id != None
    ).order_by(HelpRequest.started_helping_at.desc()).all()

    waiting = []
    for item in waiting_items:
        student = db.query(User).filter(User.id == item.student_id).first()
        question = db.query(Question).filter(Question.id == item.question_id).first()
        waiting.append({
            "id": item.id,
            "position": item.queue_position or 0,
            "student_name": student.name if student else "Unknown",
            "student_id": student.id if student else None,
            "question": f"Q{question.question_number}" if question else "?",
            "wait_time": int((datetime.utcnow() - item.joined_queue_at).total_seconds() / 60)
                if item.joined_queue_at else 0,
        })

    helped = []
    for item in being_helped_items:
        student = db.query(User).filter(User.id == item.student_id).first()
        ta = db.query(User).filter(User.id == item.assigned_ta_id).first()
        helped.append({
            "id": item.id,
            "student_name": student.name if student else "Unknown",
            "student_id": student.id if student else None,
            "ta_name": ta.name if ta else "Unknown",
        })

    return {
        "room_id": room.id,
        "room_name": room.name,
        "room_location": room.location,
        "is_open": room.is_open,
        "assignment_name": assignment.name if assignment else "Unknown",
        "assignment_id": room.assignment_id,
        "waiting": waiting,
        "being_helped": helped,
        "total_waiting": len(waiting),
        "total_being_helped": len(helped),
    }
