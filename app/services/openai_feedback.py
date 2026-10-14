import requests
from typing import Dict, Optional
import json
import logging
from datetime import datetime
import os
from sqlalchemy.orm import Session
from app.models.db import SessionLocal, HelpRequest, Question, Assignment, Course, Session as HelpSession, LLMConfig, RequestStatus
from app.services.feedback_formatting import format_feedback_text

logger = logging.getLogger(__name__)

class FeedbackGenerator:
    def __init__(self):
        # No fallback LLM – sessions must select an LLM explicitly
        self.fallback_api_url = None
        self.fallback_api_key = None
        self.fallback_model_name = None
        self.mock_mode = os.getenv("MOCK_LLM_MODE", "false").lower() in ("1", "true", "yes")

    def _get_llm_config_from_request(self, help_request_id: int, db: Session) -> Optional[Dict]:
        """Get the LLM configuration from the active help session for this request"""
        try:
            # Get the help request
            help_request = db.query(HelpRequest).filter(HelpRequest.id == help_request_id).first()
            if not help_request:
                return None

            # Get the question and assignment
            question = db.query(Question).filter(Question.id == help_request.question_id).first()
            if not question:
                return None

            assignment = db.query(Assignment).filter(Assignment.id == question.assignment_id).first()
            if not assignment:
                return None

            # Get the active help session for this assignment (prefer assignment-specific),
            # falling back to course-level if needed
            active_session = db.query(HelpSession).filter(
                HelpSession.assignment_id == assignment.id,
                HelpSession.active == True
            ).first()
            if not active_session:
                active_session = db.query(HelpSession).filter(
                    HelpSession.course_id == assignment.course_id,
                    HelpSession.active == True
                ).first()

            # Try active session LLM config first
            llm_config = None
            if active_session and active_session.active_llm_config_id:
                llm_config = db.query(LLMConfig).filter(LLMConfig.id == active_session.active_llm_config_id).first()

            # Fallback 1: assignment-level llm_config_id
            if not llm_config and assignment.llm_config_id:
                llm_config = db.query(LLMConfig).filter(LLMConfig.id == assignment.llm_config_id).first()

            # Fallback 2: any public LLM config
            if not llm_config:
                llm_config = db.query(LLMConfig).filter(LLMConfig.is_public == True).first()

            if not llm_config:
                logger.info(f"No LLM configured for assignment {assignment.id} or course {assignment.course_id}")
                return None

            logger.info(f"Using configured LLM: {llm_config.name}")
            return {
                "base_url": llm_config.base_url,
                "api_key": llm_config.api_key,
                "model_name": llm_config.model_name
            }

        except Exception as e:
            logger.error(f"Error getting LLM config from request: {e}")
            return None

    def generate_feedback_background(self, help_request_id: int) -> Dict:
        """Background-task-safe wrapper that creates its own DB session"""
        db = SessionLocal()
        try:
            return self.generate_feedback(help_request_id, db)
        except Exception as e:
            logger.error(f"Background AI feedback failed for request {help_request_id}: {e}")
            return {"ok": False, "message": str(e)}
        finally:
            db.close()

    def _persist_fallback_feedback(
        self,
        help_request: HelpRequest,
        db: Session,
        *,
        progress_status: str,
        detected_issues: list[str],
        suggested_direction: str,
        raw_feedback: str,
    ) -> Dict:
        ai_generated_at = datetime.utcnow()
        feedback = {
            "progress_status": progress_status,
            "detected_issues": detected_issues,
            "suggested_direction": suggested_direction,
            "raw_feedback": raw_feedback,
        }

        help_request.ai_feedback = format_feedback_text(feedback) or suggested_direction
        help_request.ai_progress_status = self._normalize_progress_status(progress_status)
        help_request.status = RequestStatus.AI_GENERATED
        help_request.ai_generated_at = ai_generated_at
        help_request.ai_queue_state = None
        help_request.ai_queue_enqueued_at = None
        help_request.ai_queue_started_at = None
        help_request.ai_queue_error = None
        help_request.last_progress_update = ai_generated_at
        db.commit()

        feedback["ok"] = True
        return feedback

    def generate_feedback(self,
                         help_request_id: int,
                         db: Session) -> Dict:
        """Generate feedback using the LLM configuration from the active help session"""

        # Get the help request and related data
        help_request = db.query(HelpRequest).filter(HelpRequest.id == help_request_id).first()
        if not help_request:
            return {"ok": False, "message": "Help request not found"}
        if help_request.status != RequestStatus.PENDING:
            return {"ok": False, "message": f"Request is already {help_request.status.value}"}

        question = db.query(Question).filter(Question.id == help_request.question_id).first()
        if not question:
            return {"ok": False, "message": "Question not found"}

        # Get LLM configuration from active session unless mock mode is enabled
        llm_config = None if self.mock_mode else self._get_llm_config_from_request(help_request_id, db)
        if not self.mock_mode and (
            not llm_config
            or not llm_config.get("api_key")
            or not llm_config.get("base_url")
            or not llm_config.get("model_name")
        ):
            now = datetime.utcnow()
            help_request.ai_progress_status = "error"
            help_request.ai_feedback = None
            help_request.ai_queue_state = "failed"
            help_request.ai_queue_error = "No LLM configured for this session"
            help_request.ai_queue_started_at = None
            help_request.last_progress_update = now
            db.commit()
            return {"ok": False, "message": "No LLM configured for this session"}

        prompt = self._create_feedback_prompt(
            question.problem_description,
            question.official_solution,
            question.hinting_strategy,
            help_request.submission_text or help_request.extracted_text or "",
            help_request.student_comment
        )

        try:
            if self.mock_mode:
                feedback_data = self._build_mock_feedback(question, help_request)
            else:
                response = self._call_llm(prompt, llm_config)
                feedback_data = self._parse_feedback_response(response)

            # Update the help request with AI feedback
            db.refresh(help_request)
            if help_request.status != RequestStatus.PENDING:
                help_request.ai_queue_state = None
                help_request.ai_queue_enqueued_at = None
                help_request.ai_queue_started_at = None
                help_request.ai_queue_error = None
                db.commit()
                return {"ok": False, "message": "Request was resolved before AI feedback completed"}

            ai_generated_at = datetime.utcnow()
            help_request.ai_feedback = (
                format_feedback_text(feedback_data)
                or feedback_data.get("suggested_direction", "")
            )
            help_request.ai_progress_status = self._normalize_progress_status(
                feedback_data.get("progress_status")
            )
            help_request.status = RequestStatus.AI_GENERATED
            help_request.ai_generated_at = ai_generated_at
            help_request.ai_queue_state = None
            help_request.ai_queue_enqueued_at = None
            help_request.ai_queue_started_at = None
            help_request.ai_queue_error = None
            help_request.last_progress_update = ai_generated_at
            db.commit()
            feedback_data["ok"] = True
            return feedback_data

        except Exception as e:
            logger.error(f"Error generating feedback for request {help_request_id}: {e}")
            db.rollback()
            latest_request = db.query(HelpRequest).filter(HelpRequest.id == help_request_id).first()
            if latest_request and latest_request.status == RequestStatus.PENDING:
                now = datetime.utcnow()
                latest_request.ai_progress_status = "error"
                latest_request.ai_feedback = None
                latest_request.ai_queue_state = "failed"
                latest_request.ai_queue_started_at = None
                latest_request.ai_queue_error = str(e)[:1000]
                latest_request.last_progress_update = now
                db.commit()
            return {"ok": False, "message": str(e)}

    def _build_mock_feedback(self, question: Question, help_request: HelpRequest) -> Dict:
        snippet = (help_request.student_comment or help_request.submission_text or "").strip()
        snippet = " ".join(snippet.split())[:140]
        if not snippet:
            snippet = "The student has not shared much context yet."

        feedback = {
            "progress_status": "minor_issues",
            "student_reasoning": "The student has started a plausible approach but still needs help checking intermediate steps.",
            "detected_issues": [
                "The current approach needs a smaller hand-worked example to validate the logic.",
                "The student should compare intermediate state against the intended invariant."
            ],
            "what_they_did_right": [
                "They selected the correct question for this request.",
                "They supplied enough context for a TA to continue the review."
            ],
            "suggested_direction": (
                "Ask the student to run one tiny example, note each intermediate state, "
                "and identify the first place where the result diverges from expectations."
            ),
            "key_concepts": [
                "State tracing",
                "Boundary conditions",
                "Debugging with smaller examples"
            ],
            "source_excerpt": snippet,
        }
        feedback["raw_feedback"] = json.dumps(feedback)
        return feedback

    def _normalize_progress_status(self, status: Optional[str]) -> str:
        mapping = {
            "on_track": "on_track",
            "almost_there": "on_track",
            "minor_issues": "minor_issues",
            "making_progress": "minor_issues",
            "early_stage": "minor_issues",
            "stuck": "stuck",
            "off_track": "stuck",
        }
        return mapping.get((status or "").strip().lower(), "minor_issues")

    def _create_feedback_prompt(self,
                               problem_description: str,
                               official_solution: str,
                               hinting_strategy: str,
                               student_submission: str,
                               student_comment: Optional[str] = None) -> str:

        comment_section = f"\nStudent's comment: {student_comment}" if student_comment else ""

        return f"""You are an educational AI assistant helping TAs provide feedback to students.
Your task is to analyze a student's submission and generate helpful, non-solution feedback.

CRITICAL RULES:
1. NEVER reveal the solution or any part of it
2. NEVER write code for the student
3. Focus on guiding the student to discover the solution themselves
4. Be encouraging and constructive

Problem Description:
{problem_description}

Official Solution (DO NOT REVEAL THIS):
{official_solution}

Hinting Strategy:
{hinting_strategy}

Student's Submission:
{student_submission}
{comment_section}

Please analyze the submission and provide:
1. Progress Status: One of [early_stage, making_progress, almost_there, off_track]
2. Student Reasoning: Explain what approach the student is taking and their thought process
3. Detected Issues: List specific problems, errors, or misconceptions
4. What They Did Right: Acknowledge correct parts of their approach
5. Suggested Direction: Provide specific guidance without revealing the solution
6. Key Concepts: Identify concepts the student needs to understand better

Format your response as JSON:
{{
    "progress_status": "...",
    "student_reasoning": "...",
    "detected_issues": ["issue1", "issue2", ...],
    "what_they_did_right": ["correct1", "correct2", ...],
    "suggested_direction": "...",
    "key_concepts": ["concept1", "concept2", ...]
}}"""

    def _strip_thinking_tags(self, text: str) -> str:
        """Strip <think>...</think> tags from reasoning model responses"""
        import re
        # Remove <think>...</think> blocks (greedy, handles multiline)
        stripped = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        # Also handle unclosed <think> tag (response cut off during thinking)
        stripped = re.sub(r'<think>.*', '', stripped, flags=re.DOTALL).strip()
        return stripped if stripped else text

    def _call_llm(self, prompt: str, llm_config: Dict) -> str:
        payload = {
            "model": llm_config["model_name"],
            "messages": [
                {"role": "system", "content": "You are a helpful educational assistant. Always respond with valid JSON when asked to format your response as JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2048
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {llm_config['api_key']}"
        }

        response = requests.post(
            f"{llm_config['base_url'].rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()

        raw_content = response.json()["choices"][0]["message"]["content"]
        return self._strip_thinking_tags(raw_content)

    def _parse_feedback_response(self, response: str) -> Dict:
        try:
            import re
            response = response.strip()
            # Strip thinking tags if any remain
            response = self._strip_thinking_tags(response)
            # Strip markdown code fences
            if response.startswith("```json"):
                response = response[7:]
            elif response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            # Try to extract JSON object if there's surrounding text
            if not response.startswith("{"):
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    response = match.group(0)

            feedback = json.loads(response.strip())

            if "progress_status" not in feedback:
                feedback["progress_status"] = "minor_issues"
            if "student_reasoning" not in feedback:
                feedback["student_reasoning"] = "Unable to determine student's approach"
            if "detected_issues" not in feedback:
                feedback["detected_issues"] = []
            if "what_they_did_right" not in feedback:
                feedback["what_they_did_right"] = []
            if "suggested_direction" not in feedback:
                feedback["suggested_direction"] = "Please review your work and try again."
            if "key_concepts" not in feedback:
                feedback["key_concepts"] = []
            feedback["progress_status"] = self._normalize_progress_status(
                feedback.get("progress_status")
            )

            feedback["raw_feedback"] = response

            return feedback
        except json.JSONDecodeError:
            return {
                "progress_status": "minor_issues",
                "detected_issues": ["Failed to parse AI response"],
                "suggested_direction": response[:500],
                "raw_feedback": response
            }

# Create a global instance for backward compatibility
feedback_generator = FeedbackGenerator()
