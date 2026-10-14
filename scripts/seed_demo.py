"""Create a fictional local demo. Does not import files or contact external services."""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
from app.models.db import (init_db, SessionLocal, User, UserRole, Course, Assignment,
    Question, CourseEnrollment, TAAssignment, QueueRoom, HelpRequest, RequestStatus,
    Session as HelpSession, FeedbackHistory)


def main():
    init_db()
    with SessionLocal() as db:
        if db.query(Course).filter_by(canvas_course_id="demo-workshop").first():
            print("Demo already exists; no data changed.")
            return
        instructor = User(email="teacher@example.com", name="Demo Instructor", role=UserRole.TEACHER)
        assistant = User(email="ta@example.com", name="Demo Assistant", role=UserRole.TA)
        learners = [User(email="student@example.com" if i == 0 else f"learner{i+1}@example.com",
                         name=f"Demo Learner {i+1}", role=UserRole.STUDENT) for i in range(8)]
        db.add_all([instructor, assistant, *learners]); db.flush()
        course = Course(canvas_course_id="demo-workshop", name="API Engineering Workshop", teacher_id=instructor.id)
        db.add(course); db.flush()
        task = Assignment(course_id=course.id, name="Build a Reliable Request Handler",
                          description="Fictional workshop for exploring feedback and queue workflows.",
                          queue_open=True, queue_opened_at=datetime.utcnow(), queue_opened_by=instructor.id)
        db.add(task); db.flush()
        question = Question(assignment_id=task.id, question_number=1, label="1",
            problem_description="Design a request handler that validates input and reports useful errors.",
            official_solution="Validate required fields, reject invalid values, and return a structured error response.",
            hinting_strategy="Ask which inputs are accepted and how a caller can recover from an error.")
        db.add(question)
        db.add(TAAssignment(ta_id=assistant.id, course_id=course.id))
        for learner in [assistant, *learners]:
            db.add(CourseEnrollment(user_id=learner.id, course_id=course.id, role=learner.role))
        room = QueueRoom(course_id=course.id, name="Workshop Support", location="Demo workspace",
                         is_open=True, opened_by=instructor.id, opened_at=datetime.utcnow())
        db.add(room); db.flush()
        queue = QueueRoom(parent_room_id=room.id, course_id=course.id, assignment_id=task.id,
                          name="API Help", is_open=True, opened_by=instructor.id, opened_at=datetime.utcnow())
        session = HelpSession(course_id=course.id, assignment_id=task.id, session_name="API Workshop",
                              started_by=instructor.id, active=True)
        db.add_all([queue, session]); db.flush()
        for i, learner in enumerate(learners):
            pending = i < 4
            created = datetime.utcnow() - timedelta(minutes=(i+1)*8)
            request = HelpRequest(student_id=learner.id, question_id=question.id,
                queue_room_id=queue.id, session_id=session.id,
                submission_text="def handle(payload):\n    return payload['message']",
                student_comment="How should I handle a missing message field?",
                status=RequestStatus.AI_GENERATED if pending else RequestStatus.RESOLVED,
                ai_feedback="Check whether the message field exists before accessing it. How should an invalid request be reported?",
                ai_generated_at=created + timedelta(seconds=10), created_at=created,
                queue_position=i+1 if pending else None, joined_queue_at=created,
                assigned_ta_id=None if pending else assistant.id,
                final_feedback=None if pending else "Validate the field and return a clear error when it is missing.",
                resolved_at=None if pending else created + timedelta(minutes=4))
            db.add(request); db.flush()
            if not pending:
                db.add(FeedbackHistory(help_request_id=request.id, ta_id=assistant.id,
                    action="approved", feedback_text=request.final_feedback,
                    created_at=request.resolved_at))
        db.commit()
    print("Demo ready: teacher@example.com / ta@example.com / student@example.com")


if __name__ == "__main__":
    main()
