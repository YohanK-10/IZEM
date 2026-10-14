"""
Tests for queue counting consistency across endpoints.

Bugs covered:
1. /api/room/{room_id}/queue  — total_waiting only counted child queue items,
   ignoring students whose queue_room_id == parent room (the common seeded case).
2. /api/course/{course_id}/rooms — same omission in the per-room waiting count.
3. TAHomePage /api/ta/dashboard active_rooms — correctly counts parent+child,
   creating a visible inconsistency: home shows N, room detail shows 0.
"""

import pytest
from datetime import datetime, timedelta
from app.models.db import (
    User, UserRole, AuthToken, Course, Assignment, Question,
    QueueRoom, HelpRequest, RequestStatus, CourseEnrollment, TAAssignment,
)


# ─── Shared fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def ta_user(db_session):
    user = User(email="ta@queue-test.com", name="Queue TA", role=UserRole.TA)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def ta_client(client, db_session, ta_user):
    token = AuthToken(
        user_id=ta_user.id, token="ta-queue-token",
        used=True, expires_at=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(token)
    db_session.commit()
    client.cookies.set("session_token", "ta-queue-token")
    return client


@pytest.fixture
def teacher_user(db_session):
    user = User(email="teacher@queue-test.com", name="Queue Teacher", role=UserRole.TEACHER)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def teacher_client(client, db_session, teacher_user):
    token = AuthToken(
        user_id=teacher_user.id, token="teacher-queue-token",
        used=True, expires_at=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(token)
    db_session.commit()
    client.cookies.set("session_token", "teacher-queue-token")
    return client


def make_student(db_session, email, name="Student"):
    s = User(email=email, name=name, role=UserRole.STUDENT)
    db_session.add(s)
    db_session.flush()
    return s


def make_pending_request(db_session, student, question, room, pos):
    req = HelpRequest(
        student_id=student.id,
        question_id=question.id,
        status=RequestStatus.PENDING,
        queue_room_id=room.id,
        queue_position=pos,
        joined_queue_at=datetime.utcnow() - timedelta(minutes=10 - pos),
        created_at=datetime.utcnow() - timedelta(minutes=10 - pos),
        is_overtime=False,
    )
    db_session.add(req)
    db_session.flush()
    return req


# ─── Scenario builder ─────────────────────────────────────────────────────────

def setup_signoff_scenario(db_session, ta_user, teacher_user, num_students_in_parent=3):
    """
    Creates:
      course → assignment (is_signoff=True, queue_open=True)
        → parent room "Sign-off Queue" (open, is_signoff=True)
            → child queue "Hi" (open, is_signoff=False, empty)
      N students waiting directly in the parent room.

    This mirrors the exact production state: students seeded into the parent room,
    TA later manually adds a child queue "Hi" via the room UI.
    """
    course = Course(name="Signoff Test Course")
    db_session.add(course)
    db_session.flush()

    db_session.add(CourseEnrollment(user_id=ta_user.id, course_id=course.id, role=UserRole.TA))
    db_session.add(CourseEnrollment(user_id=teacher_user.id, course_id=course.id, role=UserRole.TEACHER))
    db_session.add(TAAssignment(ta_id=ta_user.id, course_id=course.id))

    assignment = Assignment(
        name="Lab 3 – Individual Sign-off",
        course_id=course.id,
        is_signoff=True,
        queue_open=True,
        queue_opened_at=datetime.utcnow() - timedelta(minutes=30),
        queue_opened_by=ta_user.id,
    )
    db_session.add(assignment)
    db_session.flush()

    q1 = Question(assignment_id=assignment.id, question_number=1,
                  problem_description="Implement linked list", official_solution="...",
                  hinting_strategy="...", require_signoff=True)
    q2 = Question(assignment_id=assignment.id, question_number=2,
                  problem_description="Explain time complexity", official_solution="...",
                  hinting_strategy="...", require_signoff=True)
    db_session.add_all([q1, q2])
    db_session.flush()

    parent_room = QueueRoom(
        assignment_id=assignment.id,
        course_id=course.id,
        name="Sign-off Queue",
        is_open=True,
        is_signoff=True,
        opened_at=datetime.utcnow() - timedelta(minutes=30),
        opened_by=ta_user.id,
    )
    db_session.add(parent_room)
    db_session.flush()

    # Child queue added by TA later — empty
    child_queue = QueueRoom(
        parent_room_id=parent_room.id,
        name="Hi",
        is_open=True,
        is_signoff=False,
        opened_at=datetime.utcnow() - timedelta(minutes=5),
        opened_by=ta_user.id,
    )
    db_session.add(child_queue)
    db_session.flush()

    students = []
    for i in range(num_students_in_parent):
        s = make_student(db_session, f"s{i}@signoff-test.com", f"Student {i}")
        db_session.add(CourseEnrollment(user_id=s.id, course_id=course.id, role=UserRole.STUDENT))
        q = q1 if i % 2 == 0 else q2
        make_pending_request(db_session, s, q, parent_room, pos=i + 1)
        students.append(s)

    db_session.commit()
    return {
        "course": course,
        "assignment": assignment,
        "parent_room": parent_room,
        "child_queue": child_queue,
        "questions": [q1, q2],
        "students": students,
    }


# ─── Bug 1: /api/room/{room_id}/queue total_waiting ──────────────────────────

class TestRoomQueueEndpoint:
    def test_total_waiting_includes_students_in_parent_room(self, ta_client, db_session, ta_user, teacher_user):
        """
        Students whose queue_room_id == parent room id must appear in total_waiting.
        Before the fix this returned total_waiting=0 because only child queue rows
        were counted.
        """
        ctx = setup_signoff_scenario(db_session, ta_user, teacher_user, num_students_in_parent=3)
        room_id = ctx["parent_room"].id

        resp = ta_client.get(f"/api/room/{room_id}/queue")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_waiting"] == 3, (
            f"Expected 3 students waiting in parent room, got {data['total_waiting']}. "
            "Students stored directly in the parent room were being ignored."
        )

    def test_students_in_parent_room_appear_in_queue_data(self, ta_client, db_session, ta_user, teacher_user):
        """
        The queues list returned by the endpoint must expose the students
        waiting directly in the parent room (not just named child queues).
        """
        ctx = setup_signoff_scenario(db_session, ta_user, teacher_user, num_students_in_parent=2)
        room_id = ctx["parent_room"].id
        student_ids = {s.id for s in ctx["students"]}

        resp = ta_client.get(f"/api/room/{room_id}/queue")
        assert resp.status_code == 200
        data = resp.json()

        # Collect all student_ids surfaced anywhere in queues
        surfaced = set()
        for q in data["queues"]:
            for item in q.get("waiting", []):
                surfaced.add(item["student_id"])

        assert student_ids.issubset(surfaced), (
            f"Students {student_ids - surfaced} are in the parent room but do not "
            "appear in any queue lane. They were invisible to the TA."
        )

    def test_empty_child_queue_still_appears(self, ta_client, db_session, ta_user, teacher_user):
        """The named child queue 'Hi' (empty) must still be listed."""
        ctx = setup_signoff_scenario(db_session, ta_user, teacher_user, num_students_in_parent=1)
        room_id = ctx["parent_room"].id

        resp = ta_client.get(f"/api/room/{room_id}/queue")
        assert resp.status_code == 200
        data = resp.json()

        queue_names = [q["name"] for q in data["queues"]]
        assert "Hi" in queue_names

    def test_child_queue_students_counted_separately(self, ta_client, db_session, ta_user, teacher_user):
        """Students in a child queue must also count toward total_waiting."""
        ctx = setup_signoff_scenario(db_session, ta_user, teacher_user, num_students_in_parent=2)
        child_queue = ctx["child_queue"]
        q = ctx["questions"][0]

        # Add one more student to the child queue
        extra = make_student(db_session, "extra@signoff-test.com", "Extra Student")
        db_session.add(CourseEnrollment(
            user_id=extra.id, course_id=ctx["course"].id, role=UserRole.STUDENT))
        make_pending_request(db_session, extra, q, child_queue, pos=1)
        db_session.commit()

        resp = ta_client.get(f"/api/room/{ctx['parent_room'].id}/queue")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_waiting"] == 3  # 2 in parent + 1 in child


# ─── Bug 2: /api/course/{course_id}/rooms waiting count ──────────────────────

class TestCourseRoomsWaitingCount:
    def test_room_card_shows_correct_waiting_count(self, ta_client, db_session, ta_user, teacher_user):
        """
        The Rooms page room card must show waiting=3 for a room that has 3 students
        stored directly in it, even when a child queue exists (and is empty).
        Before the fix this showed waiting=0.
        """
        ctx = setup_signoff_scenario(db_session, ta_user, teacher_user, num_students_in_parent=3)
        course_id = ctx["course"].id

        resp = ta_client.get(f"/api/course/{course_id}/rooms")
        assert resp.status_code == 200
        data = resp.json()

        parent_id = ctx["parent_room"].id
        room_data = next((r for r in data["rooms"] if r["id"] == parent_id), None)
        assert room_data is not None, "Parent sign-off room not in rooms list"
        assert room_data["waiting"] == 3, (
            f"Expected waiting=3, got {room_data['waiting']}. "
            "Students stored directly in the parent room were ignored."
        )

    def test_room_card_waiting_zero_when_truly_empty(self, ta_client, db_session, ta_user, teacher_user):
        """Sanity: a room with no students at all shows waiting=0."""
        ctx = setup_signoff_scenario(db_session, ta_user, teacher_user, num_students_in_parent=0)
        course_id = ctx["course"].id

        resp = ta_client.get(f"/api/course/{course_id}/rooms")
        assert resp.status_code == 200
        data = resp.json()

        parent_id = ctx["parent_room"].id
        room_data = next((r for r in data["rooms"] if r["id"] == parent_id), None)
        assert room_data is not None
        assert room_data["waiting"] == 0

    def test_ta_dashboard_and_rooms_page_agree(self, ta_client, db_session, ta_user, teacher_user):
        """
        /api/ta/dashboard active_rooms[].queue_count and
        /api/course/{id}/rooms[].waiting must return the same number
        for the same room. The home card and room card must be consistent.
        """
        ctx = setup_signoff_scenario(db_session, ta_user, teacher_user, num_students_in_parent=3)
        course_id = ctx["course"].id
        parent_id = ctx["parent_room"].id

        dashboard_resp = ta_client.get("/api/ta/dashboard")
        assert dashboard_resp.status_code == 200
        dashboard_data = dashboard_resp.json()

        rooms_resp = ta_client.get(f"/api/course/{course_id}/rooms")
        assert rooms_resp.status_code == 200
        rooms_data = rooms_resp.json()

        dashboard_count = next(
            (r["queue_count"] for r in dashboard_data["active_rooms"] if r["room_id"] == parent_id),
            None,
        )
        rooms_count = next(
            (r["waiting"] for r in rooms_data["rooms"] if r["id"] == parent_id),
            None,
        )

        assert dashboard_count is not None, "Room not found in TA dashboard active_rooms"
        assert rooms_count is not None, "Room not found in /course/rooms"
        assert dashboard_count == rooms_count, (
            f"Home card shows {dashboard_count} but Rooms page shows {rooms_count}. "
            "Inconsistency between dashboard and rooms endpoints."
        )


# ─── Bug 3: /api/queue/{assignment_id} lane consistency ──────────────────────

class TestAssignmentQueueEndpoint:
    def test_parent_room_students_visible_in_queue(self, ta_client, db_session, ta_user, teacher_user):
        """
        /api/queue/{assignment_id} must return the students stored in the parent
        room inside queue_items, with the correct room_id so the frontend lane
        computation places them in the parent room lane.
        """
        ctx = setup_signoff_scenario(db_session, ta_user, teacher_user, num_students_in_parent=3)
        assignment_id = ctx["assignment"].id
        parent_id = ctx["parent_room"].id

        resp = ta_client.get(f"/api/queue/{assignment_id}")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_in_queue"] == 3
        room_ids = {item["room_id"] for item in data["queue_items"]}
        assert parent_id in room_ids, (
            "queue_items must carry the parent room id so the frontend "
            "can render the correct lane."
        )

    def test_parent_room_in_rooms_list(self, ta_client, db_session, ta_user, teacher_user):
        """
        The rooms array must include the parent room so the frontend creates
        a lane for it in LabSessionPage.
        """
        ctx = setup_signoff_scenario(db_session, ta_user, teacher_user, num_students_in_parent=3)
        assignment_id = ctx["assignment"].id
        parent_id = ctx["parent_room"].id

        resp = ta_client.get(f"/api/queue/{assignment_id}")
        assert resp.status_code == 200
        data = resp.json()

        room_ids = [r["id"] for r in data["rooms"]]
        assert parent_id in room_ids

    def test_child_queue_in_queues_list(self, ta_client, db_session, ta_user, teacher_user):
        """The child queue 'Hi' must appear in the queues array."""
        ctx = setup_signoff_scenario(db_session, ta_user, teacher_user, num_students_in_parent=1)
        assignment_id = ctx["assignment"].id

        resp = ta_client.get(f"/api/queue/{assignment_id}")
        assert resp.status_code == 200
        data = resp.json()

        queue_names = [q["name"] for q in data.get("queues", [])]
        assert "Hi" in queue_names
