"""Admin + sign-off search endpoints — appended to api router via include."""
from datetime import date
from typing import Optional

from fastapi import Depends, HTTPException, Request, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.db import (
    get_db, User, UserRole, Course, Assignment, Question, CourseEnrollment,
    SignoffFlow, SignoffPoint, SignoffRecord,
    Group, GroupMember, GroupCategory,
)
from app.routes.auth import get_current_user
from app.routes.api import router, _require_course_access, _serialize_flow
from app.services.signoff_analytics_service import (
    export_teacher_signoff_csv,
    get_teacher_signoff_analytics,
)


# ─── Admin: Course Management ─────────────────────────────────────────────────

@router.get("/course/{course_id}/admin")
async def get_course_admin(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    course, _ = _require_course_access(course_id, current_user, db, teacher_only=True)
    flows = db.query(SignoffFlow).filter(SignoffFlow.course_id == course_id).order_by(SignoffFlow.order).all()
    assignments = db.query(Assignment).filter(Assignment.course_id == course_id).all()
    students = db.query(User).join(
        CourseEnrollment,
        (CourseEnrollment.user_id == User.id) &
        (CourseEnrollment.course_id == course_id) &
        (CourseEnrollment.role == UserRole.STUDENT)
    ).order_by(User.name).all()
    groups = db.query(Group).filter(Group.course_id == course_id).all()

    return {
        "course_id": course_id,
        "course_name": course.name,
        "flows": [_serialize_flow(f) for f in flows],
        "assignments": [{"id": a.id, "name": a.name} for a in assignments],
        "students": [{"id": s.id, "name": s.name, "email": s.email} for s in students],
        "groups": [
            {
                "id": g.id,
                "name": g.name,
                "assignment_id": g.assignment_id,
                "members": [{"id": m.student_id, "name": m.student.name} for m in g.members],
            }
            for g in groups
        ],
    }


@router.post("/course/{course_id}/admin/flows")
async def admin_create_flow(
    course_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_course_access(course_id, current_user, db, teacher_only=True)
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name is required")
    max_order = db.query(func.max(SignoffFlow.order)).filter(SignoffFlow.course_id == course_id).scalar() or 0
    flow = SignoffFlow(course_id=course_id, name=name, order=max_order + 1)
    db.add(flow)
    db.commit()
    db.refresh(flow)
    return _serialize_flow(flow)


@router.put("/course/{course_id}/admin/flows/{flow_id}")
async def admin_update_flow(
    course_id: int,
    flow_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_course_access(course_id, current_user, db, teacher_only=True)
    flow = db.query(SignoffFlow).filter(SignoffFlow.id == flow_id, SignoffFlow.course_id == course_id).first()
    if not flow:
        raise HTTPException(status_code=404)
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name is required")
    flow.name = name
    db.commit()
    return _serialize_flow(flow)


@router.delete("/course/{course_id}/admin/flows/{flow_id}")
async def admin_delete_flow(
    course_id: int,
    flow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_course_access(course_id, current_user, db, teacher_only=True)
    flow = db.query(SignoffFlow).filter(SignoffFlow.id == flow_id, SignoffFlow.course_id == course_id).first()
    if not flow:
        raise HTTPException(status_code=404)
    db.delete(flow)
    db.commit()
    return {"ok": True}


@router.post("/course/{course_id}/admin/flows/{flow_id}/points")
async def admin_create_point(
    course_id: int,
    flow_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_course_access(course_id, current_user, db, teacher_only=True)
    flow = db.query(SignoffFlow).filter(SignoffFlow.id == flow_id, SignoffFlow.course_id == course_id).first()
    if not flow:
        raise HTTPException(status_code=404)
    body = await request.json()
    label = (body.get("label") or "").strip()
    if not label:
        raise HTTPException(status_code=422, detail="Label is required")
    max_order = db.query(func.max(SignoffPoint.order)).filter(SignoffPoint.flow_id == flow_id).scalar() or 0
    point = SignoffPoint(flow_id=flow_id, label=label, order=max_order + 1)
    db.add(point)
    db.commit()
    db.refresh(point)
    return {"id": point.id, "label": point.label, "order": point.order}


@router.put("/course/{course_id}/admin/points/{point_id}")
async def admin_update_point(
    course_id: int,
    point_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_course_access(course_id, current_user, db, teacher_only=True)
    point = db.query(SignoffPoint).filter(SignoffPoint.id == point_id).first()
    if not point:
        raise HTTPException(status_code=404)
    body = await request.json()
    label = (body.get("label") or "").strip()
    if not label:
        raise HTTPException(status_code=422, detail="Label is required")
    point.label = label
    db.commit()
    return {"id": point.id, "label": point.label, "order": point.order}


@router.delete("/course/{course_id}/admin/points/{point_id}")
async def admin_delete_point(
    course_id: int,
    point_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_course_access(course_id, current_user, db, teacher_only=True)
    point = db.query(SignoffPoint).filter(SignoffPoint.id == point_id).first()
    if not point:
        raise HTTPException(status_code=404)
    db.delete(point)
    db.commit()
    return {"ok": True}


# ─── Admin: Groups ─────────────────────────────────────────────────────────────

@router.post("/course/{course_id}/admin/groups")
async def admin_create_group(
    course_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_course_access(course_id, current_user, db, teacher_only=True)
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name is required")
    assignment_id = body.get("assignment_id") or None
    group = Group(course_id=course_id, name=name, assignment_id=assignment_id)
    db.add(group)
    db.commit()
    db.refresh(group)
    return {"id": group.id, "name": group.name, "assignment_id": group.assignment_id, "members": []}


@router.put("/course/{course_id}/admin/groups/{group_id}")
async def admin_update_group(
    course_id: int,
    group_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_course_access(course_id, current_user, db, teacher_only=True)
    group = db.query(Group).filter(Group.id == group_id, Group.course_id == course_id).first()
    if not group:
        raise HTTPException(status_code=404)
    body = await request.json()
    if "name" in body:
        name = (body["name"] or "").strip()
        if name:
            group.name = name
    if "assignment_id" in body:
        group.assignment_id = body["assignment_id"] or None
    db.commit()
    return {
        "id": group.id, "name": group.name, "assignment_id": group.assignment_id,
        "members": [{"id": m.student_id, "name": m.student.name} for m in group.members],
    }


@router.delete("/course/{course_id}/admin/groups/{group_id}")
async def admin_delete_group(
    course_id: int,
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_course_access(course_id, current_user, db, teacher_only=True)
    group = db.query(Group).filter(Group.id == group_id, Group.course_id == course_id).first()
    if not group:
        raise HTTPException(status_code=404)
    db.delete(group)
    db.commit()
    return {"ok": True}


@router.post("/course/{course_id}/admin/groups/{group_id}/members")
async def admin_add_group_member(
    course_id: int,
    group_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_course_access(course_id, current_user, db, teacher_only=True)
    group = db.query(Group).filter(Group.id == group_id, Group.course_id == course_id).first()
    if not group:
        raise HTTPException(status_code=404)
    body = await request.json()
    student_id = body.get("student_id")
    if not student_id:
        raise HTTPException(status_code=422, detail="student_id required")
    existing = db.query(GroupMember).filter(
        GroupMember.group_id == group_id, GroupMember.student_id == student_id
    ).first()
    if not existing:
        db.add(GroupMember(group_id=group_id, student_id=student_id))
        db.commit()
    student = db.query(User).filter(User.id == student_id).first()
    return {"id": student_id, "name": student.name if student else ""}


@router.delete("/course/{course_id}/admin/groups/{group_id}/members/{student_id}")
async def admin_remove_group_member(
    course_id: int,
    group_id: int,
    student_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_course_access(course_id, current_user, db, teacher_only=True)
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id, GroupMember.student_id == student_id
    ).first()
    if member:
        db.delete(member)
        db.commit()
    return {"ok": True}


# ─── Sign-off search ──────────────────────────────────────────────────────────

@router.get("/course/{course_id}/signoff/search")
async def signoff_search(
    course_id: int,
    q: str = Query(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Search (flow, student) and (flow, group) pairs."""
    _require_course_access(course_id, current_user, db)
    flows = db.query(SignoffFlow).filter(SignoffFlow.course_id == course_id).order_by(SignoffFlow.order).all()
    students = db.query(User).join(
        CourseEnrollment,
        (CourseEnrollment.user_id == User.id) &
        (CourseEnrollment.course_id == course_id) &
        (CourseEnrollment.role == UserRole.STUDENT)
    ).order_by(User.name).all()
    groups = db.query(Group).filter(Group.course_id == course_id).all()

    query = q.strip().lower()
    results = []

    for flow in flows:
        for student in students:
            label = f"{flow.name} — {student.name}"
            if not query or query in label.lower() or query in student.email.lower():
                results.append({
                    "type": "student",
                    "flow_id": flow.id,
                    "flow_name": flow.name,
                    "student_id": student.id,
                    "student_name": student.name,
                    "label": label,
                })
        for group in groups:
            member_names = [m.student.name for m in group.members]
            label = f"{flow.name} — {group.name}"
            if not query or query in label.lower() or any(query in n.lower() for n in member_names):
                results.append({
                    "type": "group",
                    "flow_id": flow.id,
                    "flow_name": flow.name,
                    "group_id": group.id,
                    "group_name": group.name,
                    "member_count": len(group.members),
                    "label": label,
                })

    return results[:50]


# ─── Sign-off analytics ───────────────────────────────────────────────────────

@router.get("/signoff-analytics")
async def get_signoff_analytics(
    course_id: Optional[int] = Query(None),
    assignment_id: Optional[int] = Query(None),
    flow_id: Optional[int] = Query(None),
    grader_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Only teachers can access sign-off analytics")
    return get_teacher_signoff_analytics(
        db=db,
        teacher_id=current_user.id,
        course_id=course_id,
        assignment_id=assignment_id,
        flow_id=flow_id,
        grader_id=grader_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/signoff-analytics/export.csv")
async def export_signoff_analytics_csv(
    course_id: Optional[int] = Query(None),
    assignment_id: Optional[int] = Query(None),
    flow_id: Optional[int] = Query(None),
    grader_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Only teachers can export sign-off analytics")
    csv_data = export_teacher_signoff_csv(
        db=db,
        teacher_id=current_user.id,
        course_id=course_id,
        assignment_id=assignment_id,
        flow_id=flow_id,
        grader_id=grader_id,
        start_date=start_date,
        end_date=end_date,
    )
    filename = f"izem-signoff-analytics-{date.today().isoformat()}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=csv_data, media_type="text/csv; charset=utf-8", headers=headers)


@router.get("/course/{course_id}/signoff/q/search")
async def signoff_search_by_question(
    course_id: int,
    q: str = Query(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Search (assignment, student) pairs for question-based sign-off labs."""
    _require_course_access(course_id, current_user, db)
    assignments = db.query(Assignment).filter(
        Assignment.course_id == course_id,
        Assignment.is_signoff == True,
    ).order_by(Assignment.created_at).all()
    students = db.query(User).join(
        CourseEnrollment,
        (CourseEnrollment.user_id == User.id) &
        (CourseEnrollment.course_id == course_id) &
        (CourseEnrollment.role == UserRole.STUDENT)
    ).order_by(User.name).all()
    query = q.strip().lower()
    results = []

    for a in assignments:
        if a.signoff_group_category_id:
            # Group-based sign-off: show groups from the assigned category
            cat = db.query(GroupCategory).filter(GroupCategory.id == a.signoff_group_category_id).first()
            if not cat:
                continue
            for group in cat.groups:
                member_names = [m.student.name for m in group.members]
                label = f"{a.name} — {group.name}"
                if not query or query in label.lower() or any(query in n.lower() for n in member_names):
                    results.append({
                        "type": "group",
                        "assignment_id": a.id,
                        "assignment_name": a.name,
                        "group_id": group.id,
                        "category_id": group.category_id,
                        "group_name": group.name,
                        "category_name": cat.name,
                        "member_count": len(group.members),
                        "label": label,
                    })
        else:
            # Individual sign-off: show each enrolled student
            for student in students:
                label = f"{a.name} — {student.name}"
                if not query or query in label.lower() or query in student.email.lower():
                    results.append({
                        "type": "student",
                        "assignment_id": a.id,
                        "assignment_name": a.name,
                        "student_id": student.id,
                        "student_name": student.name,
                        "label": label,
                    })

    return results[:50]
