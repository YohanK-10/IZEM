from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.db import (
    HelpRequest, Question, Assignment, Course, User,
    CourseEnrollment, QueueRoom, UserRole, RequestStatus
)


def enrich_requests(db: Session, requests):
    """Batch-load Question, User, Assignment for a list of HelpRequests (fixes N+1)."""
    if not requests:
        return
    question_ids = {r.question_id for r in requests}
    student_ids = {r.student_id for r in requests}

    questions = {q.id: q for q in db.query(Question).filter(Question.id.in_(question_ids)).all()}
    students = {u.id: u for u in db.query(User).filter(User.id.in_(student_ids)).all()}

    assignment_ids = {q.assignment_id for q in questions.values()}
    assignments = {a.id: a for a in db.query(Assignment).filter(Assignment.id.in_(assignment_ids)).all()}

    for req in requests:
        q = questions.get(req.question_id)
        req.question_obj = q
        req.student = students.get(req.student_id)
        req.assignment_obj = assignments.get(q.assignment_id) if q else None


def get_courses_summary(db: Session, teacher_id: int, show_hidden: bool = False):
    """Get teacher's courses with aggregated counts in fewer queries."""
    query = db.query(Course).filter(Course.teacher_id == teacher_id)
    if not show_hidden:
        query = query.filter(Course.hidden == False)
    courses = query.all()

    if not courses:
        return []

    course_ids = [c.id for c in courses]

    # Assignments count per course
    assignments_counts = dict(
        db.query(Assignment.course_id, func.count(Assignment.id))
        .filter(Assignment.course_id.in_(course_ids))
        .group_by(Assignment.course_id)
        .all()
    )

    # Students count per course
    students_counts = dict(
        db.query(CourseEnrollment.course_id, func.count(CourseEnrollment.id))
        .filter(
            CourseEnrollment.course_id.in_(course_ids),
            CourseEnrollment.role == UserRole.STUDENT
        )
        .group_by(CourseEnrollment.course_id)
        .all()
    )

    # TAs count per course
    tas_counts = dict(
        db.query(CourseEnrollment.course_id, func.count(CourseEnrollment.id))
        .filter(
            CourseEnrollment.course_id.in_(course_ids),
            CourseEnrollment.role == UserRole.TA
        )
        .group_by(CourseEnrollment.course_id)
        .all()
    )

    # Active sessions (open rooms) per course
    active_sessions_counts = dict(
        db.query(Assignment.course_id, func.count(QueueRoom.id))
        .join(Assignment, QueueRoom.assignment_id == Assignment.id)
        .filter(
            Assignment.course_id.in_(course_ids),
            QueueRoom.is_open == True
        )
        .group_by(Assignment.course_id)
        .all()
    )

    # First open assignment per course
    open_assignments = db.query(Assignment).filter(
        Assignment.course_id.in_(course_ids),
        Assignment.queue_open == True
    ).all()
    first_open_map = {}
    for a in open_assignments:
        if a.course_id not in first_open_map:
            first_open_map[a.course_id] = a.id

    result = []
    for course in courses:
        cid = course.id
        active = active_sessions_counts.get(cid, 0)
        result.append({
            "course": course,
            "assignments_count": assignments_counts.get(cid, 0),
            "students_count": students_counts.get(cid, 0),
            "tas_count": tas_counts.get(cid, 0),
            "active_sessions": active,
            "first_open_assignment_id": first_open_map.get(cid)
        })
    return result
