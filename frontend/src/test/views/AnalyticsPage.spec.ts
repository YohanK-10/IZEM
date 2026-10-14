import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import AnalyticsPage from '@/app/views/AnalyticsPage.vue'
import * as api from '@/app/api'
import type { AnalyticsData } from '@/app/types'

vi.mock('@/app/api', () => ({
  analyticsApi: { get: vi.fn() },
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

const mockAnalytics: AnalyticsData = {
  summary: {
    total_requests: 100,
    closed_requests: 80,
    open_requests: 20,
    closed_rate: 0.8,
    closed_rate_display: '80%',
    avg_resolution_minutes: 15,
    avg_resolution_display: '15 min',
    avg_queue_wait_minutes: 5,
    avg_queue_wait_display: '5 min',
    approved_count: 50,
    edited_count: 20,
    in_person_count: 10,
    ai_approval_rate: 0.7,
    ai_approval_rate_display: '70%',
    student_count: 30,
    ta_count: 5,
    session_count: 10,
    status_breakdown: [],
  },
  course_stats: [],
  assignment_stats: [],
  ta_stats: [],
  common_problems: [],
  focus: {
    scope_label: 'All Courses',
    title: 'Overview',
    subtitle: '',
    top_question: null,
    top_ta: null,
  },
  filters: { course_id: null, assignment_id: null, courses: [], assignments: [] },
  charts: {
    requests_over_time: { labels: [], counts: [] },
    status_distribution: { labels: [], counts: [], colors: [] },
    ta_comparison: { labels: [], approved: [], edited: [], in_person: [] },
  },
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: AnalyticsPage }],
  })
}

describe('AnalyticsPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('shows loading state', () => {
    vi.mocked(api.analyticsApi.get).mockReturnValue(new Promise(() => {}))
    const wrapper = mount(AnalyticsPage, { global: { plugins: [makeRouter()] } })
    expect(wrapper.text()).toMatch(/loading/i)
  })

  it('renders summary numbers after load', async () => {
    vi.mocked(api.analyticsApi.get).mockResolvedValue(mockAnalytics)
    const wrapper = mount(AnalyticsPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    expect(wrapper.text()).toContain('100')
  })

  it('shows error message on failure', async () => {
    vi.mocked(api.analyticsApi.get).mockRejectedValue(new Error('Analytics unavailable'))
    const wrapper = mount(AnalyticsPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    expect(wrapper.text()).toContain('Analytics unavailable')
  })

  it('calls analyticsApi.get on mount', async () => {
    vi.mocked(api.analyticsApi.get).mockResolvedValue(mockAnalytics)
    mount(AnalyticsPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    expect(api.analyticsApi.get).toHaveBeenCalledOnce()
  })
})
