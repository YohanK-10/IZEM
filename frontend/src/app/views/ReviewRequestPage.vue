<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'

const route = useRoute()
const router = useRouter()
const requestId = computed(() => Number(route.params.requestId))
const fromOvertime = computed(() => route.query.from === 'overtime')
const overtimeCourseId = computed(() => (route.query.courseId ? Number(route.query.courseId) : null))

function goBack() {
  if (fromOvertime.value && overtimeCourseId.value) {
    router.push(`/course/${overtimeCourseId.value}/overview`)
  } else {
    router.push('/ta-dashboard')
  }
}

const data = ref<any>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const actionError = ref<string | null>(null)
const actionLoading = ref(false)

// Edit mode
const editMode = ref(false)
const editFeedback = ref('')

// Reject reason
const rejectMode = ref(false)
const rejectReason = ref('In-person help required')

let pollTimer: ReturnType<typeof setInterval> | null = null

function stopPolling() {
  if (!pollTimer) return
  clearInterval(pollTimer)
  pollTimer = null
}

function restartPollingIfNeeded() {
  stopPolling()
  if (data.value && !data.value.ai_feedback && data.value.ai_progress_status !== 'error') {
    pollTimer = setInterval(loadRequest, 3000)
  }
}

async function loadRequest() {
  try {
    data.value = await api.get<any>(`/ta/request/${requestId.value}`)
    error.value = null
    // Stop polling once AI feedback is ready or errored
    if ((data.value.ai_feedback || data.value.ai_progress_status === 'error') && pollTimer) {
      stopPolling()
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load request'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadRequest()
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
    actionError.value = null
    actionLoading.value = false
    editMode.value = false
    editFeedback.value = ''
    rejectMode.value = false
    rejectReason.value = 'In-person help required'
    await loadRequest()
    restartPollingIfNeeded()
  },
)

const isTerminal = computed(() => ['approved', 'edited', 'in_person', 'resolved'].includes(data.value?.status ?? ''))
const claimedByOtherReviewer = computed(() =>
  Boolean(data.value && !isTerminal.value && data.value.can_review === false),
)
const reviewOwnerLabel = computed(() => data.value?.assigned_ta_name || 'another TA')

async function approve() {
  actionLoading.value = true
  actionError.value = null
  try {
    await api.post(`/ta/request/${requestId.value}/approve`, {})
    await loadRequest()
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to approve'
    await loadRequest()
  } finally {
    actionLoading.value = false
  }
}

async function submitEdit() {
  if (!editFeedback.value.trim()) return
  actionLoading.value = true
  actionError.value = null
  try {
    await api.post(`/ta/request/${requestId.value}/edit`, { feedback: editFeedback.value })
    editMode.value = false
    editFeedback.value = ''
    await loadRequest()
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to submit edit'
    await loadRequest()
  } finally {
    actionLoading.value = false
  }
}

async function submitReject() {
  actionLoading.value = true
  actionError.value = null
  try {
    await api.post(`/ta/request/${requestId.value}/reject`, { reason: rejectReason.value })
    rejectMode.value = false
    await loadRequest()
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to send to in-person'
    await loadRequest()
  } finally {
    actionLoading.value = false
  }
}

function startEdit() {
  editFeedback.value = data.value?.ai_feedback ?? ''
  editMode.value = true
  rejectMode.value = false
}

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
    pending: 'Pending',
    ai_generated: 'AI Generated',
    approved: 'Approved',
    edited: 'Edited',
    in_person: 'In Person',
    resolved: 'Resolved',
  }
  return map[status] ?? status
}

function aiProgressLabel(progress: string | null | undefined) {
  const map: Record<string, string> = {
    queued: 'Queued for AI analysis',
    processing: 'Generating AI feedback...',
    error: 'AI generation failed',
  }
  return progress ? (map[progress] ?? progress) : 'Generating...'
}

async function copyFeedback() {
  const text = data.value?.final_feedback ?? data.value?.ai_feedback ?? ''
  if (text) await navigator.clipboard.writeText(text)
}

const aiError = computed(() => data.value?.ai_progress_status === 'error')

async function retryAI() {
  actionLoading.value = true
  actionError.value = null
  try {
    await api.post(`/ta/request/${requestId.value}/retry-ai`, {})
    await loadRequest()
    // Resume polling until AI feedback arrives
    restartPollingIfNeeded()
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Failed to retry AI'
  } finally {
    actionLoading.value = false
  }
}
</script>

<template>
  <div class="p-6">
    <!-- Back nav -->
    <div class="mb-4 flex items-center gap-4">
      <button class="text-sm text-blue-600 hover:underline" @click="goBack">
        {{ fromOvertime ? '← Overtime Questions' : '← TA Dashboard' }}
      </button>
      <span v-if="data" class="text-sm text-gray-400">
        {{ data.assignment_name }}
      </span>
    </div>

    <div v-if="loading" class="text-gray-500 text-sm">Loading request…</div>

    <div v-else-if="error" class="bg-red-50 border border-red-200 text-red-800 p-4 rounded text-sm">
      {{ error }}
    </div>

    <template v-else-if="data">
      <!-- Header -->
      <div class="flex items-start justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 class="text-xl font-bold text-gray-900">Request #{{ data.id }} — {{ data.student_name }}</h1>
          <p class="text-sm text-gray-500 mt-1">{{ data.created_at }}</p>
        </div>
        <span :class="['text-sm px-3 py-1 rounded-full font-medium', statusBadge(data.status)]">
          {{ statusLabel(data.status) }}
        </span>
      </div>

      <!-- Main two-column layout -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <!-- Left: Question + student submission -->
        <div class="space-y-4">
          <!-- Question -->
          <div class="bg-white border border-gray-200 rounded-lg p-4">
            <h2 class="text-sm font-semibold text-gray-700 mb-2 uppercase tracking-wide">
              Question {{ data.question?.label ?? data.question?.number }}
            </h2>
            <p class="text-sm text-gray-900 whitespace-pre-wrap">
              {{ data.question?.problem_description }}
            </p>
          </div>

          <!-- Submission -->
          <div class="bg-white border border-gray-200 rounded-lg p-4">
            <h2 class="text-sm font-semibold text-gray-700 mb-2 uppercase tracking-wide">Student Submission</h2>
            <pre v-if="data.submission_text" class="text-sm text-gray-900 whitespace-pre-wrap font-sans">{{
              data.submission_text
            }}</pre>
            <p v-else class="text-sm text-gray-400 italic">No text submitted.</p>
          </div>

          <!-- Submission image -->
          <div v-if="data.submission_image_url" class="bg-white border border-gray-200 rounded-lg p-4">
            <h2 class="text-sm font-semibold text-gray-700 mb-2 uppercase tracking-wide">Submitted Image</h2>
            <img :src="data.submission_image_url" alt="Submission" class="max-w-full rounded" />
            <p v-if="data.extracted_text" class="text-xs text-gray-500 mt-2 whitespace-pre-wrap">
              Extracted: {{ data.extracted_text }}
            </p>
          </div>

          <!-- Student comment -->
          <div v-if="data.student_comment" class="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h2 class="text-sm font-semibold text-blue-700 mb-1 uppercase tracking-wide">Student Comment</h2>
            <p class="text-sm text-blue-900">{{ data.student_comment }}</p>
          </div>

          <!-- AI Feedback -->
          <div class="bg-white border border-gray-200 rounded-lg p-4">
            <div class="flex items-center justify-between mb-3">
              <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide">AI Feedback</h2>
              <div class="flex items-center gap-2">
                <span v-if="!data.ai_feedback && !aiError" class="text-xs text-amber-600 animate-pulse">
                  {{ aiProgressLabel(data.ai_progress_status) }}
                </span>
                <button
                  v-if="data.ai_feedback"
                  class="text-xs text-gray-500 hover:text-gray-700 border border-gray-300 rounded px-2 py-0.5"
                  @click="copyFeedback"
                >
                  Copy
                </button>
              </div>
            </div>

            <!-- AI error state -->
            <div
              v-if="aiError"
              class="flex items-start justify-between gap-4 bg-red-50 border border-red-200 rounded-lg p-3"
            >
              <div>
                <p class="text-sm font-medium text-red-800">AI failed to generate feedback</p>
                <p class="text-xs text-red-600 mt-0.5">
                  The model returned an error or is not configured. You can retry or write manually.
                </p>
              </div>
              <button
                :disabled="actionLoading || claimedByOtherReviewer"
                class="flex-shrink-0 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
                @click="retryAI"
              >
                {{ actionLoading ? 'Retrying…' : 'Retry AI' }}
              </button>
            </div>

            <div v-else-if="data.ai_feedback" class="text-sm text-gray-800 whitespace-pre-wrap">
              {{ data.ai_feedback }}
            </div>
            <div v-else class="text-sm text-gray-400 italic">
              {{ aiProgressLabel(data.ai_progress_status) }}
            </div>
          </div>

          <!-- Write / Edit feedback (same width as AI feedback box) -->
          <div v-if="editMode && !isTerminal" class="bg-white border border-gray-200 rounded-lg p-4">
            <h3 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">
              {{ data.ai_feedback ? 'Edit Feedback' : 'Write Feedback' }}
            </h3>
            <textarea
              v-model="editFeedback"
              rows="6"
              autofocus
              class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
              :placeholder="
                data.ai_feedback
                  ? 'Edit the AI feedback before sending to student…'
                  : 'Write your feedback for the student…'
              "
            ></textarea>
            <div class="flex gap-2 mt-2">
              <button
                :disabled="actionLoading || !editFeedback.trim()"
                class="bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded transition-colors"
                @click="submitEdit"
              >
                Send Feedback
              </button>
              <button class="text-sm text-gray-500 hover:text-gray-700 px-3 py-2" @click="editMode = false">
                Cancel
              </button>
            </div>
          </div>
        </div>

        <!-- Right: Official solution + hinting strategy -->
        <div class="space-y-4">
          <!-- Official solution (collapsible) -->
          <details
            v-if="data.question?.official_solution"
            class="bg-emerald-50 border border-emerald-200 rounded-lg p-4"
            open
          >
            <summary class="text-sm font-semibold text-emerald-800 cursor-pointer">Official Solution</summary>
            <p class="text-sm text-emerald-900 mt-2 whitespace-pre-wrap">
              {{ data.question.official_solution }}
            </p>
          </details>

          <!-- Hinting strategy (collapsible) -->
          <details
            v-if="data.question?.hinting_strategy"
            class="bg-amber-50 border border-amber-200 rounded-lg p-4"
            open
          >
            <summary class="text-sm font-semibold text-amber-800 cursor-pointer">Hinting Strategy</summary>
            <p class="text-sm text-amber-900 mt-2 whitespace-pre-wrap">
              {{ data.question.hinting_strategy }}
            </p>
          </details>
        </div>
      </div>

      <div
        v-if="claimedByOtherReviewer"
        class="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
      >
        This request is already being reviewed by {{ reviewOwnerLabel }}. You can still view it, but only the assigned
        TA can send feedback.
      </div>

      <!-- Action error -->
      <div v-if="actionError" class="mb-4 bg-red-50 border border-red-200 text-red-800 p-3 rounded text-sm">
        {{ actionError }}
      </div>

      <!-- Terminal state: show final feedback -->
      <div v-if="isTerminal && data.final_feedback" class="bg-emerald-50 border border-emerald-200 rounded-lg p-5 mb-6">
        <div class="flex items-center justify-between mb-2">
          <h2 class="text-base font-semibold text-emerald-900">Final Feedback Sent</h2>
          <button class="text-xs text-emerald-700 border border-emerald-300 rounded px-2 py-0.5" @click="copyFeedback">
            Copy
          </button>
        </div>
        <p class="text-sm text-emerald-800 whitespace-pre-wrap">{{ data.final_feedback }}</p>
      </div>

      <!-- Actions (only when not terminal) -->
      <div v-if="!isTerminal" class="space-y-3">
        <!-- Reject / in-person mode -->
        <div v-if="rejectMode" class="bg-white border border-gray-200 rounded-lg p-4">
          <h3 class="text-sm font-semibold text-gray-700 mb-2">Send to In-Person Help</h3>
          <input
            v-model="rejectReason"
            type="text"
            class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
            placeholder="Reason…"
          />
          <div class="flex gap-2 mt-2">
            <button
              :disabled="actionLoading"
              class="bg-orange-600 hover:bg-orange-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded transition-colors"
              @click="submitReject"
            >
              Confirm In-Person
            </button>
            <button class="text-sm text-gray-500 hover:text-gray-700 px-3 py-2" @click="rejectMode = false">
              Cancel
            </button>
          </div>
        </div>

        <!-- Main action buttons -->
        <div v-else-if="!editMode" class="flex flex-wrap gap-2">
          <button
            :disabled="actionLoading || !data.ai_feedback || claimedByOtherReviewer"
            class="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded transition-colors"
            @click="approve"
          >
            Approve & Send
          </button>
          <button
            :disabled="actionLoading || claimedByOtherReviewer"
            class="bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded transition-colors"
            @click="startEdit"
          >
            {{ data.ai_feedback ? 'Edit Feedback' : 'Write Feedback' }}
          </button>
          <button
            v-if="!fromOvertime"
            :disabled="actionLoading || claimedByOtherReviewer"
            class="bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white text-sm px-4 py-2 rounded transition-colors"
            @click="rejectMode = true"
          >
            In-Person Help
          </button>
        </div>
      </div>
    </template>
  </div>
</template>
