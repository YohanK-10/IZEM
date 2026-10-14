from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Enum, Float, text, UniqueConstraint, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session, backref
from datetime import datetime, timedelta
import enum
from typing import Optional
import uuid
import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = "sqlite:///./ai_feedback_app.db"
DATABASE_URL = (os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL).strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+" not in DATABASE_URL.split("://", 1)[0]:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

IS_SQLITE = DATABASE_URL.startswith("sqlite")

DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "50"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "40"))
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
SQLITE_BUSY_TIMEOUT_MS = int(os.getenv("SQLITE_BUSY_TIMEOUT_MS", "30000"))

engine_kwargs = {
    "pool_size": DB_POOL_SIZE,
    "max_overflow": DB_MAX_OVERFLOW,
    "pool_timeout": DB_POOL_TIMEOUT,
    "pool_pre_ping": True,
}
if IS_SQLITE:
    engine_kwargs["connect_args"] = {
        "check_same_thread": False,
        "timeout": SQLITE_BUSY_TIMEOUT_MS / 1000,
    }

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


if IS_SQLITE:
    @event.listens_for(engine, "connect")
    def configure_sqlite_connection(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.close()

class UserRole(enum.Enum):
    STUDENT = "student"
    TA = "ta"
    TEACHER = "teacher"

class RequestStatus(enum.Enum):
    PENDING = "pending"
    AI_GENERATED = "ai_generated"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"
    IN_PERSON = "in_person"
    RESOLVED = "resolved"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    canvas_user_id = Column(String, unique=True, nullable=True)
    role = Column(Enum(UserRole, values_callable=lambda x: [e.value for e in x]), default=UserRole.STUDENT)
    canvas_api_token = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    auth_tokens = relationship("AuthToken", back_populates="user")
    courses_teaching = relationship("Course", back_populates="teacher")
    ta_assignments = relationship("TAAssignment", back_populates="ta")
    help_requests = relationship("HelpRequest", back_populates="student", foreign_keys="HelpRequest.student_id")
    reviewed_requests = relationship("HelpRequest", back_populates="assigned_ta", foreign_keys="HelpRequest.assigned_ta_id")

class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"))
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(hours=24))
    created_at = Column(DateTime, default=datetime.utcnow)
    used = Column(Boolean, default=False)

    user = relationship("User", back_populates="auth_tokens")

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    canvas_course_id = Column(String, unique=True, index=True)
    name = Column(String, nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"))
    hidden = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    teacher = relationship("User", back_populates="courses_teaching")
    assignments = relationship("Assignment", back_populates="course")
    ta_assignments = relationship("TAAssignment", back_populates="course")
    sessions = relationship("Session", back_populates="course")
    enrollments = relationship("CourseEnrollment", back_populates="course")

class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    canvas_assignment_id = Column(String, unique=True, nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id"))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    queue_open = Column(Boolean, default=False)  # Whether the queue is open for this assignment
    is_signoff = Column(Boolean, default=False, nullable=False, server_default="0")
    signoff_group_category_id = Column(Integer, ForeignKey("group_categories.id"), nullable=True)
    queue_opened_at = Column(DateTime, nullable=True)
    queue_closed_at = Column(DateTime, nullable=True)
    queue_opened_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    llm_config_id = Column(Integer, ForeignKey("llm_configs.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    course = relationship("Course", back_populates="assignments")
    questions = relationship("Question", back_populates="assignment")
    ta_assignments = relationship("TAAssignment", back_populates="assignment")
    queue_opener = relationship("User", foreign_keys=[queue_opened_by])
    queues = relationship("QueueRoom", back_populates="assignment")
    llm_config = relationship("LLMConfig", foreign_keys=[llm_config_id])

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"))
    question_number = Column(Integer, nullable=False)
    label = Column(String, nullable=True)   # e.g. "1", "1.1", "1-A"
    problem_description = Column(Text, nullable=False)
    official_solution = Column(Text, nullable=True)
    hinting_strategy = Column(Text, nullable=True)
    starter_file_content = Column(Text, nullable=True)
    require_signoff = Column(Boolean, default=False, nullable=False, server_default="0")
    created_at = Column(DateTime, default=datetime.utcnow)

    assignment = relationship("Assignment", back_populates="questions")
    help_requests = relationship("HelpRequest", back_populates="question")

class TAAssignment(Base):
    __tablename__ = "ta_assignments"
    __table_args__ = (
        UniqueConstraint('ta_id', 'course_id', 'assignment_id', name='uq_ta_course_assignment'),
    )

    id = Column(Integer, primary_key=True, index=True)
    ta_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    ta = relationship("User", back_populates="ta_assignments")
    course = relationship("Course", back_populates="ta_assignments")
    assignment = relationship("Assignment", back_populates="ta_assignments")

class HelpRequest(Base):
    __tablename__ = "help_requests"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    assigned_ta_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    submission_text = Column(Text, nullable=True)
    submission_image = Column(String, nullable=True)
    extracted_text = Column(Text, nullable=True)
    student_comment = Column(Text, nullable=True)
    status = Column(Enum(RequestStatus, values_callable=lambda x: [e.value for e in x]), default=RequestStatus.PENDING)
    ai_feedback = Column(Text, nullable=True)
    ai_progress_status = Column(String, nullable=True)
    ai_generated_at = Column(DateTime, nullable=True)
    ai_queue_state = Column(String, nullable=True)
    ai_queue_enqueued_at = Column(DateTime, nullable=True)
    ai_queue_started_at = Column(DateTime, nullable=True)
    ai_queue_error = Column(Text, nullable=True)
    final_feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    # Queue-related fields
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    queue_position = Column(Integer, nullable=True)
    joined_queue_at = Column(DateTime, nullable=True)
    started_helping_at = Column(DateTime, nullable=True)
    last_progress_update = Column(DateTime, nullable=True)
    queue_room_id = Column(Integer, ForeignKey("queue_rooms.id"), nullable=True)

    # Overtime: flagged when a queue closes with pending requests kept for later
    is_overtime = Column(Boolean, default=False, nullable=False, server_default="0")

    student = relationship("User", back_populates="help_requests", foreign_keys=[student_id])
    assigned_ta = relationship("User", back_populates="reviewed_requests", foreign_keys=[assigned_ta_id])
    question = relationship("Question", back_populates="help_requests")
    feedback_history = relationship("FeedbackHistory", back_populates="help_request")
    notifications = relationship("Notification", back_populates="help_request")
    queue_room = relationship("QueueRoom", back_populates="help_requests")

class FeedbackHistory(Base):
    __tablename__ = "feedback_history"

    id = Column(Integer, primary_key=True, index=True)
    help_request_id = Column(Integer, ForeignKey("help_requests.id"))
    ta_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String, nullable=False)
    feedback_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    help_request = relationship("HelpRequest", back_populates="feedback_history")
    ta = relationship("User")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    help_request_id = Column(Integer, ForeignKey("help_requests.id"), nullable=True)
    type = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    help_request = relationship("HelpRequest", back_populates="notifications")

class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"))
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=True)
    session_name = Column(String, nullable=False)
    started_by = Column(Integer, ForeignKey("users.id"))
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)
    active_llm_config_id = Column(Integer, ForeignKey("llm_configs.id"), nullable=True)

    course = relationship("Course")
    assignment = relationship("Assignment")
    starter = relationship("User")

class LLMConfig(Base):
    __tablename__ = "llm_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    base_url = Column(String, nullable=False)
    api_key = Column(String, nullable=False)
    model_name = Column(String, nullable=False)
    is_public = Column(Boolean, default=False)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User")

class CourseEnrollment(Base):
    __tablename__ = "course_enrollments"
    __table_args__ = (
        UniqueConstraint('user_id', 'course_id', 'role', name='uq_user_course_role'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), index=True)
    role = Column(Enum(UserRole, values_callable=lambda x: [e.value for e in x]), nullable=False)  # student or ta (teacher is on Course)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    course = relationship("Course", back_populates="enrollments")

class QueueRoom(Base):
    __tablename__ = "queue_rooms"
    __table_args__ = (
        UniqueConstraint('parent_room_id', 'name', name='uq_queue_room_name_per_parent'),
    )

    id = Column(Integer, primary_key=True, index=True)
    parent_room_id = Column(Integer, ForeignKey("queue_rooms.id"), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id"), index=True, nullable=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), index=True, nullable=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=True)
    is_open = Column(Boolean, default=False)
    is_signoff = Column(Boolean, default=False)
    opened_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    opened_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    assignment = relationship("Assignment", back_populates="queues")
    help_requests = relationship("HelpRequest", back_populates="queue_room")
    # Named queues within this room (child records)
    queues = relationship(
        "QueueRoom",
        backref=backref("parent_room", remote_side="QueueRoom.id"),
        foreign_keys="[QueueRoom.parent_room_id]",
    )

class SignoffFlow(Base):
    __tablename__ = "signoff_flows"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    course = relationship("Course")
    points = relationship("SignoffPoint", back_populates="flow", order_by="SignoffPoint.order", cascade="all, delete-orphan")


class SignoffPoint(Base):
    __tablename__ = "signoff_points"

    id = Column(Integer, primary_key=True, index=True)
    flow_id = Column(Integer, ForeignKey("signoff_flows.id"), nullable=False, index=True)
    label = Column(String, nullable=False)  # e.g. "AP-4.A"
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    flow = relationship("SignoffFlow", back_populates="points")
    records = relationship("SignoffRecord", back_populates="point", order_by="SignoffRecord.created_at")


class SignoffRecord(Base):
    __tablename__ = "signoff_records"

    id = Column(Integer, primary_key=True, index=True)
    point_id = Column(Integer, ForeignKey("signoff_points.id"), nullable=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    graded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, nullable=False)  # "signed_off" | "insufficient"
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    point = relationship("SignoffPoint", back_populates="records")
    question = relationship("Question")
    student = relationship("User", foreign_keys=[student_id])
    grader = relationship("User", foreign_keys=[graded_by])


class GroupCategory(Base):
    """A Canvas group category (e.g. 'Math', 'Programming') belonging to a course."""
    __tablename__ = "group_categories"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    canvas_group_category_id = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    course = relationship("Course")
    groups = relationship("Group", back_populates="category", cascade="all, delete-orphan")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("group_categories.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    canvas_group_id = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    course = relationship("Course")
    category = relationship("GroupCategory", back_populates="groups")
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (
        # A student can only be in one group per category
        UniqueConstraint('student_id', 'category_id', name='uq_student_category'),
    )

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("group_categories.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    group = relationship("Group", back_populates="members")
    category = relationship("GroupCategory")
    student = relationship("User")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
    # Ensure new columns exist in legacy SQLite DBs
    try:
        with engine.connect() as conn:
            course_columns = [row[1] for row in conn.execute(text("PRAGMA table_info(courses)"))]
            if 'hidden' not in course_columns:
                conn.execute(text("ALTER TABLE courses ADD COLUMN hidden BOOLEAN DEFAULT 0"))
                conn.commit()

            help_request_columns = [row[1] for row in conn.execute(text("PRAGMA table_info(help_requests)"))]
            if 'ai_generated_at' not in help_request_columns:
                conn.execute(text("ALTER TABLE help_requests ADD COLUMN ai_generated_at DATETIME"))
                conn.commit()
            if 'ai_queue_state' not in help_request_columns:
                conn.execute(text("ALTER TABLE help_requests ADD COLUMN ai_queue_state VARCHAR"))
                conn.commit()
            if 'ai_queue_enqueued_at' not in help_request_columns:
                conn.execute(text("ALTER TABLE help_requests ADD COLUMN ai_queue_enqueued_at DATETIME"))
                conn.commit()
            if 'ai_queue_started_at' not in help_request_columns:
                conn.execute(text("ALTER TABLE help_requests ADD COLUMN ai_queue_started_at DATETIME"))
                conn.commit()
            if 'ai_queue_error' not in help_request_columns:
                conn.execute(text("ALTER TABLE help_requests ADD COLUMN ai_queue_error TEXT"))
                conn.commit()

            qr_columns = [row[1] for row in conn.execute(text("PRAGMA table_info(queue_rooms)"))]
            if 'parent_room_id' not in qr_columns:
                conn.execute(text("ALTER TABLE queue_rooms ADD COLUMN parent_room_id INTEGER REFERENCES queue_rooms(id)"))
                conn.commit()

            # Issue 14: llm_config_id on assignments
            assign_columns = [row[1] for row in conn.execute(text("PRAGMA table_info(assignments)"))]
            if 'llm_config_id' not in assign_columns:
                conn.execute(text("ALTER TABLE assignments ADD COLUMN llm_config_id INTEGER REFERENCES llm_configs(id)"))
                conn.commit()

            # Issue 7: course_id on QueueRoom for direct filtering
            qr_columns2 = [row[1] for row in conn.execute(text("PRAGMA table_info(queue_rooms)"))]
            if 'course_id' not in qr_columns2:
                conn.execute(text("ALTER TABLE queue_rooms ADD COLUMN course_id INTEGER REFERENCES courses(id)"))
                conn.execute(text(
                    "UPDATE queue_rooms SET course_id = ("
                    "  SELECT a.course_id FROM assignments a WHERE a.id = queue_rooms.assignment_id"
                    ") WHERE assignment_id IS NOT NULL"
                ))
                conn.commit()

            # Issue 4: session_id on HelpRequest to record which lab session it came from
            hr_columns = [row[1] for row in conn.execute(text("PRAGMA table_info(help_requests)"))]
            if 'session_id' not in hr_columns:
                conn.execute(text("ALTER TABLE help_requests ADD COLUMN session_id INTEGER REFERENCES sessions(id)"))
                conn.commit()

            # Overtime: flag requests kept after queue close for course-level backlog
            hr_columns2 = [row[1] for row in conn.execute(text("PRAGMA table_info(help_requests)"))]
            if 'is_overtime' not in hr_columns2:
                conn.execute(text("ALTER TABLE help_requests ADD COLUMN is_overtime BOOLEAN NOT NULL DEFAULT 0"))
                conn.commit()

            # Question label field (e.g. "1", "1.1", "1-A")
            q_columns = [row[1] for row in conn.execute(text("PRAGMA table_info(questions)"))]
            if 'label' not in q_columns:
                conn.execute(text("ALTER TABLE questions ADD COLUMN label VARCHAR"))
                conn.commit()
                q_columns = [row[1] for row in conn.execute(text("PRAGMA table_info(questions)"))]
            if 'require_signoff' not in q_columns:
                conn.execute(text("ALTER TABLE questions ADD COLUMN require_signoff BOOLEAN NOT NULL DEFAULT 0"))
                conn.commit()

            # Sign-off lab flag on assignments
            a_columns = [row[1] for row in conn.execute(text("PRAGMA table_info(assignments)"))]
            if 'is_signoff' not in a_columns:
                conn.execute(text("ALTER TABLE assignments ADD COLUMN is_signoff BOOLEAN NOT NULL DEFAULT 0"))
                conn.commit()
            if 'signoff_group_category_id' not in a_columns:
                conn.execute(text("ALTER TABLE assignments ADD COLUMN signoff_group_category_id INTEGER REFERENCES group_categories(id)"))
                conn.commit()

            # is_signoff flag on queue_rooms
            qr_columns = [row[1] for row in conn.execute(text("PRAGMA table_info(queue_rooms)")).fetchall()]
            if 'is_signoff' not in qr_columns:
                conn.execute(text("ALTER TABLE queue_rooms ADD COLUMN is_signoff BOOLEAN NOT NULL DEFAULT 0"))
                conn.commit()

            # question_id on signoff_records + make point_id nullable (SQLite table recreation)
            sr_columns_info = conn.execute(text("PRAGMA table_info(signoff_records)")).fetchall()
            sr_column_names = [row[1] for row in sr_columns_info]
            # Check if point_id is still NOT NULL (notnull flag is index 3)
            point_id_info = next((row for row in sr_columns_info if row[1] == 'point_id'), None)
            needs_recreate = point_id_info is not None and point_id_info[3] == 1  # notnull=1
            if 'question_id' not in sr_column_names or needs_recreate:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS signoff_records_new (
                        id INTEGER PRIMARY KEY,
                        point_id INTEGER REFERENCES signoff_points(id),
                        question_id INTEGER REFERENCES questions(id),
                        student_id INTEGER NOT NULL REFERENCES users(id),
                        graded_by INTEGER NOT NULL REFERENCES users(id),
                        status VARCHAR NOT NULL,
                        comment TEXT,
                        created_at DATETIME
                    )
                """))
                existing = [row[1] for row in conn.execute(text("PRAGMA table_info(signoff_records_new)")).fetchall()]
                # Copy existing columns (question_id will be NULL for old rows)
                cols = [c for c in ['id', 'point_id', 'student_id', 'graded_by', 'status', 'comment', 'created_at'] if c in sr_column_names]
                cols_str = ', '.join(cols)
                conn.execute(text(f"INSERT INTO signoff_records_new ({cols_str}) SELECT {cols_str} FROM signoff_records"))
                conn.execute(text("DROP TABLE signoff_records"))
                conn.execute(text("ALTER TABLE signoff_records_new RENAME TO signoff_records"))
                conn.commit()

            # Issue 13: backfill CourseEnrollment from TAAssignment so enrollment
            # is queryable from one table for both students and TAs.
            ta_rows = conn.execute(text(
                "SELECT DISTINCT ta_id, course_id FROM ta_assignments"
            )).fetchall()
            for ta_id, course_id in ta_rows:
                exists = conn.execute(text(
                    "SELECT 1 FROM course_enrollments "
                    "WHERE user_id=:u AND course_id=:c AND role='ta'"
                ), {"u": ta_id, "c": course_id}).fetchone()
                if not exists:
                    conn.execute(text(
                        "INSERT INTO course_enrollments (user_id, course_id, role, created_at) "
                        "VALUES (:u, :c, 'ta', datetime('now'))"
                    ), {"u": ta_id, "c": course_id})
            conn.commit()

            # Group categories + updated groups/group_members schema
            tables = [row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]
            if 'group_categories' not in tables:
                conn.execute(text("""
                    CREATE TABLE group_categories (
                        id INTEGER PRIMARY KEY,
                        course_id INTEGER NOT NULL REFERENCES courses(id),
                        name VARCHAR NOT NULL,
                        canvas_group_category_id VARCHAR UNIQUE,
                        created_at DATETIME
                    )
                """))
                conn.commit()

            # Migrate groups table: add category_id, canvas_group_id if missing
            g_columns = [row[1] for row in conn.execute(text("PRAGMA table_info(groups)")).fetchall()]
            if 'category_id' not in g_columns:
                # Create a default "Imported" category per course for existing groups
                course_ids = conn.execute(text("SELECT DISTINCT course_id FROM groups")).fetchall()
                for (cid,) in course_ids:
                    conn.execute(text(
                        "INSERT INTO group_categories (course_id, name, created_at) VALUES (:c, 'Imported', datetime('now'))"
                    ), {"c": cid})
                conn.commit()
                conn.execute(text("ALTER TABLE groups ADD COLUMN category_id INTEGER REFERENCES group_categories(id)"))
                # Backfill: assign each group to its course's default category
                conn.execute(text("""
                    UPDATE groups SET category_id = (
                        SELECT id FROM group_categories WHERE course_id = groups.course_id LIMIT 1
                    ) WHERE category_id IS NULL
                """))
                conn.commit()
            if 'canvas_group_id' not in g_columns:
                conn.execute(text("ALTER TABLE groups ADD COLUMN canvas_group_id VARCHAR UNIQUE"))
                conn.commit()

            # Migrate group_members: add category_id if missing, replace old unique constraint
            gm_columns = [row[1] for row in conn.execute(text("PRAGMA table_info(group_members)")).fetchall()]
            if 'category_id' not in gm_columns:
                conn.execute(text("""
                    CREATE TABLE group_members_new (
                        id INTEGER PRIMARY KEY,
                        group_id INTEGER NOT NULL REFERENCES groups(id),
                        category_id INTEGER NOT NULL REFERENCES group_categories(id),
                        student_id INTEGER NOT NULL REFERENCES users(id),
                        created_at DATETIME,
                        UNIQUE(student_id, category_id)
                    )
                """))
                conn.execute(text("""
                    INSERT INTO group_members_new (id, group_id, category_id, student_id, created_at)
                    SELECT gm.id, gm.group_id, g.category_id, gm.student_id, gm.created_at
                    FROM group_members gm
                    JOIN groups g ON g.id = gm.group_id
                    WHERE g.category_id IS NOT NULL
                """))
                conn.execute(text("DROP TABLE group_members"))
                conn.execute(text("ALTER TABLE group_members_new RENAME TO group_members"))
                conn.commit()

    except Exception as e:
        logger.warning(f"Schema migration: {e}")
