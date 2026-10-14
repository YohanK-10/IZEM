import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import NotFoundPage from '@/app/views/NotFoundPage.vue'
import { useAuthStore } from '@/app/stores/auth'

vi.mock('@/app/api', () => ({
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

vi.mock('@/app/api/client', () => ({
  setSessionExpiredHandler: vi.fn(),
}))

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/ta-dashboard', component: { template: '<div />' } },
      { path: '/student-home', component: { template: '<div />' } },
      { path: '/404', component: NotFoundPage },
    ],
  })
}

describe('NotFoundPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders 404 message', () => {
    const wrapper = mount(NotFoundPage, { global: { plugins: [makeRouter()] } })
    expect(wrapper.text()).toContain('404')
    expect(wrapper.text()).toContain('Page not found')
  })

  it('shows a home link', () => {
    const wrapper = mount(NotFoundPage, { global: { plugins: [makeRouter()] } })
    expect(wrapper.text()).toMatch(/home/i)
  })

  it('links to /ta-dashboard for TA users', async () => {
    const router = makeRouter()
    const store = useAuthStore()
    store.user = {
      id: 2,
      name: 'TA',
      email: 'ta@example.com',
      role: 'ta',
      canvas_user_id: null,
      has_canvas_token: false,
    }
    const wrapper = mount(NotFoundPage, { global: { plugins: [router] } })
    await router.isReady()
    // RouterLink renders with href matching the `to` prop resolved by the router
    const link = wrapper.find('a')
    expect(link.attributes('href')).toContain('ta-dashboard')
  })

  it('links to /student-home for student users', async () => {
    const router = makeRouter()
    const store = useAuthStore()
    store.user = {
      id: 3,
      name: 'S',
      email: 's@example.com',
      role: 'student',
      canvas_user_id: null,
      has_canvas_token: false,
    }
    const wrapper = mount(NotFoundPage, { global: { plugins: [router] } })
    await router.isReady()
    const link = wrapper.find('a')
    expect(link.attributes('href')).toContain('student-home')
  })

  it('links to / for unauthenticated users', async () => {
    const router = makeRouter()
    const wrapper = mount(NotFoundPage, { global: { plugins: [router] } })
    await router.isReady()
    const link = wrapper.find('a')
    expect(link.attributes('href')).toBe('/')
  })
})
