<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { studentApi } from '../api'
import type { StudentDashboard, StudentAssignment } from '../types'
import { BookOpen, Clock, ArrowRight } from 'lucide-vue-next'
import { useNotificationsStore } from '../stores/notifications'

const router = useRouter()
const notificationsStore = useNotificationsStore()

const data = ref<StudentDashboard | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

async function fetchDashboard(options: { silent?: boolean } = {}) {
  const { silent = false } = options
  try {
    data.value = await studentApi.dashboard()
    await notificationsStore.fetchNotifications(10, { silent: true })
    error.value = null
  } catch (e) {
    if (!silent || !data.value) {
      error.value = e instanceof Error ? e.message : 'Failed to load dashboard'
    }
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await fetchDashboard()
  pollTimer = setInterval(() => {
    void fetchDashboard({ silent: true })
  }, 5000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})

function openAssignmentRoom(assignment: StudentAssignment) {
  if (assignment.rooms.length === 1) {
    router.push(`/room/${assignment.rooms[0].id}`)
    return
  }
  router.push(`/course/${assignment.course_id}/rooms`)
}

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
  <div class="max-w-4xl mx-auto">
    <div v-if="loading" class="text-gray-500 text-sm py-4">Loading…</div>

    <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
      {{ error }}
    </div>

    <template v-else-if="data">
      <h1 class="text-2xl font-bold text-gray-900 mb-6">Home</h1>

      <!-- In-queue banner -->
      <div
        v-if="data.in_queue && data.active_assignment_id"
        class="mb-6 bg-blue-50 border border-blue-200 rounded-lg p-4"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <Clock class="text-blue-600 w-6 h-6 flex-shrink-0" />
            <div>
              <p class="font-medium text-blue-900">You're in the queue</p>
              <p class="text-sm text-blue-700">Waiting for a TA to help you.</p>
            </div>
          </div>
          <RouterLink
            :to="`/student-queue/${data.active_assignment_id}`"
            class="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
          >
            Go to Queue
            <ArrowRight class="ml-2 w-4 h-4" />
          </RouterLink>
        </div>
      </div>

      <!-- Open Sessions -->
      <div v-if="data.open_assignments.length > 0" class="mb-8">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Open Sessions</h2>
        <div class="space-y-3">
          <div
            v-for="assignment in data.open_assignments"
            :key="assignment.id"
            class="bg-white shadow rounded-lg p-5 flex items-center justify-between gap-4"
          >
            <div class="min-w-0">
              <h3 class="text-base font-semibold text-gray-900 truncate">{{ assignment.name }}</h3>
              <p class="text-sm text-gray-500">{{ assignment.course_name }}</p>
              <p class="text-xs text-gray-400 mt-1">
                {{ assignment.questions.length }} question{{ assignment.questions.length !== 1 ? 's' : '' }}
                <span v-if="assignment.rooms.length > 0">
                  · {{ assignment.rooms.length }} room{{ assignment.rooms.length !== 1 ? 's' : '' }}
                </span>
              </p>
            </div>
            <div class="flex items-center gap-3 flex-shrink-0">
              <span
                class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800"
              >
                <span class="w-1.5 h-1.5 rounded-full bg-green-500 mr-1.5"></span>
                Open
              </span>
              <button
                v-if="!data.in_queue"
                class="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 shadow-sm transition-colors"
                @click="openAssignmentRoom(assignment)"
              >
                {{ assignment.rooms.length === 1 ? 'Open Room' : 'View Rooms' }}
              </button>
              <span v-else class="text-xs text-gray-400 italic">Already in queue</span>
            </div>
          </div>
        </div>
      </div>

      <!-- My Courses (no open sessions) -->
      <div v-else-if="data.enrolled_courses.length > 0" class="mb-8">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">My Courses</h2>
        <div class="bg-white shadow rounded-lg divide-y divide-gray-200">
          <div v-for="course in data.enrolled_courses" :key="course.id" class="p-4 flex items-center justify-between">
            <div>
              <p class="font-medium text-gray-900">{{ course.name }}</p>
              <p class="text-sm text-gray-500">No open sessions right now</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else class="mb-8 bg-white shadow rounded-lg p-8 text-center">
        <BookOpen class="text-gray-300 w-10 h-10 mx-auto mb-3" />
        <h3 class="text-lg font-medium text-gray-900">No courses yet</h3>
        <p class="text-gray-500 mt-1">Contact your teacher to be enrolled in a course.</p>
      </div>

      <!-- Help History -->
      <div v-if="data.recent_requests.length > 0">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Help History</h2>
        <div class="bg-white shadow rounded-lg overflow-hidden">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Assignment</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Question</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
              <tr
                v-for="req in data.recent_requests"
                :key="req.id"
                class="hover:bg-gray-50 cursor-pointer"
                @click="router.push(`/student/request/${req.id}`)"
              >
                <td class="px-4 py-3 text-sm text-gray-900">{{ req.assignment_name }}</td>
                <td class="px-4 py-3 text-sm text-gray-600">
                  <span v-if="req.question_number">Q{{ req.question_number }}</span>
                  <span v-else>—</span>
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
                <td class="px-4 py-3 text-sm text-gray-500">{{ req.created_at }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
