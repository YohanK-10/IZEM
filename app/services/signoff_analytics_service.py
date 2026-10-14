"""Sign-off analytics aggregation for the teacher dashboard.

Aggregates SignoffRecord rows (both flow-based via SignoffPoint and
question-based via Question/Assignment) into KPIs, breakdowns and
per-entity tables, mirroring the shape of analytics_service for the UI.
"""
import csv
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from io import StringIO
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, aliased, selectinload

from app.models.db import (
    Assignment,
    Course,
    Question,
    SignoffFlow,
    SignoffPoint,
    SignoffRecord,
    TAAssignment,
    User,
)


SIGNED_OFF = "signed_off"
INSUFFICIENT = "insufficient"

STATUS_META = [
    {
        "status": SIGNED_OFF,
        "label": "Signed off",
        "badge_classes": "bg-emerald-100 text-emerald-800",
        "chart_color": "#10b981",
    },
    {
        "status": INSUFFICIENT,
        "label": "Insufficient",
        "badge_classes": "bg-rose-100 text-rose-800",
        "chart_color": "#f43f5e",
    },
]


def get_teacher_signoff_analytics(
    db: Session,
    teacher_id: int,
    course_id: Optional[int] = None,
    assignment_id: Optional[int] = None,
    flow_id: Optional[int] = None,
    grader_id: Optional[int] = None,
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
    course_lookup = {c.id: c for c in courses}
    assignment_lookup = {
        a.id: a
        for c in courses
        for a in c.assignments
        if a.is_signoff
    }

    selected_assignment = assignment_lookup.get(assignment_id) if assignment_id else None
    if selected_assignment:
        course_id = selected_assignment.course_id

    flows = (
        db.query(SignoffFlow)
        .options(selectinload(SignoffFlow.points))
        .filter(SignoffFlow.course_id.in_([c.id for c in courses]))
        .order_by(SignoffFlow.order.asc())
        .all()
    )
    flow_lookup = {f.id: f for f in flows}
    selected_flow = flow_lookup.get(flow_id) if flow_id else None
    if selected_flow:
        course_id = selected_flow.course_id

    selected_course = course_lookup.get(course_id) if course_id else None
    if course_id and not selected_course:
        course_id = None

    grader_lookup_for_validation = _load_graders_for_courses(
        db, [c.id for c in courses]
    )
    selected_grader = grader_lookup_for_validation.get(grader_id) if grader_id else None

    rows = _load_signoff_rows(
        db=db,
        teacher_id=teacher_id,
        course_id=course_id,
        assignment_id=selected_assignment.id if selected_assignment else None,
        flow_id=selected_flow.id if selected_flow else None,
        grader_id=selected_grader.id if selected_grader else None,
        start_date=start_date,
        end_date=end_date,
    )

    payload = _build_payload(
        rows=rows,
        courses=courses,
        flows=flows,
        assignment_lookup=assignment_lookup,
        selected_course=selected_course,
        selected_assignment=selected_assignment,
        selected_flow=selected_flow,
        selected_grader=selected_grader,
        start_date=start_date,
        end_date=end_date,
    )

    scoped_courses = [selected_course] if selected_course else courses
    scoped_course_ids = [c.id for c in scoped_courses if c]
    scoped_graders = _load_graders_for_courses(db, scoped_course_ids)

    filters = {
        "course_id": selected_course.id if selected_course else None,
        "assignment_id": selected_assignment.id if selected_assignment else None,
        "flow_id": selected_flow.id if selected_flow else None,
        "grader_id": selected_grader.id if selected_grader else None,
        "start_date": start_date.isoformat() if start_date else "",
        "end_date": end_date.isoformat() if end_date else "",
        "courses": [
            {"id": c.id, "name": c.name}
            for c in courses
        ],
        "assignments": [
            {
                "id": a.id,
                "name": a.name,
                "course_id": a.course_id,
                "course_name": course_lookup[a.course_id].name,
            }
            for a in sorted(
                (a for c in (scoped_courses if selected_course else courses) for a in c.assignments if a.is_signoff),
                key=lambda a: (course_lookup[a.course_id].name.lower(), a.name.lower()),
            )
        ],
        "flows": [
            {
                "id": f.id,
                "name": f.name,
                "course_id": f.course_id,
                "course_name": course_lookup[f.course_id].name if f.course_id in course_lookup else "",
                "point_count": len(f.points),
            }
            for f in flows
            if not selected_course or f.course_id == selected_course.id
        ],
        "graders": [
            {"id": g.id, "name": g.name, "email": g.email}
            for g in scoped_graders.values()
        ],
    }

    return {"filters": filters, **payload}


def export_teacher_signoff_csv(
    db: Session,
    teacher_id: int,
    course_id: Optional[int] = None,
    assignment_id: Optional[int] = None,
    flow_id: Optional[int] = None,
    grader_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    if start_date and end_date and end_date < start_date:
        start_date, end_date = end_date, start_date

    rows = _load_signoff_rows(
        db=db,
        teacher_id=teacher_id,
        course_id=course_id,
        assignment_id=assignment_id,
        flow_id=flow_id,
        grader_id=grader_id,
        start_date=start_date,
        end_date=end_date,
    )

    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "record_id",
        "status",
        "course_id",
        "course_name",
        "scope",
        "flow_id",
        "flow_name",
        "point_id",
        "point_label",
        "assignment_id",
        "assignment_name",
        "question_id",
        "question_number",
        "student_id",
        "student_name",
        "student_email",
        "grader_id",
        "grader_name",
        "comment",
        "created_at_utc",
    ])
    for r in rows:
        writer.writerow([
            r.record_id,
            r.status,
            r.course_id,
            r.course_name,
            "flow" if r.point_id else "question",
            r.flow_id or "",
            r.flow_name or "",
            r.point_id or "",
            r.point_label or "",
            r.assignment_id or "",
            r.assignment_name or "",
            r.question_id or "",
            r.question_number if r.question_number is not None else "",
            r.student_id,
            r.student_name,
            r.student_email or "",
            r.grader_id,
            r.grader_name or "",
            (r.comment or "").replace("\n", " "),
            _serialize_utc(r.created_at),
        ])
    return output.getvalue()


# ─── Loaders ──────────────────────────────────────────────────────────────────

def _load_signoff_rows(
    db: Session,
    teacher_id: int,
    course_id: Optional[int],
    assignment_id: Optional[int],
    flow_id: Optional[int],
    grader_id: Optional[int],
    start_date: Optional[date],
    end_date: Optional[date],
):
    student = aliased(User)
    grader = aliased(User)

    flow_course = aliased(Course)
    q_assignment = aliased(Assignment)
    q_course = aliased(Course)

    query = (
        db.query(
            SignoffRecord.id.label("record_id"),
            SignoffRecord.status.label("status"),
            SignoffRecord.created_at.label("created_at"),
            SignoffRecord.comment.label("comment"),
            SignoffRecord.student_id.label("student_id"),
            student.name.label("student_name"),
            student.email.label("student_email"),
            SignoffRecord.graded_by.label("grader_id"),
            grader.name.label("grader_name"),
            SignoffRecord.point_id.label("point_id"),
            SignoffPoint.label.label("point_label"),
            SignoffPoint.flow_id.label("flow_id"),
            SignoffFlow.name.label("flow_name"),
            SignoffRecord.question_id.label("question_id"),
            Question.question_number.label("question_number"),
            Question.assignment_id.label("assignment_id"),
            q_assignment.name.label("assignment_name"),
            # course resolution: prefer flow's course, else question's assignment course
            func.coalesce(flow_course.id, q_course.id).label("course_id"),
            func.coalesce(flow_course.name, q_course.name).label("course_name"),
        )
        .join(student, SignoffRecord.student_id == student.id)
        .join(grader, SignoffRecord.graded_by == grader.id)
        .outerjoin(SignoffPoint, SignoffRecord.point_id == SignoffPoint.id)
        .outerjoin(SignoffFlow, SignoffPoint.flow_id == SignoffFlow.id)
        .outerjoin(flow_course, SignoffFlow.course_id == flow_course.id)
        .outerjoin(Question, SignoffRecord.question_id == Question.id)
        .outerjoin(q_assignment, Question.assignment_id == q_assignment.id)
        .outerjoin(q_course, q_assignment.course_id == q_course.id)
        .filter(
            (flow_course.teacher_id == teacher_id)
            | (q_course.teacher_id == teacher_id)
        )
    )

    if course_id:
        query = query.filter(
            (flow_course.id == course_id) | (q_course.id == course_id)
        )
    if assignment_id:
        query = query.filter(Question.assignment_id == assignment_id)
    if flow_id:
        query = query.filter(SignoffPoint.flow_id == flow_id)
    if grader_id:
        query = query.filter(SignoffRecord.graded_by == grader_id)

    start_dt, end_dt = _build_datetime_range(start_date, end_date)
    if start_dt:
        query = query.filter(SignoffRecord.created_at >= start_dt)
    if end_dt:
        query = query.filter(SignoffRecord.created_at < end_dt)

    return query.order_by(SignoffRecord.created_at.asc()).all()


def _load_graders_for_courses(db: Session, course_ids):
    if not course_ids:
        return {}
    rows = (
        db.query(User.id, User.name, User.email)
        .join(TAAssignment, TAAssignment.ta_id == User.id)
        .filter(TAAssignment.course_id.in_(course_ids))
        .distinct()
        .order_by(User.name.asc())
        .all()
    )
    return {row.id: row for row in rows}


# ─── Aggregation ──────────────────────────────────────────────────────────────

def _build_payload(
    rows,
    courses,
    flows,
    assignment_lookup,
    selected_course,
    selected_assignment,
    selected_flow,
    selected_grader,
    start_date,
    end_date,
):
    course_scope = [selected_course] if selected_course else courses
    flow_scope = (
        [selected_flow]
        if selected_flow
        else [f for f in flows if not selected_course or f.course_id == selected_course.id]
    )
    assignment_scope = (
        [selected_assignment]
        if selected_assignment
        else [
            a
            for c in course_scope
            for a in c.assignments
            if a.is_signoff
        ]
    )

    course_stats = {
        c.id: _init_bucket({"course_id": c.id, "course_name": c.name})
        for c in course_scope
        if c
    }
    flow_stats = {
        f.id: _init_bucket(
            {
                "flow_id": f.id,
                "flow_name": f.name,
                "course_id": f.course_id,
                "course_name": next((c.name for c in courses if c.id == f.course_id), ""),
                "point_count": len(f.points),
            }
        )
        for f in flow_scope
    }
    assignment_stats = {
        a.id: _init_bucket(
            {
                "assignment_id": a.id,
                "assignment_name": a.name,
                "course_id": a.course_id,
                "course_name": next((c.name for c in courses if c.id == a.course_id), ""),
            }
        )
        for a in assignment_scope
    }
    grader_stats = {}
    point_stats = {}  # for "stuck points"

    status_counts = Counter({SIGNED_OFF: 0, INSUFFICIENT: 0})
    student_ids = set()
    grader_ids = set()
    flow_ids_seen = set()
    assignment_ids_seen = set()
    points_covered = set()
    questions_covered = set()
    activity_by_day = Counter()
    student_record_counter = Counter()  # (student_id, point_or_question_key) → count
    recent_window_start = (datetime.utcnow() - timedelta(days=7))

    recent_activity_count = 0

    for r in rows:
        status_counts[r.status] += 1
        student_ids.add(r.student_id)
        grader_ids.add(r.grader_id)
        if r.created_at:
            activity_by_day[r.created_at.date().isoformat()] += 1
            if r.created_at >= recent_window_start:
                recent_activity_count += 1

        if r.point_id:
            points_covered.add(r.point_id)
        if r.question_id:
            questions_covered.add(r.question_id)
        if r.flow_id:
            flow_ids_seen.add(r.flow_id)
        if r.assignment_id:
            assignment_ids_seen.add(r.assignment_id)

        target_key = ("p", r.point_id) if r.point_id else ("q", r.question_id)
        student_record_counter[(r.student_id, target_key)] += 1

        # course bucket
        _apply_to_bucket(course_stats.get(r.course_id), r)

        # flow bucket
        if r.flow_id:
            _apply_to_bucket(flow_stats.get(r.flow_id), r)

        # assignment bucket
        if r.assignment_id:
            _apply_to_bucket(assignment_stats.get(r.assignment_id), r)

        # grader bucket
        gbucket = grader_stats.setdefault(
            r.grader_id,
            _init_bucket(
                {
                    "grader_id": r.grader_id,
                    "grader_name": r.grader_name or "—",
                }
            ),
        )
        _apply_to_bucket(gbucket, r)

        # point bucket (for stuck-points)
        pkey = target_key
        pbucket = point_stats.setdefault(
            pkey,
            {
                "key": pkey,
                "label": _label_for_target(r),
                "scope": "Flow" if r.point_id else "Question",
                "context": _context_for_target(r),
                "course_name": r.course_name or "",
                "course_id": r.course_id,
                "signed_off": 0,
                "insufficient": 0,
                "students": set(),
            },
        )
        if r.status == SIGNED_OFF:
            pbucket["signed_off"] += 1
        else:
            pbucket["insufficient"] += 1
        pbucket["students"].add(r.student_id)

    total = len(rows)
    signed_off = status_counts[SIGNED_OFF]
    insufficient = status_counts[INSUFFICIENT]
    pass_rate = _safe_pct(signed_off, total)
    fail_rate = _safe_pct(insufficient, total)

    # Retries: students who have >1 record on the same target
    retries = sum(1 for cnt in student_record_counter.values() if cnt > 1)
    retry_rate = _safe_pct(retries, len(student_record_counter)) if student_record_counter else 0.0

    avg_per_student = round(total / len(student_ids), 1) if student_ids else None
    avg_per_grader = round(total / len(grader_ids), 1) if grader_ids else None

    summary = {
        "total_signoffs": total,
        "signed_off_count": signed_off,
        "insufficient_count": insufficient,
        "signed_off_rate": pass_rate,
        "signed_off_rate_display": _fmt_pct(pass_rate),
        "insufficient_rate": fail_rate,
        "insufficient_rate_display": _fmt_pct(fail_rate),
        "student_count": len(student_ids),
        "grader_count": len(grader_ids),
        "flow_count": len(flow_ids_seen),
        "assignment_count": len(assignment_ids_seen),
        "points_covered": len(points_covered),
        "questions_covered": len(questions_covered),
        "avg_per_student": avg_per_student,
        "avg_per_student_display": _fmt_num(avg_per_student),
        "avg_per_grader": avg_per_grader,
        "avg_per_grader_display": _fmt_num(avg_per_grader),
        "recent_activity_count": recent_activity_count,
        "retry_count": retries,
        "retry_rate": retry_rate,
        "retry_rate_display": _fmt_pct(retry_rate),
        "status_breakdown": [
            {
                "status": meta["status"],
                "label": meta["label"],
                "count": status_counts[meta["status"]],
                "percentage": _safe_pct(status_counts[meta["status"]], total),
                "percentage_display": _fmt_pct(_safe_pct(status_counts[meta["status"]], total)),
                "badge_classes": meta["badge_classes"],
                "chart_color": meta["chart_color"],
            }
            for meta in STATUS_META
        ],
    }

    finalized_courses = sorted(
        (_finalize_bucket(b) for b in course_stats.values()),
        key=lambda b: (-b["total"], b["course_name"].lower()),
    )
    finalized_flows = sorted(
        (_finalize_bucket(b) for b in flow_stats.values()),
        key=lambda b: (-b["total"], b["flow_name"].lower()),
    )
    finalized_assignments = sorted(
        (_finalize_bucket(b) for b in assignment_stats.values()),
        key=lambda b: (-b["total"], b["assignment_name"].lower()),
    )
    finalized_graders = sorted(
        (_finalize_bucket(b) for b in grader_stats.values()),
        key=lambda b: (-b["total"], (b["grader_name"] or "").lower()),
    )

    stuck_points = sorted(
        (
            {
                "label": p["label"],
                "scope": p["scope"],
                "context": p["context"],
                "course_name": p["course_name"],
                "signed_off": p["signed_off"],
                "insufficient": p["insufficient"],
                "total": p["signed_off"] + p["insufficient"],
                "student_count": len(p["students"]),
                "insufficient_rate": _safe_pct(p["insufficient"], p["signed_off"] + p["insufficient"]),
                "insufficient_rate_display": _fmt_pct(
                    _safe_pct(p["insufficient"], p["signed_off"] + p["insufficient"])
                ),
            }
            for p in point_stats.values()
            if p["insufficient"] > 0
        ),
        key=lambda x: (-x["insufficient_rate"], -x["insufficient"]),
    )[:10]

    activity_labels = sorted(activity_by_day.keys())
    activity_counts = [activity_by_day[k] for k in activity_labels]

    focus_title = (
        selected_assignment.name if selected_assignment
        else selected_flow.name if selected_flow
        else selected_course.name if selected_course
        else "All courses"
    )

    return {
        "summary": summary,
        "course_stats": finalized_courses,
        "flow_stats": finalized_flows,
        "assignment_stats": finalized_assignments,
        "grader_stats": finalized_graders,
        "stuck_points": stuck_points,
        "focus": {
            "title": focus_title,
            "subtitle": _build_subtitle(
                selected_course, selected_assignment, selected_flow, selected_grader, start_date, end_date
            ),
        },
        "charts": {
            "activity_over_time": {"labels": activity_labels, "counts": activity_counts},
        },
    }


def _init_bucket(base):
    return {
        **base,
        "total": 0,
        "signed_off": 0,
        "insufficient": 0,
        "students": set(),
    }


def _apply_to_bucket(bucket, row):
    if bucket is None:
        return
    bucket["total"] += 1
    if row.status == SIGNED_OFF:
        bucket["signed_off"] += 1
    else:
        bucket["insufficient"] += 1
    bucket["students"].add(row.student_id)


def _finalize_bucket(bucket):
    total = bucket["total"]
    signed = bucket["signed_off"]
    insuf = bucket["insufficient"]
    pass_rate = _safe_pct(signed, total)
    fail_rate = _safe_pct(insuf, total)
    return {
        **{k: v for k, v in bucket.items() if k != "students"},
        "student_count": len(bucket["students"]),
        "signed_off_rate": pass_rate,
        "signed_off_rate_display": _fmt_pct(pass_rate),
        "insufficient_rate": fail_rate,
        "insufficient_rate_display": _fmt_pct(fail_rate),
    }


def _label_for_target(row):
    if row.point_label:
        return row.point_label
    if row.question_number is not None:
        return f"Q{row.question_number}"
    return "—"


def _context_for_target(row):
    if row.flow_name:
        return row.flow_name
    if row.assignment_name:
        return row.assignment_name
    return ""


def _build_datetime_range(start_date, end_date):
    start_dt = datetime.combine(start_date, time.min) if start_date else None
    end_dt = (
        datetime.combine(end_date + timedelta(days=1), time.min) if end_date else None
    )
    return start_dt, end_dt


def _safe_pct(part, whole):
    if not whole:
        return 0.0
    return round((part / whole) * 100, 1)


def _fmt_pct(value):
    return f"{value:.1f}%"


def _fmt_num(value):
    if value is None:
        return "—"
    return f"{value:.1f}"


def _serialize_utc(value):
    if not value:
        return ""
    return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _build_subtitle(course, assignment, flow, grader, start_date, end_date):
    bits = []
    if assignment:
        bits.append(f"Assignment: {assignment.name}")
    elif flow:
        bits.append(f"Flow: {flow.name}")
    elif course:
        bits.append(f"Course: {course.name}")
    else:
        bits.append("All teacher courses")
    if grader:
        bits.append(f"grader: {grader.name}")
    if start_date:
        bits.append(f"from {start_date.isoformat()}")
    if end_date:
        bits.append(f"through {end_date.isoformat()}")
    return " · ".join(bits)
