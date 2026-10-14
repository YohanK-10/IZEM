// TypeScript types matching the backend data models

export type UserRole = 'teacher' | 'ta' | 'student'

export interface User {
  id: number
  name: string
  email: string
  role: UserRole
  canvas_user_id: string | null
  has_canvas_token: boolean
}

export interface NotificationItem {
  id: number
  type: string
  message: string
  read: boolean
  link: string
  created_at: string | null
}

export interface NotificationsResponse {
  unread: number
  items: NotificationItem[]
}

export interface Course {
  id: number
  name: string
  canvas_course_id: string | null
  hidden: boolean
  role: 'teacher' | 'ta' | 'student'
  // teacher-specific
  assignments_count?: number
  students_count?: number
  tas_count?: number
  active_sessions?: number
  first_open_assignment_id?: number | null
  // ta-specific
  assignments?: Assignment[]
  // student-specific
  open_queues?: number
  open_assignments?: Pick<Assignment, 'id' | 'name'>[]
}

export interface Assignment {
  id: number
  name: string
  queue_open: boolean
  course_id?: number
}

export interface QueueItem {
  id: number
  student_name: string
  student_id: number
  question_number: number | null
  question_id: number | null
  require_signoff: boolean
  submission_text: string | null
  status: 'pending' | 'ai_generated' | 'approved' | 'edited' | 'rejected' | 'in_person' | 'resolved'
  queue_position: number | null
  wait_time_minutes: number
  student_comment: string | null
  room_id: number | null
  has_ai_feedback: boolean
  assigned_ta_name?: string | null
}

export interface QueueRoom {
  id: number
  name: string
  location: string | null
  is_signoff: boolean
  assignment_id?: number | null
  parent_room_id?: number | null
}

export interface Question {
  id: number
  question_number: number
  description: string
  label?: string | null
  require_signoff?: boolean
}

export interface QueueState {
  assignment: {
    id: number
    name: string
    queue_open: boolean
    is_signoff: boolean
    course_id: number
  }
  course: { id: number; name: string } | null
  rooms: QueueRoom[]
  queues?: QueueRoom[]
  questions: Question[]
  queue_items: QueueItem[]
  being_helped_items: QueueItem[]
  total_in_queue: number
  total_being_helped: number
  my_request: {
    id: number
    queue_position: number | null
    status: string
    question_id: number
    ai_progress_status?: string | null
  } | null
}

export interface LLMConfig {
  id: number
  name: string
  base_url: string
  model_name: string
  is_public: boolean
  owned: boolean
}

export interface LLMConfigsResponse {
  my_configs: LLMConfig[]
  public_configs: LLMConfig[]
}

export interface AnalyticsSummary {
  total_requests: number
  closed_requests: number
  open_requests: number
  closed_rate: number
  closed_rate_display: string
  avg_resolution_minutes: number | null
  avg_resolution_display: string
  avg_queue_wait_minutes: number | null
  avg_queue_wait_display: string
  approved_count: number
  edited_count: number
  in_person_count: number
  ai_approval_rate: number
  ai_approval_rate_display: string
  student_count: number
  ta_count: number
  session_count: number
  status_breakdown: Array<{
    status: string
    label: string
    count: number
    percentage: number
    percentage_display: string
    badge_classes: string
    chart_color: string
  }>
}

// ─── TA Dashboard ────────────────────────────────────────────────────────────

export interface TARoom {
  assignment_id: number
  assignment_name: string
  course_name: string
  room_id: number
  room_name: string
  queue_count: number
}

export interface TAAssignmentItem {
  id: number
  name: string
  queue_open: boolean
}

export interface TACourse {
  id: number
  name: string
  assignments: TAAssignmentItem[]
}

export interface TARequest {
  id: number
  student_name: string
  assignment_name: string
  question_number: number | null
  status: string
  resolved_at: string | null
}

export interface TADashboard {
  active_rooms: TARoom[]
  courses: TACourse[]
  pending_requests: TARequest[]
  recent_resolved: TARequest[]
  available_llms: { id: number; name: string; model_name: string }[]
  request_count: number
}

// ─── Student Dashboard ────────────────────────────────────────────────────────

export interface StudentQuestion {
  id: number
  question_number: number
  description: string
}

export interface StudentRoom {
  id: number
  name: string
}

export interface StudentAssignment {
  id: number
  name: string
  course_id: number
  course_name: string
  questions: StudentQuestion[]
  rooms: StudentRoom[]
}

export interface StudentRequest {
  id: number
  assignment_name: string
  question_number: number | null
  status: string
  created_at: string
}

export interface StudentDashboard {
  open_assignments: StudentAssignment[]
  enrolled_courses: { id: number; name: string }[]
  in_queue: boolean
  active_assignment_id: number | null
  recent_requests: StudentRequest[]
}

export interface SignoffAnalyticsStatus {
  status: string
  label: string
  count: number
  percentage: number
  percentage_display: string
  badge_classes: string
  chart_color: string
}

export interface SignoffAnalyticsSummary {
  total_signoffs: number
  signed_off_count: number
  insufficient_count: number
  signed_off_rate: number
  signed_off_rate_display: string
  insufficient_rate: number
  insufficient_rate_display: string
  student_count: number
  grader_count: number
  flow_count: number
  assignment_count: number
  points_covered: number
  questions_covered: number
  avg_per_student: number | null
  avg_per_student_display: string
  avg_per_grader: number | null
  avg_per_grader_display: string
  recent_activity_count: number
  retry_count: number
  retry_rate: number
  retry_rate_display: string
  status_breakdown: SignoffAnalyticsStatus[]
}

export interface SignoffAnalyticsData {
  summary: SignoffAnalyticsSummary
  course_stats: Array<{
    course_id: number
    course_name: string
    total: number
    signed_off: number
    insufficient: number
    student_count: number
    signed_off_rate_display: string
    insufficient_rate_display: string
  }>
  flow_stats: Array<{
    flow_id: number
    flow_name: string
    course_name: string
    point_count: number
    total: number
    signed_off: number
    insufficient: number
    student_count: number
    signed_off_rate_display: string
    insufficient_rate_display: string
  }>
  assignment_stats: Array<{
    assignment_id: number
    assignment_name: string
    course_name: string
    total: number
    signed_off: number
    insufficient: number
    student_count: number
    signed_off_rate_display: string
    insufficient_rate_display: string
  }>
  grader_stats: Array<{
    grader_id: number
    grader_name: string
    total: number
    signed_off: number
    insufficient: number
    student_count: number
    signed_off_rate_display: string
    insufficient_rate_display: string
  }>
  stuck_points: Array<{
    label: string
    scope: string
    context: string
    course_name: string
    signed_off: number
    insufficient: number
    total: number
    student_count: number
    insufficient_rate: number
    insufficient_rate_display: string
  }>
  focus: { title: string; subtitle: string }
  filters: {
    course_id: number | null
    assignment_id: number | null
    flow_id: number | null
    grader_id: number | null
    start_date: string
    end_date: string
    courses: Array<{ id: number; name: string }>
    assignments: Array<{ id: number; name: string; course_id: number; course_name: string }>
    flows: Array<{
      id: number
      name: string
      course_id: number
      course_name: string
      point_count: number
    }>
    graders: Array<{ id: number; name: string; email: string }>
  }
  charts: {
    activity_over_time: { labels: string[]; counts: number[] }
  }
}

export interface AnalyticsData {
  summary: AnalyticsSummary
  course_stats: unknown[]
  assignment_stats: unknown[]
  ta_stats: unknown[]
  common_problems: Array<{
    question_label: string
    problem_summary: string
    assignment_name: string
    request_count: number
    request_share_display: string
    avg_resolution_display: string
  }>
  focus: {
    scope_label: string
    title: string
    subtitle: string
    top_question: unknown | null
    top_ta: unknown | null
  }
  filters: {
    course_id: number | null
    assignment_id: number | null
    courses: Array<{ id: number; name: string; assignment_count: number }>
    assignments: Array<{ id: number; name: string; course_id: number; course_name: string }>
  }
  charts: {
    requests_over_time: { labels: string[]; counts: number[] }
    status_distribution: { labels: string[]; counts: number[]; colors: string[] }
    ta_comparison: { labels: string[]; approved: number[]; edited: number[]; in_person: number[] }
  }
}
