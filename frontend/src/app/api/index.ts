import { api, ApiError } from './client'
import type {
  User,
  Course,
  QueueState,
  LLMConfigsResponse,
  LLMConfig,
  AnalyticsData,
  SignoffAnalyticsData,
  NotificationsResponse,
  TADashboard,
  StudentDashboard,
} from '../types'

export { ApiError }

// ─── Auth ────────────────────────────────────────────────────────────────────

export const authApi = {
  /** Login with email. Test accounts get a direct session; others get a magic link. */
  login(email: string): Promise<User | { message: string }> {
    return api.post('/auth/login', { email })
  },

  logout(): Promise<{ ok: boolean }> {
    return api.post('/auth/logout')
  },

  /** Returns the current logged-in user, or throws ApiError(401) if not authenticated. */
  me(): Promise<User> {
    return api.get('/me')
  },
}

// ─── Courses ─────────────────────────────────────────────────────────────────

export const coursesApi = {
  list(showHidden = false): Promise<Course[]> {
    return api.get(`/courses${showHidden ? '?show_hidden=true' : ''}`)
  },

  rooms(courseId: number): Promise<{
    course_id: number
    course_name: string
    rooms: Array<{
      id: number
      name: string
      location: string | null
      is_open: boolean
      assignment_id: number | null
      assignment_name: string | null
      waiting: number
      being_helped: number
      opened_at: string | null
      ta_name: string | null
    }>
  }> {
    return api.get(`/course/${courseId}/rooms`)
  },
}

// ─── Queue ───────────────────────────────────────────────────────────────────

export const queueApi = {
  getState(assignmentId: number): Promise<QueueState> {
    return api.get(`/queue/${assignmentId}`)
  },
}

// ─── Analytics ───────────────────────────────────────────────────────────────

export const analyticsApi = {
  get(params?: {
    course_id?: number
    assignment_id?: number
    start_date?: string
    end_date?: string
  }): Promise<AnalyticsData> {
    const qs = new URLSearchParams()
    if (params?.course_id) qs.set('course_id', String(params.course_id))
    if (params?.assignment_id) qs.set('assignment_id', String(params.assignment_id))
    if (params?.start_date) qs.set('start_date', params.start_date)
    if (params?.end_date) qs.set('end_date', params.end_date)
    const query = qs.toString()
    return api.get(`/analytics${query ? `?${query}` : ''}`)
  },
}

// ─── Sign-off Analytics ──────────────────────────────────────────────────────

export const signoffAnalyticsApi = {
  get(params?: {
    course_id?: number
    assignment_id?: number
    flow_id?: number
    grader_id?: number
    start_date?: string
    end_date?: string
  }): Promise<SignoffAnalyticsData> {
    const qs = new URLSearchParams()
    if (params?.course_id) qs.set('course_id', String(params.course_id))
    if (params?.assignment_id) qs.set('assignment_id', String(params.assignment_id))
    if (params?.flow_id) qs.set('flow_id', String(params.flow_id))
    if (params?.grader_id) qs.set('grader_id', String(params.grader_id))
    if (params?.start_date) qs.set('start_date', params.start_date)
    if (params?.end_date) qs.set('end_date', params.end_date)
    const query = qs.toString()
    return api.get(`/signoff-analytics${query ? `?${query}` : ''}`)
  },
}

// ─── Notifications ───────────────────────────────────────────────────────────

export const notificationsApi = {
  list(limit = 10): Promise<NotificationsResponse> {
    return api.get(`/notifications?limit=${limit}`)
  },

  markRead(notificationId: number): Promise<{ status: string }> {
    return api.post(`/notifications/${notificationId}/read`)
  },

  markAllRead(): Promise<{ status: string }> {
    return api.post('/notifications/read-all')
  },
}

// ─── TA ──────────────────────────────────────────────────────────────────────

export const taApi = {
  dashboard(): Promise<TADashboard> {
    return api.get('/ta/dashboard')
  },

  openQueue(
    assignmentId: number,
    data: { llm_id: number; rooms: { name: string; is_signoff: boolean }[] },
  ): Promise<{ ok: boolean }> {
    return api.post(`/ta/assignment/${assignmentId}/queue/open`, data)
  },

  closeQueue(
    assignmentId: number,
    action: 'keep' | 'kick',
  ): Promise<{ ok: boolean; assignment_id: number; queue_open: boolean }> {
    return api.post(`/ta/assignment/${assignmentId}/queue/close`, { action })
  },
}

// ─── Student ─────────────────────────────────────────────────────────────────

export const studentApi = {
  dashboard(): Promise<StudentDashboard> {
    return api.get('/student/dashboard')
  },

  submitHelp(data: {
    question_id: number
    submission_text: string
    student_comment: string
    queue_room_id: number | null
  }): Promise<{ ok: boolean; request_id: number }> {
    return api.post('/student/help/submit', data)
  },

  courseProgress(courseId: number): Promise<{
    course_id: number
    assignments: Array<{
      assignment_id: number
      assignment_name: string
      requests: Array<{
        id: number
        status: string
        resolved_at: string | null
        final_feedback: string | null
        ta_name: string | null
      }>
    }>
  }> {
    return api.get(`/student/course/${courseId}/progress`)
  },
}

// ─── Settings ────────────────────────────────────────────────────────────────

export const settingsApi = {
  get(): Promise<{ has_canvas_token: boolean; canvas_user_id: string | null }> {
    return api.get('/settings')
  },

  saveCanvasToken(token: string): Promise<{ ok: boolean; has_canvas_token: boolean }> {
    return api.post('/settings/canvas-token', { token })
  },
}

// ─── Canvas ───────────────────────────────────────────────────────────────────

export interface CanvasCourse {
  canvas_course_id: string
  name: string
  already_imported: boolean
}

export const canvasApi = {
  listCourses(): Promise<CanvasCourse[]> {
    return api.get('/canvas/courses')
  },

  importCourse(
    canvas_course_id: string,
    name: string,
  ): Promise<{ id: number; name: string; canvas_course_id: string }> {
    return api.post('/canvas/import', { canvas_course_id, name })
  },
}

// ─── LLM Configs ─────────────────────────────────────────────────────────────

export const llmApi = {
  list(): Promise<LLMConfigsResponse> {
    return api.get('/llm/configs')
  },

  create(data: {
    name: string
    base_url: string
    api_key: string
    model_name: string
    is_public: boolean
  }): Promise<LLMConfig> {
    return api.post('/llm/configs', data)
  },

  update(
    id: number,
    data: Partial<{
      name: string
      base_url: string
      api_key: string
      model_name: string
      is_public: boolean
    }>,
  ): Promise<LLMConfig> {
    return api.put(`/llm/configs/${id}`, data)
  },

  delete(id: number): Promise<{ ok: boolean }> {
    return api.delete(`/llm/configs/${id}`)
  },

  test(data: { base_url: string; api_key: string; model_name: string }): Promise<{ ok: boolean; message?: string }> {
    return api.post('/llm/configs/test', data)
  },

  testSaved(id: number): Promise<{ ok: boolean; message?: string }> {
    return api.post(`/llm/configs/${id}/test`)
  },
}
