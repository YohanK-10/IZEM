import pytest
from unittest.mock import patch
from app.models.db import UserRole, User, AuthToken, RequestStatus
from datetime import datetime, timedelta

@pytest.fixture
def ta_user(db_session):
    """Creates a basic TA test user."""
    user = User(email="ta@test.com", name="Test TA", role=UserRole.TA)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def teacher_user(db_session):
    """Creates a basic Teacher test user."""
    user = User(email="teacher@test.com", name="Test Teacher", role=UserRole.TEACHER)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def ta_client(client, db_session, ta_user):
    """Returns a TestClient authenticated as a TA."""
    token = AuthToken(
        user_id=ta_user.id, token="ta-token-123", used=True,
        expires_at=datetime.utcnow() + timedelta(days=1)
    )
    db_session.add(token)
    db_session.commit()
    client.cookies.set("session_token", "ta-token-123")
    return client

@pytest.fixture
def teacher_client(client, db_session, teacher_user):
    """Returns a TestClient authenticated as a Teacher."""
    token = AuthToken(
        user_id=teacher_user.id, token="teacher-token-123", used=True,
        expires_at=datetime.utcnow() + timedelta(days=1)
    )
    db_session.add(token)
    db_session.commit()
    client.cookies.set("session_token", "teacher-token-123")
    return client

@patch("app.routes.api.ALLOW_TEST_ACCOUNTS", True)
def test_api_login_with_test_account(client, db_session):
    # Test logging in with a predefined test account (issue 24 logic)
    payload = {"email": "student@example.com"}

    response = client.post("/api/auth/login", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "student@example.com"
    assert data["role"] == UserRole.STUDENT.value

    # Ensure cookie is set
    assert "session_token" in response.cookies


@patch("app.routes.api.email_service.send_magic_link")
def test_api_login_magic_link(mock_send_email, client, db_session):
    # Create a normal user in the database
    user = User(email="realstudent@example.com", name="Real", role=UserRole.STUDENT)
    db_session.add(user)
    db_session.commit()

    payload = {"email": "realstudent@example.com"}
    response = client.post("/api/auth/login", json=payload)

    assert response.status_code == 200
    # FIX: Match the exact string your API returns
    assert "Check your email for the login link" in response.json()["message"]

    # Ensure the email service was actually called
    mock_send_email.assert_called_once()
    args, _ = mock_send_email.call_args
    assert args[0] == "realstudent@example.com"
    assert args[1] is not None


def test_get_me_authenticated(auth_client, test_user):
    response = auth_client.get("/api/me")

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user.email
    assert data["role"] == test_user.role.value


def test_get_me_unauthenticated(client):
    response = client.get("/api/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_student_dashboard_access(auth_client, test_user):
    # Test user is a STUDENT, should have access
    response = auth_client.get("/api/student/dashboard")
    assert response.status_code == 200


def test_ta_dashboard_forbidden_for_student(auth_client):
    # Test user is a STUDENT, trying to access TA route
    response = auth_client.get("/api/ta/dashboard")
    assert response.status_code == 403
    assert response.json()["detail"] == "TA only"


@patch("app.services.help_request_service.notify_tas_new_request")
def test_student_submit_help_success(mock_notify, auth_client, db_session, test_user):
    # Setup necessary mock data in DB for a question and queue room
    from app.models.db import Course, Assignment, Question, QueueRoom, RequestStatus, HelpRequest

    course = Course(name="Test Course")
    db_session.add(course)
    db_session.commit()

    assignment = Assignment(name="Assignment 1", course_id=course.id, queue_open=True)
    db_session.add(assignment)
    db_session.commit()

    question = Question(assignment_id=assignment.id, question_number=1, problem_description="Test",
                        official_solution="Dummy solution", hinting_strategy="Solve it")
    room = QueueRoom(assignment_id=assignment.id, is_open=True, name="Room 1")
    db_session.add_all([question, room])
    db_session.commit()

    # We need to bypass the `require_assignment_access` dependency logic
    from app.models.db import CourseEnrollment
    enrollment = CourseEnrollment(user_id=test_user.id, course_id=course.id, role=UserRole.STUDENT)
    db_session.add(enrollment)
    db_session.commit()

    # Perform the form upload
    response = auth_client.post(
        "/api/student/help/submit",
        data={
            "student_comment": "I need help with this specific error.",
            "submission_text": "print('hello')",
            "question_id": question.id,
            "queue_room_id": room.id
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "request_id" in data

    # Feedback is now handled via the ai_queue_state field, not a direct call.
    req = db_session.query(HelpRequest).filter_by(id=data["request_id"]).first()
    assert req is not None
    assert req.ai_queue_state == "queued"


# --- LOGIN TESTS FOR TA & TEACHER TEST ACCOUNTS ---

@patch("app.routes.api.ALLOW_TEST_ACCOUNTS", True)
def test_api_login_ta_test_account(client, db_session):
    response = client.post("/api/auth/login", json={"email": "ta@example.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "ta@example.com"
    assert data["role"] == UserRole.TA.value
    assert "session_token" in response.cookies


@patch("app.routes.api.ALLOW_TEST_ACCOUNTS", True)
def test_api_login_teacher_test_account(client, db_session):
    response = client.post("/api/auth/login", json={"email": "teacher@example.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "teacher@example.com"
    assert data["role"] == UserRole.TEACHER.value
    assert "session_token" in response.cookies


# 1. Student Dashboard Access
def test_student_dashboard_access_ta(ta_client):
    response = ta_client.get("/api/student/dashboard")
    assert response.status_code == 403
    assert response.json()["detail"] == "Student only"


def test_student_dashboard_access_teacher(teacher_client):
    response = teacher_client.get("/api/student/dashboard")
    assert response.status_code == 403
    assert response.json()["detail"] == "Student only"


# 2. TA Dashboard Access
def test_ta_dashboard_access_ta(ta_client):
    response = ta_client.get("/api/ta/dashboard")
    assert response.status_code == 200


def test_ta_dashboard_access_teacher(teacher_client):
    response = teacher_client.get("/api/ta/dashboard")
    assert response.status_code == 403
    assert response.json()["detail"] == "TA only"

# 3. Teacher Dashboard Access
def test_teacher_dashboard_access_teacher(teacher_client):
    response = teacher_client.get("/api/settings")
    assert response.status_code == 200


def test_teacher_dashboard_access_student(auth_client):  # auth_client is our student
    response = auth_client.get("/api/settings")
    assert response.status_code == 403
    assert response.json()["detail"] == "Only teachers can access settings"


def test_teacher_dashboard_access_ta(ta_client):
    response = ta_client.get("/api/settings")
    assert response.status_code == 403
    assert response.json()["detail"] == "Only teachers can access settings"


@pytest.fixture
def active_help_request_id(client, db_session, ta_user, test_user):
    """
    A setup fixture that simulates the full journey up to the point of TA review:
    1. Creates course, assignment, and question.
    2. Grants TA and Student access.
    3. TA opens the queue.
    4. Student submits a help request.
    5. Mocks the AI background task and sets the status to AI_GENERATED.
    """
    from app.models.db import Course, Assignment, Question, QueueRoom, CourseEnrollment, \
        TAAssignment, HelpRequest, UserRole, AuthToken
    from datetime import datetime, timedelta

    # --- 1. Setup DB entities ---
    course = Course(name="Lifecycle Course")
    db_session.add(course)
    db_session.commit()

    assignment = Assignment(name="Lifecycle Assignment", course_id=course.id, queue_open=False)
    db_session.add(assignment)
    db_session.commit()

    question = Question(
        assignment_id=assignment.id,
        question_number=1,
        problem_description="How to loop?",
        official_solution="Use a for loop",
        hinting_strategy="Remind them about the syntax."
    )
    db_session.add(question)

    # Enrollments and TA Assignments
    db_session.add(
        CourseEnrollment(user_id=test_user.id, course_id=course.id, role=UserRole.STUDENT))
    db_session.add(TAAssignment(ta_id=ta_user.id, course_id=course.id))

    # Create specific tokens for this lifecycle test
    ta_token = "ta-lifecycle-token"
    student_token = "student-lifecycle-token"
    db_session.add(AuthToken(user_id=ta_user.id, token=ta_token, used=True,
                             expires_at=datetime.utcnow() + timedelta(days=1)))
    db_session.add(AuthToken(user_id=test_user.id, token=student_token, used=True,
                             expires_at=datetime.utcnow() + timedelta(days=1)))
    db_session.commit()

    # --- 2. TA Opens Queue ---
    # Switch identity to TA
    client.cookies.set("session_token", ta_token)

    resp = client.post(f"/api/ta/assignment/{assignment.id}/queue/open",
                       json={"room_names": ["Virtual Room"]})
    assert resp.status_code == 200

    room = db_session.query(QueueRoom).filter_by(assignment_id=assignment.id).first()

    # --- 3. Student Joins Queue ---
    # Switch identity to Student
    client.cookies.set("session_token", student_token)

    with patch("app.services.openai_feedback.feedback_generator.generate_feedback_background"), \
            patch("app.services.help_request_service.notify_tas_new_request"):
        resp = client.post(
            "/api/student/help/submit",
            data={
                "student_comment": "I am stuck on the loop.",
                "submission_text": "while True:",
                "question_id": question.id,
                "queue_room_id": room.id
            }
        )
        assert resp.status_code == 200
        req_id = resp.json()["request_id"]

    # --- 4. Simulate AI finishing ---
    req = db_session.query(HelpRequest).get(req_id)
    req.status = RequestStatus.AI_GENERATED
    req.ai_feedback = "AI suggests using a for loop instead of while True."
    db_session.commit()

    # Switch identity back to TA so the downstream tests start with the right permissions
    client.cookies.set("session_token", ta_token)

    return req_id

    # TEST 1: TA Approves AI Feedback Directly
def test_ta_action_approve_ai_feedback(ta_client, db_session, active_help_request_id):
        from app.models.db import HelpRequest

        # 1. TA Claims the request
        claim_resp = ta_client.post(f"/api/ta/request/{active_help_request_id}/claim")
        assert claim_resp.status_code == 200

        # 2. TA Approves the request
        approve_resp = ta_client.post(f"/api/ta/request/{active_help_request_id}/approve")
        assert approve_resp.status_code == 200

        # 3. Verify Database State
        req = db_session.query(HelpRequest).get(active_help_request_id)
        assert req.status == RequestStatus.APPROVED

    # TEST 2: TA Edits AI Feedback
def test_ta_action_edit_ai_feedback(ta_client, db_session, active_help_request_id):
        from app.models.db import HelpRequest

        # 1. TA Claims the request
        ta_client.post(f"/api/ta/request/{active_help_request_id}/claim")

        # 2. TA Edits the feedback
        custom_feedback = "AI was close, but make sure to check your indentations too!"
        edit_resp = ta_client.post(
            f"/api/ta/request/{active_help_request_id}/edit",
            json={"feedback": custom_feedback}
        )
        assert edit_resp.status_code == 200

        # 3. Verify Database State
        req = db_session.query(HelpRequest).get(active_help_request_id)
        assert req.status == RequestStatus.EDITED
        assert req.final_feedback == custom_feedback

    # TEST 3: TA Rejects AI Feedback (In-Person Help)
def test_ta_action_reject_for_in_person(ta_client, db_session, active_help_request_id):
        from app.models.db import HelpRequest

        # 1. TA Claims the request
        ta_client.post(f"/api/ta/request/{active_help_request_id}/claim")

        # 2. TA Rejects the feedback for in-person help
        rejection_reason = "This logic is too complex for text, I will come over."
        reject_resp = ta_client.post(
            f"/api/ta/request/{active_help_request_id}/reject",
            json={"reason": rejection_reason}
        )
        assert reject_resp.status_code == 200

        # 3. Verify Database State
        req = db_session.query(HelpRequest).get(active_help_request_id)
        assert req.status == RequestStatus.IN_PERSON


# --- ANALYTICS TESTS ---

def test_analytics_teacher_access(teacher_client, db_session):
    response = teacher_client.get("/api/analytics")
    # Even if the DB is empty, a teacher should get a 200 OK and a valid data structure
    assert response.status_code == 200
    data = response.json()

    # FIX: Check inside the 'summary' dictionary
    assert "summary" in data
    assert "total_requests" in data["summary"]


def test_analytics_student_forbidden(auth_client):
    response = auth_client.get("/api/analytics")
    assert response.status_code == 403
    assert response.json()["detail"] == "Only teachers can access analytics"


# --- LLM CONFIGS CRUD TESTS ---

def test_llm_config_crud_lifecycle(teacher_client, db_session):
    from app.models.db import LLMConfig

    # 1. Create a new LLM Config
    payload = {
        "name": "Test OpenAI",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-test-key",
        "model_name": "gpt-4",
        "is_public": True
    }
    create_resp = teacher_client.post("/api/llm/configs", json=payload)
    assert create_resp.status_code == 200
    data = create_resp.json()
    assert data["name"] == "Test OpenAI"
    llm_id = data["id"]

    # 2. Get Configs
    get_resp = teacher_client.get("/api/llm/configs")
    assert get_resp.status_code == 200
    assert len(get_resp.json()["my_configs"]) >= 1

    # 3. Update the Config
    update_resp = teacher_client.put(f"/api/llm/configs/{llm_id}", json={"name": "Updated OpenAI"})
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Updated OpenAI"

    # 4. Delete the Config
    delete_resp = teacher_client.delete(f"/api/llm/configs/{llm_id}")
    assert delete_resp.status_code == 200

    # Verify deletion in DB
    assert db_session.query(LLMConfig).filter_by(id=llm_id).first() is None


def test_llm_config_student_forbidden(auth_client):
    response = auth_client.get("/api/llm/configs")
    assert response.status_code == 403


# --- ROOM & QUEUE MANAGEMENT TESTS ---

def test_course_room_and_queue_lifecycle(teacher_client, db_session, teacher_user):
    from app.models.db import Course, CourseEnrollment, UserRole, QueueRoom, Assignment

    # Setup a Course
    course = Course(name="Room Management Course")
    db_session.add(course)
    db_session.commit()

    assignment = Assignment(name="Lab 1", course_id=course.id)
    db_session.add(assignment)
    db_session.commit()

    # Enroll Teacher
    db_session.add(
        CourseEnrollment(user_id=teacher_user.id, course_id=course.id, role=UserRole.TEACHER))
    db_session.commit()

    # 1. Create a Course Room
    room_resp = teacher_client.post(
        f"/api/course/{course.id}/rooms",
        json={"name": "Main Physical Lab", "location": "Room 101", "assignment_id": assignment.id}
    )
    assert room_resp.status_code == 200
    room_id = room_resp.json()["id"]

    # 2. Create a nested Child Queue inside the Room
    queue_resp = teacher_client.post(f"/api/room/{room_id}/queues", json={"name": "Help Desk A"})
    assert queue_resp.status_code == 200
    queue_id = queue_resp.json()["id"]

    # 3. Fetch the Room Queue data
    get_queue_resp = teacher_client.get(f"/api/room/{room_id}/queue")
    assert get_queue_resp.status_code == 200
    data = get_queue_resp.json()
    assert data["room"]["name"] == "Main Physical Lab"
    assert len(data["queues"]) == 1
    assert data["queues"][0]["name"] == "Help Desk A"

    # 4. Close the Room (Should also close child queues)
    close_resp = teacher_client.post(f"/api/room/{room_id}/close")
    assert close_resp.status_code == 200

    # Verify in DB
    room = db_session.query(QueueRoom).get(room_id)
    child_queue = db_session.query(QueueRoom).get(queue_id)
    assert room.is_open is False
    assert child_queue.is_open is False


def test_course_room_has_no_implicit_queue(teacher_client, db_session, teacher_user):
    from app.models.db import Course, CourseEnrollment, UserRole, Assignment

    course = Course(name="Implicit Queue Course")
    db_session.add(course)
    db_session.commit()

    assignment = Assignment(name="Lab 1", course_id=course.id)
    db_session.add(assignment)
    db_session.commit()

    db_session.add(
        CourseEnrollment(user_id=teacher_user.id, course_id=course.id, role=UserRole.TEACHER))
    db_session.commit()

    room_resp = teacher_client.post(
        f"/api/course/{course.id}/rooms",
        json={"name": "Quiet Lab", "location": "B-201", "assignment_id": assignment.id}
    )
    assert room_resp.status_code == 200
    room_id = room_resp.json()["id"]

    queue_resp = teacher_client.get(f"/api/room/{room_id}/queue")
    assert queue_resp.status_code == 200

    data = queue_resp.json()
    assert data["room"]["name"] == "Quiet Lab"
    assert data["queues"] == []
    assert data["total_waiting"] == 0
    assert data["total_being_helped"] == 0


def test_room_queue_inherits_lab_and_opens_assignment(teacher_client, db_session, teacher_user):
    from app.models.db import Course, Assignment, CourseEnrollment, UserRole

    course = Course(name="Inherited Lab Course")
    db_session.add(course)
    db_session.commit()

    assignment = Assignment(name="Lab 7", course_id=course.id, queue_open=False)
    db_session.add(assignment)
    db_session.commit()

    db_session.add(
        CourseEnrollment(user_id=teacher_user.id, course_id=course.id, role=UserRole.TEACHER))
    db_session.commit()

    room_resp = teacher_client.post(
        f"/api/course/{course.id}/rooms",
        json={"name": "Lab 7 Room", "assignment_id": assignment.id}
    )
    assert room_resp.status_code == 200
    room_id = room_resp.json()["id"]

    queue_resp = teacher_client.post(
        f"/api/room/{room_id}/queues",
        json={"name": "Help Desk"}
    )
    assert queue_resp.status_code == 200
    assert queue_resp.json()["assignment_id"] == assignment.id

    db_session.refresh(assignment)
    assert assignment.queue_open is True


def test_room_queue_returns_questions_for_its_linked_lab(teacher_client, db_session, teacher_user):
    from app.models.db import Course, Assignment, Question, CourseEnrollment, UserRole

    course = Course(name="Queue Lab Mapping Course")
    db_session.add(course)
    db_session.commit()

    room_assignment = Assignment(name="Lab 1", course_id=course.id, queue_open=False)
    queue_assignment = Assignment(name="Lab 2", course_id=course.id, queue_open=False)
    db_session.add_all([room_assignment, queue_assignment])
    db_session.commit()

    db_session.add(
        CourseEnrollment(user_id=teacher_user.id, course_id=course.id, role=UserRole.TEACHER))
    db_session.commit()

    db_session.add_all([
        Question(
            assignment_id=room_assignment.id,
            question_number=1,
            problem_description="Room-level question",
            official_solution="A",
            hinting_strategy="A",
            require_signoff=True,
        ),
        Question(
            assignment_id=queue_assignment.id,
            question_number=3,
            problem_description="Queue-level signoff exercise",
            official_solution="B",
            hinting_strategy="B",
            require_signoff=True,
        ),
        Question(
            assignment_id=queue_assignment.id,
            question_number=4,
            problem_description="Non signoff exercise",
            official_solution="C",
            hinting_strategy="C",
            require_signoff=False,
        ),
    ])
    db_session.commit()

    room_resp = teacher_client.post(
        f"/api/course/{course.id}/rooms",
        json={"name": "Mapped Room", "assignment_id": room_assignment.id}
    )
    assert room_resp.status_code == 200
    room_id = room_resp.json()["id"]

    queue_resp = teacher_client.post(
        f"/api/room/{room_id}/queues",
        json={
            "name": "Sign-off",
            "assignment_id": queue_assignment.id,
            "is_signoff": True,
        }
    )
    assert queue_resp.status_code == 200

    get_queue_resp = teacher_client.get(f"/api/room/{room_id}/queue")
    assert get_queue_resp.status_code == 200

    data = get_queue_resp.json()
    assert data["assignments"] == [
        {"id": room_assignment.id, "name": "Lab 1"},
        {"id": queue_assignment.id, "name": "Lab 2"},
    ]
    assert data["queues"][0]["assignment_id"] == queue_assignment.id
    assert data["queues"][0]["assignment_name"] == "Lab 2"
    assert len(data["queues"][0]["questions"]) == 1
    assert data["queues"][0]["questions"][0]["question_number"] == 3
    assert data["queues"][0]["questions"][0]["description"] == "Queue-level signoff exercise"
    assert data["queues"][0]["questions"][0]["require_signoff"] is True


@patch("app.services.help_request_service.notify_tas_new_request")
def test_signoff_request_allows_blank_comment(
    mock_notify,
    auth_client,
    db_session,
    test_user,
):
    from app.models.db import Course, Assignment, Question, QueueRoom, CourseEnrollment, UserRole

    course = Course(name="Signoff Course")
    db_session.add(course)
    db_session.commit()

    assignment = Assignment(name="Lab 4", course_id=course.id, queue_open=False)
    db_session.add(assignment)
    db_session.commit()

    question = Question(
        assignment_id=assignment.id,
        question_number=1,
        problem_description="Check the final output",
        official_solution="All tests pass",
        hinting_strategy="Review the edge cases",
        require_signoff=True,
    )
    db_session.add(question)
    db_session.add(
        CourseEnrollment(user_id=test_user.id, course_id=course.id, role=UserRole.STUDENT))
    db_session.commit()

    room = QueueRoom(assignment_id=assignment.id, course_id=course.id, is_open=True, name="Lab 4 Room")
    db_session.add(room)
    db_session.commit()

    queue = QueueRoom(
        parent_room_id=room.id,
        assignment_id=assignment.id,
        is_open=True,
        is_signoff=True,
        name="Sign-off",
    )
    db_session.add(queue)
    db_session.commit()

    response = auth_client.post(
        "/api/student/help/submit",
        data={
            "student_comment": "",
            "submission_text": "All done",
            "question_id": question.id,
            "queue_room_id": queue.id,
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    mock_notify.assert_called_once()


# --- QUEUE ACTIONS (LEAVE & CALL NEXT) ---

def test_queue_student_leave(auth_client, db_session, test_user):
    from app.models.db import HelpRequest, RequestStatus, Question, Assignment, QueueRoom, Course

    # DB Setup for a dummy request
    course = Course(name="Test Course")
    db_session.add(course)
    db_session.commit()
    assignment = Assignment(name="Test Assignment", course_id=course.id)
    db_session.add(assignment)
    db_session.commit()
    question = Question(assignment_id=assignment.id, question_number=1, problem_description="X",
                        official_solution="Y", hinting_strategy="Z")
    room = QueueRoom(assignment_id=assignment.id, is_open=True, name="Test Room")
    db_session.add_all([question, room])
    db_session.commit()

    # Create an active request for the student
    req = HelpRequest(
        student_id=test_user.id, question_id=question.id, queue_room_id=room.id,
        status=RequestStatus.PENDING, queue_position=1, joined_queue_at=datetime.utcnow()
    )
    db_session.add(req)
    db_session.commit()

    # Student Leaves Queue
    resp = auth_client.post("/api/queue/leave")
    assert resp.status_code == 200

    # Verify state updated to resolved and position cleared
    db_session.refresh(req)
    assert req.status == RequestStatus.RESOLVED
    assert req.queue_position is None


def test_queue_ta_call_next(ta_client, db_session, ta_user, test_user):
    from app.models.db import HelpRequest, RequestStatus, Question, Assignment, QueueRoom, Course, \
        TAAssignment

    # DB Setup
    course = Course(name="Test Course 2")
    db_session.add(course)
    db_session.commit()
    assignment = Assignment(name="Test Assignment 2", course_id=course.id)
    db_session.add(assignment)
    db_session.commit()
    question = Question(assignment_id=assignment.id, question_number=1, problem_description="X",
                        official_solution="Y", hinting_strategy="Z")
    db_session.add(question)

    # Assign TA to course
    db_session.add(TAAssignment(ta_id=ta_user.id, course_id=course.id))
    db_session.commit()

    # Create an active, unassigned request
    req = HelpRequest(
        student_id=test_user.id, question_id=question.id,
        status=RequestStatus.PENDING, joined_queue_at=datetime.utcnow()
    )
    db_session.add(req)
    db_session.commit()

    # TA Calls Next
    resp = ta_client.post(f"/api/queue/call-next/{assignment.id}")
    assert resp.status_code == 200

    # Verify the request was assigned to the TA
    db_session.refresh(req)
    assert req.assigned_ta_id == ta_user.id
    assert req.started_helping_at is not None


# --- NOTIFICATIONS TEST ---

def test_get_notifications(auth_client):
    # Simply ensures the endpoint is wired up correctly and returns a 200 OK
    resp = auth_client.get("/api/notifications?limit=10")
    assert resp.status_code == 200

    # FIX: Check for the 'items' key which contains the list
    data = resp.json()
    assert "unread" in data
    assert isinstance(data["items"], list)


# ==========================================
# --- EDGE CASE & ERROR HANDLING TESTS ---
# ==========================================

# 1. Auth Edge Cases
def test_login_invalid_email_format(client):
    """Test that improperly formatted emails are rejected."""
    response = client.post("/api/auth/login", json={"email": "not-an-email"})
    assert response.status_code == 422
    assert "Invalid email address" in response.json()["detail"]


# 2. LLM Config Edge Cases
def test_llm_config_missing_required_fields(teacher_client):
    """Test that creating an LLM config without required fields fails."""
    # Missing 'api_key' and 'model_name'
    payload = {"name": "Test LLM", "base_url": "https://api.openai.com/v1"}
    response = teacher_client.post("/api/llm/configs", json=payload)
    assert response.status_code == 422
    assert "Missing field" in response.json()["detail"]


def test_update_nonexistent_llm_config(teacher_client):
    """Test updating an LLM config that does not exist."""
    response = teacher_client.put("/api/llm/configs/99999", json={"name": "Ghost LLM"})
    assert response.status_code == 404
    assert response.json()["detail"] == "LLM config not found"


# 3. Room & Queue Edge Cases
def test_duplicate_queue_room_name_rejected(teacher_client, db_session, teacher_user):
    """Test that creating two child queues with the same name in a room throws a 409 Conflict."""
    from app.models.db import Course, QueueRoom, CourseEnrollment, UserRole, Assignment

    # Setup Course and Parent Room
    course = Course(name="Edge Case Course")
    db_session.add(course)
    db_session.commit()

    assignment = Assignment(name="Lab 1", course_id=course.id, queue_open=True)
    db_session.add(assignment)
    db_session.commit()

    # FIX: Enroll the teacher in the course so they have access!
    db_session.add(
        CourseEnrollment(user_id=teacher_user.id, course_id=course.id, role=UserRole.TEACHER))
    db_session.commit()

    parent_room = QueueRoom(
        course_id=course.id, assignment_id=assignment.id, name="Parent Lab", is_open=True)
    db_session.add(parent_room)
    db_session.commit()

    # Create first child queue
    resp1 = teacher_client.post(f"/api/room/{parent_room.id}/queues", json={"name": "Help Desk"})
    assert resp1.status_code == 200

    # Attempt to create duplicate child queue
    resp2 = teacher_client.post(f"/api/room/{parent_room.id}/queues", json={"name": "Help Desk"})
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"]


# 4. Queue Interaction Edge Cases
def test_student_leave_empty_queue(auth_client):
    """Test a student trying to leave the queue when they aren't in one."""
    response = auth_client.post("/api/queue/leave")
    assert response.status_code == 404
    assert response.json()["detail"] == "Not in queue"


def test_ta_call_next_empty_queue(ta_client, db_session, ta_user):
    """Test a TA clicking 'Call Next' when nobody is in the queue."""
    from app.models.db import Course, Assignment, TAAssignment, Question

    course = Course(name="Empty Queue Course")
    db_session.add(course)
    db_session.commit()
    assignment = Assignment(name="Empty Queue Assignment", course_id=course.id)
    db_session.add(assignment)
    db_session.commit()
    db_session.add(Question(assignment_id=assignment.id, question_number=1, problem_description="X",
                            official_solution="Y", hinting_strategy="Z"))
    db_session.add(TAAssignment(ta_id=ta_user.id, course_id=course.id))
    db_session.commit()

    response = ta_client.post(f"/api/queue/call-next/{assignment.id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Queue is empty"


# 5. Help Request Edge Cases
def test_student_submit_invalid_file_extension(auth_client, db_session, test_user):
    """Test that students cannot upload disallowed file types (like .exe)."""
    from app.models.db import Course, Assignment, Question, QueueRoom, CourseEnrollment, UserRole

    # Quick Setup
    course = Course(name="Upload Course")
    db_session.add(course)
    db_session.commit()
    assignment = Assignment(name="Upload Assignment", course_id=course.id, queue_open=True)
    db_session.add(assignment)
    db_session.commit()
    question = Question(assignment_id=assignment.id, question_number=1, problem_description="X",
                        official_solution="Y", hinting_strategy="Z")
    room = QueueRoom(assignment_id=assignment.id, is_open=True, name="Upload Room")
    db_session.add_all([question, room])
    db_session.add(
        CourseEnrollment(user_id=test_user.id, course_id=course.id, role=UserRole.STUDENT))
    db_session.commit()

    # Create a dummy file with a disallowed extension
    files = {"attachment": ("virus.exe", b"malicious bytes", "application/x-msdownload")}
    data = {
        "student_comment": "Here is my code",
        "question_id": question.id,
        "queue_room_id": room.id
    }

    response = auth_client.post("/api/student/help/submit", data=data, files=files)
    assert response.status_code == 400
    assert "File type '.exe' is not allowed" in response.json()["detail"]


def test_ta_edit_empty_feedback(ta_client, active_help_request_id):
    """Test that a TA cannot submit empty feedback when editing a request."""
    # Attempt to edit with empty string
    response = ta_client.post(
        f"/api/ta/request/{active_help_request_id}/edit",
        json={"feedback": "   "}
    )
    assert response.status_code == 422
    assert "feedback is required" in response.json()["detail"]
