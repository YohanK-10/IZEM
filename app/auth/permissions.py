from collections.abc import Iterable

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.db import (
    Course, Assignment, Question, HelpRequest, TAAssignment,
    CourseEnrollment, QueueRoom, UserRole,
)


def require_teacher_owns_course(db: Session, course_id: int, teacher_id: int) -> Course:
    """Load a course and verify the teacher owns it. Returns Course or raises 404."""
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.teacher_id == teacher_id
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


def _get_effective_course_role(db: Session, course_id: int, user_id: int, course: Course | None = None) -> UserRole | None:
    if course is None:
        course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return None
    if course.teacher_id == user_id:
        return UserRole.TEACHER

    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == user_id,
        CourseEnrollment.course_id == course_id,
    ).first()
    if enrollment:
        return enrollment.role

    ta_assignment = db.query(TAAssignment).filter(
        TAAssignment.ta_id == user_id,
        TAAssignment.course_id == course_id,
    ).first()
    if ta_assignment:
        return UserRole.TA

    return None


def require_course_access(
    db: Session,
    course_id: int,
    user_id: int,
    allowed_roles: Iterable[UserRole] | None = None,
) -> Course:
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    effective_role = _get_effective_course_role(db, course_id, user_id, course)
    if effective_role is None:
        raise HTTPException(status_code=403, detail="Not authorized for this course")

    if allowed_roles is not None and effective_role not in set(allowed_roles):
        raise HTTPException(status_code=403, detail="Not authorized for this course")

    return course


def require_assignment_access(
    db: Session,
    assignment_id: int,
    user_id: int,
    allowed_roles: Iterable[UserRole] | None = None,
) -> tuple[Assignment, Course]:
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    course = require_course_access(db, assignment.course_id, user_id, allowed_roles)
    return assignment, course


def require_request_access(
    db: Session,
    request_id: int,
    user_id: int,
    allowed_roles: Iterable[UserRole] | None = None,
) -> tuple[HelpRequest, Question, Assignment, Course]:
    help_request = db.query(HelpRequest).filter(HelpRequest.id == request_id).first()
    if not help_request:
        raise HTTPException(status_code=404, detail="Request not found")

    question = db.query(Question).filter(Question.id == help_request.question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    assignment, course = require_assignment_access(
        db, question.assignment_id, user_id, allowed_roles
    )
    return help_request, question, assignment, course


def require_room_access(
    db: Session,
    room_id: int,
    user_id: int,
    allowed_roles: Iterable[UserRole] | None = None,
) -> tuple[QueueRoom, Course]:
    room = db.query(QueueRoom).filter(QueueRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    parent_room = None
    if room.parent_room_id:
        parent_room = db.query(QueueRoom).filter(QueueRoom.id == room.parent_room_id).first()

    course_id = room.course_id or (parent_room.course_id if parent_room else None)

    assignment_id = room.assignment_id
    if not assignment_id and parent_room and parent_room.assignment_id:
        assignment_id = parent_room.assignment_id

    if course_id is None and assignment_id is not None:
        assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if assignment:
            course_id = assignment.course_id

    if course_id is None:
        raise HTTPException(status_code=404, detail="Room course not found")

    course = require_course_access(db, course_id, user_id, allowed_roles)
    return room, course


def require_teacher_owns_assignment(db: Session, assignment_id: int, teacher_id: int) -> Assignment:
    """Load an assignment whose course is owned by the teacher. Returns Assignment or raises 404."""
    assignment = db.query(Assignment).join(Course).filter(
        Assignment.id == assignment_id,
        Course.teacher_id == teacher_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment


def require_ta_assigned(db: Session, assignment_id: int, ta_id: int) -> TAAssignment:
    """Verify a TA is assigned to the given assignment (or its course). Returns TAAssignment or raises 403."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    enrollment = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == ta_id,
        CourseEnrollment.course_id == assignment.course_id,
        CourseEnrollment.role == UserRole.TA,
    ).first()
    if enrollment:
        return db.query(TAAssignment).filter(
            TAAssignment.ta_id == ta_id,
            TAAssignment.course_id == assignment.course_id,
        ).first() or TAAssignment(ta_id=ta_id, course_id=assignment.course_id)
    ta_assignment = db.query(TAAssignment).filter(
        TAAssignment.ta_id == ta_id,
        or_(TAAssignment.assignment_id == assignment_id, TAAssignment.course_id == assignment.course_id)
    ).first()
    if not ta_assignment:
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")
    return ta_assignment


def require_teacher_owns_request(db: Session, request_id: int, teacher_id: int):
    """Verify a help request belongs to a course taught by this teacher.
    Returns (HelpRequest, Question, Assignment, Course) or raises."""
    help_request = db.query(HelpRequest).filter(HelpRequest.id == request_id).first()
    if not help_request:
        raise HTTPException(status_code=404, detail="Request not found")
    question = db.query(Question).filter(Question.id == help_request.question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    assignment = db.query(Assignment).filter(Assignment.id == question.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    course = db.query(Course).filter(Course.id == assignment.course_id).first()
    if not course or course.teacher_id != teacher_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return help_request, question, assignment, course


def require_ta_owns_request(db: Session, request_id: int, ta_id: int) -> HelpRequest:
    """Verify a help request is assigned to this TA. Returns HelpRequest or raises."""
    help_request = db.query(HelpRequest).filter(
        HelpRequest.id == request_id,
        HelpRequest.assigned_ta_id == ta_id
    ).first()
    if not help_request:
        raise HTTPException(status_code=404, detail="Request not found")
    return help_request
