import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import TADashboardPage from '@/app/views/TADashboardPage.vue'
import * as api from '@/app/api'
import type { TADashboard } from '@/app/types'

vi.mock('@/app/api', () => ({
  taApi: { dashboard: vi.fn(), openQueue: vi.fn(), closeQueue: vi.fn() },
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

vi.mock('@/app/utils/time', () => ({ fmtUtc: vi.fn((d: string) => d) }))

const mockDashboard: TADashboard = {
  active_rooms: [
    {
      assignment_id: 1,
      assignment_name: 'Assignment 1',
      course_name: 'Algorithms',
      room_id: 10,
      room_name: 'Room A',
      queue_count: 3,
    },
  ],
  courses: [{ id: 1, name: 'Algorithms', assignments: [{ id: 1, name: 'Assignment 1', queue_open: true }] }],
  pending_requests: [
    {
      id: 1,
      student_name: 'Alice',
      assignment_name: 'Assignment 1',
      question_number: 2,
      status: 'pending',
      resolved_at: null,
    },
  ],
  recent_resolved: [],
  available_llms: [{ id: 1, name: 'GPT-4', model_name: 'gpt-4' }],
  request_count: 1,
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: TADashboardPage },
      { path: '/review-request/:id', component: { template: '<div />' } },
      { path: '/lab-session/:id', component: { template: '<div />' } },
    ],
  })
}

describe('TADashboardPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows loading state', () => {
    vi.mocked(api.taApi.dashboard).mockReturnValue(new Promise(() => {}))
    const wrapper = mount(TADashboardPage, { global: { plugins: [makeRouter()] } })
    expect(wrapper.text()).toMatch(/loading/i)
  })

  it('renders active rooms after load', async () => {
    vi.mocked(api.taApi.dashboard).mockResolvedValue(mockDashboard)
    const wrapper = mount(TADashboardPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    expect(wrapper.text()).toContain('Room A')
  })

  it('shows pending requests', async () => {
    vi.mocked(api.taApi.dashboard).mockResolvedValue(mockDashboard)
    const wrapper = mount(TADashboardPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    expect(wrapper.text()).toContain('Alice')
  })

  it('shows error on fetch failure', async () => {
    vi.mocked(api.taApi.dashboard).mockRejectedValue(new Error('Connection refused'))
    const wrapper = mount(TADashboardPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    expect(wrapper.text()).toContain('Connection refused')
  })

  it('polls for updates', async () => {
    vi.mocked(api.taApi.dashboard).mockResolvedValue(mockDashboard)
    mount(TADashboardPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    const before = vi.mocked(api.taApi.dashboard).mock.calls.length
    vi.advanceTimersByTime(5000)
    await flushPromises()
    expect(vi.mocked(api.taApi.dashboard).mock.calls.length).toBeGreaterThan(before)
  })
})
