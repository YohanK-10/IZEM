import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { notificationsApi } from '../api'
import type { NotificationItem } from '../types'

let pollTimer: ReturnType<typeof setInterval> | null = null

export const useNotificationsStore = defineStore('notifications', () => {
  const items = ref<NotificationItem[]>([])
  const unread = ref(0)
  const loading = ref(false)
  const initialized = ref(false)

  const hasUnread = computed(() => unread.value > 0)

  async function fetchNotifications(limit = 10, options: { silent?: boolean } = {}) {
    const { silent = false } = options
    if (!silent) loading.value = true

    try {
      const data = await notificationsApi.list(limit)
      items.value = data.items
      unread.value = data.unread
      initialized.value = true
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('izem:notifications-updated'))
      }
      return data
    } finally {
      if (!silent) loading.value = false
    }
  }

  async function markRead(notificationId: number) {
    const item = items.value.find((entry) => entry.id === notificationId)
    if (item && !item.read) {
      item.read = true
      unread.value = Math.max(0, unread.value - 1)
    }

    try {
      await notificationsApi.markRead(notificationId)
    } catch (error) {
      await fetchNotifications(items.value.length || 10, { silent: true })
      throw error
    }
  }

  async function markAllRead() {
    if (!items.value.length || unread.value === 0) return

    items.value = items.value.map((item) => ({ ...item, read: true }))
    unread.value = 0

    try {
      await notificationsApi.markAllRead()
    } catch (error) {
      await fetchNotifications(items.value.length || 10, { silent: true })
      throw error
    }
  }

  function startPolling(limit = 10) {
    if (pollTimer) return
    pollTimer = setInterval(() => {
      void fetchNotifications(limit, { silent: true }).catch(() => undefined)
    }, 5000)
  }

  function stopPolling() {
    if (!pollTimer) return
    clearInterval(pollTimer)
    pollTimer = null
  }

  function clear() {
    stopPolling()
    items.value = []
    unread.value = 0
    loading.value = false
    initialized.value = false
  }

  return {
    items,
    unread,
    loading,
    initialized,
    hasUnread,
    fetchNotifications,
    markRead,
    markAllRead,
    startPolling,
    stopPolling,
    clear,
  }
})
