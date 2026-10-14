import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import CoursesPage from '@/app/views/CoursesPage.vue'
import { useAuthStore } from '@/app/stores/auth'
import * as api from '@/app/api'
import type { Course } from '@/app/types'

vi.mock('@/app/api', () => ({
  coursesApi: { list: vi.fn() },
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

const teacherCourse: Course = {
  id: 1,
  name: 'Advanced Algorithms',
  canvas_course_id: null,
  hidden: false,
  role: 'teacher',
}
const taCourse: Course = {
  id: 2,
  name: 'Data Structures',
  canvas_course_id: null,
  hidden: false,
  role: 'ta',
}
const studentCourse: Course = {
  id: 3,
  name: 'Intro to CS',
  canvas_course_id: null,
  hidden: false,
  role: 'student',
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: CoursesPage },
      { path: '/settings/canvas', component: { template: '<div />' } },
      { path: '/course/:id/configure', component: { template: '<div />' } },
      { path: '/course/:id', component: { template: '<div />' } },
    ],
  })
}

describe('CoursesPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('shows loading state', async () => {
    vi.mocked(api.coursesApi.list).mockReturnValue(new Promise(() => {}))
    const wrapper = mount(CoursesPage, { global: { plugins: [makeRouter()] } })
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Loading courses')
  })

  it('shows error state', async () => {
    vi.mocked(api.coursesApi.list).mockRejectedValue(new Error('Network error'))
    const wrapper = mount(CoursesPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    expect(wrapper.text()).toContain('Network error')
  })

  it('renders teacher courses section', async () => {
    vi.mocked(api.coursesApi.list).mockResolvedValue([teacherCourse])
    const wrapper = mount(CoursesPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    expect(wrapper.text()).toContain('Advanced Algorithms')
  })

  it('renders TA and student courses sections', async () => {
    vi.mocked(api.coursesApi.list).mockResolvedValue([taCourse, studentCourse])
    const wrapper = mount(CoursesPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    expect(wrapper.text()).toContain('Data Structures')
    expect(wrapper.text()).toContain('Intro to CS')
  })

  it('shows Canvas import button for teacher role', async () => {
    vi.mocked(api.coursesApi.list).mockResolvedValue([teacherCourse])
    const authStore = useAuthStore()
    authStore.user = {
      id: 1,
      name: 'T',
      email: 't@example.com',
      role: 'teacher',
      canvas_user_id: null,
      has_canvas_token: false,
    }
    const wrapper = mount(CoursesPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    expect(wrapper.text()).toContain('Canvas')
  })

  it('calls fetchCourses on mount', async () => {
    vi.mocked(api.coursesApi.list).mockResolvedValue([])
    mount(CoursesPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    expect(api.coursesApi.list).toHaveBeenCalledOnce()
  })

  it('cardColor cycles through colors for multiple courses', async () => {
    const manyCourses = Array.from({ length: 9 }, (_, i) => ({
      ...teacherCourse,
      id: i + 1,
      name: `Course ${i + 1}`,
    }))
    vi.mocked(api.coursesApi.list).mockResolvedValue(manyCourses)
    const wrapper = mount(CoursesPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    // Ensure all courses are rendered (no crash from cycling)
    expect(wrapper.text()).toContain('Course 9')
  })
})
