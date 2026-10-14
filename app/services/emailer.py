import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import os
from datetime import datetime
from html import escape as html_escape
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv("EMAIL_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("EMAIL_PORT", "587"))
        self.email_user = os.getenv("EMAIL_USER", "")
        self.email_pass = os.getenv("EMAIL_PASS", "")
        self.app_url = os.getenv("APP_URL", "http://localhost:8000")

    def send_email(self, to_email: str, subject: str, body_html: str, body_text: Optional[str] = None):
        if not self.email_user or not self.email_pass:
            logger.info(f"Email service not configured. Would have sent email to {to_email}")
            return False

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.email_user
        msg['To'] = to_email

        text_part = MIMEText(body_text or body_html, 'plain')
        html_part = MIMEText(body_html, 'html')

        msg.attach(text_part)
        msg.attach(html_part)

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_user, self.email_pass)
                server.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_magic_link(self, to_email: str, token: str):
        magic_link = f"{self.app_url}/auth/verify?token={token}"

        subject = "Your IZEM login link"

        body_html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2>Welcome to IZEM</h2>
                <p>Click the link below to log in:</p>
                <p style="margin: 20px 0;">
                    <a href="{magic_link}"
                       style="background-color: #4CAF50; color: white; padding: 14px 20px;
                              text-decoration: none; border-radius: 4px; display: inline-block;">
                        Log In
                    </a>
                </p>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #666;">{magic_link}</p>
                <p style="color: #666; font-size: 14px; margin-top: 30px;">
                    This link will expire in 30 minutes. If you didn't request this email,
                    you can safely ignore it.
                </p>
            </body>
        </html>
        """

        body_text = f"""
        Welcome to IZEM

        Click this link to log in:
        {magic_link}

        This link will expire in 30 minutes. If you didn't request this email, you can safely ignore it.
        """

        return self.send_email(to_email, subject, body_html, body_text)

    def send_feedback_ready_notification(self, to_email: str, student_name: str,
                                       assignment_name: str, question_number: int):
        subject = "Feedback available - IZEM"
        safe_name = html_escape(student_name)
        safe_assignment = html_escape(assignment_name)

        body_html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2>Your feedback is ready!</h2>
                <p>Hi {safe_name},</p>
                <p>A TA has reviewed and approved feedback for your submission:</p>
                <ul>
                    <li><strong>Assignment:</strong> {safe_assignment}</li>
                    <li><strong>Question:</strong> {question_number}</li>
                </ul>
                <p>
                    <a href="{self.app_url}/student-home"
                       style="background-color: #2196F3; color: white; padding: 10px 20px;
                              text-decoration: none; border-radius: 4px; display: inline-block;">
                        View Feedback
                    </a>
                </p>
            </body>
        </html>
        """

        return self.send_email(to_email, subject, body_html)

    def send_overtime_feedback_email(
        self,
        to_email: str,
        student_name: str,
        assignment_name: str,
        question_number: int,
        feedback_text: str,
        ta_name: str,
    ):
        """Send the actual feedback content to a student for an overtime (at-home) request."""
        subject = f"Your feedback for {assignment_name} – IZEM"
        safe_name = html_escape(student_name)
        safe_assignment = html_escape(assignment_name)
        safe_ta = html_escape(ta_name)
        safe_feedback = html_escape(feedback_text).replace("\n", "<br>")

        body_html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #1a1a1a;">
                <h2 style="color: #2563eb;">Feedback ready – {safe_assignment}</h2>
                <p>Hi {safe_name},</p>
                <p>A TA has reviewed your submission for <strong>{safe_assignment}</strong>, Question {question_number}.</p>
                <p>Here is their feedback:</p>
                <div style="background: #f0f9ff; border-left: 4px solid #2563eb; padding: 16px 20px;
                            border-radius: 4px; margin: 20px 0; white-space: pre-wrap;">
                    {safe_feedback}
                </div>
                <p style="color: #6b7280; font-size: 13px;">Reviewed by {safe_ta}</p>
                <p>
                    <a href="{self.app_url}/student-home"
                       style="background-color: #2563eb; color: white; padding: 10px 20px;
                              text-decoration: none; border-radius: 6px; display: inline-block;">
                        View in IZEM
                    </a>
                </p>
                <p style="color: #9ca3af; font-size: 12px; margin-top: 30px;">
                    You are receiving this because you submitted a help request during a lab session.
                </p>
            </body>
        </html>
        """

        body_text = (
            f"Feedback ready – {assignment_name}\n\n"
            f"Hi {student_name},\n\n"
            f"A TA has reviewed your submission for {assignment_name}, Question {question_number}.\n\n"
            f"Feedback:\n{feedback_text}\n\n"
            f"Reviewed by {ta_name}\n\n"
            f"View in IZEM: {self.app_url}/student-home"
        )

        return self.send_email(to_email, subject, body_html, body_text)

    def send_ta_new_request_notification(self, to_email: str, ta_name: str,
                                       student_name: str, assignment_name: str):
        subject = "New help request - IZEM"
        safe_ta = html_escape(ta_name)
        safe_student = html_escape(student_name)
        safe_assignment = html_escape(assignment_name)

        body_html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2>New help request in your queue</h2>
                <p>Hi {safe_ta},</p>
                <p>A new help request has been submitted:</p>
                <ul>
                    <li><strong>Student:</strong> {safe_student}</li>
                    <li><strong>Assignment:</strong> {safe_assignment}</li>
                </ul>
                <p>
                    <a href="{self.app_url}/ta-dashboard"
                       style="background-color: #FF9800; color: white; padding: 10px 20px;
                              text-decoration: none; border-radius: 4px; display: inline-block;">
                        Review Request
                    </a>
                </p>
            </body>
        </html>
        """

        return self.send_email(to_email, subject, body_html)

email_service = EmailService()
