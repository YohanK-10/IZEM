from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from io import BytesIO
import json
from datetime import datetime
from typing import Dict, List, Optional

class PDFReportGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()

    def _create_custom_styles(self):
        """Create custom paragraph styles"""
        # Only add styles if they don't already exist
        if 'CustomTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CustomTitle',
                parent=self.styles['Title'],
                fontSize=24,
                textColor=colors.HexColor('#1f2937'),
                spaceAfter=30,
                alignment=TA_CENTER
            ))

        if 'CustomHeading' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CustomHeading',
                parent=self.styles['Heading1'],
                fontSize=16,
                textColor=colors.HexColor('#374151'),
                spaceBefore=20,
                spaceAfter=12
            ))

        if 'InfoText' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='InfoText',
                parent=self.styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#6b7280'),
                alignment=TA_LEFT
            ))

        # Create a custom code style instead of overriding the existing one
        if 'CustomCode' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CustomCode',
                parent=self.styles['Code'],
                fontSize=9,
                fontName='Courier',
                backgroundColor=colors.HexColor('#f3f4f6'),
                borderColor=colors.HexColor('#e5e7eb'),
                borderWidth=1,
                borderPadding=6
            ))

    def generate_assignment_report(self, assignment: Dict, questions: List[Dict],
                                 help_requests: List[Dict]) -> BytesIO:
        """Generate a PDF report for an assignment"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75*inch)
        story = []

        # Title
        story.append(Paragraph(assignment['name'], self.styles['CustomTitle']))

        # Date
        story.append(Paragraph(
            f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
            self.styles['InfoText']
        ))
        story.append(Spacer(1, 0.3*inch))

        # Questions Summary
        story.append(Paragraph("Questions Overview", self.styles['CustomHeading']))

        questions_data = [['Question #', 'Description', 'Help Requests']]
        for q in questions:
            request_count = len([r for r in help_requests if r['question_id'] == q['id']])
            desc = q['problem_description'][:100] + '...' if len(q['problem_description']) > 100 else q['problem_description']
            questions_data.append([
                str(q['question_number']),
                desc,
                str(request_count)
            ])

        questions_table = Table(questions_data, colWidths=[1*inch, 4*inch, 1.5*inch])
        questions_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9fafb')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb'))
        ]))
        story.append(questions_table)
        story.append(PageBreak())

        # Detailed Questions
        story.append(Paragraph("Question Details", self.styles['CustomHeading']))

        for q in questions:
            story.append(Paragraph(f"Question {q['question_number']}", self.styles['Heading2']))
            story.append(Paragraph("Problem Description:", self.styles['Heading3']))
            story.append(Paragraph(q['problem_description'], self.styles['Normal']))
            story.append(Spacer(1, 0.2*inch))

            if q.get('hinting_strategy'):
                story.append(Paragraph("Hinting Strategy:", self.styles['Heading3']))
                story.append(Paragraph(q['hinting_strategy'], self.styles['Normal']))
                story.append(Spacer(1, 0.2*inch))

            story.append(Spacer(1, 0.3*inch))

        doc.build(story)
        buffer.seek(0)
        return buffer

    def generate_help_request_report(self, help_request: Dict, student: Dict,
                                   question: Dict, assignment: Dict) -> BytesIO:
        """Generate a PDF report for a help request"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        story = []

        # Title
        story.append(Paragraph(f"Help Request #{help_request['id']}", self.styles['CustomTitle']))

        # Student Info
        story.append(Paragraph("Student Information", self.styles['CustomHeading']))
        student_data = [
            ['Name:', student['name']],
            ['Email:', student['email']],
            ['Submitted:', help_request['created_at'].strftime('%B %d, %Y at %I:%M %p')]
        ]

        student_table = Table(student_data, colWidths=[1.5*inch, 5*inch])
        student_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ]))
        story.append(student_table)
        story.append(Spacer(1, 0.3*inch))

        # Assignment & Question
        story.append(Paragraph("Assignment Details", self.styles['CustomHeading']))
        story.append(Paragraph(f"Assignment: {assignment['name']}", self.styles['Normal']))
        story.append(Paragraph(f"Question {question['question_number']}", self.styles['Normal']))
        story.append(Spacer(1, 0.2*inch))

        # Student Submission
        if help_request.get('submission_text'):
            story.append(Paragraph("Student's Code", self.styles['CustomHeading']))
            code_text = help_request['submission_text'].replace('\n', '<br/>')
            story.append(Paragraph(code_text, self.styles['CustomCode']))
            story.append(Spacer(1, 0.3*inch))

        if help_request.get('student_comment'):
            story.append(Paragraph("Student's Comment", self.styles['CustomHeading']))
            story.append(Paragraph(help_request['student_comment'], self.styles['Normal']))
            story.append(Spacer(1, 0.3*inch))

        # AI Feedback
        if help_request.get('ai_feedback'):
            story.append(Paragraph("AI Analysis", self.styles['CustomHeading']))

            try:
                ai_data = json.loads(help_request['ai_feedback'])

                if ai_data.get('student_reasoning'):
                    story.append(Paragraph("Student's Approach:", self.styles['Heading3']))
                    story.append(Paragraph(ai_data['student_reasoning'], self.styles['Normal']))
                    story.append(Spacer(1, 0.2*inch))

                if ai_data.get('what_they_did_right'):
                    story.append(Paragraph("What They Did Right:", self.styles['Heading3']))
                    for item in ai_data['what_they_did_right']:
                        story.append(Paragraph(f"• {item}", self.styles['Normal']))
                    story.append(Spacer(1, 0.2*inch))

                if ai_data.get('detected_issues'):
                    story.append(Paragraph("Issues Detected:", self.styles['Heading3']))
                    for item in ai_data['detected_issues']:
                        story.append(Paragraph(f"• {item}", self.styles['Normal']))
                    story.append(Spacer(1, 0.2*inch))

                if ai_data.get('suggested_direction'):
                    story.append(Paragraph("Suggested Feedback:", self.styles['Heading3']))
                    story.append(Paragraph(ai_data['suggested_direction'], self.styles['Normal']))
            except (json.JSONDecodeError, KeyError, TypeError):
                story.append(Paragraph(help_request['ai_feedback'], self.styles['Normal']))

        # Final Feedback
        if help_request.get('final_feedback'):
            story.append(Spacer(1, 0.3*inch))
            story.append(Paragraph("Final Feedback to Student", self.styles['CustomHeading']))
            story.append(Paragraph(help_request['final_feedback'], self.styles['Normal']))

        doc.build(story)
        buffer.seek(0)
        return buffer

    def generate_analytics_report(self, course: Dict, analytics_data: Dict) -> BytesIO:
        """Generate analytics report for a course"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        story = []

        # Title
        story.append(Paragraph(f"Analytics Report: {course['name']}", self.styles['CustomTitle']))
        story.append(Paragraph(
            f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
            self.styles['InfoText']
        ))
        story.append(Spacer(1, 0.5*inch))

        # Summary Statistics
        story.append(Paragraph("Summary Statistics", self.styles['CustomHeading']))

        stats_data = [
            ['Metric', 'Value'],
            ['Total Help Requests', str(analytics_data.get('total_requests', 0))],
            ['Average Response Time', analytics_data.get('avg_response_time', 'N/A')],
            ['AI Approval Rate', f"{analytics_data.get('ai_approval_rate', 0):.1f}%"],
            ['Active Students', str(analytics_data.get('active_students', 0))],
            ['Active TAs', str(analytics_data.get('active_tas', 0))]
        ]

        stats_table = Table(stats_data, colWidths=[3*inch, 3*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9fafb')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb'))
        ]))
        story.append(stats_table)

        doc.build(story)
        buffer.seek(0)
        return buffer

# Create singleton instance
pdf_generator = PDFReportGenerator()
