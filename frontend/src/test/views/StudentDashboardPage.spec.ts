import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import StudentDashboardPage from '@/app/views/StudentDashboardPage.vue'
import * as api from '@/app/api'
import type { StudentDashboard } from '@/app/types'

vi.mock('@/app/api', () => ({
  studentApi: { dashboard: vi.fn() },
  notificationsApi: { list: vi.fn() },
  authApi: { me: vi.fn(), login: vi.fn(), logout: vi.fn() },
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

const mockDashboard: StudentDashboard = {
  open_assignments: [
    {
      id: 1,
      name: 'Assignment 1',
      course_id: 10,
      course_name: 'Algorithms',
      questions: [{ id: 1, question_number: 1, description: 'Q1' }],
      rooms: [{ id: 1, name: 'Room A' }],
    },
  ],
  enrolled_courses: [{ id: 10, name: 'Algorithms' }],
  in_queue: false,
  active_assignment_id: null,
  recent_requests: [
    {
      id: 1,
      assignment_name: 'Assignment 1',
      question_number: 1,
      status: 'approved',
      created_at: '2026-01-01T00:00:00Z',
    },
  ],
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: StudentDashboardPage },
      { path: '/room/:id', component: { template: '<div />' } },
      { path: '/course/:id/rooms', component: { template: '<div />' } },
    ],
  })
}

describe('StudentDashboardPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.useFakeTimers()
    vi.mocked(api.notificationsApi.list).mockResolvedValue({ items: [], unread: 0 })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows loading state', () => {
    vi.mocked(api.studentApi.dashboard).mockReturnValue(new Promise(() => {}))
    const wrapper = mount(StudentDashboardPage, { global: { plugins: [makeRouter()] } })
    expect(wrapper.text()).toMatch(/loading/i)
  })

  it('renders open assignments after load', async () => {
    vi.mocked(api.studentApi.dashboard).mockResolvedValue(mockDashboard)
    const wrapper = mount(StudentDashboardPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    expect(wrapper.text()).toContain('Assignment 1')
  })

  it('shows error on fetch failure', async () => {
    vi.mocked(api.studentApi.dashboard).mockRejectedValue(new Error('Not found'))
    const wrapper = mount(StudentDashboardPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    expect(wrapper.text()).toContain('Not found')
  })

  it('shows recent request status', async () => {
    vi.mocked(api.studentApi.dashboard).mockResolvedValue(mockDashboard)
    const wrapper = mount(StudentDashboardPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    // Status should be formatted
    expect(wrapper.text()).toMatch(/approved/i)
  })

  it('sets up polling on mount', async () => {
    vi.mocked(api.studentApi.dashboard).mockResolvedValue(mockDashboard)
    mount(StudentDashboardPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    const callCount = vi.mocked(api.studentApi.dashboard).mock.calls.length

    vi.advanceTimersByTime(5000)
    await flushPromises()
    expect(vi.mocked(api.studentApi.dashboard).mock.calls.length).toBeGreaterThan(callCount)
  })
})
