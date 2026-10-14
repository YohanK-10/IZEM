<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { taApi } from '../api'
import type { TADashboard } from '../types'
import { Users, ExternalLink } from 'lucide-vue-next'
import { fmtUtc } from '../utils/time'

const router = useRouter()

const data = ref<TADashboard | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null
let notificationRefreshTimer: ReturnType<typeof setTimeout> | null = null

async function fetchDashboard(options: { silent?: boolean } = {}) {
  const { silent = false } = options
  try {
    data.value = await taApi.dashboard()
    error.value = null
  } catch (e) {
    if (!silent || !data.value) {
      error.value = e instanceof Error ? e.message : 'Failed to load dashboard'
    }
  } finally {
    loading.value = false
  }
}

function goToRequest(requestId: number) {
  router.push(`/review-request/${requestId}`)
}

function handleNotificationsUpdated() {
  void fetchDashboard({ silent: true })
  if (notificationRefreshTimer) clearTimeout(notificationRefreshTimer)
  notificationRefreshTimer = setTimeout(() => {
    void fetchDashboard({ silent: true })
  }, 750)
}

onMounted(async () => {
  await fetchDashboard()
  pollTimer = setInterval(() => {
    void fetchDashboard({ silent: true })
  }, 5000)
  window.addEventListener('izem:notifications-updated', handleNotificationsUpdated)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (notificationRefreshTimer) clearTimeout(notificationRefreshTimer)
  window.removeEventListener('izem:notifications-updated', handleNotificationsUpdated)
})

function statusLabel(status: string): string {
  return status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function statusClass(status: string): string {
  const map: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-800',
    ai_generated: 'bg-blue-100 text-blue-800',
    approved: 'bg-green-100 text-green-800',
    edited: 'bg-purple-100 text-purple-800',
    in_person: 'bg-orange-100 text-orange-800',
    resolved: 'bg-gray-100 text-gray-700',
    rejected: 'bg-red-100 text-red-800',
  }
  return map[status] ?? 'bg-gray-100 text-gray-700'
}
</script>

<template>
  <div class="max-w-5xl mx-auto">
    <div v-if="loading" class="text-gray-500 text-sm py-4">Loading dashboard…</div>

    <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
      {{ error }}
    </div>

    <template v-else-if="data">
      <!-- Header -->
      <div class="flex items-center justify-between mb-6">
        <h1 class="text-2xl font-bold text-gray-900">TA Dashboard</h1>
        <span
          v-if="data.request_count > 0"
          class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800"
        >
          {{ data.request_count }} pending
        </span>
      </div>

      <!-- Active Queues -->
      <div v-if="data.active_rooms.length > 0" class="mb-8">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Active Queues</h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <button
            v-for="item in data.active_rooms"
            :key="item.room_id"
            class="block text-left bg-white shadow rounded-lg p-5 hover:shadow-md transition-shadow w-full"
            @click="router.push(`/room/${item.room_id}`)"
          >
            <h3 class="font-semibold text-gray-900">{{ item.assignment_name }}</h3>
            <p class="text-sm text-gray-500">{{ item.course_name }}</p>
            <p class="text-sm text-gray-500 mt-1 flex items-center gap-1">
              <ExternalLink class="w-3 h-3" />
              {{ item.room_name }}
            </p>
            <div class="mt-3 flex items-center justify-between">
              <div class="flex items-center">
                <span class="text-2xl font-bold" :class="item.queue_count > 0 ? 'text-red-600' : 'text-gray-400'">
                  {{ item.queue_count }}
                </span>
                <span class="ml-2 text-sm text-gray-500">waiting</span>
              </div>
              <span class="text-xs text-gray-400">ID: {{ item.room_id }}</span>
            </div>
          </button>
        </div>
      </div>

      <!-- My Courses -->
      <div v-if="data.courses.length > 0" class="mb-8">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">My Courses</h2>
        <div class="bg-white shadow rounded-lg divide-y divide-gray-200">
          <div v-for="course in data.courses" :key="course.id" class="p-4">
            <h3 class="font-semibold text-gray-900 mb-2">{{ course.name }}</h3>
            <div v-if="course.assignments.length > 0" class="space-y-2">
              <div
                v-for="assignment in course.assignments"
                :key="assignment.id"
                class="flex items-center justify-between pl-4"
              >
                <div class="min-w-0 flex items-center gap-2">
                  <span class="text-sm text-gray-700">{{ assignment.name }}</span>
                  <span
                    v-if="assignment.queue_open"
                    class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-100 text-emerald-700"
                  >
                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5"></span>
                    Live
                  </span>
                </div>
                <button
                  class="inline-flex items-center px-3 py-1 text-xs font-medium rounded-md text-gray-700 bg-gray-100 hover:bg-gray-200"
                  @click="router.push(`/course/${course.id}/rooms`)"
                >
                  Manage Rooms
                </button>
              </div>
            </div>
            <p v-else class="text-sm text-gray-500 pl-4">No assignments yet</p>
          </div>
        </div>
      </div>

      <!-- Assigned to Me -->
      <div v-if="data.pending_requests.length > 0" class="mb-8">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Assigned to Me</h2>
        <div class="bg-white shadow rounded-lg overflow-hidden">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Student</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Assignment</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th class="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
              <tr v-for="req in data.pending_requests" :key="req.id" class="hover:bg-gray-50">
                <td class="px-4 py-3 text-sm text-gray-900">{{ req.student_name }}</td>
                <td class="px-4 py-3 text-sm text-gray-600">
                  {{ req.assignment_name }}
                  <span v-if="req.question_number">Q{{ req.question_number }}</span>
                </td>
                <td class="px-4 py-3 text-sm">
                  <span
                    :class="[
                      'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                      statusClass(req.status),
                    ]"
                  >
                    {{ statusLabel(req.status) }}
                  </span>
                </td>
                <td class="px-4 py-3 text-right">
                  <button
                    type="button"
                    class="text-blue-600 hover:text-blue-800 text-sm font-medium"
                    @click="goToRequest(req.id)"
                  >
                    Review
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Recently Resolved -->
      <div class="mb-8">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Recently Resolved</h2>
        <div class="bg-white shadow rounded-lg overflow-hidden">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Student</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Assignment</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Resolved</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
              <tr
                v-for="req in data.recent_resolved"
                :key="req.id"
                class="hover:bg-gray-50 cursor-pointer"
                @click="router.push(`/review-request/${req.id}`)"
              >
                <td class="px-4 py-3 text-sm text-gray-900">{{ req.student_name }}</td>
                <td class="px-4 py-3 text-sm text-gray-600">
                  {{ req.assignment_name }}
                  <span v-if="req.question_number">Q{{ req.question_number }}</span>
                </td>
                <td class="px-4 py-3 text-sm">
                  <span
                    :class="[
                      'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                      statusClass(req.status),
                    ]"
                  >
                    {{ statusLabel(req.status) }}
                  </span>
                </td>
                <td class="px-4 py-3 text-sm text-gray-500">
                  {{ req.resolved_at ? fmtUtc(req.resolved_at) : '—' }}
                </td>
              </tr>
              <tr v-if="data.recent_resolved.length === 0">
                <td colspan="4" class="px-4 py-6 text-sm text-gray-500 text-center">
                  No recently resolved requests yet.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Empty state -->
      <div
        v-if="data.courses.length === 0 && data.active_rooms.length === 0"
        class="bg-white shadow rounded-lg p-8 text-center"
      >
        <Users class="text-gray-300 w-10 h-10 mx-auto mb-3" />
        <h3 class="text-lg font-medium text-gray-900">No courses assigned</h3>
        <p class="text-gray-500 mt-1">Contact your teacher to be assigned to a course.</p>
      </div>
    </template>
  </div>
</template>
