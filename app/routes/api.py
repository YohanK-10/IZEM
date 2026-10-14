from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional
from datetime import datetime, date, timezone
import logging
import re
import os
import uuid
import threading

from app.models.db import (
    get_db, User, UserRole, AuthToken, Course, Assignment,
    LLMConfig, TAAssignment, CourseEnrollment, QueueRoom,
    HelpRequest, RequestStatus, Question,
    Session as LabSession,
    SignoffFlow, SignoffPoint, SignoffRecord,
    Group, GroupMember, GroupCategory,
)
from app.auth.permissions import (
    require_assignment_access,
    require_course_access,
    require_request_access,
    require_room_access,
)
from app.routes.auth import get_current_user
from app.repositories.queries import get_courses_summary
from app.services.analytics_service import (
    export_teacher_analytics_csv,
    get_teacher_analytics_dashboard,
)
from app.services.emailer import email_service
from app.services.feedback_formatting import format_feedback_text
from app.services.notification_service import get_notifications, mark_all_read, mark_read

logger = logging.getLogger(__name__)

ALLOW_TEST_ACCOUNTS = os.getenv("ALLOW_TEST_ACCOUNTS", "false").lower() in ("1", "true", "yes")
ALLOW_DEV_LOGIN_FOR_EXISTING_USERS = os.getenv(
    "ALLOW_DEV_LOGIN_FOR_EXISTING_USERS",
    "false",
).lower() in ("1", "true", "yes")

# Single source of truth for test accounts (issue 24)
TEST_ACCOUNTS: dict[str, tuple[str, UserRole]] = {
    "teacher@example.com":          ("Demo Instructor",    UserRole.TEACHER),
    "student@example.com":           ("Test Student", UserRole.STUDENT),
    "ta@example.com":                ("Test TA",      UserRole.TA),
    "learner.two@example.com": ("Demo Learner Two",     UserRole.STUDENT),
    "assistant.two@example.com": ("Demo Assistant Two",     UserRole.TA)
}

# Serialises queue-position reads to prevent duplicate positions (issue 22)
_queue_position_lock = threading.Lock()


def build_submission_image_url(stored_path: str | None) -> str | None:
    if not stored_path:
        return None
    return f"/uploads/{os.path.basename(stored_path)}"


def serialize_utc(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    return dt.replace(microsecond=0, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _get_effective_assignment_id(
    db: Session,
    room: Optional[QueueRoom],
    *,
    parent_room: Optional[QueueRoom] = None,
) -> Optional[int]:
    if room is None:
        return None
    if room.assignment_id is not None:
        return room.assignment_id
    if parent_room is None and room.parent_room_id is not None:
        parent_room = db.query(QueueRoom).filter(QueueRoom.id == room.parent_room_id).first()
    if parent_room is not None:
        return parent_room.assignment_id
    return None


def _resolve_stale_unclaimed_request(db: Session, help_request: HelpRequest) -> bool:
    if help_request.status not in (RequestStatus.PENDING, RequestStatus.AI_GENERATED):
        return False
    if help_request.assigned_ta_id is not None:
        return False
    if help_request.is_overtime:
        return False

    question = db.query(Question).filter(Question.id == help_request.question_id).first()
    assignment = db.query(Assignment).filter(
        Assignment.id == question.assignment_id
    ).first() if question else None

    if assignment and assignment.queue_open:
        return False

    now = datetime.utcnow()
    help_request.status = RequestStatus.RESOLVED
    help_request.resolved_at = now
    help_request.queue_position = None
    help_request.ai_progress_status = None
    help_request.ai_feedback = None
    help_request.ai_queue_state = None
    help_request.ai_queue_enqueued_at = None
    help_request.ai_queue_started_at = None
    help_request.ai_queue_error = None
    help_request.last_progress_update = now
    help_request.final_feedback = (
        help_request.final_feedback
        or "The queue was closed before a TA could pick up your request."
    )
    return True


def _validate_top_level_room_names(
    db: Session,
    *,
    course_id: int,
    room_names: list[str],
    assignment_id: Optional[int] = None,
) -> list[str]:
    sanitized_names = [name.strip() for name in room_names if name and name.strip()]
    if not sanitized_names:
        raise HTTPException(status_code=422, detail="At least one room name is required")

    submitted_lower = [name.lower() for name in sanitized_names]
    if len(set(submitted_lower)) != len(submitted_lower):
        raise HTTPException(status_code=409, detail="Duplicate room names submitted")

    query = db.query(QueueRoom).filter(
        QueueRoom.parent_room_id == None,
        QueueRoom.is_open == True,
        QueueRoom.course_id == course_id,
    )
    if assignment_id is not None:
        query = query.filter(QueueRoom.assignment_id == assignment_id)

    existing_names = {
        (room.name or "").strip().lower()
        for room in query.all()
        if room.name
    }
    conflicts = [name for name in sanitized_names if name.lower() in existing_names]
    if conflicts:
        joined = ", ".join(conflicts)
        scope = "this assignment" if assignment_id is not None else "this course"
        raise HTTPException(status_code=409, detail=f"Room name(s) already exist for {scope}: {joined}")

    return sanitized_names

router = APIRouter(prefix="/api", tags=["api"])


# ─── Auth ─────────────────────────────────────────────────────────────────────

@router.post("/auth/login")
async def api_login(request: Request, response: Response, db: Session = Depends(get_db)):
    body = await request.json()
    email = (body.get("email") or "").strip().lower()

    if not email or not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
        raise HTTPException(status_code=422, detail="Invalid email address")

    if ALLOW_TEST_ACCOUNTS and email in TEST_ACCOUNTS:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            name, role = TEST_ACCOUNTS[email]
            user = User(email=email, name=name, role=role)
            db.add(user)
            db.commit()
            db.refresh(user)

        auth_token = AuthToken(user_id=user.id)
        auth_token.used = True
        db.add(auth_token)
        db.commit()

        response.set_cookie(
            key="session_token",
            value=auth_token.token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=86400
        )
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role.value,
            "has_canvas_token": bool(user.canvas_api_token),
        }

    # Normal magic-link flow
    user = db.query(User).filter(User.email == email).first()
    if ALLOW_DEV_LOGIN_FOR_EXISTING_USERS and user:
        auth_token = AuthToken(user_id=user.id)
        auth_token.used = True
        db.add(auth_token)
        db.commit()

        response.set_cookie(
            key="session_token",
            value=auth_token.token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=86400
        )
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role.value,
            "has_canvas_token": bool(user.canvas_api_token),
        }

    if not user:
        return {"message": "If this email is registered, a login link has been sent."}

    # Clean up expired unused tokens
    from app.models.db import AuthToken as AT
    existing = db.query(AT).filter(
        AT.user_id == user.id,
        AT.used == False,
        AT.expires_at > datetime.utcnow()
    ).first()
    if existing:
        db.delete(existing)

    auth_token = AuthToken(user_id=user.id)
    db.add(auth_token)
    db.commit()

    email_service.send_magic_link(email, auth_token.token)
    return {"message": "Check your email for the login link."}


@router.post("/auth/logout")
async def api_logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("session_token")
    if token:
        auth_token = db.query(AuthToken).filter(AuthToken.token == token).first()
        if auth_token:
            db.delete(auth_token)
            db.commit()
    response.delete_cookie("session_token")
    return {"ok": True}


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role.value,
        "canvas_user_id": current_user.canvas_user_id,
        "has_canvas_token": bool(current_user.canvas_api_token),
    }


@router.get("/notifications")
async def api_get_notifications(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_notifications(db, current_user.id, current_user.role.value, limit)


@router.post("/notifications/{notification_id}/read")
async def api_mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return mark_read(db, notification_id, current_user.id)


@router.post("/notifications/read-all")
async def api_mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return mark_all_read(db, current_user.id)


# ─── Courses ──────────────────────────────────────────────────────────────────

@router.get("/courses")
async def get_courses(
    show_hidden: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    role = current_user.role

    if role == UserRole.TEACHER:
        data = get_courses_summary(db, current_user.id, show_hidden)
        return [
            {
                "id": item["course"].id,
                "name": item["course"].name,
                "canvas_course_id": item["course"].canvas_course_id,
                "hidden": item["course"].hidden,
                "assignments_count": item["assignments_count"],
                "students_count": item["students_count"],
                "tas_count": item["tas_count"],
                "active_sessions": item["active_sessions"],
                "first_open_assignment_id": item["first_open_assignment_id"],
                "role": "teacher",
            }
            for item in data
        ]

    if role == UserRole.TA:
        course_ids = [
            ta.course_id
            for ta in db.query(TAAssignment).filter(TAAssignment.ta_id == current_user.id).all()
        ]
        courses = db.query(Course).filter(Course.id.in_(course_ids)).all() if course_ids else []
        result = []
        for course in courses:
            open_assignment = db.query(Assignment).filter(
                Assignment.course_id == course.id,
                Assignment.queue_open == True
            ).first()
            assignments = db.query(Assignment).filter(Assignment.course_id == course.id).all()
            result.append({
                "id": course.id,
                "name": course.name,
                "canvas_course_id": course.canvas_course_id,
                "hidden": False,
                "assignments_count": len(assignments),
                "active_sessions": 1 if open_assignment else 0,
                "first_open_assignment_id": open_assignment.id if open_assignment else None,
                "assignments": [
                    {"id": a.id, "name": a.name, "queue_open": a.queue_open}
                    for a in assignments
                ],
                "role": "ta",
            })
        return result

    if role == UserRole.STUDENT:
        enrolled_ids = [
            cid for (cid,) in db.query(CourseEnrollment.course_id).filter(
                CourseEnrollment.user_id == current_user.id,
                CourseEnrollment.role == UserRole.STUDENT
            ).all()
        ]
        courses = db.query(Course).filter(Course.id.in_(enrolled_ids)).all() if enrolled_ids else []
        result = []
        for course in courses:
            open_assignments = db.query(Assignment).filter(
                Assignment.course_id == course.id,
                Assignment.queue_open == True
            ).all()
            result.append({
                "id": course.id,
                "name": course.name,
                "canvas_course_id": course.canvas_course_id,
                "open_queues": len(open_assignments),
                "open_assignments": [
                    {"id": a.id, "name": a.name}
                    for a in open_assignments
                ],
                "role": "student",
            })
        return result

    return []


# ─── Queue ────────────────────────────────────────────────────────────────────

@router.get("/queue/{assignment_id}")
async def get_queue(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role == UserRole.STUDENT:
        assignment, course = require_assignment_access(
            db, assignment_id, current_user.id, {UserRole.STUDENT}
        )
    elif current_user.role in (UserRole.TA, UserRole.TEACHER):
        assignment, course = require_assignment_access(
            db, assignment_id, current_user.id, {UserRole.TA, UserRole.TEACHER}
        )
    else:
        raise HTTPException(status_code=403)

    rooms = db.query(QueueRoom).filter(
        QueueRoom.assignment_id == assignment_id,
        QueueRoom.is_open == True,
        QueueRoom.parent_room_id == None
    ).all()

    question_ids = [
        q[0] for q in db.query(Question.id).filter(Question.assignment_id == assignment_id).all()
    ]
    questions = db.query(Question).filter(Question.assignment_id == assignment_id).order_by(
        Question.question_number
    ).all() if question_ids else []

    queue_items = db.query(HelpRequest).filter(
        HelpRequest.question_id.in_(question_ids),
        HelpRequest.status.in_([RequestStatus.PENDING, RequestStatus.AI_GENERATED]),
        HelpRequest.assigned_ta_id == None,
        HelpRequest.is_overtime.is_not(True),
    ).order_by(
        HelpRequest.queue_room_id.asc(),
        HelpRequest.queue_position.asc(),
        HelpRequest.joined_queue_at.asc(),
    ).all() if question_ids else []

    being_helped_items = db.query(HelpRequest).filter(
        HelpRequest.question_id.in_(question_ids),
        HelpRequest.status.in_([RequestStatus.PENDING, RequestStatus.AI_GENERATED]),
        HelpRequest.assigned_ta_id != None,
    ).order_by(
        HelpRequest.queue_room_id.asc(),
        HelpRequest.started_helping_at.asc(),
        HelpRequest.joined_queue_at.asc(),
    ).all() if question_ids else []

    # Build a map of all queue rooms (parent + child) for is_signoff lookup
    all_room_ids = {
        item.queue_room_id
        for item in [*queue_items, *being_helped_items]
        if item.queue_room_id
    }
    room_signoff_map: dict = {}
    if all_room_ids:
        for r in db.query(QueueRoom).filter(QueueRoom.id.in_(all_room_ids)).all():
            room_signoff_map[r.id] = bool(r.is_signoff)

    ta_ids = {item.assigned_ta_id for item in being_helped_items if item.assigned_ta_id}
    ta_name_map = {}
    if ta_ids:
        ta_name_map = {
            user.id: user.name
            for user in db.query(User).filter(User.id.in_(ta_ids)).all()
        }

    def serialize_queue_item(item: HelpRequest) -> dict:
        q = db.query(Question).filter(Question.id == item.question_id).first()
        student = db.query(User).filter(User.id == item.student_id).first()
        wait_time = (
            int((datetime.utcnow() - item.joined_queue_at).total_seconds() / 60)
            if item.joined_queue_at else 0
        )
        is_signoff_item = room_signoff_map.get(item.queue_room_id, False) or (bool(q.require_signoff) if q else False)
        return {
            "id": item.id,
            "student_name": student.name if student else "Unknown",
            "student_id": item.student_id,
            "question_number": q.question_number if q else None,
            "question_id": item.question_id,
            "require_signoff": is_signoff_item,
            "status": item.status.value,
            "queue_position": item.queue_position,
            "wait_time_minutes": wait_time,
            "student_comment": item.student_comment,
            "submission_text": item.submission_text,
            "room_id": item.queue_room_id,
            "has_ai_feedback": bool(item.ai_feedback),
            "assigned_ta_name": ta_name_map.get(item.assigned_ta_id),
        }

    items_data = [serialize_queue_item(item) for item in queue_items]
    helped_data = [serialize_queue_item(item) for item in being_helped_items]

    my_request = None
    if current_user.role == UserRole.STUDENT and question_ids:
        req = db.query(HelpRequest).filter(
            HelpRequest.student_id == current_user.id,
            HelpRequest.question_id.in_(question_ids),
            HelpRequest.status.in_([
                RequestStatus.PENDING,
                RequestStatus.AI_GENERATED,
                RequestStatus.APPROVED,
                RequestStatus.EDITED,
                RequestStatus.IN_PERSON,
            ])
        ).order_by(HelpRequest.created_at.desc(), HelpRequest.id.desc()).first()
        if req and _resolve_stale_unclaimed_request(db, req):
            db.commit()
            req = None
        if req:
            my_request = {
                "id": req.id,
                "queue_position": req.queue_position,
                "status": req.status.value,
                "question_id": req.question_id,
                "ai_progress_status": req.ai_progress_status,
                "is_overtime": bool(req.is_overtime),
            }

    # Child queues (named queues inside each room)
    room_ids = [r.id for r in rooms]
    child_queues = db.query(QueueRoom).filter(
        QueueRoom.parent_room_id.in_(room_ids),
        QueueRoom.is_open == True
    ).all() if room_ids else []
    parent_room_map = {room.id: room for room in rooms}

    return {
        "assignment": {
            "id": assignment.id,
            "name": assignment.name,
            "queue_open": assignment.queue_open,
            "is_signoff": bool(assignment.is_signoff),
            "course_id": assignment.course_id,
        },
        "course": {"id": course.id, "name": course.name} if course else None,
        "rooms": [{"id": r.id, "name": r.name, "location": r.location, "is_signoff": bool(r.is_signoff)} for r in rooms],
        "queues": [
            {
                "id": q.id,
                "name": q.name,
                "parent_room_id": q.parent_room_id,
                "assignment_id": _get_effective_assignment_id(
                    db,
                    q,
                    parent_room=parent_room_map.get(q.parent_room_id),
                ),
                "location": None,
                "is_signoff": bool(q.is_signoff),
            }
            for q in child_queues
        ],
        "questions": [
            {"id": q.id, "question_number": q.question_number, "label": q.label, "description": q.problem_description[:200], "require_signoff": bool(q.require_signoff)}
            for q in questions
        ],
        "queue_items": items_data,
        "being_helped_items": helped_data,
        "total_in_queue": len(items_data),
        "total_being_helped": len(helped_data),
        "my_request": my_request,
    }


# ─── Analytics ────────────────────────────────────────────────────────────────

@router.get("/analytics")
async def get_analytics(
    course_id: Optional[int] = Query(None),
    assignment_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Only teachers can access analytics")

    return get_teacher_analytics_dashboard(
        db=db,
        teacher_id=current_user.id,
        course_id=course_id,
        assignment_id=assignment_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/analytics/export.csv")
async def export_analytics_csv(
    course_id: Optional[int] = Query(None),
    assignment_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Only teachers can export analytics")

    csv_data = export_teacher_analytics_csv(
        db=db,
        teacher_id=current_user.id,
        course_id=course_id,
        assignment_id=assignment_id,
        start_date=start_date,
        end_date=end_date,
    )
    filename = f"izem-analytics-{date.today().isoformat()}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=csv_data, media_type="text/csv; charset=utf-8", headers=headers)


# ─── LLM Configs ──────────────────────────────────────────────────────────────

@router.get("/llm/configs")
async def get_llm_configs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in (UserRole.TEACHER, UserRole.TA):
        raise HTTPException(status_code=403, detail="Not authorized")

    def serialize(llm, owned: bool):
        return {
            "id": llm.id,
            "name": llm.name,
            "base_url": llm.base_url,
            "model_name": llm.model_name,
            "is_public": llm.is_public,
            "owned": owned,
        }

    my_configs = db.query(LLMConfig).filter(LLMConfig.owner_user_id == current_user.id).all()
    public_configs = db.query(LLMConfig).filter(
        LLMConfig.is_public == True,
        LLMConfig.owner_user_id != current_user.id
    ).all()

    return {
        "my_configs": [serialize(c, owned=True) for c in my_configs],
        "public_configs": [serialize(c, owned=False) for c in public_configs],
    }


@router.post("/llm/configs")
async def create_llm_config(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Only teachers can create LLM configs")

    body = await request.json()
    required = ("name", "base_url", "api_key", "model_name")
    for field in required:
        if not body.get(field):
            raise HTTPException(status_code=422, detail=f"Missing field: {field}")

    llm = LLMConfig(
        name=body["name"],
        base_url=body["base_url"].rstrip('/'),
        api_key=body["api_key"],
        model_name=body["model_name"],
        is_public=bool(body.get("is_public", False)),
        owner_user_id=current_user.id
    )
    db.add(llm)
    db.commit()
    db.refresh(llm)
    return {
        "id": llm.id, "name": llm.name, "base_url": llm.base_url,
        "model_name": llm.model_name, "is_public": llm.is_public, "owned": True
    }


@router.put("/llm/configs/{llm_id}")
async def update_llm_config(
    llm_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    llm = db.query(LLMConfig).filter(
        LLMConfig.id == llm_id,
        LLMConfig.owner_user_id == current_user.id
    ).first()
    if not llm:
        raise HTTPException(status_code=404, detail="LLM config not found")

    body = await request.json()
    if body.get("name"):
        llm.name = body["name"]
    if body.get("base_url"):
        llm.base_url = body["base_url"].rstrip('/')
    if body.get("api_key"):
        llm.api_key = body["api_key"]
    if body.get("model_name"):
        llm.model_name = body["model_name"]
    if "is_public" in body:
        llm.is_public = bool(body["is_public"])

    db.commit()
    return {
        "id": llm.id, "name": llm.name, "base_url": llm.base_url,
        "model_name": llm.model_name, "is_public": llm.is_public, "owned": True
    }


@router.delete("/llm/configs/{llm_id}")
async def delete_llm_config(
    llm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    llm = db.query(LLMConfig).filter(
        LLMConfig.id == llm_id,
        LLMConfig.owner_user_id == current_user.id
    ).first()
    if not llm:
        raise HTTPException(status_code=404, detail="LLM config not found")
    # Null out FK references before deleting to avoid orphan rows (issue 14)
    db.query(Assignment).filter(Assignment.llm_config_id == llm_id).update({"llm_config_id": None})
    db.query(LabSession).filter(LabSession.active_llm_config_id == llm_id).update({"active_llm_config_id": None})
    db.delete(llm)
    db.commit()
    return {"ok": True}


@router.post("/llm/configs/test")
async def test_llm_config_adhoc(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test an LLM connection using ad-hoc credentials (not yet saved)."""
    if current_user.role not in (UserRole.TEACHER, UserRole.TA):
        raise HTTPException(status_code=403)
    body = await request.json()
    base_url = (body.get("base_url") or "").rstrip("/")
    api_key  = body.get("api_key") or ""
    model    = body.get("model_name") or ""
    if not base_url or not api_key or not model:
        raise HTTPException(status_code=422, detail="base_url, api_key and model_name are required")
    try:
        import requests as _req
        resp = _req.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
            timeout=10,
        )
        if resp.status_code < 400:
            return {"ok": True, "message": "Connection successful"}
        return {"ok": False, "message": f"LLM returned HTTP {resp.status_code}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@router.post("/llm/configs/{llm_id}/test")
async def test_llm_config_saved(
    llm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test a saved LLM config by id."""
    if current_user.role not in (UserRole.TEACHER, UserRole.TA):
        raise HTTPException(status_code=403)
    llm = db.query(LLMConfig).filter(LLMConfig.id == llm_id).first()
    if not llm:
        raise HTTPException(status_code=404, detail="LLM config not found")
    try:
        import requests as _req
        resp = _req.post(
            f"{llm.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {llm.api_key}", "Content-Type": "application/json"},
            json={"model": llm.model_name, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
            timeout=10,
        )
        if resp.status_code < 400:
            return {"ok": True, "message": "Connection successful"}
        return {"ok": False, "message": f"LLM returned HTTP {resp.status_code}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# ─── Settings ─────────────────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Only teachers can access settings")
    return {
        "has_canvas_token": bool(current_user.canvas_api_token),
        "canvas_user_id": current_user.canvas_user_id,
    }


@router.post("/settings/canvas-token")
async def save_canvas_token(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Only teachers can set Canvas token")

    from app.services.canvas import CanvasAPIClient
    body = await request.json()
    token = (body.get("token") or "").strip()
    if not token:
        raise HTTPException(status_code=422, detail="Token is required")

    canvas = CanvasAPIClient(token)
    if not canvas.validate_token():
        raise HTTPException(status_code=400, detail="Invalid Canvas API token")

    current_user.canvas_api_token = token
    profile = canvas.get_user_profile()
    if profile:
        current_user.canvas_user_id = str(profile.get("id"))
    db.commit()
    return {"ok": True, "has_canvas_token": True}


# ─── Canvas Course Import ──────────────────────────────────────────────────────

@router.get("/canvas/courses")
async def canvas_list_courses(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Teachers only")
    if not current_user.canvas_api_token:
        raise HTTPException(status_code=400, detail="No Canvas token configured")
    from app.services.canvas import CanvasAPIClient
    canvas = CanvasAPIClient(current_user.canvas_api_token)
    courses = canvas.get_courses()
    imported_ids = {
        c.canvas_course_id
        for c in db.query(Course).filter(Course.teacher_id == current_user.id).all()
        if c.canvas_course_id
    }
    return [
        {
            "canvas_course_id": str(c["id"]),
            "name": c.get("name", f"Course {c['id']}"),
            "already_imported": str(c["id"]) in imported_ids,
        }
        for c in courses
    ]


@router.post("/canvas/import")
async def canvas_import_course(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Teachers only")
    if not current_user.canvas_api_token:
        raise HTTPException(status_code=400, detail="No Canvas token configured")

    canvas_course_id = str(body.get("canvas_course_id", "")).strip()
    name = str(body.get("name", "")).strip()
    if not canvas_course_id or not name:
        raise HTTPException(status_code=400, detail="canvas_course_id and name are required")

    existing = db.query(Course).filter(Course.canvas_course_id == canvas_course_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Course already imported")

    from app.services.canvas import CanvasAPIClient
    canvas = CanvasAPIClient(current_user.canvas_api_token)

    try:
        canvas_courses = canvas.get_courses()
        course_data = next((c for c in canvas_courses if str(c.get("id")) == canvas_course_id), None)
        if not course_data:
            raise HTTPException(status_code=404, detail="Canvas course not found")

        course = Course(
            canvas_course_id=canvas_course_id,
            name=course_data.get("name", name),
            teacher_id=current_user.id,
        )
        db.add(course)
        db.flush()

        imported_tas = 0
        for raw_ta in canvas.identify_tas(canvas_course_id):
            email = (raw_ta.get("email") or raw_ta.get("login_id") or "").strip().lower()
            if not email:
                continue

            ta_user = db.query(User).filter(User.email == email).first()
            if not ta_user:
                ta_user = User(
                    email=email,
                    name=raw_ta.get("name", "Unknown TA"),
                    canvas_user_id=str(raw_ta.get("id")) if raw_ta.get("id") is not None else None,
                    role=UserRole.TA,
                )
                db.add(ta_user)
                db.flush()
            elif raw_ta.get("id") is not None and not ta_user.canvas_user_id:
                ta_user.canvas_user_id = str(raw_ta.get("id"))

            existing_assignment = db.query(TAAssignment).filter(
                TAAssignment.ta_id == ta_user.id,
                TAAssignment.course_id == course.id,
                TAAssignment.assignment_id == None,
            ).first()
            if not existing_assignment:
                db.add(TAAssignment(ta_id=ta_user.id, course_id=course.id))
            imported_tas += 1

        db.commit()
        db.refresh(course)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Canvas import failed for course %s", canvas_course_id)
        raise HTTPException(status_code=500, detail="Failed to import Canvas course") from exc

    return {
        "id": course.id,
        "name": course.name,
        "canvas_course_id": course.canvas_course_id,
        "imported_tas": imported_tas,
    }


# ─── TA Dashboard ──────────────────────────────────────────────────────────────

@router.get("/ta/dashboard")
async def ta_dashboard(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.TA:
        raise HTTPException(status_code=403, detail="TA only")

    course_ids = list({
        ta.course_id
        for ta in db.query(TAAssignment).filter(
            TAAssignment.ta_id == current_user.id,
            TAAssignment.assignment_id == None,
        ).all()
    })
    courses = db.query(Course).filter(Course.id.in_(course_ids)).all() if course_ids else []

    # Active rooms (open queues with room info)
    active_rooms = []
    for course in courses:
        for assignment in db.query(Assignment).filter(Assignment.course_id == course.id, Assignment.queue_open == True).all():
            for room in db.query(QueueRoom).filter(
                QueueRoom.assignment_id == assignment.id,
                QueueRoom.parent_room_id == None,
                QueueRoom.is_open == True,
            ).all():
                q_ids = [q.id for q in db.query(Question).filter(Question.assignment_id == assignment.id).all()]
                child_queue_ids = [
                    q.id for q in db.query(QueueRoom).filter(
                        QueueRoom.parent_room_id == room.id,
                        QueueRoom.is_open == True,
                    ).all()
                ]
                tracked_room_ids = [room.id, *child_queue_ids]
                queue_count = db.query(HelpRequest).filter(
                    HelpRequest.question_id.in_(q_ids),
                    HelpRequest.queue_room_id.in_(tracked_room_ids),
                    HelpRequest.status.in_([RequestStatus.PENDING, RequestStatus.AI_GENERATED])
                ).count() if q_ids else 0
                active_rooms.append({
                    "assignment_id": assignment.id, "assignment_name": assignment.name,
                    "course_name": course.name, "room_id": room.id, "room_name": room.name,
                    "queue_count": queue_count,
                })

    # Courses with assignment list
    courses_data = []
    for course in courses:
        assignments = db.query(Assignment).filter(Assignment.course_id == course.id).all()
        courses_data.append({
            "id": course.id, "name": course.name,
            "assignments": [{"id": a.id, "name": a.name, "queue_open": a.queue_open} for a in assignments],
        })

    # Pending requests assigned to this TA
    pending = (
        db.query(HelpRequest)
        .join(Question, HelpRequest.question_id == Question.id)
        .join(Assignment, Question.assignment_id == Assignment.id)
        .filter(
            HelpRequest.assigned_ta_id == current_user.id,
            HelpRequest.status == RequestStatus.AI_GENERATED,
            HelpRequest.is_overtime == False,
            Assignment.queue_open == True,
        )
        .order_by(HelpRequest.created_at.desc())
        .limit(20)
        .all()
    )

    pending_list = []
    for req in pending:
        q = db.query(Question).filter(Question.id == req.question_id).first()
        a = db.query(Assignment).filter(Assignment.id == q.assignment_id).first() if q else None
        s = db.query(User).filter(User.id == req.student_id).first()
        pending_list.append({
            "id": req.id, "student_name": s.name if s else "--",
            "assignment_name": a.name if a else "--",
            "question_number": q.question_number if q else None, "status": req.status.value,
        })

    # Recently resolved
    resolved = db.query(HelpRequest).filter(
        HelpRequest.assigned_ta_id == current_user.id,
        HelpRequest.status.in_([RequestStatus.APPROVED, RequestStatus.EDITED, RequestStatus.IN_PERSON, RequestStatus.RESOLVED])
    ).order_by(HelpRequest.resolved_at.desc()).limit(10).all()

    resolved_list = []
    for req in resolved:
        q = db.query(Question).filter(Question.id == req.question_id).first()
        a = db.query(Assignment).filter(Assignment.id == q.assignment_id).first() if q else None
        s = db.query(User).filter(User.id == req.student_id).first()
        resolved_list.append({
            "id": req.id, "student_name": s.name if s else "--",
            "assignment_name": a.name if a else "--",
            "question_number": q.question_number if q else None, "status": req.status.value,
            "resolved_at": serialize_utc(req.resolved_at),
        })

    # Available LLMs for open queue modal
    llm_list = db.query(LLMConfig).filter(
        (LLMConfig.owner_user_id == current_user.id) | (LLMConfig.is_public == True)
    ).all()

    return {
        "active_rooms": active_rooms, "courses": courses_data,
        "pending_requests": pending_list, "recent_resolved": resolved_list,
        "request_count": len(pending_list),
        "available_llms": [{"id": l.id, "name": l.name, "model_name": l.model_name} for l in llm_list],
    }


@router.post("/ta/assignment/{assignment_id}/queue/open")
async def ta_open_queue(
    assignment_id: int, request: Request,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    assignment, _course = require_assignment_access(
        db, assignment_id, current_user.id, {UserRole.TA, UserRole.TEACHER}
    )
    body = await request.json()
    llm_id = body.get("llm_id")
    # Support both new {rooms: [{name, is_signoff}]} and legacy {room_names: [...]}
    rooms_data = body.get("rooms")
    if not rooms_data:
        legacy = body.get("room_names") or ["Room A"]
        rooms_data = [{"name": n, "is_signoff": False} for n in legacy]

    sanitized_entries = [
        {
            "name": (entry.get("name") or "").strip(),
            "is_signoff": bool(entry.get("is_signoff", False)),
        }
        for entry in rooms_data
        if (entry.get("name") or "").strip()
    ]
    room_names = _validate_top_level_room_names(
        db,
        course_id=assignment.course_id,
        assignment_id=assignment.id,
        room_names=[entry["name"] for entry in sanitized_entries],
    )

    assignment.queue_open = True
    assignment.queue_opened_at = datetime.utcnow()
    assignment.queue_opened_by = current_user.id
    if llm_id:
        assignment.llm_config_id = llm_id

    created_rooms = []
    for room_entry, name in zip(sanitized_entries, room_names):
        is_signoff = room_entry["is_signoff"]
        room = QueueRoom(
            assignment_id=assignment_id,
            course_id=assignment.course_id,
            name=name,
            is_open=True,
            is_signoff=is_signoff,
            opened_at=datetime.utcnow(),
            opened_by=current_user.id,
        )
        db.add(room)
        created_rooms.append(name)
    db.commit()
    return {"ok": True, "assignment_id": assignment_id, "rooms": created_rooms}




# ─── Course Configure (teacher only) ─────────────────────────────────────────

@router.get("/course/{course_id}/configure")
async def get_course_configure(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Teacher only")
    course = db.query(Course).filter(Course.id == course_id, Course.teacher_id == current_user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    assignments = db.query(Assignment).filter(Assignment.course_id == course_id).order_by(Assignment.created_at).all()
    result = []
    for a in assignments:
        questions = db.query(Question).filter(Question.assignment_id == a.id).order_by(Question.question_number).all()
        result.append({
            "id": a.id,
            "name": a.name,
            "description": a.description,
            "is_signoff": bool(a.is_signoff),
            "signoff_group_category_id": a.signoff_group_category_id,
            "llm_config_id": a.llm_config_id,
            "questions": [
                {
                    "id": q.id,
                    "question_number": q.question_number,
                    "label": q.label,
                    "problem_description": q.problem_description,
                    "official_solution": q.official_solution,
                    "hinting_strategy": q.hinting_strategy,
                    "require_signoff": bool(q.require_signoff),
                }
                for q in questions
            ],
        })
    ta_ids = db.query(TAAssignment.ta_id).filter(
        TAAssignment.course_id == course_id,
        TAAssignment.assignment_id == None
    ).distinct().all()
    ta_users = db.query(User).filter(User.id.in_([r[0] for r in ta_ids])).order_by(User.name).all()
    tas = [{"id": u.id, "name": u.name, "email": u.email} for u in ta_users]

    group_categories = db.query(GroupCategory).filter(GroupCategory.course_id == course_id).order_by(GroupCategory.name).all()
    categories = [{"id": c.id, "name": c.name} for c in group_categories]

    llm_list = db.query(LLMConfig).filter(
        or_(LLMConfig.owner_user_id == current_user.id, LLMConfig.is_public == True)
    ).order_by(LLMConfig.name).all()
    available_llms = [{"id": l.id, "name": l.name, "model_name": l.model_name} for l in llm_list]

    return {"course_id": course_id, "course_name": course.name, "assignments": result, "tas": tas, "group_categories": categories, "available_llms": available_llms}


@router.post("/course/{course_id}/assignments")
async def create_assignment(
    course_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Teacher only")
    course = db.query(Course).filter(Course.id == course_id, Course.teacher_id == current_user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Assignment name is required")
    a = Assignment(course_id=course_id, name=name, description=body.get("description", ""))
    db.add(a)
    db.commit()
    db.refresh(a)
    return {"id": a.id, "name": a.name, "description": a.description, "questions": []}


@router.put("/course/{course_id}/assignments/{assignment_id}")
async def update_assignment(
    course_id: int,
    assignment_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Teacher only")
    course = db.query(Course).filter(Course.id == course_id, Course.teacher_id == current_user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    a = db.query(Assignment).filter(Assignment.id == assignment_id, Assignment.course_id == course_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    body = await request.json()
    if "name" in body:
        a.name = (body["name"] or "").strip() or a.name
    if "description" in body:
        a.description = body["description"]
    if "is_signoff" in body:
        a.is_signoff = bool(body["is_signoff"])
    if "signoff_group_category_id" in body:
        a.signoff_group_category_id = body["signoff_group_category_id"]  # int or None
    if "llm_config_id" in body:
        a.llm_config_id = body["llm_config_id"]  # int or None
    db.commit()
    return {"ok": True}


@router.delete("/course/{course_id}/assignments/{assignment_id}")
async def delete_assignment(
    course_id: int,
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Teacher only")
    course = db.query(Course).filter(Course.id == course_id, Course.teacher_id == current_user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    a = db.query(Assignment).filter(Assignment.id == assignment_id, Assignment.course_id == course_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.delete(a)
    db.commit()
    return {"ok": True}


@router.post("/course/{course_id}/assignments/{assignment_id}/questions")
async def create_question(
    course_id: int,
    assignment_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Teacher only")
    course = db.query(Course).filter(Course.id == course_id, Course.teacher_id == current_user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    a = db.query(Assignment).filter(Assignment.id == assignment_id, Assignment.course_id == course_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    body = await request.json()
    problem = (body.get("problem_description") or "").strip()
    if not problem:
        raise HTTPException(status_code=422, detail="Question text is required")
    # Auto-number
    max_num = db.query(func.max(Question.question_number)).filter(Question.assignment_id == assignment_id).scalar() or 0
    q = Question(
        assignment_id=assignment_id,
        question_number=max_num + 1,
        label=body.get("label") or None,
        problem_description=problem,
        official_solution=body.get("official_solution") or None,
        hinting_strategy=body.get("hinting_strategy") or None,
        require_signoff=bool(body.get("require_signoff", False)),
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return {
        "id": q.id,
        "question_number": q.question_number,
        "label": q.label,
        "problem_description": q.problem_description,
        "official_solution": q.official_solution,
        "hinting_strategy": q.hinting_strategy,
        "require_signoff": bool(q.require_signoff),
    }


@router.put("/course/{course_id}/assignments/{assignment_id}/questions/{question_id}")
async def update_question(
    course_id: int,
    assignment_id: int,
    question_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Teacher only")
    course = db.query(Course).filter(Course.id == course_id, Course.teacher_id == current_user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    q = db.query(Question).filter(Question.id == question_id, Question.assignment_id == assignment_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    body = await request.json()
    if "label" in body:
        q.label = body["label"] or None
    if "problem_description" in body:
        q.problem_description = (body["problem_description"] or "").strip() or q.problem_description
    if "official_solution" in body:
        q.official_solution = body["official_solution"] or None
    if "hinting_strategy" in body:
        q.hinting_strategy = body["hinting_strategy"] or None
    if "require_signoff" in body:
        q.require_signoff = bool(body["require_signoff"])
    db.commit()
    return {"ok": True}


@router.delete("/course/{course_id}/assignments/{assignment_id}/questions/{question_id}")
async def delete_question(
    course_id: int,
    assignment_id: int,
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Teacher only")
    course = db.query(Course).filter(Course.id == course_id, Course.teacher_id == current_user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    q = db.query(Question).filter(Question.id == question_id, Question.assignment_id == assignment_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(q)
    db.commit()
    return {"ok": True}


# ─── Student Dashboard ─────────────────────────────────────────────────────────

@router.get("/student/dashboard")
async def student_dashboard(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Student only")

    enrolled_ids = [cid for (cid,) in db.query(CourseEnrollment.course_id).filter(
        CourseEnrollment.user_id == current_user.id, CourseEnrollment.role == UserRole.STUDENT
    ).all()]
    courses = db.query(Course).filter(Course.id.in_(enrolled_ids)).all() if enrolled_ids else []

    # Open assignments with questions and top-level rooms
    open_assignments = []
    for course in courses:
        for assignment in db.query(Assignment).filter(Assignment.course_id == course.id, Assignment.queue_open == True).all():
            questions = db.query(Question).filter(Question.assignment_id == assignment.id).order_by(Question.question_number).all()
            rooms = db.query(QueueRoom).filter(
                QueueRoom.assignment_id == assignment.id,
                QueueRoom.parent_room_id == None,
                QueueRoom.is_open == True,
            ).order_by(QueueRoom.id.asc()).all()
            open_assignments.append({
                "id": assignment.id, "name": assignment.name, "course_id": course.id, "course_name": course.name,
                "questions": [{"id": q.id, "question_number": q.question_number, "description": q.problem_description[:80]} for q in questions],
                "rooms": [{"id": r.id, "name": r.name} for r in rooms],
            })

    # Check if the student is still in an open queue session.
    # A claimed request may remain active while a TA is finishing review, but once the
    # assignment queue has been closed we should not keep showing the dashboard banner.
    active_req = None
    active_assignment_id = None
    active_requests = db.query(HelpRequest).filter(
        HelpRequest.student_id == current_user.id,
        HelpRequest.status.in_([RequestStatus.PENDING, RequestStatus.AI_GENERATED])
    ).order_by(HelpRequest.created_at.desc(), HelpRequest.id.desc()).all()

    stale_requests_updated = False
    for candidate in active_requests:
        if _resolve_stale_unclaimed_request(db, candidate):
            stale_requests_updated = True
            continue
        question = db.query(Question).filter(Question.id == candidate.question_id).first()
        if not question:
            continue
        assignment = db.query(Assignment).filter(Assignment.id == question.assignment_id).first()
        if not assignment or not assignment.queue_open:
            continue
        active_req = candidate
        active_assignment_id = assignment.id
        break

    if stale_requests_updated:
        db.commit()

    in_queue = bool(active_req)

    # Help history
    recent = db.query(HelpRequest).filter(HelpRequest.student_id == current_user.id).order_by(HelpRequest.created_at.desc()).limit(10).all()
    history = []
    for req in recent:
        q = db.query(Question).filter(Question.id == req.question_id).first()
        a = db.query(Assignment).filter(Assignment.id == q.assignment_id).first() if q else None
        history.append({
            "id": req.id, "assignment_name": a.name if a else "--",
            "question_number": q.question_number if q else None, "status": req.status.value,
            "created_at": serialize_utc(req.created_at),
        })

    return {
        "open_assignments": open_assignments,
        "enrolled_courses": [{"id": c.id, "name": c.name} for c in courses],
        "in_queue": in_queue, "active_assignment_id": active_assignment_id,
        "recent_requests": history,
    }


QUEUE_UPLOAD_DIR = "uploads"
os.makedirs(QUEUE_UPLOAD_DIR, exist_ok=True)
QUEUE_ALLOWED_TYPES = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",  # images
    ".pdf",                                              # documents
    ".txt", ".md",                                       # plain text
}
QUEUE_MAX_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/student/help/submit")
async def student_submit_help(
        student_comment: str = Form(""),  # Changed from Form(...) to make it optional
        submission_text: str = Form(""),
        question_id: Optional[int] = Form(None),
        queue_room_id: Optional[int] = Form(None),
        assignment_id: Optional[int] = Form(None),
        attachment: Optional[UploadFile] = File(None),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403)
    from app.services.queue_service import get_next_queue_position

    student_comment = student_comment.strip()
    submission_text = submission_text.strip()

    # Check not already in another active queue. If we find stale unclaimed requests whose
    # assignment queue has already been closed, clean them up instead of blocking the student.
    existing_requests = db.query(HelpRequest).filter(
        HelpRequest.student_id == current_user.id,
        HelpRequest.status.in_([RequestStatus.PENDING, RequestStatus.AI_GENERATED])
    ).order_by(HelpRequest.created_at.desc(), HelpRequest.id.desc()).all()

    blocking_request = None
    stale_requests: list[HelpRequest] = []
    for existing in existing_requests:
        existing_question = db.query(Question).filter(Question.id == existing.question_id).first()
        existing_assignment = db.query(Assignment).filter(
            Assignment.id == existing_question.assignment_id
        ).first() if existing_question else None

        if not existing_assignment:
            stale_requests.append(existing)
            continue

        if existing.assigned_ta_id or existing_assignment.queue_open:
            blocking_request = existing
            break

        stale_requests.append(existing)

    if stale_requests:
        now = datetime.utcnow()
        for stale in stale_requests:
            stale.status = RequestStatus.RESOLVED
            stale.resolved_at = now
            stale.queue_position = None
            stale.ai_progress_status = None
            stale.ai_feedback = None
            stale.final_feedback = (
                    stale.final_feedback
                    or "The queue was closed before a TA could pick up your request."
            )
            stale.ai_queue_state = None
            stale.ai_queue_enqueued_at = None
            stale.ai_queue_started_at = None
            stale.ai_queue_error = None
            stale.last_progress_update = now
        db.commit()

    if blocking_request:
        raise HTTPException(status_code=400, detail="You are already in a queue.")

    selected_room = None
    selected_room_course = None

    # Auto-resolve question_id from the queue room's assignment when not supplied
    if not question_id and queue_room_id:
        selected_room, selected_room_course = require_room_access(
            db, queue_room_id, current_user.id, {UserRole.STUDENT}
        )
        assignment_id = None
        assignment_id = selected_room.assignment_id
        if not assignment_id and selected_room.parent_room_id:
            parent = db.query(QueueRoom).filter(
                QueueRoom.id == selected_room.parent_room_id).first()
            if parent:
                assignment_id = parent.assignment_id
        if assignment_id:
            first_q = db.query(Question).filter(
                Question.assignment_id == assignment_id
            ).order_by(Question.question_number).first()
            if first_q:
                question_id = first_q.id

    # Fallback: resolve from assignment_id directly (e.g. "Other" question selected)
    if not question_id and assignment_id:
        first_q = db.query(Question).filter(
            Question.assignment_id == assignment_id
        ).order_by(Question.question_number).first()
        if first_q:
            question_id = first_q.id

    if not question_id:
        raise HTTPException(status_code=422,
                            detail="No questions found for this queue. Ask your TA to set up the assignment.")

    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    assignment, _course = require_assignment_access(
        db, question.assignment_id, current_user.id, {UserRole.STUDENT}
    )

    if queue_room_id:
        if selected_room is None:
            selected_room, selected_room_course = require_room_access(
                db, queue_room_id, current_user.id, {UserRole.STUDENT}
            )

        queue_assignment_id = selected_room.assignment_id
        if not queue_assignment_id and selected_room.parent_room_id:
            parent = db.query(QueueRoom).filter(
                QueueRoom.id == selected_room.parent_room_id).first()
            if parent:
                queue_assignment_id = parent.assignment_id

        if queue_assignment_id and queue_assignment_id != assignment.id:
            raise HTTPException(status_code=400,
                                detail="Queue room does not belong to this assignment")
        if selected_room_course and selected_room_course.id != assignment.course_id:
            raise HTTPException(status_code=400, detail="Queue room does not belong to this course")

    is_signoff = bool(question.require_signoff) or bool(selected_room.is_signoff if selected_room else False)
    if not student_comment:
        if not is_signoff:
            raise HTTPException(status_code=422, detail="Question is required.")
        else:
            student_comment = "Ready for sign-off"

    # Handle optional file attachment
    attachment_path = None
    if attachment and attachment.filename:
        ext = os.path.splitext(attachment.filename)[1].lower()
        if ext not in QUEUE_ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"File type '{ext}' is not allowed. Upload images (jpg, png, gif, webp, bmp) or documents (pdf, txt, md)."
            )
        contents = b""
        while True:
            chunk = await attachment.read(64 * 1024)
            if not chunk:
                break
            contents += chunk
            if len(contents) > QUEUE_MAX_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size is {QUEUE_MAX_SIZE // (1024 * 1024)} MB."
                )
        filename = f"{uuid.uuid4()}{ext}"
        full_path = os.path.join(QUEUE_UPLOAD_DIR, filename)
        with open(full_path, "wb") as f:
            f.write(contents)
        attachment_path = filename

    # Resolve the active lab session for this assignment (issue 4)
    active_session_id = None
    active_lab = db.query(LabSession).filter(
        LabSession.assignment_id == assignment.id,
        LabSession.active == True,
    ).first() or db.query(LabSession).filter(
        LabSession.course_id == assignment.course_id,
        LabSession.active == True,
    ).first()
    if active_lab:
        active_session_id = active_lab.id

    # Assign queue position under a lock to prevent duplicate positions when
    # two students submit simultaneously (issue 22).
    with _queue_position_lock:
        now = datetime.utcnow()
        help_request = HelpRequest(
            student_id=current_user.id,
            question_id=question_id,
            submission_text=submission_text,
            submission_image=attachment_path,
            student_comment=student_comment,
            queue_room_id=queue_room_id,
            session_id=active_session_id,
            status=RequestStatus.PENDING,
            ai_progress_status="queued",
            ai_queue_state="queued",
            ai_queue_enqueued_at=now,
            ai_queue_started_at=None,
            ai_queue_error=None,
            queue_position=get_next_queue_position(db, assignment.id, queue_room_id),
            joined_queue_at=now,
            last_progress_update=now,
        )
        db.add(help_request)
        db.commit()
        db.refresh(help_request)

    from app.services.help_request_service import notify_tas_new_request
    notify_tas_new_request(db, assignment, help_request, current_user.name)

    return {"ok": True, "request_id": help_request.id,
            "queue_position": help_request.queue_position}
# ─── TA Request Review ─────────────────────────────────────────────────────────

@router.get("/ta/request/{request_id}")
async def ta_get_request(
    request_id: int,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if current_user.role not in (UserRole.TA, UserRole.TEACHER):
        raise HTTPException(status_code=403)
    help_request, question, assignment, _course = require_request_access(
        db, request_id, current_user.id, {UserRole.TA, UserRole.TEACHER}
    )
    student = db.query(User).filter(User.id == help_request.student_id).first()

    from app.models.db import FeedbackHistory
    history = db.query(FeedbackHistory).filter(
        FeedbackHistory.help_request_id == request_id
    ).order_by(FeedbackHistory.created_at.desc()).all()

    image_url = build_submission_image_url(help_request.submission_image)
    ta_ids = [h.ta_id for h in history if h.ta_id]
    ta_names = {}
    if ta_ids:
        ta_names = {
            user.id: user.name
            for user in db.query(User).filter(User.id.in_(ta_ids)).all()
        }

    # Determine if this request is for a sign-off room
    room_is_signoff = False
    if help_request.queue_room_id:
        room = db.query(QueueRoom).filter(QueueRoom.id == help_request.queue_room_id).first()
        if room:
            room_is_signoff = bool(room.is_signoff)
    assigned_ta = db.query(User).filter(User.id == help_request.assigned_ta_id).first() if help_request.assigned_ta_id else None
    can_review = (
        help_request.status not in (RequestStatus.PENDING, RequestStatus.AI_GENERATED)
        or help_request.assigned_ta_id in (None, current_user.id)
    )

    return {
        "id": help_request.id,
        "status": help_request.status.value,
        "student_name": student.name if student else "--",
        "student_id": student.id if student else None,
        "assigned_ta_id": help_request.assigned_ta_id,
        "assigned_ta_name": assigned_ta.name if assigned_ta else None,
        "can_review": can_review,
        "submission_text": help_request.submission_text,
        "submission_image_url": image_url,
        "extracted_text": help_request.extracted_text,
        "student_comment": help_request.student_comment,
        "ai_feedback": format_feedback_text(help_request.ai_feedback) or help_request.ai_feedback,
        "ai_progress_status": help_request.ai_progress_status,
        "final_feedback": format_feedback_text(help_request.final_feedback) or help_request.final_feedback,
        "created_at": serialize_utc(help_request.created_at),
        "room_is_signoff": room_is_signoff,
        "question": {
            "id": question.id,
            "number": question.question_number,
            "label": question.label,
            "problem_description": question.problem_description,
            "official_solution": question.official_solution,
            "hinting_strategy": question.hinting_strategy,
            "require_signoff": bool(question.require_signoff),
        },
        "assignment_name": assignment.name if assignment else "--",
        "assignment_id": assignment.id if assignment else None,
        "course_id": assignment.course_id if assignment else None,
        "feedback_history": [
            {
                "id": h.id,
                "action": h.action,
                "feedback_text": format_feedback_text(h.feedback_text) or h.feedback_text,
                "ta_id": h.ta_id,
                "ta_name": ta_names.get(h.ta_id, "--"),
                "created_at": serialize_utc(h.created_at),
            }
            for h in history
        ],
    }


@router.post("/ta/request/{request_id}/claim")
async def ta_claim_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in (UserRole.TA, UserRole.TEACHER):
        raise HTTPException(status_code=403)
    require_request_access(
        db, request_id, current_user.id, {UserRole.TA, UserRole.TEACHER}
    )
    from app.services.help_request_service import claim_request
    try:
        help_request = claim_request(db, request_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not help_request:
        raise HTTPException(status_code=404)

    # Build signoff redirect info if this is a sign-off request
    signoff_redirect = None
    question = db.query(Question).filter(Question.id == help_request.question_id).first()
    if question:
        assignment = db.query(Assignment).filter(Assignment.id == question.assignment_id).first()
        if assignment and assignment.is_signoff:
            course_id = assignment.course_id
            if assignment.signoff_group_category_id:
                # Group sign-off: find the student's group in this category
                member = db.query(GroupMember).filter(
                    GroupMember.student_id == help_request.student_id,
                    GroupMember.category_id == assignment.signoff_group_category_id,
                ).first()
                signoff_redirect = {
                    "course_id": course_id,
                    "assignment_id": assignment.id,
                    "type": "group",
                    "group_id": member.group_id if member else None,
                    "student_id": help_request.student_id,
                }
            else:
                signoff_redirect = {
                    "course_id": course_id,
                    "assignment_id": assignment.id,
                    "type": "student",
                    "student_id": help_request.student_id,
                }

    return {"ok": True, "signoff_redirect": signoff_redirect}


@router.post("/ta/request/{request_id}/approve")
async def ta_approve_request(
    request_id: int,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if current_user.role not in (UserRole.TA, UserRole.TEACHER):
        raise HTTPException(status_code=403)
    require_request_access(db, request_id, current_user.id, {UserRole.TA, UserRole.TEACHER})
    from app.services.help_request_service import approve_request
    try:
        help_request, question, assignment = approve_request(db, request_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not help_request:
        raise HTTPException(status_code=404)
    return {"ok": True, "status": help_request.status.value, "assignment_id": assignment.id if assignment else None}


@router.post("/ta/request/{request_id}/edit")
async def ta_edit_request(
    request_id: int, request: Request,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if current_user.role not in (UserRole.TA, UserRole.TEACHER):
        raise HTTPException(status_code=403)
    require_request_access(db, request_id, current_user.id, {UserRole.TA, UserRole.TEACHER})
    body = await request.json()
    feedback = body.get("feedback", "").strip()
    if not feedback:
        raise HTTPException(status_code=422, detail="feedback is required")
    from app.services.help_request_service import edit_request
    try:
        help_request, question, assignment = edit_request(db, request_id, current_user.id, feedback)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not help_request:
        raise HTTPException(status_code=404)
    return {"ok": True, "status": help_request.status.value, "assignment_id": assignment.id if assignment else None}


@router.post("/ta/request/{request_id}/reject")
async def ta_reject_request(
    request_id: int, request: Request,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if current_user.role not in (UserRole.TA, UserRole.TEACHER):
        raise HTTPException(status_code=403)
    require_request_access(db, request_id, current_user.id, {UserRole.TA, UserRole.TEACHER})
    body = await request.json()
    reason = body.get("reason", "In-person help required").strip()
    from app.services.help_request_service import reject_request
    try:
        help_request, question, assignment = reject_request(db, request_id, current_user.id, reason)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not help_request:
        raise HTTPException(status_code=404)
    return {"ok": True, "status": help_request.status.value, "assignment_id": assignment.id if assignment else None}


@router.post("/ta/request/{request_id}/retry-ai")
async def ta_retry_ai(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in (UserRole.TA, UserRole.TEACHER):
        raise HTTPException(status_code=403)
    require_request_access(db, request_id, current_user.id, {UserRole.TA, UserRole.TEACHER})
    from app.services.help_request_service import ensure_request_owned_by_reviewer
    try:
        help_request = ensure_request_owned_by_reviewer(db, request_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not help_request:
        raise HTTPException(status_code=404, detail="Request not found")
    if help_request.status not in (RequestStatus.PENDING, RequestStatus.AI_GENERATED):
        raise HTTPException(status_code=400, detail="Request is already resolved")

    # Reset to pending and re-queue AI generation.
    now = datetime.utcnow()
    help_request.status = RequestStatus.PENDING
    help_request.ai_feedback = None
    help_request.final_feedback = None
    help_request.ai_generated_at = None
    help_request.ai_progress_status = "queued"
    help_request.ai_queue_state = "queued"
    help_request.ai_queue_enqueued_at = now
    help_request.ai_queue_started_at = None
    help_request.ai_queue_error = None
    help_request.last_progress_update = now
    db.commit()

    return {"ok": True}


# ─── Course Overtime Questions ────────────────────────────────────────────────

@router.post("/ta/assignment/{assignment_id}/queue/close")
async def ta_close_queue(
        assignment_id: int, request: Request,
        current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if current_user.role not in (UserRole.TA, UserRole.TEACHER):
        raise HTTPException(status_code=403, detail="TA or teacher only")

    assignment, _course = require_assignment_access(
        db, assignment_id, current_user.id, {UserRole.TA, UserRole.TEACHER}
    )

    try:
        body = await request.json()
        action = body.get("action", "kick")
    except Exception:
        action = "kick"

    question_ids = [q[0] for q in
                    db.query(Question.id).filter(Question.assignment_id == assignment_id).all()]

    if question_ids:
        pending_requests = db.query(HelpRequest).filter(
            HelpRequest.question_id.in_(question_ids),
            HelpRequest.status.in_([RequestStatus.PENDING, RequestStatus.AI_GENERATED]),
            HelpRequest.assigned_ta_id == None
        ).all()

        for req in pending_requests:
            if action == "claim":
                req.assigned_ta_id = current_user.id
                req.started_helping_at = datetime.utcnow()
            elif action == "keep":
                # Flag as overtime: visible to all TAs/teacher on the course overview
                req.is_overtime = True
                req.queue_position = None
                req.queue_room_id = None
            elif action == "kick":
                # Mark as resolved so it drops out of the active queue
                req.status = RequestStatus.RESOLVED
                req.resolved_at = datetime.utcnow()
                req.queue_position = None
                req.final_feedback = None  # Explicitly ensure no feedback is sent

    from app.services.queue_service import close_queue
    close_queue(db, assignment.id, resolve_unassigned=False)

    return {"ok": True, "assignment_id": assignment.id, "queue_open": False}


@router.get("/course/{course_id}/overtime")
async def get_overtime_requests(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in (UserRole.TA, UserRole.TEACHER):
        raise HTTPException(status_code=403)

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # All overtime requests across all assignments in this course
    requests = (
        db.query(HelpRequest)
        .join(Question, HelpRequest.question_id == Question.id)
        .join(Assignment, Question.assignment_id == Assignment.id)
        .filter(
            Assignment.course_id == course_id,
            HelpRequest.is_overtime == True,
            HelpRequest.status.in_([RequestStatus.PENDING, RequestStatus.AI_GENERATED]),
        )
        .order_by(HelpRequest.created_at.asc())
        .all()
    )

    result = []
    for req in requests:
        question = db.query(Question).filter(Question.id == req.question_id).first()
        assignment = db.query(Assignment).filter(Assignment.id == question.assignment_id).first() if question else None
        student = db.query(User).filter(User.id == req.student_id).first()
        result.append({
            "id": req.id,
            "student_name": student.name if student else "Unknown",
            "assignment_name": assignment.name if assignment else "Unknown",
            "question_number": question.question_number if question else None,
            "student_comment": req.student_comment,
            "submission_text": req.submission_text,
            "status": req.status.value,
            "ai_feedback": format_feedback_text(req.ai_feedback) or req.ai_feedback,
            "ai_progress_status": req.ai_progress_status,
            "created_at": req.created_at.strftime("%Y-%m-%d %H:%M") if req.created_at else None,
        })

    return {"course_id": course_id, "course_name": course.name, "overtime_requests": result}


# ─── Student Request View ─────────────────────────────────────────────────────

@router.get("/student/request/{request_id}")
async def student_get_request(
    request_id: int,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403)

    help_request = db.query(HelpRequest).filter(
        HelpRequest.id == request_id,
        HelpRequest.student_id == current_user.id
    ).first()
    if not help_request:
        raise HTTPException(status_code=404, detail="Request not found")
    if _resolve_stale_unclaimed_request(db, help_request):
        db.commit()

    question = db.query(Question).filter(Question.id == help_request.question_id).first()
    assignment = db.query(Assignment).filter(Assignment.id == question.assignment_id).first() if question else None
    assigned_ta = db.query(User).filter(User.id == help_request.assigned_ta_id).first() if help_request.assigned_ta_id else None
    image_url = build_submission_image_url(help_request.submission_image)

    return {
        "id": help_request.id,
        "status": help_request.status.value,
        "submission_text": help_request.submission_text,
        "submission_image_url": image_url,
        "student_comment": help_request.student_comment,
        "ai_progress_status": help_request.ai_progress_status,
        "final_feedback": format_feedback_text(help_request.final_feedback) or help_request.final_feedback,
        "created_at": serialize_utc(help_request.created_at),
        "question_number": question.question_number if question else None,
        "problem_description": question.problem_description if question else None,
        "assignment_name": assignment.name if assignment else "--",
        "assignment_id": assignment.id if assignment else None,
        "ta_name": assigned_ta.name if assigned_ta else None,
    }


@router.get("/student/request/{request_id}/status")
async def student_request_status(
    request_id: int,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403)
    help_request = db.query(HelpRequest).filter(
        HelpRequest.id == request_id, HelpRequest.student_id == current_user.id
    ).first()
    if not help_request:
        raise HTTPException(status_code=404)
    if _resolve_stale_unclaimed_request(db, help_request):
        db.commit()
    return {
        "status": help_request.status.value,
        "final_feedback": format_feedback_text(help_request.final_feedback) or help_request.final_feedback,
        "ai_progress_status": help_request.ai_progress_status,
    }


@router.get("/student/course/{course_id}/progress")
async def student_course_progress(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the student's progress: sign-off points per lab + help requests."""
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403)

    enrolled = db.query(CourseEnrollment).filter(
        CourseEnrollment.user_id == current_user.id,
        CourseEnrollment.course_id == course_id,
    ).first()
    if not enrolled:
        raise HTTPException(status_code=403, detail="Not enrolled in this course")

    assignments = db.query(Assignment).filter(Assignment.course_id == course_id).order_by(Assignment.created_at).all()

    rows = []
    for assignment in assignments:
        questions = db.query(Question).filter(Question.assignment_id == assignment.id).order_by(Question.question_number).all()

        # ── Sign-off points (per question that has require_signoff) ──────────
        signoff_points = []
        for q in questions:
            if not q.require_signoff:
                continue
            record = db.query(SignoffRecord).filter(
                SignoffRecord.question_id == q.id,
                SignoffRecord.student_id == current_user.id,
            ).order_by(SignoffRecord.created_at.desc()).first()
            signoff_points.append({
                "question_id": q.id,
                "label": q.label or f"Q{q.question_number}",
                "status": record.status if record else None,
                "graded_at": serialize_utc(record.created_at) if record else None,
            })

        # ── Help requests ────────────────────────────────────────────────────
        question_ids = [q.id for q in questions]
        resolved_statuses = [RequestStatus.APPROVED, RequestStatus.EDITED, RequestStatus.IN_PERSON]
        requests = []
        if question_ids:
            reqs = db.query(HelpRequest).filter(
                HelpRequest.student_id == current_user.id,
                HelpRequest.question_id.in_(question_ids),
                HelpRequest.status.in_(resolved_statuses),
            ).order_by(HelpRequest.resolved_at.desc()).all()
            requests = [
                {
                    "id": r.id,
                    "status": r.status.value,
                    "resolved_at": serialize_utc(r.resolved_at),
                    "ta_name": db.query(User).filter(User.id == r.assigned_ta_id).first().name
                        if r.assigned_ta_id else None,
                }
                for r in reqs
            ]

        if not signoff_points and not requests:
            continue

        rows.append({
            "assignment_id": assignment.id,
            "assignment_name": assignment.name,
            "is_signoff": bool(assignment.is_signoff),
            "signoff_points": signoff_points,
            "requests": requests,
        })

    return {"course_id": course_id, "assignments": rows}


# ─── Queue Actions ────────────────────────────────────────────────────────────

@router.post("/queue/leave")
async def api_leave_queue(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    req = db.query(HelpRequest).filter(
        HelpRequest.student_id == current_user.id,
        HelpRequest.status.in_([RequestStatus.PENDING, RequestStatus.AI_GENERATED])
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Not in queue")

    question = db.query(Question).filter(Question.id == req.question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # Capture position before nulling it — used in the shift query below
    leaving_position = req.queue_position

    req.status = RequestStatus.RESOLVED
    req.resolved_at = datetime.utcnow()
    req.queue_position = None
    req.ai_queue_state = None
    req.ai_queue_enqueued_at = None
    req.ai_queue_started_at = None
    req.ai_queue_error = None

    from app.services.queue_service import collapse_queue_positions
    collapse_queue_positions(db, question.assignment_id, leaving_position, req.queue_room_id)
    db.commit()

    return {"ok": True}


@router.post("/queue/call-next/{assignment_id}")
async def api_call_next(
    assignment_id: int,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    require_assignment_access(db, assignment_id, current_user.id, {UserRole.TA, UserRole.TEACHER})

    question_ids = [q[0] for q in db.query(Question.id).filter(Question.assignment_id == assignment_id).all()]
    if not question_ids:
        raise HTTPException(status_code=404, detail="No questions for this assignment")

    next_req = db.query(HelpRequest).filter(
        HelpRequest.question_id.in_(question_ids),
        HelpRequest.status.in_([RequestStatus.PENDING, RequestStatus.AI_GENERATED]),
        HelpRequest.assigned_ta_id == None,
    ).order_by(
        HelpRequest.joined_queue_at.asc(),
        HelpRequest.id.asc(),
    ).first()

    if not next_req:
        raise HTTPException(status_code=404, detail="Queue is empty")

    next_req.assigned_ta_id = current_user.id
    next_req.started_helping_at = datetime.utcnow()
    db.commit()

    student = db.query(User).filter(User.id == next_req.student_id).first()
    return {"ok": True, "request_id": next_req.id, "student_name": student.name if student else "--"}


# ─── Room Queue (authenticated TA/teacher view) ───────────────────────────────

def _effective_room_assignment_id(db: Session, room: QueueRoom | None) -> int | None:
    if room is None:
        return None
    if room.assignment_id:
        return room.assignment_id
    if room.parent_room_id:
        parent = db.query(QueueRoom).filter(QueueRoom.id == room.parent_room_id).first()
        if parent:
            return parent.assignment_id
    return None


def _serialize_assignment_questions(
    db: Session,
    assignment_id: int | None,
    *,
    signoff_only: bool = False,
) -> list[dict]:
    if not assignment_id:
        return []

    query = db.query(Question).filter(Question.assignment_id == assignment_id)
    if signoff_only:
        query = query.filter(Question.require_signoff == True)

    return [
        {
            "id": q.id,
            "question_number": q.question_number,
            "label": q.label,
            "description": q.problem_description[:200],
            "require_signoff": bool(q.require_signoff),
        }
        for q in query.order_by(Question.question_number).all()
    ]


def _serialize_course_assignments(course_id: int | None, db: Session) -> list[dict]:
    if not course_id:
        return []

    assignments = (
        db.query(Assignment)
        .filter(Assignment.course_id == course_id)
        .order_by(Assignment.created_at.asc(), Assignment.id.asc())
        .all()
    )
    return [{"id": assignment.id, "name": assignment.name} for assignment in assignments]


@router.get("/room/{room_id}/queue")
async def get_room_queue(
        room_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    room, course = require_room_access(db, room_id, current_user.id)

    effective_assignment_id = _get_effective_assignment_id(db, room)
    assignment = db.query(Assignment).filter(Assignment.id == effective_assignment_id).first() if effective_assignment_id else None

    def ser(item):
        q = db.query(Question).filter(Question.id == item.question_id).first()
        s = db.query(User).filter(User.id == item.student_id).first()
        wait = int((
                               datetime.utcnow() - item.joined_queue_at).total_seconds() / 60) if item.joined_queue_at else 0
        return {
            "id": item.id,
            "student_id": item.student_id,
            "student_name": s.name if s else "--",
            "question_number": q.question_number if q else None,
            "status": item.status.value,
            "queue_position": item.queue_position,
            "wait_time_minutes": wait,
            "student_comment": item.student_comment,
            "has_ai_feedback": bool(item.ai_feedback),
        }

    # Get named queues (children) within this room
    child_queues = db.query(QueueRoom).filter(
        QueueRoom.parent_room_id == room_id,
        QueueRoom.is_open == True
    ).order_by(QueueRoom.id).all()

    queues_data = []
    total_waiting = 0
    total_being_helped = 0

    # Students stored directly in the parent room (queue_room_id == room_id).
    # This is the normal state for seeded / freshly-opened sign-off queues that
    # don't have any named child queues yet, or when students joined before
    # child queues were created.
    parent_waiting = db.query(HelpRequest).filter(
        HelpRequest.queue_room_id == room_id,
        HelpRequest.status.in_([RequestStatus.PENDING, RequestStatus.AI_GENERATED]),
        HelpRequest.assigned_ta_id == None,
    ).order_by(HelpRequest.queue_position.asc()).all()

    parent_helped = db.query(HelpRequest).filter(
        HelpRequest.queue_room_id == room_id,
        HelpRequest.status.in_([RequestStatus.PENDING, RequestStatus.AI_GENERATED]),
        HelpRequest.assigned_ta_id != None,
    ).all()

    if parent_waiting or parent_helped:
        total_waiting += len(parent_waiting)
        total_being_helped += len(parent_helped)
        queues_data.append({
            "id": room.id,
            "name": room.name,
            "assignment_id": effective_assignment_id,
            "assignment_name": assignment.name if assignment else None,
            "is_signoff": bool(room.is_signoff),
            "can_delete": False,
            "questions": _serialize_assignment_questions(
                db, effective_assignment_id,
                signoff_only=bool(room.is_signoff),
            ),
            "waiting": [ser(i) for i in parent_waiting],
            "being_helped": [ser(i) for i in parent_helped],
        })

    for cq in child_queues:
        queue_assignment_id = _effective_room_assignment_id(db, cq)
        queue_assignment = (
            db.query(Assignment).filter(Assignment.id == queue_assignment_id).first()
            if queue_assignment_id else None
        )
        waiting_items = db.query(HelpRequest).filter(
            HelpRequest.queue_room_id == cq.id,
            HelpRequest.status.in_([RequestStatus.PENDING, RequestStatus.AI_GENERATED]),
            HelpRequest.assigned_ta_id == None,
        ).order_by(HelpRequest.queue_position.asc()).all()

        helped_items = db.query(HelpRequest).filter(
            HelpRequest.queue_room_id == cq.id,
            HelpRequest.status.in_([RequestStatus.PENDING, RequestStatus.AI_GENERATED]),
            HelpRequest.assigned_ta_id != None,
        ).all()

        total_waiting += len(waiting_items)
        total_being_helped += len(helped_items)

        queues_data.append({
            "id": cq.id,
            "name": cq.name,
            "assignment_id": queue_assignment_id,
            "assignment_name": queue_assignment.name if queue_assignment else None,
            "is_signoff": bool(cq.is_signoff),
            "can_delete": True,
            "questions": _serialize_assignment_questions(
                db,
                queue_assignment_id,
                signoff_only=bool(cq.is_signoff),
            ),
            "waiting": [ser(i) for i in waiting_items],
            "being_helped": [ser(i) for i in helped_items],
        })

    return {
        "room": {
            "id": room.id,
            "name": room.name,
            "location": room.location,
            "is_open": room.is_open,
            "assignment_id": effective_assignment_id,
            "assignment_name": assignment.name if assignment else None,
            "course_id": course.id if course else None,
            "course_name": course.name if course else None,
        },
        "assignments": _serialize_course_assignments(course.id if course else None, db),
        "queues": queues_data,
        "questions": _serialize_assignment_questions(db, effective_assignment_id),
        "total_waiting": total_waiting,
        "total_being_helped": total_being_helped,
    }


# ─── Queue Management (create/delete named queues within a room) ──────────────

@router.post("/room/{room_id}/queues")
async def create_room_queue(
        room_id: int,
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if current_user.role not in (UserRole.TA, UserRole.TEACHER):
        raise HTTPException(status_code=403, detail="TA or teacher only")
    room, room_course = require_room_access(
        db, room_id, current_user.id, {UserRole.TA, UserRole.TEACHER}
    )
    if room.parent_room_id is not None:
        raise HTTPException(status_code=404, detail="Room not found")

    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")

    assignment_id = body.get("assignment_id")
    if assignment_id is None:
        assignment_id = _get_effective_assignment_id(db, room)
    if not assignment_id:
        raise HTTPException(
            status_code=422,
            detail="Cannot create a queue without an assignment. The room has no linked assignment.",
        )
    assignment, _assignment_course = require_assignment_access(
        db, assignment_id, current_user.id, {UserRole.TA, UserRole.TEACHER}
    )
    if assignment.course_id != room_course.id:
        raise HTTPException(status_code=400,
                            detail="Assignment does not belong to this room's course")
    assignment.queue_open = True
    if not assignment.queue_opened_at:
        assignment.queue_opened_at = datetime.utcnow()
    if not assignment.queue_opened_by:
        assignment.queue_opened_by = current_user.id

    is_signoff = bool(body.get("is_signoff", False))

    # Look for ANY queue with this name (open or closed)
    existing_queue = db.query(QueueRoom).filter(
        QueueRoom.parent_room_id == room_id,
        QueueRoom.name == name,
    ).first()

    if existing_queue:
        if existing_queue.is_open:
            raise HTTPException(status_code=409,
                                detail=f'A queue named "{name}" already exists and is active.')
        else:
            # Recycle the existing closed queue!
            existing_queue.is_open = True
            existing_queue.opened_at = datetime.utcnow()
            existing_queue.closed_at = None
            existing_queue.opened_by = current_user.id
            existing_queue.assignment_id = assignment_id
            existing_queue.is_signoff = is_signoff
            db.commit()

            return {
                "id": existing_queue.id,
                "name": existing_queue.name,
                "assignment_id": existing_queue.assignment_id,
                "is_signoff": existing_queue.is_signoff
            }

    # If it genuinely doesn't exist, create a new one
    queue = QueueRoom(
        parent_room_id=room_id,
        name=name,
        assignment_id=assignment_id,
        course_id=room_course.id,
        is_open=True,
        is_signoff=is_signoff,
        opened_at=datetime.utcnow(),
        opened_by=current_user.id,
    )
    db.add(queue)
    db.commit()
    db.refresh(queue)

    return {
        "id": queue.id,
        "name": queue.name,
        "assignment_id": queue.assignment_id,
        "is_signoff": queue.is_signoff
    }
@router.delete("/queue/{queue_id}")
async def delete_room_queue(
    queue_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in (UserRole.TA, UserRole.TEACHER):
        raise HTTPException(status_code=403, detail="TA or teacher only")
    queue, _course = require_room_access(
        db, queue_id, current_user.id, {UserRole.TA, UserRole.TEACHER}
    )
    if queue.parent_room_id is None:
        raise HTTPException(status_code=404, detail="Queue not found")

    # Soft-close: keep record for statistics, just mark as closed
    queue.is_open = False
    queue.closed_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post("/queue/{queue_id}/close")
async def close_single_queue(
    queue_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Close a single child queue with keep/kick handling for its pending requests."""
    if current_user.role not in (UserRole.TA, UserRole.TEACHER):
        raise HTTPException(status_code=403, detail="TA or teacher only")
    queue, _course = require_room_access(
        db, queue_id, current_user.id, {UserRole.TA, UserRole.TEACHER}
    )
    if queue.parent_room_id is None:
        raise HTTPException(status_code=400, detail="Use the assignment close endpoint for top-level rooms")

    try:
        body = await request.json()
        action = body.get("action", "kick")
    except Exception:
        action = "kick"

    # Handle pending requests in this specific queue only
    pending_requests = db.query(HelpRequest).filter(
        HelpRequest.queue_room_id == queue_id,
        HelpRequest.status.in_([RequestStatus.PENDING, RequestStatus.AI_GENERATED]),
        HelpRequest.assigned_ta_id == None,
    ).all()

    for req in pending_requests:
        if action == "keep":
            req.is_overtime = True
            req.queue_position = None
            req.queue_room_id = None
        else:  # kick
            req.status = RequestStatus.RESOLVED
            req.resolved_at = datetime.utcnow()
            req.queue_position = None
            req.final_feedback = None

    # Close only this queue
    queue.is_open = False
    queue.closed_at = datetime.utcnow()
    db.flush()
    if queue.assignment_id:
        remaining = db.query(QueueRoom).filter(
            QueueRoom.assignment_id == queue.assignment_id,
            QueueRoom.is_open == True
        ).count()
        if remaining == 0:
            assignment = db.query(Assignment).filter(Assignment.id == queue.assignment_id).first()
            if assignment:
                assignment.queue_open = False
                assignment.queue_closed_at = datetime.utcnow()
    db.commit()
    return {"ok": True}

# ─── Room History ──────────────────────────────────────────────────────────────

@router.post("/room/{room_id}/close")
async def close_room(
    room_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    room, _course = require_room_access(
        db, room_id, current_user.id, {UserRole.TA, UserRole.TEACHER}
    )

    try:
        body = await request.json()
        action = body.get("action", "keep")
    except Exception:
        action = "keep"

    child_queues = db.query(QueueRoom).filter(QueueRoom.parent_room_id == room_id).all()
    scoped_room_ids = [room.id, *[child.id for child in child_queues]]

    pending_requests = db.query(HelpRequest).filter(
        HelpRequest.queue_room_id.in_(scoped_room_ids),
        HelpRequest.status.in_([RequestStatus.PENDING, RequestStatus.AI_GENERATED]),
        HelpRequest.assigned_ta_id == None,
    ).all()

    for req in pending_requests:
        if action == "keep":
            req.is_overtime = True
            req.queue_position = None
            req.queue_room_id = None
        else:
            req.status = RequestStatus.RESOLVED
            req.resolved_at = datetime.utcnow()
            req.queue_position = None
            req.final_feedback = None

    room.is_open = False
    room.closed_at = datetime.utcnow()

    # Also close all child queues
    for child in child_queues:
        child.is_open = False
        child.closed_at = datetime.utcnow()
    db.flush()
    # Close any active sessions tied to this room's assignment so session
    # duration is recorded and analytics are reliable.
    assignment_ids_to_check = set()
    if room.assignment_id:
        assignment_ids_to_check.add(room.assignment_id)
    for child in child_queues:
        if child.assignment_id:
            assignment_ids_to_check.add(child.assignment_id)

    # Check each assignment involved to see if it should be closed
    for a_id in assignment_ids_to_check:
        remaining_open_queues = db.query(QueueRoom).filter(
            QueueRoom.assignment_id == a_id,
            QueueRoom.is_open == True,
        ).count()

        if remaining_open_queues == 0:
            assignment = db.query(Assignment).filter(Assignment.id == a_id).first()
            if assignment:
                assignment.queue_open = False
                assignment.queue_closed_at = datetime.utcnow()

            # Close active sessions for this assignment too
            active_sessions = db.query(LabSession).filter(
                LabSession.assignment_id == a_id,
                LabSession.active == True,
            ).all()
            now = datetime.utcnow()
            for s in active_sessions:
                s.active = False
                s.ended_at = now

    db.commit()
    return {"ok": True}






@router.get("/room/{room_id}/history")
async def get_room_history(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    room, _course = require_room_access(db, room_id, current_user.id)

    # Collect IDs: the room itself + all child queues
    child_ids = [q.id for q in db.query(QueueRoom).filter(QueueRoom.parent_room_id == room_id).all()]
    room_ids = [room_id] + child_ids

    resolved_statuses = [
        RequestStatus.APPROVED, RequestStatus.EDITED,
        RequestStatus.IN_PERSON, RequestStatus.RESOLVED,
    ]

    requests = (
        db.query(HelpRequest)
        .filter(
            HelpRequest.queue_room_id.in_(room_ids),
            HelpRequest.status.in_(resolved_statuses),
        )
        .order_by(HelpRequest.resolved_at.desc())
        .limit(100)
        .all()
    )

    # Build a queue_id → queue_name map for all child queues
    queue_name_map = {q.id: q.name for q in db.query(QueueRoom).filter(QueueRoom.id.in_(room_ids)).all()}

    history = []
    for req in requests:
        student = db.query(User).filter(User.id == req.student_id).first()
        ta = db.query(User).filter(User.id == req.assigned_ta_id).first() if req.assigned_ta_id else None
        question = db.query(Question).filter(Question.id == req.question_id).first()
        queue_name = queue_name_map.get(req.queue_room_id, "—")
        history.append({
            "id": req.id,
            "student_name": student.name if student else "Unknown",
            "ta_name": ta.name if ta else "—",
            "queue_name": queue_name,
            "question_number": question.question_number if question else None,
            "status": req.status.value,
            "resolved_at": serialize_utc(req.resolved_at),
            "wait_minutes": (
                int((req.resolved_at - req.joined_queue_at).total_seconds() / 60)
                if req.resolved_at and req.joined_queue_at else None
            ),
        })

    return {"room_name": room.name, "history": history}


# ─── Course Rooms ─────────────────────────────────────────────────────────────

@router.get("/course/{course_id}/rooms")
async def get_course_rooms(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    course = require_course_access(db, course_id, current_user.id)

    # Top-level rooms for this course — match via course_id column OR via assignment's course_id
    rooms = db.query(QueueRoom).filter(
        QueueRoom.parent_room_id == None,
        QueueRoom.is_open == True,
    ).filter(
        (QueueRoom.course_id == course_id) |
        (QueueRoom.assignment_id.in_(
            db.query(Assignment.id).filter(Assignment.course_id == course_id)
        ))
    ).all()

    rooms_data = []
    for room in rooms:
        assignment = db.query(Assignment).filter(Assignment.id == room.assignment_id).first() if room.assignment_id else None

        child_queue_ids = [
            q.id for q in db.query(QueueRoom).filter(
                QueueRoom.parent_room_id == room.id,
                QueueRoom.is_open == True,
            ).all()
        ]
        # Count students in child queues AND students stored directly in the parent room.
        tracked_ids = [room.id, *child_queue_ids]
        waiting = db.query(HelpRequest).filter(
            HelpRequest.queue_room_id.in_(tracked_ids),
            HelpRequest.status.in_([RequestStatus.PENDING, RequestStatus.AI_GENERATED]),
            HelpRequest.started_helping_at == None,
        ).count()
        being_helped = db.query(HelpRequest).filter(
            HelpRequest.queue_room_id.in_(tracked_ids),
            HelpRequest.started_helping_at != None,
            HelpRequest.status.in_([RequestStatus.PENDING, RequestStatus.AI_GENERATED]),
        ).count()

        opener = db.query(User).filter(User.id == room.opened_by).first() if room.opened_by else None
        rooms_data.append({
            "id": room.id,
            "name": room.name,
            "location": room.location,
            "is_open": room.is_open,
            "assignment_id": room.assignment_id,
            "assignment_name": assignment.name if assignment else None,
            "waiting": waiting,
            "being_helped": being_helped,
            "opened_at": serialize_utc(room.opened_at),
            "ta_name": opener.name if opener else None,
        })

    assignments = db.query(Assignment).filter(Assignment.course_id == course_id).all()

    return {
        "course_id": course.id,
        "course_name": course.name,
        "rooms": rooms_data,
        "assignments": [{"id": a.id, "name": a.name} for a in assignments],
    }


@router.post("/course/{course_id}/rooms")
async def create_course_room(
    course_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    course = require_course_access(
        db, course_id, current_user.id, {UserRole.TA, UserRole.TEACHER}
    )

    body = await request.json()
    name = (body.get("name") or "").strip()
    location = (body.get("location") or "").strip() or None
    assignment_id = body.get("assignment_id") or None

    if not name:
        raise HTTPException(status_code=422, detail="Room name is required")

    if not assignment_id:
        raise HTTPException(status_code=422, detail="Assignment is required when creating a room")

    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id, Assignment.course_id == course_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    _validate_top_level_room_names(
        db,
        course_id=course_id,
        assignment_id=assignment_id,
        room_names=[name],
    )

    room = QueueRoom(
        name=name,
        location=location,
        course_id=course_id,
        assignment_id=assignment_id,
        is_open=True,
        opened_at=datetime.utcnow(),
        opened_by=current_user.id,
    )
    db.add(room)
    if not assignment.queue_open:
        assignment.queue_open = True
        assignment.queue_opened_at = datetime.utcnow()
        assignment.queue_opened_by = current_user.id
    db.commit()
    db.refresh(room)
    return {"ok": True, "id": room.id}


# ─── Sign-off ──────────────────────────────────────────────────────────────────

def _require_course_access(course_id: int, current_user: User, db: Session, teacher_only: bool = False):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    is_teacher = course.teacher_id == current_user.id
    if teacher_only and not is_teacher:
        raise HTTPException(status_code=403, detail="Teacher only")
    if not is_teacher:
        enrolled = db.query(CourseEnrollment).filter(
            CourseEnrollment.user_id == current_user.id,
            CourseEnrollment.course_id == course_id,
        ).first()
        ta_assigned = db.query(TAAssignment).filter(
            TAAssignment.ta_id == current_user.id,
            TAAssignment.course_id == course_id,
        ).first()
        if not enrolled and not ta_assigned:
            raise HTTPException(status_code=403, detail="Not enrolled in this course")
    return course, is_teacher


# ─── Question-based sign-off endpoints ────────────────────────────────────────

@router.get("/course/{course_id}/signoff/assignments")
async def get_signoff_assignments(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return assignments marked as sign-off labs, with their required questions."""
    _require_course_access(course_id, current_user, db)
    assignments = db.query(Assignment).filter(
        Assignment.course_id == course_id,
        Assignment.is_signoff == True,
    ).order_by(Assignment.created_at).all()
    result = []
    for a in assignments:
        questions = db.query(Question).filter(
            Question.assignment_id == a.id,
            Question.require_signoff == True,
        ).order_by(Question.question_number).all()
        result.append({
            "id": a.id,
            "name": a.name,
            "questions": [{"id": q.id, "label": q.label or str(q.question_number)} for q in questions],
        })
    return result


@router.get("/course/{course_id}/signoff/q/students")
async def get_signoff_students_by_question(
    course_id: int,
    assignment_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all enrolled students with their sign-off status per question for an assignment."""
    _require_course_access(course_id, current_user, db)
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id, Assignment.course_id == course_id, Assignment.is_signoff == True
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    questions = db.query(Question).filter(
        Question.assignment_id == assignment_id,
        Question.require_signoff == True,
    ).order_by(Question.question_number).all()

    students = db.query(User).join(
        CourseEnrollment,
        (CourseEnrollment.user_id == User.id) &
        (CourseEnrollment.course_id == course_id) &
        (CourseEnrollment.role == UserRole.STUDENT)
    ).order_by(User.name).all()

    result = []
    for student in students:
        cells = {}
        for q in questions:
            record = db.query(SignoffRecord).filter(
                SignoffRecord.question_id == q.id,
                SignoffRecord.student_id == student.id,
            ).order_by(SignoffRecord.created_at.desc()).first()
            cells[q.id] = {
                "status": record.status if record else None,
                "comment": record.comment if record else None,
            }
        result.append({"id": student.id, "name": student.name, "email": student.email, "cells": cells})

    return {
        "assignment": {"id": assignment.id, "name": assignment.name},
        "questions": [{"id": q.id, "label": q.label or str(q.question_number)} for q in questions],
        "students": result,
    }


@router.get("/course/{course_id}/signoff/q/student/{student_id}")
async def get_student_signoff_by_question(
    course_id: int,
    student_id: int,
    assignment_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_course_access(course_id, current_user, db)
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id, Assignment.course_id == course_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=404)
    student = db.query(User).filter(User.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404)
    questions = db.query(Question).filter(
        Question.assignment_id == assignment_id,
        Question.require_signoff == True,
    ).order_by(Question.question_number).all()

    points_data = []
    for q in questions:
        records = db.query(SignoffRecord).filter(
            SignoffRecord.question_id == q.id,
            SignoffRecord.student_id == student_id,
        ).order_by(SignoffRecord.created_at.desc()).all()
        points_data.append({
            "id": q.id,
            "label": q.label or str(q.question_number),
            "latest_status": records[0].status if records else None,
            "history": [
                {
                    "id": r.id,
                    "status": r.status,
                    "comment": r.comment,
                    "graded_by": db.query(User).filter(User.id == r.graded_by).first().name,
                    "created_at": r.created_at.strftime("%b %d, %H:%M"),
                }
                for r in records
            ],
        })

    return {
        "student": {"id": student.id, "name": student.name, "email": student.email},
        "assignment": {"id": assignment.id, "name": assignment.name},
        "questions": [{"id": q.id, "label": q.label or str(q.question_number)} for q in questions],
        "points": points_data,
    }


@router.post("/signoff/questions/{question_id}/grade")
async def grade_signoff_question(
    question_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in (UserRole.TA, UserRole.TEACHER):
        raise HTTPException(status_code=403, detail="TA or teacher only")
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404)
    body = await request.json()
    student_id = body.get("student_id")
    status = body.get("status")
    comment = (body.get("comment") or "").strip() or None
    if not student_id or status not in ("signed_off", "insufficient"):
        raise HTTPException(status_code=422, detail="student_id and valid status required")
    record = SignoffRecord(
        question_id=question_id,
        student_id=student_id,
        graded_by=current_user.id,
        status=status,
        comment=comment,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "id": record.id,
        "status": record.status,
        "comment": record.comment,
        "graded_at": record.created_at.strftime("%b %d, %H:%M"),
    }


def _serialize_flow(flow: SignoffFlow) -> dict:
    return {
        "id": flow.id,
        "name": flow.name,
        "order": flow.order,
        "points": [{"id": p.id, "label": p.label, "order": p.order} for p in flow.points],
    }


@router.get("/course/{course_id}/signoff/flows")
async def get_signoff_flows(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_course_access(course_id, current_user, db)
    flows = db.query(SignoffFlow).filter(SignoffFlow.course_id == course_id).order_by(SignoffFlow.order).all()
    return [_serialize_flow(f) for f in flows]


@router.post("/course/{course_id}/signoff/flows")
async def create_signoff_flow(
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


@router.put("/signoff/flows/{flow_id}")
async def update_signoff_flow(
    flow_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    flow = db.query(SignoffFlow).filter(SignoffFlow.id == flow_id).first()
    if not flow:
        raise HTTPException(status_code=404)
    _require_course_access(flow.course_id, current_user, db, teacher_only=True)
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name is required")
    flow.name = name
    db.commit()
    return _serialize_flow(flow)


@router.delete("/signoff/flows/{flow_id}")
async def delete_signoff_flow(
    flow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    flow = db.query(SignoffFlow).filter(SignoffFlow.id == flow_id).first()
    if not flow:
        raise HTTPException(status_code=404)
    _require_course_access(flow.course_id, current_user, db, teacher_only=True)
    db.delete(flow)
    db.commit()
    return {"ok": True}


@router.post("/signoff/flows/{flow_id}/points")
async def create_signoff_point(
    flow_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    flow = db.query(SignoffFlow).filter(SignoffFlow.id == flow_id).first()
    if not flow:
        raise HTTPException(status_code=404)
    _require_course_access(flow.course_id, current_user, db, teacher_only=True)
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


@router.put("/signoff/points/{point_id}")
async def update_signoff_point(
    point_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    point = db.query(SignoffPoint).filter(SignoffPoint.id == point_id).first()
    if not point:
        raise HTTPException(status_code=404)
    flow = db.query(SignoffFlow).filter(SignoffFlow.id == point.flow_id).first()
    _require_course_access(flow.course_id, current_user, db, teacher_only=True)
    body = await request.json()
    label = (body.get("label") or "").strip()
    if not label:
        raise HTTPException(status_code=422, detail="Label is required")
    point.label = label
    db.commit()
    return {"id": point.id, "label": point.label, "order": point.order}


@router.delete("/signoff/points/{point_id}")
async def delete_signoff_point(
    point_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    point = db.query(SignoffPoint).filter(SignoffPoint.id == point_id).first()
    if not point:
        raise HTTPException(status_code=404)
    flow = db.query(SignoffFlow).filter(SignoffFlow.id == point.flow_id).first()
    _require_course_access(flow.course_id, current_user, db, teacher_only=True)
    db.delete(point)
    db.commit()
    return {"ok": True}


@router.get("/course/{course_id}/signoff/students")
async def get_signoff_students(
    course_id: int,
    flow_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_course_access(course_id, current_user, db)
    flow = db.query(SignoffFlow).filter(SignoffFlow.id == flow_id, SignoffFlow.course_id == course_id).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    students = db.query(User).join(
        CourseEnrollment,
        (CourseEnrollment.user_id == User.id) &
        (CourseEnrollment.course_id == course_id) &
        (CourseEnrollment.role == UserRole.STUDENT)
    ).order_by(User.name).all()

    result = []
    for student in students:
        cells = {}
        for point in flow.points:
            record = db.query(SignoffRecord).filter(
                SignoffRecord.point_id == point.id,
                SignoffRecord.student_id == student.id,
            ).order_by(SignoffRecord.created_at.desc()).first()
            cells[point.id] = {
                "status": record.status if record else None,
                "comment": record.comment if record else None,
                "graded_at": record.created_at.strftime("%b %d, %H:%M") if record else None,
            }
        result.append({
            "id": student.id,
            "name": student.name,
            "email": student.email,
            "cells": cells,
        })

    return {"flow": _serialize_flow(flow), "students": result}


@router.get("/course/{course_id}/signoff/student/{student_id}")
async def get_student_signoff_detail(
    course_id: int,
    student_id: int,
    flow_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_course_access(course_id, current_user, db)
    flow = db.query(SignoffFlow).filter(SignoffFlow.id == flow_id, SignoffFlow.course_id == course_id).first()
    if not flow:
        raise HTTPException(status_code=404)
    student = db.query(User).filter(User.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404)

    points_data = []
    for point in flow.points:
        records = db.query(SignoffRecord).filter(
            SignoffRecord.point_id == point.id,
            SignoffRecord.student_id == student_id,
        ).order_by(SignoffRecord.created_at.desc()).all()
        points_data.append({
            "id": point.id,
            "label": point.label,
            "latest_status": records[0].status if records else None,
            "history": [
                {
                    "id": r.id,
                    "status": r.status,
                    "comment": r.comment,
                    "graded_by": db.query(User).filter(User.id == r.graded_by).first().name,
                    "created_at": r.created_at.strftime("%b %d, %H:%M"),
                }
                for r in records
            ],
        })

    return {
        "student": {"id": student.id, "name": student.name, "email": student.email},
        "flow": _serialize_flow(flow),
        "points": points_data,
    }


@router.post("/signoff/points/{point_id}/grade")
async def grade_signoff_point(
    point_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in (UserRole.TA, UserRole.TEACHER):
        raise HTTPException(status_code=403, detail="TA or teacher only")
    point = db.query(SignoffPoint).filter(SignoffPoint.id == point_id).first()
    if not point:
        raise HTTPException(status_code=404)
    body = await request.json()
    student_id = body.get("student_id")
    status = body.get("status")
    comment = (body.get("comment") or "").strip() or None
    if not student_id or status not in ("signed_off", "insufficient"):
        raise HTTPException(status_code=422, detail="student_id and valid status required")
    record = SignoffRecord(
        point_id=point_id,
        student_id=student_id,
        graded_by=current_user.id,
        status=status,
        comment=comment,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "id": record.id,
        "status": record.status,
        "comment": record.comment,
        "graded_at": record.created_at.strftime("%b %d, %H:%M"),
    }


@router.get("/course/{course_id}/signoff/stats")
async def get_signoff_stats(
    course_id: int,
    flow_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_course_access(course_id, current_user, db)
    flow = db.query(SignoffFlow).filter(SignoffFlow.id == flow_id, SignoffFlow.course_id == course_id).first()
    if not flow:
        raise HTTPException(status_code=404)

    student_ids = [
        e.user_id for e in db.query(CourseEnrollment).filter(
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.role == UserRole.STUDENT,
        ).all()
    ]
    total_students = len(student_ids)

    stats = []
    for point in flow.points:
        signed_off = 0
        insufficient = 0
        for sid in student_ids:
            latest = db.query(SignoffRecord).filter(
                SignoffRecord.point_id == point.id,
                SignoffRecord.student_id == sid,
            ).order_by(SignoffRecord.created_at.desc()).first()
            if latest:
                if latest.status == "signed_off":
                    signed_off += 1
                else:
                    insufficient += 1
        stats.append({
            "point_id": point.id,
            "label": point.label,
            "signed_off": signed_off,
            "insufficient": insufficient,
            "empty": total_students - signed_off - insufficient,
            "total": total_students,
        })

    return {"flow": _serialize_flow(flow), "stats": stats, "total_students": total_students}


# ─── Group categories ──────────────────────────────────────────────────────────

@router.get("/course/{course_id}/group-categories")
async def list_group_categories(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_course_access(course_id, current_user, db)
    categories = db.query(GroupCategory).filter(
        GroupCategory.course_id == course_id
    ).order_by(GroupCategory.name).all()
    return [
        {
            "id": cat.id,
            "name": cat.name,
            "canvas_group_category_id": cat.canvas_group_category_id,
            "groups": [
                {
                    "id": g.id,
                    "name": g.name,
                    "canvas_group_id": g.canvas_group_id,
                    "member_count": len(g.members),
                }
                for g in cat.groups
            ],
        }
        for cat in categories
    ]


@router.get("/course/{course_id}/group-categories/{category_id}/groups/{group_id}/members")
async def get_group_members(
    course_id: int,
    category_id: int,
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_course_access(course_id, current_user, db)
    group = db.query(Group).filter(
        Group.id == group_id,
        Group.category_id == category_id,
        Group.course_id == course_id,
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return {
        "id": group.id,
        "name": group.name,
        "category": {"id": group.category.id, "name": group.category.name},
        "members": [
            {"id": m.student_id, "name": m.student.name, "email": m.student.email}
            for m in group.members
        ],
    }


@router.post("/course/{course_id}/group-categories/sync")
async def sync_group_categories_from_canvas(
    course_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Import group categories, groups, and memberships from Canvas payload."""
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Teachers only")
    _require_course_access(course_id, current_user, db)

    body = await request.json()
    # Expected shape: list of { name, canvas_group_category_id, groups: [{ name, canvas_group_id, member_canvas_ids: [...] }] }
    categories_payload = body.get("categories", [])

    # Build canvas_user_id → User map for fast lookup
    canvas_ids = {
        uid
        for cat in categories_payload
        for grp in cat.get("groups", [])
        for uid in grp.get("member_canvas_ids", [])
    }
    user_map: dict[str, User] = {}
    if canvas_ids:
        users = db.query(User).filter(User.canvas_user_id.in_(list(canvas_ids))).all()
        user_map = {u.canvas_user_id: u for u in users}

    created_cats = 0
    created_groups = 0
    created_members = 0

    for cat_data in categories_payload:
        canvas_cat_id = str(cat_data.get("canvas_group_category_id") or "")
        cat = None
        if canvas_cat_id:
            cat = db.query(GroupCategory).filter(
                GroupCategory.canvas_group_category_id == canvas_cat_id
            ).first()
        if not cat:
            cat = GroupCategory(
                course_id=course_id,
                name=cat_data["name"],
                canvas_group_category_id=canvas_cat_id or None,
            )
            db.add(cat)
            db.flush()
            created_cats += 1
        else:
            cat.name = cat_data["name"]

        for grp_data in cat_data.get("groups", []):
            canvas_grp_id = str(grp_data.get("canvas_group_id") or "")
            grp = None
            if canvas_grp_id:
                grp = db.query(Group).filter(Group.canvas_group_id == canvas_grp_id).first()
            if not grp:
                grp = Group(
                    course_id=course_id,
                    category_id=cat.id,
                    name=grp_data["name"],
                    canvas_group_id=canvas_grp_id or None,
                )
                db.add(grp)
                db.flush()
                created_groups += 1
            else:
                grp.name = grp_data["name"]
                grp.category_id = cat.id

            for canvas_uid in grp_data.get("member_canvas_ids", []):
                user = user_map.get(str(canvas_uid))
                if not user:
                    continue
                exists = db.query(GroupMember).filter(
                    GroupMember.group_id == grp.id,
                    GroupMember.student_id == user.id,
                ).first()
                if not exists:
                    # Remove from any other group in the same category first
                    old = db.query(GroupMember).filter(
                        GroupMember.category_id == cat.id,
                        GroupMember.student_id == user.id,
                    ).first()
                    if old:
                        db.delete(old)
                    db.add(GroupMember(
                        group_id=grp.id,
                        category_id=cat.id,
                        student_id=user.id,
                    ))
                    created_members += 1

    db.commit()
    return {"created_categories": created_cats, "created_groups": created_groups, "created_members": created_members}
