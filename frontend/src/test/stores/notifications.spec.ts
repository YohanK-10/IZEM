import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useNotificationsStore } from '@/app/stores/notifications'
import * as api from '@/app/api'
import type { NotificationsResponse } from '@/app/types'

vi.mock('@/app/api', () => ({
  notificationsApi: {
    list: vi.fn(),
    markRead: vi.fn(),
    markAllRead: vi.fn(),
  },
}))

const mockResponse: NotificationsResponse = {
  unread: 2,
  items: [
    {
      id: 1,
      type: 'queue',
      message: 'You have a queue update',
      read: false,
      link: '/queue/1',
      created_at: null,
    },
    { id: 2, type: 'system', message: 'System notice', read: false, link: '', created_at: null },
    { id: 3, type: 'queue', message: 'Old notification', read: true, link: '', created_at: null },
  ],
}

describe('useNotificationsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts empty and uninitialized', () => {
    const store = useNotificationsStore()
    expect(store.items).toEqual([])
    expect(store.unread).toBe(0)
    expect(store.initialized).toBe(false)
    expect(store.hasUnread).toBe(false)
  })

  describe('fetchNotifications', () => {
    it('populates items and unread count', async () => {
      vi.mocked(api.notificationsApi.list).mockResolvedValue(mockResponse)
      const store = useNotificationsStore()
      await store.fetchNotifications()
      expect(store.items).toHaveLength(3)
      expect(store.unread).toBe(2)
      expect(store.initialized).toBe(true)
      expect(store.hasUnread).toBe(true)
    })

    it('dispatches izem:notifications-updated event', async () => {
      vi.mocked(api.notificationsApi.list).mockResolvedValue(mockResponse)
      const store = useNotificationsStore()
      const listener = vi.fn()
      window.addEventListener('izem:notifications-updated', listener)
      await store.fetchNotifications()
      window.removeEventListener('izem:notifications-updated', listener)
      expect(listener).toHaveBeenCalled()
    })
  })

  describe('markRead', () => {
    it('marks item read and decrements unread optimistically', async () => {
      vi.mocked(api.notificationsApi.list).mockResolvedValue(mockResponse)
      vi.mocked(api.notificationsApi.markRead).mockResolvedValue({ status: 'ok' })
      const store = useNotificationsStore()
      await store.fetchNotifications()
      await store.markRead(1)
      expect(store.items.find((i) => i.id === 1)?.read).toBe(true)
      expect(store.unread).toBe(1)
    })

    it('does not decrement unread for already-read items', async () => {
      vi.mocked(api.notificationsApi.list).mockResolvedValue(mockResponse)
      vi.mocked(api.notificationsApi.markRead).mockResolvedValue({ status: 'ok' })
      const store = useNotificationsStore()
      await store.fetchNotifications()
      await store.markRead(3) // already read
      expect(store.unread).toBe(2)
    })

    it('re-fetches on API error', async () => {
      vi.mocked(api.notificationsApi.list).mockResolvedValue(mockResponse)
      vi.mocked(api.notificationsApi.markRead).mockRejectedValue(new Error('fail'))
      const store = useNotificationsStore()
      await store.fetchNotifications()
      vi.mocked(api.notificationsApi.list).mockResolvedValue({ ...mockResponse, unread: 2 })
      await expect(store.markRead(1)).rejects.toThrow('fail')
      expect(api.notificationsApi.list).toHaveBeenCalledTimes(2)
    })
  })

  describe('markAllRead', () => {
    it('marks all items read and zeroes unread', async () => {
      vi.mocked(api.notificationsApi.list).mockResolvedValue(mockResponse)
      vi.mocked(api.notificationsApi.markAllRead).mockResolvedValue({ status: 'ok' })
      const store = useNotificationsStore()
      await store.fetchNotifications()
      await store.markAllRead()
      expect(store.unread).toBe(0)
      expect(store.items.every((i) => i.read)).toBe(true)
    })

    it('is a no-op when nothing is unread', async () => {
      vi.mocked(api.notificationsApi.list).mockResolvedValue({ unread: 0, items: [] })
      const store = useNotificationsStore()
      await store.fetchNotifications()
      await store.markAllRead()
      expect(api.notificationsApi.markAllRead).not.toHaveBeenCalled()
    })
  })

  describe('polling', () => {
    it('starts and stops polling', async () => {
      vi.mocked(api.notificationsApi.list).mockResolvedValue(mockResponse)
      const store = useNotificationsStore()
      store.startPolling()
      vi.advanceTimersByTime(5000)
      await Promise.resolve()
      expect(api.notificationsApi.list).toHaveBeenCalled()
      store.stopPolling()
    })
  })

  describe('clear', () => {
    it('resets all state', async () => {
      vi.mocked(api.notificationsApi.list).mockResolvedValue(mockResponse)
      const store = useNotificationsStore()
      await store.fetchNotifications()
      store.clear()
      expect(store.items).toEqual([])
      expect(store.unread).toBe(0)
      expect(store.initialized).toBe(false)
    })
  })
})
