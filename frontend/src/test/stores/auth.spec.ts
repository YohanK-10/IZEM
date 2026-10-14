import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const { mockMe, mockLogin, mockLogout, mockSetSessionExpiredHandler } = vi.hoisted(() => ({
  mockMe: vi.fn(),
  mockLogin: vi.fn(),
  mockLogout: vi.fn(),
  mockSetSessionExpiredHandler: vi.fn(),
}))

vi.mock('@/app/api', () => ({
  authApi: { me: mockMe, login: mockLogin, logout: mockLogout },
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
  },
}))

vi.mock('@/app/api/client', () => ({
  setSessionExpiredHandler: mockSetSessionExpiredHandler,
}))

import { useAuthStore } from '@/app/stores/auth'
import { ApiError } from '@/app/api'
import type { User } from '@/app/types'

const mockUser: User = {
  id: 1,
  name: 'Alice',
  email: 'alice@example.com',
  role: 'teacher',
  canvas_user_id: null,
  has_canvas_token: false,
}

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('starts with no user and not initialized', () => {
    const store = useAuthStore()
    expect(store.user).toBeNull()
    expect(store.initialized).toBe(false)
    expect(store.isAuthenticated).toBe(false)
  })

  describe('checkAuth', () => {
    it('sets user and returns true on success', async () => {
      mockMe.mockResolvedValue(mockUser)
      const store = useAuthStore()
      const result = await store.checkAuth()
      expect(result).toBe(true)
      expect(store.user).toEqual(mockUser)
      expect(store.initialized).toBe(true)
      expect(store.isAuthenticated).toBe(true)
    })

    it('returns false and sets initialized on 401', async () => {
      mockMe.mockRejectedValue(new ApiError(401, 'Unauthorized'))
      const store = useAuthStore()
      const result = await store.checkAuth()
      expect(result).toBe(false)
      expect(store.user).toBeNull()
      expect(store.initialized).toBe(true)
    })

    it('rethrows non-401 errors', async () => {
      mockMe.mockRejectedValue(new ApiError(500, 'Server Error'))
      const store = useAuthStore()
      await expect(store.checkAuth()).rejects.toThrow('Server Error')
    })
  })

  describe('login', () => {
    it('sets user and returns { user } for direct login', async () => {
      mockLogin.mockResolvedValue(mockUser)
      const store = useAuthStore()
      const result = await store.login('alice@example.com')
      expect('user' in result).toBe(true)
      expect(store.user).toEqual(mockUser)
      expect(store.loading).toBe(false)
    })

    it('returns { message } for magic link flow', async () => {
      mockLogin.mockResolvedValue({ message: 'Check your email' })
      const store = useAuthStore()
      const result = await store.login('other@example.com')
      expect('message' in result).toBe(true)
      expect(store.user).toBeNull()
    })

    it('resets loading flag after error', async () => {
      mockLogin.mockRejectedValue(new ApiError(400, 'Bad request'))
      const store = useAuthStore()
      await expect(store.login('x')).rejects.toThrow()
      expect(store.loading).toBe(false)
    })
  })

  describe('logout', () => {
    it('clears user', async () => {
      mockMe.mockResolvedValue(mockUser)
      mockLogout.mockResolvedValue({ ok: true })
      const store = useAuthStore()
      await store.checkAuth()
      await store.logout()
      expect(store.user).toBeNull()
    })
  })

  describe('role computeds', () => {
    it('reflects teacher role', async () => {
      mockMe.mockResolvedValue({ ...mockUser, role: 'teacher' })
      const store = useAuthStore()
      await store.checkAuth()
      expect(store.isTeacher).toBe(true)
      expect(store.isTA).toBe(false)
      expect(store.isStudent).toBe(false)
      expect(store.isTeachingStaff).toBe(true)
    })

    it('reflects ta role', async () => {
      mockMe.mockResolvedValue({ ...mockUser, role: 'ta' })
      const store = useAuthStore()
      await store.checkAuth()
      expect(store.isTA).toBe(true)
      expect(store.isTeachingStaff).toBe(true)
    })

    it('reflects student role', async () => {
      mockMe.mockResolvedValue({ ...mockUser, role: 'student' })
      const store = useAuthStore()
      await store.checkAuth()
      expect(store.isStudent).toBe(true)
      expect(store.isTeachingStaff).toBe(false)
    })
  })
})
