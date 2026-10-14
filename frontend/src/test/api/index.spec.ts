import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as client from '@/app/api/client'
import {
  authApi,
  coursesApi,
  queueApi,
  analyticsApi,
  notificationsApi,
  llmApi,
  settingsApi,
  canvasApi,
  taApi,
  studentApi,
  signoffAnalyticsApi,
} from '@/app/api'

vi.mock('@/app/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    postForm: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      message: string,
    ) {
      super(message)
    }
  },
  setSessionExpiredHandler: vi.fn(),
}))

const mockGet = () => vi.mocked(client.api.get)
const mockPost = () => vi.mocked(client.api.post)
const mockPut = () => vi.mocked(client.api.put)
const mockDelete = () => vi.mocked(client.api.delete)

beforeEach(() => vi.clearAllMocks())

describe('authApi', () => {
  it('login posts to /auth/login', () => {
    mockPost().mockResolvedValue({ message: 'Check email' })
    authApi.login('test@example.com')
    expect(client.api.post).toHaveBeenCalledWith('/auth/login', { email: 'test@example.com' })
  })

  it('logout posts to /auth/logout', () => {
    mockPost().mockResolvedValue({ ok: true })
    authApi.logout()
    expect(client.api.post).toHaveBeenCalledWith('/auth/logout')
  })

  it('me gets /me', () => {
    mockGet().mockResolvedValue({ id: 1 })
    authApi.me()
    expect(client.api.get).toHaveBeenCalledWith('/me')
  })
})

describe('coursesApi', () => {
  it('list without hidden flag', () => {
    mockGet().mockResolvedValue([])
    coursesApi.list()
    expect(client.api.get).toHaveBeenCalledWith('/courses')
  })

  it('list with hidden flag', () => {
    mockGet().mockResolvedValue([])
    coursesApi.list(true)
    expect(client.api.get).toHaveBeenCalledWith('/courses?show_hidden=true')
  })

  it('rooms gets /course/:id/rooms', () => {
    mockGet().mockResolvedValue({ rooms: [] })
    coursesApi.rooms(5)
    expect(client.api.get).toHaveBeenCalledWith('/course/5/rooms')
  })
})

describe('queueApi', () => {
  it('getState gets /queue/:id', () => {
    mockGet().mockResolvedValue({})
    queueApi.getState(99)
    expect(client.api.get).toHaveBeenCalledWith('/queue/99')
  })
})

describe('analyticsApi', () => {
  it('get without params', () => {
    mockGet().mockResolvedValue({})
    analyticsApi.get()
    expect(client.api.get).toHaveBeenCalledWith('/analytics')
  })

  it('get with params builds query string', () => {
    mockGet().mockResolvedValue({})
    analyticsApi.get({ course_id: 1, assignment_id: 2 })
    expect(client.api.get).toHaveBeenCalledWith(expect.stringContaining('course_id=1'))
    expect(client.api.get).toHaveBeenCalledWith(expect.stringContaining('assignment_id=2'))
  })
})

describe('signoffAnalyticsApi', () => {
  it('get without params', () => {
    mockGet().mockResolvedValue({})
    signoffAnalyticsApi.get()
    expect(client.api.get).toHaveBeenCalledWith('/signoff-analytics')
  })

  it('get with all params', () => {
    mockGet().mockResolvedValue({})
    signoffAnalyticsApi.get({ course_id: 1, flow_id: 3, grader_id: 5 })
    const call = (client.api.get as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
    expect(call).toContain('course_id=1')
    expect(call).toContain('flow_id=3')
    expect(call).toContain('grader_id=5')
  })
})

describe('notificationsApi', () => {
  it('list uses default limit', () => {
    mockGet().mockResolvedValue({ items: [], unread: 0 })
    notificationsApi.list()
    expect(client.api.get).toHaveBeenCalledWith('/notifications?limit=10')
  })

  it('list accepts custom limit', () => {
    mockGet().mockResolvedValue({ items: [], unread: 0 })
    notificationsApi.list(25)
    expect(client.api.get).toHaveBeenCalledWith('/notifications?limit=25')
  })

  it('markRead posts to /notifications/:id/read', () => {
    mockPost().mockResolvedValue({ status: 'ok' })
    notificationsApi.markRead(7)
    expect(client.api.post).toHaveBeenCalledWith('/notifications/7/read')
  })

  it('markAllRead posts to /notifications/read-all', () => {
    mockPost().mockResolvedValue({ status: 'ok' })
    notificationsApi.markAllRead()
    expect(client.api.post).toHaveBeenCalledWith('/notifications/read-all')
  })
})

describe('llmApi', () => {
  it('list gets /llm/configs', () => {
    mockGet().mockResolvedValue({ my_configs: [], public_configs: [] })
    llmApi.list()
    expect(client.api.get).toHaveBeenCalledWith('/llm/configs')
  })

  it('create posts to /llm/configs', () => {
    mockPost().mockResolvedValue({ id: 1 })
    const data = {
      name: 'GPT-4',
      base_url: 'https://api.example.com',
      api_key: 'k',
      model_name: 'm',
      is_public: false,
    }
    llmApi.create(data)
    expect(client.api.post).toHaveBeenCalledWith('/llm/configs', data)
  })

  it('update puts to /llm/configs/:id', () => {
    mockPut().mockResolvedValue({ id: 1 })
    llmApi.update(1, { name: 'Updated' })
    expect(client.api.put).toHaveBeenCalledWith('/llm/configs/1', { name: 'Updated' })
  })

  it('delete calls /llm/configs/:id', () => {
    mockDelete().mockResolvedValue({ ok: true })
    llmApi.delete(3)
    expect(client.api.delete).toHaveBeenCalledWith('/llm/configs/3')
  })

  it('test posts to /llm/configs/test', () => {
    mockPost().mockResolvedValue({ ok: true })
    llmApi.test({ base_url: 'url', api_key: 'k', model_name: 'm' })
    expect(client.api.post).toHaveBeenCalledWith('/llm/configs/test', expect.any(Object))
  })

  it('testSaved posts to /llm/configs/:id/test', () => {
    mockPost().mockResolvedValue({ ok: true })
    llmApi.testSaved(5)
    expect(client.api.post).toHaveBeenCalledWith('/llm/configs/5/test')
  })
})

describe('settingsApi', () => {
  it('get fetches /settings', () => {
    mockGet().mockResolvedValue({ has_canvas_token: false, canvas_user_id: null })
    settingsApi.get()
    expect(client.api.get).toHaveBeenCalledWith('/settings')
  })

  it('saveCanvasToken posts token', () => {
    mockPost().mockResolvedValue({ ok: true, has_canvas_token: true })
    settingsApi.saveCanvasToken('mytoken')
    expect(client.api.post).toHaveBeenCalledWith('/settings/canvas-token', { token: 'mytoken' })
  })
})

describe('canvasApi', () => {
  it('listCourses gets /canvas/courses', () => {
    mockGet().mockResolvedValue([])
    canvasApi.listCourses()
    expect(client.api.get).toHaveBeenCalledWith('/canvas/courses')
  })

  it('importCourse posts to /canvas/import', () => {
    mockPost().mockResolvedValue({ id: 1 })
    canvasApi.importCourse('canvas-123', 'My Course')
    expect(client.api.post).toHaveBeenCalledWith('/canvas/import', {
      canvas_course_id: 'canvas-123',
      name: 'My Course',
    })
  })
})

describe('taApi', () => {
  it('dashboard gets /ta/dashboard', () => {
    mockGet().mockResolvedValue({})
    taApi.dashboard()
    expect(client.api.get).toHaveBeenCalledWith('/ta/dashboard')
  })

  it('openQueue posts to /ta/assignment/:id/queue/open', () => {
    mockPost().mockResolvedValue({ ok: true })
    taApi.openQueue(10, { llm_id: 1, rooms: [] })
    expect(client.api.post).toHaveBeenCalledWith('/ta/assignment/10/queue/open', expect.any(Object))
  })

  it('closeQueue posts to /ta/assignment/:id/queue/close', () => {
    mockPost().mockResolvedValue({ ok: true, assignment_id: 10, queue_open: false })
    taApi.closeQueue(10, 'kick')
    expect(client.api.post).toHaveBeenCalledWith('/ta/assignment/10/queue/close', {
      action: 'kick',
    })
  })
})

describe('studentApi', () => {
  it('dashboard gets /student/dashboard', () => {
    mockGet().mockResolvedValue({})
    studentApi.dashboard()
    expect(client.api.get).toHaveBeenCalledWith('/student/dashboard')
  })

  it('submitHelp posts to /student/help/submit', () => {
    mockPost().mockResolvedValue({ ok: true, request_id: 1 })
    studentApi.submitHelp({
      question_id: 1,
      submission_text: 'help',
      student_comment: '',
      queue_room_id: null,
    })
    expect(client.api.post).toHaveBeenCalledWith('/student/help/submit', expect.any(Object))
  })

  it('courseProgress gets /student/course/:id/progress', () => {
    mockGet().mockResolvedValue({})
    studentApi.courseProgress(7)
    expect(client.api.get).toHaveBeenCalledWith('/student/course/7/progress')
  })
})
