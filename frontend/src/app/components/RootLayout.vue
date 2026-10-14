<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'
import { useNotificationsStore } from '../stores/notifications'
import type { NotificationItem } from '../types'

import Sidebar from './Sidebar.vue'
import AppDialog from './AppDialog.vue'
import IZEMLogo from './IZEMLogo.vue'
import { Bell, Menu, X } from 'lucide-vue-next'

const authStore = useAuthStore()
const notificationsStore = useNotificationsStore()
const route = useRoute()
const router = useRouter()

const mobileOpen = ref(false)
const notificationsOpen = ref(false)
const notificationsPanel = ref<HTMLElement | null>(null)

const homePath = computed(() => {
  if (authStore.isTA) return '/ta-dashboard'
  if (authStore.isStudent) return '/student-home'
  return '/'
})

const notifications = computed(() => notificationsStore.items)
const unreadCount = computed(() => notificationsStore.unread)

function formatNotificationTime(value: string | null) {
  if (!value) return 'Just now'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return ''
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(parsed)
}

async function toggleNotifications() {
  notificationsOpen.value = !notificationsOpen.value
  if (notificationsOpen.value) {
    await notificationsStore.fetchNotifications(10)
  }
}

async function openNotification(item: NotificationItem) {
  try {
    if (!item.read) {
      await notificationsStore.markRead(item.id)
    }
  } finally {
    notificationsOpen.value = false
    if (route.fullPath !== item.link) {
      await router.push(item.link)
    }
  }
}

async function markAllNotificationsRead() {
  await notificationsStore.markAllRead()
}

function handleDocumentClick(event: MouseEvent) {
  const target = event.target as Node | null
  if (notificationsPanel.value && target && !notificationsPanel.value.contains(target)) {
    notificationsOpen.value = false
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    notificationsOpen.value = false
    mobileOpen.value = false
  }
}

function handleVisibilityChange() {
  if (document.visibilityState === 'visible' && authStore.isAuthenticated) {
    void notificationsStore.fetchNotifications(10, { silent: true }).catch(() => undefined)
  }
}

watch(
  () => authStore.isAuthenticated,
  (isAuthenticated) => {
    if (isAuthenticated) {
      void notificationsStore.fetchNotifications(10, { silent: true }).catch(() => undefined)
      notificationsStore.startPolling(10)
      return
    }

    notificationsOpen.value = false
    notificationsStore.clear()
  },
  { immediate: true },
)

watch(
  () => route.fullPath,
  () => {
    notificationsOpen.value = false
  },
)

onMounted(() => {
  document.addEventListener('mousedown', handleDocumentClick)
  document.addEventListener('keydown', handleKeydown)
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onUnmounted(() => {
  notificationsStore.stopPolling()
  document.removeEventListener('mousedown', handleDocumentClick)
  document.removeEventListener('keydown', handleKeydown)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<template>
  <div class="h-screen flex overflow-hidden bg-gray-50 text-gray-900 antialiased">
    <!-- Desktop Sidebar -->
    <Sidebar />

    <!-- Mobile Sidebar overlay -->
    <div v-if="mobileOpen" class="fixed inset-0 z-40 md:hidden" role="dialog">
      <div class="fixed inset-0 bg-gray-900/50" @click="mobileOpen = false" />
      <div class="fixed inset-y-0 left-0 w-72 bg-white border-r border-gray-200 shadow-xl flex flex-col z-50">
        <div class="h-16 flex items-center px-6 border-b border-gray-200 justify-between">
          <RouterLink :to="homePath" class="flex items-center gap-3" @click="mobileOpen = false">
            <IZEMLogo :size="32" />
            <span class="text-lg font-semibold text-gray-900">IZEM</span>
          </RouterLink>
          <button class="text-gray-500 hover:text-gray-700" @click="mobileOpen = false">
            <X class="w-5 h-5" />
          </button>
        </div>
        <nav class="flex-1 overflow-y-auto py-4">
          <RouterLink
            v-if="authStore.isTeacher"
            to="/"
            class="flex items-center px-6 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50"
            @click="mobileOpen = false"
          >
            Courses
          </RouterLink>
          <RouterLink
            v-else-if="authStore.isTA"
            to="/ta-dashboard"
            class="flex items-center px-6 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50"
            @click="mobileOpen = false"
          >
            Dashboard
          </RouterLink>
          <RouterLink
            v-else
            to="/student-home"
            class="flex items-center px-6 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50"
            @click="mobileOpen = false"
          >
            Home
          </RouterLink>
          <template v-if="authStore.isTeacher">
            <RouterLink
              to="/analytics"
              class="flex items-center px-6 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50"
              @click="mobileOpen = false"
            >
              Analytics
            </RouterLink>
            <RouterLink
              to="/llm-settings"
              class="flex items-center px-6 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50"
              @click="mobileOpen = false"
            >
              AI Settings
            </RouterLink>
          </template>
        </nav>
        <div class="p-4 border-t border-gray-200 text-sm">
          <div class="font-medium">{{ authStore.user?.name }}</div>
          <div class="text-gray-500 text-xs">{{ authStore.user?.role?.toUpperCase() }}</div>
        </div>
      </div>
    </div>

    <!-- Main -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- Header -->
      <header
        class="relative z-30 h-16 bg-white/80 backdrop-blur border-b border-gray-200 flex items-center justify-between px-4 sm:px-6 lg:px-8 flex-shrink-0"
      >
        <button class="md:hidden text-gray-500 hover:text-gray-700" @click="mobileOpen = true">
          <Menu class="w-5 h-5" />
        </button>
        <div class="flex-1" />
        <div class="flex items-center space-x-3">
          <div ref="notificationsPanel" class="relative">
            <button
              type="button"
              class="text-gray-500 hover:text-gray-700 relative rounded-full p-2 hover:bg-gray-100 transition-colors"
              :aria-label="unreadCount > 0 ? `${unreadCount} unread notifications` : 'Notifications'"
              @click="toggleNotifications"
            >
              <Bell :class="['w-5 h-5', unreadCount > 0 ? 'text-blue-600' : '']" />
              <span
                v-if="unreadCount > 0"
                class="absolute -top-0.5 -right-0.5 min-w-[1.1rem] h-[1.1rem] px-1 rounded-full bg-blue-600 text-white text-[10px] leading-[1.1rem] font-semibold text-center"
              >
                {{ unreadCount > 9 ? '9+' : unreadCount }}
              </span>
            </button>

            <div
              v-if="notificationsOpen"
              class="absolute right-0 mt-2 w-[22rem] max-w-[calc(100vw-2rem)] overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl z-50"
            >
              <div class="flex items-start justify-between gap-3 px-4 py-3 border-b border-gray-100">
                <div>
                  <h2 class="text-sm font-semibold text-gray-900">Notifications</h2>
                  <p class="text-xs text-gray-500">
                    {{ unreadCount > 0 ? `${unreadCount} unread` : 'You are all caught up.' }}
                  </p>
                </div>
                <button
                  v-if="notificationsStore.hasUnread"
                  type="button"
                  class="text-xs font-medium text-blue-600 hover:text-blue-700"
                  @click="markAllNotificationsRead"
                >
                  Mark all read
                </button>
              </div>

              <div
                v-if="notificationsStore.loading && !notificationsStore.initialized"
                class="px-4 py-6 text-sm text-gray-500"
              >
                Loading notifications...
              </div>
              <div v-else-if="notifications.length === 0" class="px-4 py-8 text-sm text-gray-500">
                No notifications yet.
              </div>
              <ul v-else class="max-h-[26rem] overflow-y-auto divide-y divide-gray-100">
                <li v-for="item in notifications" :key="item.id">
                  <button
                    type="button"
                    class="w-full px-4 py-3 text-left hover:bg-gray-50 transition-colors"
                    @click="openNotification(item)"
                  >
                    <div class="flex items-start gap-3">
                      <span
                        :class="[
                          'mt-1 h-2.5 w-2.5 rounded-full flex-shrink-0',
                          item.read ? 'bg-gray-200' : 'bg-blue-500',
                        ]"
                      />
                      <div class="min-w-0 flex-1">
                        <p :class="['text-sm leading-5', item.read ? 'text-gray-600' : 'font-medium text-gray-900']">
                          {{ item.message }}
                        </p>
                        <p class="mt-1 text-xs text-gray-500">
                          {{ formatNotificationTime(item.created_at) }}
                        </p>
                      </div>
                    </div>
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </header>

      <!-- Page content -->
      <main class="py-6 px-4 sm:px-6 lg:px-8 flex-1 overflow-y-auto">
        <RouterView :key="route.fullPath" />
      </main>
    </div>
  </div>
  <AppDialog />
</template>
