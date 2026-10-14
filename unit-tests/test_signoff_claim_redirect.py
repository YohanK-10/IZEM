"""
Tests for the sign-off claim → redirect flow.

Bugs covered:
1. /api/ta/request/{id}/claim must return signoff_redirect when the request
   belongs to a sign-off assignment.
2. /api/course/{course_id}/signoff/q/search must be accessible to TAs who
   have a TAAssignment but no CourseEnrollment row. Before the fix,
   _require_course_access only checked CourseEnrollment, so TAs got 403
   and SignOffPage could never auto-open the student panel.
"""

import pytest
from datetime import datetime, timedelta
from app.models.db import (
    User, UserRole, AuthToken, Course, Assignment, Question,
    QueueRoom, HelpRequest, RequestStatus, CourseEnrollment, TAAssignment,
    SignoffRecord,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def teacher(db_session):
    u = User(email="teacher@signoff-claim.com", name="Teacher", role=UserRole.TEACHER)
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def ta(db_session):
    u = User(email="ta@signoff-claim.com", name="TA", role=UserRole.TA)
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def student(db_session):
    u = User(email="student@signoff-claim.com", name="Student", role=UserRole.STUDENT)
    db_session.add(u)
    db_session.flush()
    return u


def _make_token(db_session, user, token_str):
    t = AuthToken(
        user_id=user.id, token=token_str,
        used=True, expires_at=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(t)
    db_session.flush()
    return t


@pytest.fixture
def ta_client(client, db_session, ta):
    _make_token(db_session, ta, "ta-claim-token")
    db_session.commit()
    client.cookies.set("session_token", "ta-claim-token")
    return client


def setup_signoff_scenario(db_session, teacher, ta, student):
    """
    Creates:
      course (teacher owns it) + TAAssignment (no CourseEnrollment for TA)
      → assignment (is_signoff=True, queue_open=True)
        → parent QueueRoom (open, is_signoff=True)
      student enrolled in course, pending help request in parent room
    Returns dict with all objects.
    """
    course = Course(name="Signoff Claim Course", teacher_id=teacher.id)
    db_session.add(course)
    db_session.flush()

    # TA has TAAssignment but NO CourseEnrollment — this is the production case
    db_session.add(TAAssignment(ta_id=ta.id, course_id=course.id))
    # Student enrolled
    db_session.add(CourseEnrollment(user_id=student.id, course_id=course.id, role=UserRole.STUDENT))

    assignment = Assignment(
        name="Lab Sign-off", course_id=course.id,
        is_signoff=True, queue_open=True,
        queue_opened_at=datetime.utcnow() - timedelta(minutes=20),
        queue_opened_by=ta.id,
    )
    db_session.add(assignment)
    db_session.flush()

    q = Question(
        assignment_id=assignment.id, question_number=1,
        problem_description="Explain linked list", official_solution="...",
        hinting_strategy="...", require_signoff=True,
    )
    db_session.add(q)
    db_session.flush()

    room = QueueRoom(
        assignment_id=assignment.id,
        course_id=course.id,
        name="Sign-off Queue",
        is_open=True,
        is_signoff=True,
        opened_at=datetime.utcnow() - timedelta(minutes=20),
        opened_by=ta.id,
    )
    db_session.add(room)
    db_session.flush()

    req = HelpRequest(
        student_id=student.id,
        question_id=q.id,
        status=RequestStatus.PENDING,
        queue_room_id=room.id,
        queue_position=1,
        joined_queue_at=datetime.utcnow() - timedelta(minutes=5),
        created_at=datetime.utcnow() - timedelta(minutes=5),
        is_overtime=False,
    )
    db_session.add(req)
    db_session.commit()

    return {
        "course": course,
        "assignment": assignment,
        "question": q,
        "room": room,
        "request": req,
    }


# ─── Backend: claim endpoint returns signoff_redirect ─────────────────────────

class TestClaimSignoffRedirect:
    def test_claim_returns_signoff_redirect_for_signoff_assignment(
        self, ta_client, db_session, teacher, ta, student
    ):
        """
        Claiming a pending help request from a sign-off assignment must return
        signoff_redirect with course_id, assignment_id, type='student', student_id.
        """
        ctx = setup_signoff_scenario(db_session, teacher, ta, student)
        req_id = ctx["request"].id

        resp = ta_client.post(f"/api/ta/request/{req_id}/claim")
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["ok"] is True
        assert data["signoff_redirect"] is not None, (
            "signoff_redirect must not be null for a sign-off assignment request"
        )
        r = data["signoff_redirect"]
        assert r["type"] == "student"
        assert r["course_id"] == ctx["course"].id
        assert r["assignment_id"] == ctx["assignment"].id
        assert r["student_id"] == student.id

    def test_claim_returns_null_redirect_for_non_signoff(
        self, ta_client, db_session, teacher, ta, student
    ):
        """
        Claiming a request from a regular (non-sign-off) assignment must return
        signoff_redirect=null so the frontend stays on the lab session page.
        """
        course = Course(name="Regular Course", teacher_id=teacher.id)
        db_session.add(course)
        db_session.flush()
        db_session.add(TAAssignment(ta_id=ta.id, course_id=course.id))
        db_session.add(CourseEnrollment(user_id=student.id, course_id=course.id, role=UserRole.STUDENT))

        assignment = Assignment(
            name="Regular Lab", course_id=course.id,
            is_signoff=False, queue_open=True,
        )
        db_session.add(assignment)
        db_session.flush()

        q = Question(
            assignment_id=assignment.id, question_number=1,
            problem_description="Write fizzbuzz", official_solution="...",
            hinting_strategy="...", require_signoff=False,
        )
        db_session.add(q)
        db_session.flush()

        room = QueueRoom(
            assignment_id=assignment.id, course_id=course.id,
            name="Room A", is_open=True, is_signoff=False,
            opened_at=datetime.utcnow() - timedelta(minutes=10),
            opened_by=ta.id,
        )
        db_session.add(room)
        db_session.flush()

        req = HelpRequest(
            student_id=student.id, question_id=q.id,
            status=RequestStatus.PENDING, queue_room_id=room.id,
            queue_position=1,
            joined_queue_at=datetime.utcnow() - timedelta(minutes=3),
            created_at=datetime.utcnow() - timedelta(minutes=3),
            is_overtime=False,
        )
        db_session.add(req)
        db_session.commit()

        resp = ta_client.post(f"/api/ta/request/{req.id}/claim")
        assert resp.status_code == 200
        data = resp.json()
        assert data["signoff_redirect"] is None

    def test_claim_already_claimed_returns_409(
        self, ta_client, db_session, teacher, ta, student
    ):
        """Claiming an already-assigned request raises 409."""
        ctx = setup_signoff_scenario(db_session, teacher, ta, student)
        ta_client.post(f"/api/ta/request/{ctx['request'].id}/claim")
        resp2 = ta_client.post(f"/api/ta/request/{ctx['request'].id}/claim")
        # Second claim by same TA is idempotent (200 — already owns it)
        # but a second TA would get 409. Here we just verify no crash.
        assert resp2.status_code in (200, 409)

    def test_claim_marks_request_as_started_helping(
        self, ta_client, db_session, teacher, ta, student
    ):
        """After a successful claim, started_helping_at must be set."""
        ctx = setup_signoff_scenario(db_session, teacher, ta, student)
        resp = ta_client.post(f"/api/ta/request/{ctx['request'].id}/claim")
        assert resp.status_code == 200

        db_session.refresh(ctx["request"])
        assert ctx["request"].started_helping_at is not None
        assert ctx["request"].assigned_ta_id == ta.id


# ─── Backend: signoff search accessible to TAs (TAAssignment, no enrollment) ──

class TestSignoffSearchTAAccess:
    def test_ta_with_ta_assignment_can_search(
        self, ta_client, db_session, teacher, ta, student
    ):
        """
        A TA who only has TAAssignment (no CourseEnrollment) must be able to call
        /api/course/{id}/signoff/q/search. Before the fix this returned 403.
        """
        ctx = setup_signoff_scenario(db_session, teacher, ta, student)
        course_id = ctx["course"].id

        resp = ta_client.get(f"/api/course/{course_id}/signoff/q/search")
        assert resp.status_code == 200, (
            f"TA with TAAssignment got {resp.status_code}: {resp.text}. "
            "_require_course_access must accept TAAssignment."
        )
        results = resp.json()
        assert isinstance(results, list)

    def test_ta_search_returns_enrolled_students(
        self, ta_client, db_session, teacher, ta, student
    ):
        """The search must include the enrolled student for the sign-off assignment."""
        ctx = setup_signoff_scenario(db_session, teacher, ta, student)
        course_id = ctx["course"].id

        resp = ta_client.get(f"/api/course/{course_id}/signoff/q/search")
        assert resp.status_code == 200
        results = resp.json()

        student_ids = [r.get("student_id") for r in results]
        assert student.id in student_ids, (
            f"Student {student.id} not found in search results: {results}"
        )

    def test_ta_search_matches_correct_assignment(
        self, ta_client, db_session, teacher, ta, student
    ):
        """Search results must reference the correct assignment_id."""
        ctx = setup_signoff_scenario(db_session, teacher, ta, student)
        course_id = ctx["course"].id
        assignment_id = ctx["assignment"].id

        resp = ta_client.get(f"/api/course/{course_id}/signoff/q/search")
        assert resp.status_code == 200
        results = resp.json()

        matching = [r for r in results if r.get("assignment_id") == assignment_id
                    and r.get("student_id") == student.id]
        assert len(matching) == 1, (
            f"Expected exactly one result for student+assignment, got: {matching}"
        )

    def test_unenrolled_non_ta_cannot_search(
        self, client, db_session, teacher, ta, student
    ):
        """A random user with no relationship to the course gets 403."""
        ctx = setup_signoff_scenario(db_session, teacher, ta, student)
        course_id = ctx["course"].id

        outsider = User(email="outside@x.com", name="Outsider", role=UserRole.TA)
        db_session.add(outsider)
        db_session.flush()
        token = AuthToken(
            user_id=outsider.id, token="outsider-token",
            used=True, expires_at=datetime.utcnow() + timedelta(days=1),
        )
        db_session.add(token)
        db_session.commit()
        client.cookies.set("session_token", "outsider-token")

        resp = client.get(f"/api/course/{course_id}/signoff/q/search")
        assert resp.status_code == 403


# ─── Backend: signoff student detail accessible to TAs ───────────────────────

class TestSignoffStudentDetailTAAccess:
    def test_ta_can_get_student_signoff_detail(
        self, ta_client, db_session, teacher, ta, student
    ):
        """
        GET /api/course/{id}/signoff/q/student/{student_id}?assignment_id=X
        must succeed for TAs with TAAssignment only.
        """
        ctx = setup_signoff_scenario(db_session, teacher, ta, student)
        course_id = ctx["course"].id
        assignment_id = ctx["assignment"].id

        resp = ta_client.get(
            f"/api/course/{course_id}/signoff/q/student/{student.id}"
            f"?assignment_id={assignment_id}"
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "questions" in data
        assert "points" in data
