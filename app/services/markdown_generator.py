import json
from datetime import datetime
from typing import Dict, List, Optional
from io import StringIO

class MarkdownReportGenerator:
    def generate_assignment_report(self, assignment: Dict, questions: List[Dict],
                                 help_requests: List[Dict]) -> str:
        """Generate a Markdown report for an assignment"""
        md = StringIO()

        # Title
        md.write(f"# {assignment['name']}\n\n")

        md.write(f"*Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}*\n\n")

        # Questions Overview
        md.write("## Questions Overview\n\n")
        md.write("| Question # | Description | Help Requests |\n")
        md.write("|------------|-------------|---------------|\n")

        for q in questions:
            request_count = len([r for r in help_requests if r['question_id'] == q['id']])
            desc = q['problem_description'][:100] + '...' if len(q['problem_description']) > 100 else q['problem_description']
            desc = desc.replace('\n', ' ')
            md.write(f"| {q['question_number']} | {desc} | {request_count} |\n")

        md.write("\n")

        # Detailed Questions
        md.write("## Question Details\n\n")

        for q in questions:
            md.write(f"### Question {q['question_number']}\n\n")
            md.write("**Problem Description:**\n\n")
            md.write(f"{q['problem_description']}\n\n")

            if q.get('hinting_strategy'):
                md.write("**Hinting Strategy:**\n\n")
                md.write(f"{q['hinting_strategy']}\n\n")

            md.write("---\n\n")

        return md.getvalue()

    def generate_help_request_report(self, help_request: Dict, student: Dict,
                                   question: Dict, assignment: Dict) -> str:
        """Generate a Markdown report for a help request"""
        md = StringIO()

        # Title
        md.write(f"# Help Request #{help_request['id']}\n\n")

        # Student Info
        md.write("## Student Information\n\n")
        md.write(f"- **Name:** {student['name']}\n")
        md.write(f"- **Email:** {student['email']}\n")
        md.write(f"- **Submitted:** {help_request['created_at'].strftime('%B %d, %Y at %I:%M %p')}\n\n")

        # Assignment & Question
        md.write("## Assignment Details\n\n")
        md.write(f"- **Assignment:** {assignment['name']}\n")
        md.write(f"- **Question:** {question['question_number']}\n\n")

        # Problem Description
        md.write("### Problem Description\n\n")
        md.write(f"{question['problem_description']}\n\n")

        # Student Submission
        if help_request.get('submission_text'):
            md.write("## Student's Code\n\n")
            md.write("```python\n")
            md.write(help_request['submission_text'])
            md.write("\n```\n\n")

        if help_request.get('student_comment'):
            md.write("## Student's Comment\n\n")
            md.write(f"{help_request['student_comment']}\n\n")

        # AI Feedback
        if help_request.get('ai_feedback'):
            md.write("## AI Analysis\n\n")

            try:
                ai_data = json.loads(help_request['ai_feedback'])

                if ai_data.get('student_reasoning'):
                    md.write("### Student's Approach\n\n")
                    md.write(f"{ai_data['student_reasoning']}\n\n")

                if ai_data.get('what_they_did_right'):
                    md.write("### What They Did Right\n\n")
                    for item in ai_data['what_they_did_right']:
                        md.write(f"- {item}\n")
                    md.write("\n")

                if ai_data.get('detected_issues'):
                    md.write("### Issues Detected\n\n")
                    for item in ai_data['detected_issues']:
                        md.write(f"- {item}\n")
                    md.write("\n")

                if ai_data.get('key_concepts'):
                    md.write("### Key Concepts to Review\n\n")
                    for item in ai_data['key_concepts']:
                        md.write(f"- {item}\n")
                    md.write("\n")

                if ai_data.get('suggested_direction'):
                    md.write("### Suggested Feedback\n\n")
                    md.write(f"{ai_data['suggested_direction']}\n\n")
            except (json.JSONDecodeError, KeyError, TypeError):
                md.write(f"{help_request['ai_feedback']}\n\n")

        # Final Feedback
        if help_request.get('final_feedback'):
            md.write("## Final Feedback to Student\n\n")
            md.write(f"{help_request['final_feedback']}\n\n")

        # Status
        md.write("## Status\n\n")
        status_map = {
            'pending': 'Pending AI Generation',
            'ai_generated': 'AI Feedback Generated',
            'approved': 'Approved by Teacher/TA',
            'edited': 'Edited by Teacher/TA',
            'in_person': 'In-Person Help Required'
        }
        md.write(f"**Current Status:** {status_map.get(help_request['status'], help_request['status'])}\n")

        return md.getvalue()

    def generate_analytics_report(self, course: Dict, analytics_data: Dict) -> str:
        """Generate analytics report for a course"""
        md = StringIO()

        # Title
        md.write(f"# Analytics Report: {course['name']}\n\n")
        md.write(f"*Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}*\n\n")

        # Summary Statistics
        md.write("## Summary Statistics\n\n")
        md.write("| Metric | Value |\n")
        md.write("|--------|-------|\n")
        md.write(f"| Total Help Requests | {analytics_data.get('total_requests', 0)} |\n")
        md.write(f"| Average Response Time | {analytics_data.get('avg_response_time', 'N/A')} |\n")
        md.write(f"| AI Approval Rate | {analytics_data.get('ai_approval_rate', 0):.1f}% |\n")
        md.write(f"| Active Students | {analytics_data.get('active_students', 0)} |\n")
        md.write(f"| Active TAs | {analytics_data.get('active_tas', 0)} |\n\n")

        # Additional sections can be added here
        if analytics_data.get('by_assignment'):
            md.write("## Breakdown by Assignment\n\n")
            md.write("| Assignment | Requests | Avg Response Time |\n")
            md.write("|------------|----------|-------------------|\n")
            for assignment, data in analytics_data['by_assignment'].items():
                md.write(f"| {assignment} | {data['count']} | {data['avg_time']} |\n")
            md.write("\n")

        return md.getvalue()

# Create singleton instance
markdown_generator = MarkdownReportGenerator()
