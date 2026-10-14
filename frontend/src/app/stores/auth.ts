import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User } from '../types'
import { authApi, ApiError } from '../api'
import { setSessionExpiredHandler } from '../api/client'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const loading = ref(false)
  const initialized = ref(false)

  // Register the global 401 handler so any expired-session response clears
  // the store and sends the user to /login cleanly.
  setSessionExpiredHandler(() => {
    user.value = null
    window.location.href = '/login'
  })

  const isAuthenticated = computed(() => user.value !== null)
  const isTeacher = computed(() => user.value?.role === 'teacher')
  const isTA = computed(() => user.value?.role === 'ta')
  const isStudent = computed(() => user.value?.role === 'student')
  const isTeachingStaff = computed(() => ['teacher', 'ta'].includes(user.value?.role ?? ''))

  /** Fetch current user from the backend. Returns false if not authenticated. */
  async function checkAuth(): Promise<boolean> {
    try {
      user.value = await authApi.me()
      initialized.value = true
      return true
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        user.value = null
        initialized.value = true
        return false
      }
      throw err
    }
  }

  /**
   * Login with an email address.
   * - Test accounts (ALLOW_TEST_ACCOUNTS=true): sets cookie, returns user.
   * - Normal accounts: sends magic link, returns a message string.
   */
  async function login(email: string): Promise<{ user: User } | { message: string }> {
    loading.value = true
    try {
      const result = await authApi.login(email)
      if ('id' in result) {
        user.value = result as User
        return { user: user.value }
      }
      return { message: (result as { message: string }).message }
    } finally {
      loading.value = false
    }
  }

  async function logout(): Promise<void> {
    await authApi.logout()
    user.value = null
  }

  return {
    user,
    loading,
    initialized,
    isAuthenticated,
    isTeacher,
    isTA,
    isStudent,
    isTeachingStaff,
    checkAuth,
    login,
    logout,
  }
})
