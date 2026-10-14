import csv
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from io import StringIO
from typing import Optional
from urllib.parse import urlencode

from sqlalchemy import or_
from sqlalchemy.orm import Session, aliased, selectinload

from app.models.db import (
    Assignment,
    Course,
    HelpRequest,
    Question,
    QueueRoom,
    RequestStatus,
    Session as HelpSession,
    TAAssignment,
    User,
)


FAST_APPROVAL_THRESHOLD_MINUTES = 2
TERMINAL_STATUSES = {
    RequestStatus.APPROVED,
    RequestStatus.EDITED,
    RequestStatus.REJECTED,
    RequestStatus.IN_PERSON,
    RequestStatus.RESOLVED,
}
STATUS_META = [
    {
        "status": RequestStatus.PENDING,
        "label": "Pending",
        "badge_classes": "bg-amber-100 text-amber-800",
        "chart_color": "#f59e0b",
    },
    {
        "status": RequestStatus.AI_GENERATED,
        "label": "AI Generated",
        "badge_classes": "bg-sky-100 text-sky-800",
        "chart_color": "#0ea5e9",
    },
    {
        "status": RequestStatus.APPROVED,
        "label": "Approved",
        "badge_classes": "bg-emerald-100 text-emerald-800",
        "chart_color": "#10b981",
    },
    {
        "status": RequestStatus.EDITED,
        "label": "Edited",
        "badge_classes": "bg-violet-100 text-violet-800",
        "chart_color": "#8b5cf6",
    },
    {
        "status": RequestStatus.REJECTED,
        "label": "Rejected",
        "badge_classes": "bg-rose-100 text-rose-800",
        "chart_color": "#f43f5e",
    },
    {
        "status": RequestStatus.IN_PERSON,
        "label": "In Person",
        "badge_classes": "bg-orange-100 text-orange-800",
        "chart_color": "#f97316",
    },
    {
        "status": RequestStatus.RESOLVED,
        "label": "Resolved",
        "badge_classes": "bg-slate-100 text-slate-800",
        "chart_color": "#64748b",
    },
]


def get_teacher_analytics_dashboard(
    db: Session,
    teacher_id: int,
    course_id: Optional[int] = None,
    assignment_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    if start_date and end_date and end_date < start_date:
        start_date, end_date = end_date, start_date

    courses = (
        db.query(Course)
        .options(selectinload(Course.assignments))
        .filter(Course.teacher_id == teacher_id)
        .order_by(Course.name.asc())
        .all()
    )
    course_lookup = {course.id: course for course in courses}
    assignment_lookup = {
        assignment.id: assignment
        for course in courses
        for assignment in course.assignments
    }

    selected_assignment = assignment_lookup.get(assignment_id) if assignment_id else None
    if selected_assignment:
        course_id = selected_assignment.course_id

    selected_course = course_lookup.get(course_id) if course_id else None
    if course_id and not selected_course:
        course_id = None

    request_rows = _load_request_rows(
        db=db,
        teacher_id=teacher_id,
        course_id=course_id,
        assignment_id=assignment_id if selected_assignment else None,
        start_date=start_date,
        end_date=end_date,
    )

    scoped_courses = [selected_course] if selected_course else courses
    scoped_course_ids = [course.id for course in scoped_courses if course]
    ta_rows = _load_ta_rows(db, scoped_course_ids, assignment_id if selected_assignment else None)
    session_rows = _load_session_rows(
        db=db,
        teacher_id=teacher_id,
        course_id=course_id,
        assignment_id=assignment_id if selected_assignment else None,
        start_date=start_date,
        end_date=end_date,
    )

    analytics = _build_analytics_payload(
        request_rows=request_rows,
        courses=courses,
        ta_rows=ta_rows,
        selected_course=selected_course,
        selected_assignment=selected_assignment,
        start_date=start_date,
        end_date=end_date,
        session_rows=session_rows,
    )

    filters = {
        "course_id": selected_course.id if selected_course else None,
        "assignment_id": selected_assignment.id if selected_assignment else None,
        "start_date": start_date.isoformat() if start_date else "",
        "end_date": end_date.isoformat() if end_date else "",
        "courses": [
            {
                "id": course.id,
                "name": course.name,
                "assignment_count": len(course.assignments),
            }
            for course in courses
        ],
        "assignments": [
            {
                "id": assignment.id,
                "name": assignment.name,
                "course_id": assignment.course_id,
                "course_name": course.name,
            }
            for course, assignment in sorted(
                (
                    (course, assignment)
                    for course in (scoped_courses if selected_course else courses)
                    for assignment in course.assignments
                ),
                key=lambda item: (item[0].name.lower(), item[1].name.lower()),
            )
        ],
    }

    return {
        "filters": filters,
        **analytics,
    }


def export_teacher_analytics_csv(
    db: Session,
    teacher_id: int,
    course_id: Optional[int] = None,
    assignment_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    if start_date and end_date and end_date < start_date:
        start_date, end_date = end_date, start_date

    courses = (
        db.query(Course)
        .options(selectinload(Course.assignments))
        .filter(Course.teacher_id == teacher_id)
        .order_by(Course.name.asc())
        .all()
    )
    course_lookup = {course.id: course for course in courses}
    assignment_lookup = {
        assignment.id: assignment
        for course in courses
        for assignment in course.assignments
    }

    selected_assignment = assignment_lookup.get(assignment_id) if assignment_id else None
    if selected_assignment:
        course_id = selected_assignment.course_id

    selected_course = course_lookup.get(course_id) if course_id else None
    if course_id and not selected_course:
        course_id = None

    request_rows = _load_request_rows(
        db=db,
        teacher_id=teacher_id,
        course_id=course_id,
        assignment_id=assignment_id if selected_assignment else None,
        start_date=start_date,
        end_date=end_date,
    )

    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "request_id",
        "status",
        "course_id",
        "course_name",
        "assignment_id",
        "assignment_name",
        "question_id",
        "question_number",
        "queue_room_id",
        "queue_room_name",
        "student_id",
        "student_name",
        "student_email",
        "assigned_ta_id",
        "ta_name",
        "created_at_utc",
        "joined_queue_at_utc",
        "started_helping_at_utc",
        "ai_generated_at_utc",
        "resolved_at_utc",
        "queue_wait_minutes",
        "resolution_minutes",
        "time_to_ai_minutes",
        "ai_review_minutes",
    ])

    for row in request_rows:
        status = row.status.value if hasattr(row.status, "value") else row.status
        writer.writerow([
            row.request_id,
            status,
            row.course_id,
            row.course_name,
            row.assignment_id,
            row.assignment_name,
            row.question_id,
            row.question_number,
            row.queue_room_id,
            row.queue_room_name,
            row.student_id,
            row.student_name,
            row.student_email,
            row.assigned_ta_id,
            row.ta_name,
            _serialize_utc(row.created_at),
            _serialize_utc(row.joined_queue_at),
            _serialize_utc(row.started_helping_at),
            _serialize_utc(row.ai_generated_at),
            _serialize_utc(row.resolved_at),
            _minutes_between(row.joined_queue_at, row.started_helping_at),
            _minutes_between(row.created_at, row.resolved_at),
            _minutes_between(row.created_at, row.ai_generated_at),
            _minutes_between(row.ai_generated_at, row.resolved_at),
        ])

    return output.getvalue()


def _load_request_rows(
    db: Session,
    teacher_id: int,
    course_id: Optional[int],
    assignment_id: Optional[int],
    start_date: Optional[date],
    end_date: Optional[date],
):
    student_user = aliased(User)
    ta_user = aliased(User)
    query = (
        db.query(
            HelpRequest.id.label("request_id"),
            HelpRequest.student_id.label("student_id"),
            HelpRequest.assigned_ta_id.label("assigned_ta_id"),
            HelpRequest.status.label("status"),
            HelpRequest.created_at.label("created_at"),
            HelpRequest.resolved_at.label("resolved_at"),
            HelpRequest.joined_queue_at.label("joined_queue_at"),
            HelpRequest.started_helping_at.label("started_helping_at"),
            HelpRequest.ai_generated_at.label("ai_generated_at"),
            Question.id.label("question_id"),
            Question.question_number.label("question_number"),
            Question.problem_description.label("problem_description"),
            Assignment.id.label("assignment_id"),
            Assignment.name.label("assignment_name"),
            Course.id.label("course_id"),
            Course.name.label("course_name"),
            HelpRequest.queue_room_id.label("queue_room_id"),
            QueueRoom.name.label("queue_room_name"),
            student_user.name.label("student_name"),
            student_user.email.label("student_email"),
            ta_user.name.label("ta_name"),
        )
        .join(Question, HelpRequest.question_id == Question.id)
        .join(Assignment, Question.assignment_id == Assignment.id)
        .join(Course, Assignment.course_id == Course.id)
        .join(student_user, HelpRequest.student_id == student_user.id)
        .outerjoin(ta_user, HelpRequest.assigned_ta_id == ta_user.id)
        .outerjoin(QueueRoom, HelpRequest.queue_room_id == QueueRoom.id)
        .filter(Course.teacher_id == teacher_id)
    )

    if course_id:
        query = query.filter(Course.id == course_id)
    if assignment_id:
        query = query.filter(Assignment.id == assignment_id)

    start_dt, end_dt = _build_datetime_range(start_date, end_date)
    if start_dt:
        query = query.filter(HelpRequest.created_at >= start_dt)
    if end_dt:
        query = query.filter(HelpRequest.created_at < end_dt)

    return query.order_by(HelpRequest.created_at.asc()).all()


def _load_ta_rows(db: Session, course_ids, assignment_id: Optional[int]):
    if not course_ids:
        return []

    query = (
        db.query(
            User.id.label("ta_id"),
            User.name.label("ta_name"),
            User.email.label("ta_email"),
        )
        .join(TAAssignment, TAAssignment.ta_id == User.id)
        .filter(TAAssignment.course_id.in_(course_ids))
    )

    if assignment_id:
        query = query.filter(
            or_(
                TAAssignment.assignment_id.is_(None),
                TAAssignment.assignment_id == assignment_id,
            )
        )

    return query.distinct().order_by(User.name.asc()).all()


def _load_session_rows(
    db: Session,
    teacher_id: int,
    course_id: Optional[int],
    assignment_id: Optional[int],
    start_date: Optional[date],
    end_date: Optional[date],
):
    query = (
        db.query(
            HelpSession.id.label("session_id"),
            HelpSession.started_at.label("started_at"),
            HelpSession.ended_at.label("ended_at"),
            HelpSession.course_id.label("course_id"),
            HelpSession.assignment_id.label("assignment_id"),
        )
        .join(Course, HelpSession.course_id == Course.id)
        .filter(Course.teacher_id == teacher_id)
    )

    if course_id:
        query = query.filter(HelpSession.course_id == course_id)
    if assignment_id:
        query = query.filter(HelpSession.assignment_id == assignment_id)

    start_dt, end_dt = _build_datetime_range(start_date, end_date)
    if start_dt:
        query = query.filter(HelpSession.started_at >= start_dt)
    if end_dt:
        query = query.filter(HelpSession.started_at < end_dt)

    return query.order_by(HelpSession.started_at.asc()).all()


def _build_analytics_payload(
    request_rows,
    courses,
    ta_rows,
    selected_course,
    selected_assignment,
    start_date,
    end_date,
    session_rows,
):
    course_scope = [selected_course] if selected_course else courses
    scoped_assignments = [
        assignment
        for course in course_scope
        for assignment in course.assignments
        if not selected_assignment or assignment.id == selected_assignment.id
    ]

    course_stats = {
        course.id: _init_bucket(
            {
                "course_id": course.id,
                "course_name": course.name,
                "filter_url": _build_filter_url(
                    course_id=course.id,
                    start_date=start_date,
                    end_date=end_date,
                ),
            }
        )
        for course in course_scope
        if course
    }
    assignment_stats = {
        assignment.id: _init_bucket(
            {
                "assignment_id": assignment.id,
                "assignment_name": assignment.name,
                "course_id": assignment.course_id,
                "course_name": assignment.course.name,
                "filter_url": _build_filter_url(
                    course_id=assignment.course_id,
                    assignment_id=assignment.id,
                    start_date=start_date,
                    end_date=end_date,
                ),
            }
        )
        for assignment in scoped_assignments
    }
    ta_stats = {
        ta.ta_id: _init_bucket(
            {
                "ta_id": ta.ta_id,
                "ta_name": ta.ta_name,
                "ta_email": ta.ta_email,
            }
        )
        for ta in ta_rows
    }
    question_stats = {}
    requests_over_time = Counter()
    status_counts = Counter({meta["status"].value: 0 for meta in STATUS_META})
    student_ids = set()
    resolution_times = []
    queue_wait_times = []
    time_to_ai_times = []
    ai_review_times = []
    approval_speeds = []
    approved_count = 0
    edited_count = 0
    in_person_count = 0
    closed_count = 0
    fast_approvals_count = 0

    for row in request_rows:
        status_value = row.status.value
        status_counts[status_value] += 1
        student_ids.add(row.student_id)
        requests_over_time[row.created_at.date().isoformat()] += 1

        resolution_minutes = _minutes_between(row.created_at, row.resolved_at)
        queue_wait_minutes = _minutes_between(row.joined_queue_at, row.started_helping_at)
        time_to_ai_minutes = _minutes_between(row.created_at, row.ai_generated_at)
        ai_review_minutes = _minutes_between(row.ai_generated_at, row.resolved_at)
        approval_speed_minutes = (
            ai_review_minutes if row.status == RequestStatus.APPROVED else None
        )
        is_closed = bool(row.resolved_at) or row.status in TERMINAL_STATUSES

        if is_closed:
            closed_count += 1
        if row.status == RequestStatus.APPROVED:
            approved_count += 1
        if row.status == RequestStatus.EDITED:
            edited_count += 1
        if row.status == RequestStatus.IN_PERSON:
            in_person_count += 1
        if resolution_minutes is not None:
            resolution_times.append(resolution_minutes)
        if queue_wait_minutes is not None:
            queue_wait_times.append(queue_wait_minutes)
        if time_to_ai_minutes is not None:
            time_to_ai_times.append(time_to_ai_minutes)
        if ai_review_minutes is not None and row.status in TERMINAL_STATUSES:
            ai_review_times.append(ai_review_minutes)
        if approval_speed_minutes is not None:
            approval_speeds.append(approval_speed_minutes)
            if approval_speed_minutes < FAST_APPROVAL_THRESHOLD_MINUTES:
                fast_approvals_count += 1

        _apply_row_to_bucket(
            course_stats.get(row.course_id),
            row.status,
            is_closed,
            resolution_minutes,
            queue_wait_minutes,
            time_to_ai_minutes,
            ai_review_minutes,
            approval_speed_minutes,
        )
        _apply_row_to_bucket(
            assignment_stats.get(row.assignment_id),
            row.status,
            is_closed,
            resolution_minutes,
            queue_wait_minutes,
            time_to_ai_minutes,
            ai_review_minutes,
            approval_speed_minutes,
        )
        _apply_row_to_bucket(
            ta_stats.get(row.assigned_ta_id),
            row.status,
            is_closed,
            resolution_minutes,
            queue_wait_minutes,
            time_to_ai_minutes,
            ai_review_minutes,
            approval_speed_minutes,
        )

        question_bucket = question_stats.setdefault(
            row.question_id,
            {
                "question_id": row.question_id,
                "question_label": f"Q{row.question_number}",
                "problem_summary": _summarize_text(row.problem_description),
                "course_id": row.course_id,
                "course_name": row.course_name,
                "assignment_id": row.assignment_id,
                "assignment_name": row.assignment_name,
                "request_count": 0,
                "resolution_times": [],
                "queue_wait_times": [],
                "filter_url": _build_filter_url(
                    course_id=row.course_id,
                    assignment_id=row.assignment_id,
                    start_date=start_date,
                    end_date=end_date,
                ),
            },
        )
        question_bucket["request_count"] += 1
        if resolution_minutes is not None:
            question_bucket["resolution_times"].append(resolution_minutes)
        if queue_wait_minutes is not None:
            question_bucket["queue_wait_times"].append(queue_wait_minutes)

    session_durations = [
        _minutes_between(session.started_at, session.ended_at)
        for session in session_rows
        if session.ended_at
    ]
    completed_sessions = len(session_durations)
    avg_session_duration = _rounded_avg(session_durations)
    total_requests = len(request_rows)
    ai_review_total = approved_count + edited_count
    avg_resolution = _rounded_avg(resolution_times)
    avg_queue_wait = _rounded_avg(queue_wait_times)
    avg_time_to_ai = _rounded_avg(time_to_ai_times)
    avg_ai_review = _rounded_avg(ai_review_times)
    avg_approval_speed = _rounded_avg(approval_speeds)
    ai_approval_rate = _safe_percentage(approved_count, ai_review_total)
    edit_rate = _safe_percentage(edited_count, ai_review_total)
    fast_approval_rate = _safe_percentage(fast_approvals_count, approved_count)

    summary = {
        "total_requests": total_requests,
        "closed_requests": closed_count,
        "open_requests": total_requests - closed_count,
        "closed_rate": _safe_percentage(closed_count, total_requests),
        "closed_rate_display": _format_percentage(
            _safe_percentage(closed_count, total_requests)
        ),
        "avg_resolution_minutes": avg_resolution,
        "avg_resolution_display": _format_minutes(avg_resolution),
        "avg_queue_wait_minutes": avg_queue_wait,
        "avg_queue_wait_display": _format_minutes(avg_queue_wait),
        "avg_time_to_ai_minutes": avg_time_to_ai,
        "avg_time_to_ai_display": _format_minutes(avg_time_to_ai),
        "avg_ai_review_minutes": avg_ai_review,
        "avg_ai_review_display": _format_minutes(avg_ai_review),
        "approved_count": approved_count,
        "edited_count": edited_count,
        "in_person_count": in_person_count,
        "ai_approval_rate": ai_approval_rate,
        "ai_approval_rate_display": _format_percentage(ai_approval_rate),
        "edit_rate": edit_rate,
        "edit_rate_display": _format_percentage(edit_rate),
        "avg_approval_speed_minutes": avg_approval_speed,
        "avg_approval_speed_display": _format_minutes(avg_approval_speed),
        "fast_approvals_count": fast_approvals_count,
        "fast_approval_rate": fast_approval_rate,
        "fast_approval_rate_display": _format_percentage(fast_approval_rate),
        "fast_approval_threshold_minutes": FAST_APPROVAL_THRESHOLD_MINUTES,
        "student_count": len(student_ids),
        "ta_count": len(ta_rows),
        "session_count": len(session_rows),
        "completed_session_count": completed_sessions,
        "avg_session_duration_minutes": avg_session_duration,
        "avg_session_duration_display": _format_minutes(avg_session_duration),
        "status_breakdown": [
            {
                "status": meta["status"].value,
                "label": meta["label"],
                "count": status_counts[meta["status"].value],
                "percentage": _safe_percentage(
                    status_counts[meta["status"].value],
                    total_requests,
                ),
                "percentage_display": _format_percentage(
                    _safe_percentage(
                        status_counts[meta["status"].value],
                        total_requests,
                    )
                ),
                "badge_classes": meta["badge_classes"],
                "chart_color": meta["chart_color"],
            }
            for meta in STATUS_META
        ],
    }

    finalized_course_stats = _finalize_buckets(course_stats.values(), sort_key="course_name")
    finalized_assignment_stats = _finalize_buckets(
        assignment_stats.values(),
        sort_key="assignment_name",
    )
    finalized_ta_stats = sorted(
        (_finalize_bucket(bucket) for bucket in ta_stats.values()),
        key=lambda bucket: (-bucket["total_requests"], bucket["ta_name"].lower()),
    )

    common_problems = sorted(
        (
            {
                "question_id": bucket["question_id"],
                "question_label": bucket["question_label"],
                "problem_summary": bucket["problem_summary"],
                "course_id": bucket["course_id"],
                "course_name": bucket["course_name"],
                "assignment_id": bucket["assignment_id"],
                "assignment_name": bucket["assignment_name"],
                "request_count": bucket["request_count"],
                "request_share": _safe_percentage(bucket["request_count"], total_requests),
                "request_share_display": _format_percentage(
                    _safe_percentage(bucket["request_count"], total_requests)
                ),
                "avg_resolution_minutes": _rounded_avg(bucket["resolution_times"]),
                "avg_resolution_display": _format_minutes(
                    _rounded_avg(bucket["resolution_times"])
                ),
                "avg_queue_wait_minutes": _rounded_avg(bucket["queue_wait_times"]),
                "avg_queue_wait_display": _format_minutes(
                    _rounded_avg(bucket["queue_wait_times"])
                ),
                "filter_url": bucket["filter_url"],
            }
            for bucket in question_stats.values()
        ),
        key=lambda bucket: (-bucket["request_count"], bucket["assignment_name"].lower(), bucket["question_label"]),
    )

    focus = {
        "scope_label": (
            "Assignment Drill-down"
            if selected_assignment
            else "Course Drill-down"
            if selected_course
            else "All Teacher Courses"
        ),
        "title": (
            selected_assignment.name
            if selected_assignment
            else selected_course.name
            if selected_course
            else "All courses"
        ),
        "subtitle": _build_focus_subtitle(selected_course, selected_assignment, start_date, end_date),
        "top_question": common_problems[0] if common_problems else None,
        "top_ta": finalized_ta_stats[0] if finalized_ta_stats else None,
    }

    return {
        "summary": summary,
        "course_stats": finalized_course_stats,
        "assignment_stats": finalized_assignment_stats,
        "ta_stats": finalized_ta_stats,
        "common_problems": common_problems[:10],
        "focus": focus,
        "charts": {
            "requests_over_time": {
                "labels": list(requests_over_time.keys()),
                "counts": list(requests_over_time.values()),
            },
            "status_distribution": {
                "labels": [
                    status["label"]
                    for status in summary["status_breakdown"]
                    if status["count"] > 0
                ],
                "counts": [
                    status["count"]
                    for status in summary["status_breakdown"]
                    if status["count"] > 0
                ],
                "colors": [
                    status["chart_color"]
                    for status in summary["status_breakdown"]
                    if status["count"] > 0
                ],
            },
            "ta_comparison": {
                "labels": [ta["ta_name"] for ta in finalized_ta_stats[:8]],
                "approved": [ta["approved_count"] for ta in finalized_ta_stats[:8]],
                "edited": [ta["edited_count"] for ta in finalized_ta_stats[:8]],
                "in_person": [ta["in_person_count"] for ta in finalized_ta_stats[:8]],
            },
        },
    }


def _init_bucket(base):
    return {
        **base,
        "total_requests": 0,
        "closed_requests": 0,
        "status_counts": Counter(),
        "resolution_times": [],
        "queue_wait_times": [],
        "time_to_ai_times": [],
        "ai_review_times": [],
        "approval_speeds": [],
        "approved_count": 0,
        "edited_count": 0,
        "in_person_count": 0,
        "fast_approvals_count": 0,
    }


def _apply_row_to_bucket(
    bucket,
    status,
    is_closed,
    resolution_minutes,
    queue_wait_minutes,
    time_to_ai_minutes,
    ai_review_minutes,
    approval_speed_minutes,
):
    if bucket is None:
        return

    bucket["total_requests"] += 1
    bucket["status_counts"][status.value] += 1
    if is_closed:
        bucket["closed_requests"] += 1
    if status == RequestStatus.APPROVED:
        bucket["approved_count"] += 1
    if status == RequestStatus.EDITED:
        bucket["edited_count"] += 1
    if status == RequestStatus.IN_PERSON:
        bucket["in_person_count"] += 1
    if resolution_minutes is not None:
        bucket["resolution_times"].append(resolution_minutes)
    if queue_wait_minutes is not None:
        bucket["queue_wait_times"].append(queue_wait_minutes)
    if time_to_ai_minutes is not None:
        bucket["time_to_ai_times"].append(time_to_ai_minutes)
    if ai_review_minutes is not None:
        bucket["ai_review_times"].append(ai_review_minutes)
    if approval_speed_minutes is not None:
        bucket["approval_speeds"].append(approval_speed_minutes)
        if approval_speed_minutes < FAST_APPROVAL_THRESHOLD_MINUTES:
            bucket["fast_approvals_count"] += 1


def _finalize_buckets(buckets, sort_key):
    return sorted(
        (_finalize_bucket(bucket) for bucket in buckets),
        key=lambda bucket: (-bucket["total_requests"], bucket[sort_key].lower()),
    )


def _finalize_bucket(bucket):
    avg_resolution = _rounded_avg(bucket["resolution_times"])
    avg_queue_wait = _rounded_avg(bucket["queue_wait_times"])
    avg_time_to_ai = _rounded_avg(bucket["time_to_ai_times"])
    avg_ai_review = _rounded_avg(bucket["ai_review_times"])
    avg_approval_speed = _rounded_avg(bucket["approval_speeds"])
    ai_review_total = bucket["approved_count"] + bucket["edited_count"]
    approval_rate = _safe_percentage(bucket["approved_count"], ai_review_total)
    edit_rate = _safe_percentage(bucket["edited_count"], ai_review_total)
    open_requests = bucket["total_requests"] - bucket["closed_requests"]
    fast_approval_rate = _safe_percentage(
        bucket["fast_approvals_count"],
        bucket["approved_count"],
    )

    return {
        **bucket,
        "open_requests": open_requests,
        "avg_resolution_minutes": avg_resolution,
        "avg_resolution_display": _format_minutes(avg_resolution),
        "avg_queue_wait_minutes": avg_queue_wait,
        "avg_queue_wait_display": _format_minutes(avg_queue_wait),
        "avg_time_to_ai_minutes": avg_time_to_ai,
        "avg_time_to_ai_display": _format_minutes(avg_time_to_ai),
        "avg_ai_review_minutes": avg_ai_review,
        "avg_ai_review_display": _format_minutes(avg_ai_review),
        "avg_approval_speed_minutes": avg_approval_speed,
        "avg_approval_speed_display": _format_minutes(avg_approval_speed),
        "ai_approval_rate": approval_rate,
        "ai_approval_rate_display": _format_percentage(approval_rate),
        "edit_rate": edit_rate,
        "edit_rate_display": _format_percentage(edit_rate),
        "fast_approval_rate": fast_approval_rate,
        "fast_approval_rate_display": _format_percentage(fast_approval_rate),
    }


def _build_datetime_range(start_date: Optional[date], end_date: Optional[date]):
    start_dt = datetime.combine(start_date, time.min) if start_date else None
    end_dt = (
        datetime.combine(end_date + timedelta(days=1), time.min)
        if end_date
        else None
    )
    return start_dt, end_dt


def _minutes_between(start_at, end_at):
    if not start_at or not end_at:
        return None
    return round((end_at - start_at).total_seconds() / 60, 1)


def _rounded_avg(values):
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _safe_percentage(part, whole):
    if not whole:
        return 0.0
    return round((part / whole) * 100, 1)


def _format_minutes(value):
    if value is None:
        return "—"
    return f"{value:.1f} min"


def _format_percentage(value):
    return f"{value:.1f}%"


def _serialize_utc(value):
    if not value:
        return ""
    return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _summarize_text(text, limit=110):
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}…"


def _build_focus_subtitle(selected_course, selected_assignment, start_date, end_date):
    date_bits = []
    if start_date:
        date_bits.append(f"from {start_date.isoformat()}")
    if end_date:
        date_bits.append(f"through {end_date.isoformat()}")

    scope_bits = []
    if selected_assignment:
        scope_bits.append(selected_assignment.course.name)
    elif selected_course:
        scope_bits.append("all assignments")
    else:
        scope_bits.append("aggregated across all courses")

    return ", ".join(scope_bits + date_bits)


def _build_filter_url(
    course_id: Optional[int] = None,
    assignment_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    params = {}
    if course_id:
        params["course_id"] = course_id
    if assignment_id:
        params["assignment_id"] = assignment_id
    if start_date:
        params["start_date"] = start_date.isoformat()
    if end_date:
        params["end_date"] = end_date.isoformat()
    query = urlencode(params)
    return f"/teacher/analytics?{query}" if query else "/teacher/analytics"
