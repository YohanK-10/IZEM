<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { api } from '../api/client'
import { useNotificationsStore } from '../stores/notifications'

const route = useRoute()
const requestId = computed(() => Number(route.params.requestId))
const notificationsStore = useNotificationsStore()

const data = ref<any>(null)
const loading = ref(true)
const error = ref<string | null>(null)

let pollTimer: ReturnType<typeof setInterval> | null = null

function stopPolling() {
  if (!pollTimer) return
  clearInterval(pollTimer)
  pollTimer = null
}

function restartPollingIfNeeded() {
  stopPolling()
  if (data.value && !['approved', 'edited', 'in_person', 'resolved'].includes(data.value.status)) {
    pollTimer = setInterval(loadRequest, 5000)
  }
}

async function loadRequest() {
  try {
    const statusRes = await api.get<any>(`/student/request/${requestId.value}/status`)
    const previousStatus = data.value?.status ?? null
    if (data.value) {
      data.value.status = statusRes.status
      data.value.final_feedback = statusRes.final_feedback
      data.value.ai_progress_status = statusRes.ai_progress_status
    }
    if (previousStatus !== statusRes.status) {
      void notificationsStore.fetchNotifications(10, { silent: true }).catch(() => undefined)
    }
    // Stop polling once terminal
    if (['approved', 'edited', 'in_person', 'resolved'].includes(statusRes.status) && pollTimer) {
      stopPolling()
    }
  } catch {
    // ignore poll errors
  }
}

async function loadFull() {
  try {
    data.value = await api.get<any>(`/student/request/${requestId.value}`)
    void notificationsStore.fetchNotifications(10, { silent: true }).catch(() => undefined)
    error.value = null
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load request'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadFull()
  restartPollingIfNeeded()
})

onUnmounted(() => {
  stopPolling()
})

watch(
  () => route.params.requestId,
  async () => {
    data.value = null
    loading.value = true
    error.value = null
    await loadFull()
    restartPollingIfNeeded()
  },
)

const isWaiting = computed(() => ['pending', 'ai_generated'].includes(data.value?.status ?? ''))
const isInPerson = computed(() => data.value?.status === 'in_person')
const hasFeedback = computed(
  () => ['approved', 'edited'].includes(data.value?.status ?? '') && data.value?.final_feedback,
)

const waitingMessage = computed(() => {
  if (!data.value) return 'in the queue'
  if (data.value.status === 'ai_generated') return 'being reviewed by a TA'
  if (data.value.ai_progress_status === 'processing') return 'being analysed by AI'
  if (data.value.ai_progress_status === 'queued') return 'queued for AI analysis'
  return 'in the queue'
})

function statusBadge(status: string) {
  const map: Record<string, string> = {
    pending: 'bg-amber-100 text-amber-800',
    ai_generated: 'bg-sky-100 text-sky-800',
    approved: 'bg-emerald-100 text-emerald-800',
    edited: 'bg-violet-100 text-violet-800',
    in_person: 'bg-orange-100 text-orange-800',
    resolved: 'bg-gray-100 text-gray-700',
  }
  return map[status] ?? 'bg-gray-100 text-gray-700'
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    pending: 'Waiting in queue',
    ai_generated: 'Being reviewed',
    approved: 'Feedback ready',
    edited: 'Feedback ready',
    in_person: 'In-person help needed',
    resolved: 'Resolved',
  }
  return map[status] ?? status
}

async function copyFeedback() {
  const text = data.value?.final_feedback ?? ''
  if (text) await navigator.clipboard.writeText(text)
}
</script>

<template>
  <div class="p-6">
    <!-- Back nav -->
    <RouterLink to="/student-home" class="text-sm text-blue-600 hover:underline mb-4 block">
      ← Back to dashboard
    </RouterLink>

    <div v-if="loading" class="text-gray-500 text-sm">Loading request…</div>

    <div v-else-if="error" class="bg-red-50 border border-red-200 text-red-800 p-4 rounded text-sm">
      {{ error }}
    </div>

    <template v-else-if="data">
      <!-- Header -->
      <div class="flex items-start justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 class="text-xl font-bold text-gray-900">
            {{ data.assignment_name }}
            <span v-if="data.question_number" class="text-gray-400">— Q{{ data.question_number }}</span>
          </h1>
          <p class="text-sm text-gray-500 mt-1">Submitted {{ data.created_at }}</p>
        </div>
        <span :class="['text-sm px-3 py-1 rounded-full font-medium', statusBadge(data.status)]">
          {{ statusLabel(data.status) }}
        </span>
      </div>

      <!-- In-person banner -->
      <div v-if="isInPerson" class="mb-6 bg-orange-50 border border-orange-300 rounded-lg p-5">
        <div class="flex items-start gap-3">
          <span class="text-2xl">✋</span>
          <div>
            <h2 class="font-bold text-orange-900 text-base mb-1">Raise your hand!</h2>
            <p class="text-sm text-orange-800">
              A TA needs to help you in person. Please raise your hand or approach the TA desk.
            </p>
            <p v-if="data.final_feedback" class="text-sm text-orange-700 mt-2">Note: {{ data.final_feedback }}</p>
          </div>
        </div>
      </div>

      <!-- Waiting status -->
      <div v-else-if="isWaiting" class="mb-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p class="text-sm text-blue-800">
          Your request is
          <span class="font-medium">{{ waitingMessage }}</span>
          . This page updates automatically every 5 seconds.
        </p>
        <p v-if="data.ta_name" class="text-xs text-blue-600 mt-1">TA: {{ data.ta_name }}</p>
      </div>

      <!-- Feedback ready -->
      <div v-if="hasFeedback" class="mb-6 bg-emerald-50 border border-emerald-200 rounded-lg p-5">
        <div class="flex items-center justify-between mb-3">
          <h2 class="font-semibold text-emerald-900 text-base">Feedback</h2>
          <button
            class="text-xs text-emerald-700 border border-emerald-300 rounded px-2 py-0.5 hover:bg-emerald-100"
            @click="copyFeedback"
          >
            Copy
          </button>
        </div>
        <p class="text-sm text-emerald-800 whitespace-pre-wrap">{{ data.final_feedback }}</p>
      </div>

      <!-- Your submission -->
      <div class="bg-white border border-gray-200 rounded-lg p-5 mb-4">
        <h2 class="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">Your Submission</h2>

        <div v-if="data.problem_description" class="mb-3">
          <p class="text-xs text-gray-500 mb-1">Question</p>
          <p class="text-sm text-gray-800">{{ data.problem_description }}</p>
        </div>

        <div v-if="data.submission_text" class="mb-3">
          <p class="text-xs text-gray-500 mb-1">Your answer</p>
          <pre class="text-sm text-gray-800 whitespace-pre-wrap font-sans bg-gray-50 rounded p-3">{{
            data.submission_text
          }}</pre>
        </div>

        <div v-if="data.submission_image_url" class="mb-3">
          <p class="text-xs text-gray-500 mb-1">Image</p>
          <img
            :src="data.submission_image_url"
            alt="Your submission"
            class="max-w-full rounded border border-gray-200"
          />
        </div>

        <div v-if="data.student_comment">
          <p class="text-xs text-gray-500 mb-1">Your comment</p>
          <p class="text-sm text-gray-800">{{ data.student_comment }}</p>
        </div>
      </div>

      <!-- Link to queue -->
      <div v-if="isWaiting && data.assignment_id" class="text-sm">
        <RouterLink :to="`/student-queue/${data.assignment_id}`" class="text-blue-600 hover:underline">
          View queue status →
        </RouterLink>
      </div>
    </template>
  </div>
</template>
