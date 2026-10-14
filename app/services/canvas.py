import requests
from typing import List, Dict, Optional
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class CanvasAPIClient:
    def __init__(self, api_token: Optional[str] = None):
        self.base_url = os.getenv("CANVAS_API_BASE", "https://canvas.example.com")
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        } if self.api_token else {}
        logger.debug(f"Canvas client initialized with base_url: {self.base_url}")

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        url = f"{self.base_url}/api/v1{endpoint}"
        response = requests.request(method, url, headers=self.headers, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_courses(self) -> List[Dict]:
        try:
            params = {
                "enrollment_type": "teacher",
                "per_page": 100
            }
            logger.debug(f"Fetching courses with params: {params}")
            courses = self._make_request("GET", "/courses", params=params)
            logger.debug(f"Found {len(courses)} courses")
            return courses
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error fetching courses: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching courses: {e}")
            return []

    def get_course_users(self, course_id: str, enrollment_type: Optional[str] = None) -> List[Dict]:
        try:
            params = {"per_page": 100}
            if enrollment_type:
                params["enrollment_type[]"] = enrollment_type

            users = []
            page = 1
            while True:
                params["page"] = page
                response = self._make_request("GET", f"/courses/{course_id}/users", params=params)
                if not response:
                    break
                users.extend(response)
                page += 1
                if len(response) < 100:
                    break

            return users
        except Exception as e:
            logger.error(f"Error fetching course users: {e}")
            return []

    def get_assignments(self, course_id: str) -> List[Dict]:
        try:
            assignments = []
            page = 1
            while True:
                batch = self._make_request("GET", f"/courses/{course_id}/assignments", params={
                    "per_page": 100,
                    "order_by": "due_at",
                    "page": page,
                })
                if not batch:
                    break
                assignments.extend(batch)
                if len(batch) < 100:
                    break
                page += 1
            return assignments
        except Exception as e:
            logger.error(f"Error fetching assignments: {e}")
            return []

    def get_assignment_details(self, course_id: str, assignment_id: str) -> Optional[Dict]:
        try:
            assignment = self._make_request("GET", f"/courses/{course_id}/assignments/{assignment_id}")
            return assignment
        except Exception as e:
            logger.error(f"Error fetching assignment details: {e}")
            return None

    def get_user_profile(self) -> Optional[Dict]:
        try:
            profile = self._make_request("GET", "/users/self/profile")
            return profile
        except Exception as e:
            logger.error(f"Error fetching user profile: {e}")
            return None

    def validate_token(self) -> bool:
        try:
            profile = self.get_user_profile()
            return profile is not None
        except Exception:
            return False

    def get_students_for_assignment(self, course_id: str, assignment_id: str) -> List[Dict]:
        try:
            students = self.get_course_users(course_id, enrollment_type="student")

            submissions = self._make_request("GET",
                f"/courses/{course_id}/assignments/{assignment_id}/submissions",
                params={"include[]": "user", "per_page": 100}
            )

            student_map = {s['id']: s for s in students}
            for submission in submissions:
                if submission.get('user_id') in student_map:
                    student_map[submission['user_id']]['submission'] = submission

            return list(student_map.values())
        except Exception as e:
            logger.error(f"Error fetching students for assignment: {e}")
            return []

    def identify_tas(self, course_id: str) -> List[Dict]:
        tas = self.get_course_users(course_id, enrollment_type="ta")
        return tas

    def check_student_enrollment(self, course_id: str, student_email: str) -> bool:
        """Check if a student is enrolled in a Canvas course"""
        try:
            students = self.get_course_users(course_id, enrollment_type="student")
            return any(s.get("email", "").lower() == student_email.lower() for s in students)
        except Exception as e:
            logger.error(f"Error checking enrollment: {e}")
            return False

    def get_group_categories(self, course_id: str) -> List[Dict]:
        """Get all group categories (group sets) for a course."""
        try:
            return self._make_request("GET", f"/courses/{course_id}/group_categories", params={"per_page": 100})
        except Exception as e:
            logger.error(f"Error fetching group categories: {e}")
            return []

    def get_groups_in_category(self, category_id: str) -> List[Dict]:
        """Get all groups in a group category."""
        try:
            groups = []
            page = 1
            while True:
                batch = self._make_request("GET", f"/group_categories/{category_id}/groups", params={"per_page": 100, "page": page})
                if not batch:
                    break
                groups.extend(batch)
                if len(batch) < 100:
                    break
                page += 1
            return groups
        except Exception as e:
            logger.error(f"Error fetching groups in category {category_id}: {e}")
            return []

    def get_group_members(self, group_id: str) -> List[Dict]:
        """Get all members of a group."""
        try:
            return self._make_request("GET", f"/groups/{group_id}/users", params={"per_page": 100})
        except Exception as e:
            logger.error(f"Error fetching group members for group {group_id}: {e}")
            return []

    def get_enrolled_courses(self, user_email: str) -> List[str]:
        """Get list of Canvas course IDs where the user is enrolled as a student"""
        try:
            courses = self._make_request("GET", "/courses", params={
                "enrollment_type": "student",
                "per_page": 100
            })
            enrolled_course_ids = [str(c["id"]) for c in courses]
            return enrolled_course_ids
        except Exception as e:
            logger.error(f"Error fetching enrolled courses: {e}")
            return []
