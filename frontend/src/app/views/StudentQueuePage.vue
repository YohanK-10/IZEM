<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Check, Clock } from 'lucide-vue-next'
import { queueApi } from '../api'
import { api } from '../api/client'
import type { QueueState } from '../types'
import { useNotificationsStore } from '../stores/notifications'
import { useUIStore } from '../stores/ui'

const route = useRoute()
const router = useRouter()
const notificationsStore = useNotificationsStore()
const uiStore = useUIStore()
const assignmentId = Number(route.params.assignmentId)

const state = ref<QueueState | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const leaveLoading = ref(false)
const lastStatus = ref<string | null>(null)

const terminalStatuses = ['approved', 'edited', 'in_person'] as const
let pollTimer: ReturnType<typeof setInterval> | null = null

function stopPolling() {
  if (!pollTimer) return
  clearInterval(pollTimer)
  pollTimer = null
}

async function loadQueue() {
  try {
    const next = await queueApi.getState(assignmentId)
    const previousStatus = lastStatus.value
    const nextStatus = next.my_request?.status ?? null

    state.value = next
    lastStatus.value = nextStatus
    error.value = null

    if (previousStatus !== nextStatus) {
      void notificationsStore.fetchNotifications(10, { silent: true }).catch(() => undefined)
    }

    if (next.my_request && terminalStatuses.includes(next.my_request.status as (typeof terminalStatuses)[number])) {
      stopPolling()
      await notificationsStore.fetchNotifications(10, { silent: true }).catch(() => undefined)
      await router.push(`/student/request/${next.my_request.id}`)
      return
    }

    if (!next.assignment.queue_open && !next.my_request) {
      stopPolling()
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load queue'
  } finally {
    loading.value = false
  }
}

async function leaveQueue() {
  const confirmed = await uiStore.confirm({
    title: 'Leave Queue',
    message: 'Leave the queue? Your request will be cancelled.',
    confirmLabel: 'Leave Queue',
    tone: 'danger',
  })
  if (!confirmed) return
  leaveLoading.value = true
  try {
    await api.post('/queue/leave', {})
    await notificationsStore.fetchNotifications(10, { silent: true }).catch(() => undefined)
    await router.push({ name: 'student-home' })
  } catch (err) {
    await uiStore.alert({
      title: 'Could not leave queue',
      message: err instanceof Error ? err.message : 'Failed to leave queue',
      tone: 'danger',
    })
  } finally {
    leaveLoading.value = false
  }
}

onMounted(async () => {
  await notificationsStore.fetchNotifications(10, { silent: true }).catch(() => undefined)
  await loadQueue()
  pollTimer = setInterval(loadQueue, 5000)
})

onUnmounted(() => {
  stopPolling()
})

const myRequest = computed(() => state.value?.my_request ?? null)

const waitingMessage = computed(() => {
  if (!myRequest.value) return 'Waiting for a TA to review your request.'
  if (myRequest.value.status === 'ai_generated') return 'Waiting for a TA to review your request.'
  if (myRequest.value.ai_progress_status === 'processing') return 'AI is analysing your submission.'
  if (myRequest.value.ai_progress_status === 'queued') return 'Your request is queued for AI analysis.'
  return 'Waiting for a TA to review your request.'
})

const statusSteps = [
  { key: 'pending', label: 'In Queue' },
  { key: 'ai_generated', label: 'AI Analysis' },
  { key: 'approved', label: 'Reviewed' },
]

function stepState(stepKey: string): 'done' | 'active' | 'idle' {
  const status = myRequest.value?.status ?? ''
  const order: Record<string, number> = {
    pending: 0,
    ai_generated: 1,
    approved: 2,
    edited: 2,
    in_person: 2,
  }
  const current = order[status] ?? -1
  const step = order[stepKey] ?? 99
  if (current > step) return 'done'
  if (current === step) return 'active'
  return 'idle'
}

function openRooms() {
  if (!state.value) return
  if (state.value.rooms.length === 1) {
    router.push(`/room/${state.value.rooms[0].id}`)
    return
  }
  router.push(`/course/${state.value.assignment.course_id}/rooms`)
}
</script>

<template>
  <div class="max-w-2xl mx-auto p-6">
    <button
      class="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline mb-5"
      @click="router.push({ name: 'student-home' })"
    >
      <ArrowLeft class="w-4 h-4" />
      Back to dashboard
    </button>

    <div v-if="loading" class="text-gray-500 text-sm">Loading queue...</div>

    <div v-else-if="error && !state" class="bg-red-50 border border-red-200 text-red-800 p-4 rounded-lg text-sm">
      {{ error }}
    </div>

    <template v-else-if="state">
      <div class="mb-6">
        <h1 class="text-2xl font-bold text-gray-900">{{ state.assignment.name }}</h1>
        <p v-if="state.course" class="text-sm text-gray-500 mt-1">{{ state.course.name }}</p>
        <span
          v-if="!state.assignment.queue_open"
          class="inline-block mt-2 text-xs bg-red-100 text-red-700 px-2.5 py-1 rounded-full font-medium"
        >
          Queue is closed
        </span>
      </div>

      <div v-if="myRequest" class="mb-6 bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div class="flex items-center gap-5 px-6 py-5 border-b border-gray-100">
          <div
            class="w-16 h-16 rounded-full bg-blue-600 text-white flex flex-col items-center justify-center flex-shrink-0"
          >
            <span class="text-xs font-medium opacity-80 leading-none">#</span>
            <span class="text-2xl font-bold leading-tight">{{ myRequest.queue_position ?? '-' }}</span>
          </div>
          <div>
            <p class="font-semibold text-gray-900">You're in the queue</p>
            <p class="text-sm text-gray-500 mt-0.5">
              {{ waitingMessage }}
            </p>
            <p class="text-xs text-gray-400 mt-1 flex items-center gap-1">
              <Clock class="w-3 h-3" />
              Updates every 5 seconds
            </p>
          </div>
        </div>

        <div class="px-6 py-4 flex items-center gap-2">
          <template v-for="(step, idx) in statusSteps" :key="step.key">
            <div class="flex items-center gap-2 flex-shrink-0">
              <div
                :class="[
                  'w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors',
                  stepState(step.key) === 'done'
                    ? 'bg-blue-600 text-white'
                    : stepState(step.key) === 'active'
                      ? 'bg-blue-600 text-white ring-4 ring-blue-100'
                      : 'bg-gray-100 text-gray-400',
                ]"
              >
                <Check v-if="stepState(step.key) === 'done'" class="w-3.5 h-3.5" />
                <span v-else>{{ idx + 1 }}</span>
              </div>
              <span
                :class="[
                  'text-xs font-medium',
                  stepState(step.key) === 'active'
                    ? 'text-blue-700'
                    : stepState(step.key) === 'done'
                      ? 'text-blue-700'
                      : 'text-gray-400',
                ]"
              >
                {{ step.label }}
              </span>
            </div>
            <div
              v-if="idx < statusSteps.length - 1"
              :class="[
                'flex-1 h-0.5 min-w-4',
                stepState(statusSteps[idx + 1].key) !== 'idle' ? 'bg-blue-200' : 'bg-gray-200',
              ]"
            />
          </template>
        </div>

        <div class="px-6 py-3 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
          <p class="text-xs text-gray-500">
            <span class="font-semibold text-gray-700">{{ state.total_in_queue }}</span>
            student{{ state.total_in_queue === 1 ? '' : 's' }} waiting total
          </p>
          <button
            :disabled="leaveLoading"
            class="text-xs text-red-600 hover:text-red-700 border border-red-200 hover:border-red-300 bg-white rounded-lg px-3 py-1.5 disabled:opacity-50 transition-colors"
            @click="leaveQueue"
          >
            {{ leaveLoading ? 'Leaving...' : 'Leave Queue' }}
          </button>
        </div>
      </div>

      <div
        v-else-if="state.assignment.queue_open"
        class="mb-6 bg-gray-50 border border-gray-200 rounded-xl p-6 text-center"
      >
        <p class="text-gray-700 text-sm mb-3">You haven't joined this lab queue yet.</p>
        <template v-if="state.rooms.length > 0">
          <button
            class="inline-block bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-2 rounded-lg transition-colors"
            @click="openRooms"
          >
            {{ state.rooms.length === 1 ? 'Open Room' : 'View Rooms' }}
          </button>
          <p class="mt-2 text-xs text-gray-500">Queues are joined from the room page.</p>
        </template>
        <p v-else class="text-xs text-gray-500">No rooms are available for this lab yet.</p>
      </div>

      <div v-if="state.rooms.length > 0" class="mb-4">
        <h2 class="text-sm font-semibold text-gray-700 mb-2">Rooms</h2>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="room in state.rooms"
            :key="room.id"
            type="button"
            class="bg-white border border-gray-200 text-sm px-3 py-1.5 rounded-lg text-gray-700 hover:border-blue-300 hover:text-blue-700 transition-colors"
            @click="router.push(`/room/${room.id}`)"
          >
            <span class="font-medium">{{ room.name }}</span>
            <span v-if="room.location" class="text-gray-400 ml-1">- {{ room.location }}</span>
          </button>
        </div>
      </div>
    </template>
  </div>
</template>
