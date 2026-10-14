<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { studentApi } from '../api'
import type { StudentDashboard, StudentAssignment } from '../types'
import { BookOpen, Clock, ArrowRight, ChevronDown, ChevronUp, X } from 'lucide-vue-next'
import { fmtUtc } from '../utils/time'

const router = useRouter()

const data = ref<StudentDashboard | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

// ─── Modal state ──────────────────────────────────────────────────────────────
const modalAssignment = ref<StudentAssignment | null>(null)
const form = ref({
  questionId: null as number | null,
  roomId: null as number | null,
  submissionText: '',
  studentComment: '',
  screenshot: null as File | null,
  screenshotError: null as string | null,
  showExtra: false,
  submitting: false,
  submitError: null as string | null,
})

const ALLOWED_TYPES = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.pdf']
const MAX_MB = 10

function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0] ?? null
  form.value.screenshotError = null
  form.value.screenshot = null
  if (!file) return
  const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  if (!ALLOWED_TYPES.includes(ext)) {
    form.value.screenshotError = `Invalid type. Allowed: JPG, PNG, GIF, BMP, WEBP, PDF.`
    ;(e.target as HTMLInputElement).value = ''
    return
  }
  if (file.size > MAX_MB * 1024 * 1024) {
    form.value.screenshotError = `File too large (max ${MAX_MB} MB).`
    ;(e.target as HTMLInputElement).value = ''
    return
  }
  form.value.screenshot = file
}

async function fetchDashboard() {
  try {
    data.value = await studentApi.dashboard()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load dashboard'
  } finally {
    loading.value = false
  }
}

onMounted(fetchDashboard)

function openModal(assignment: StudentAssignment) {
  modalAssignment.value = assignment
  form.value = {
    questionId: null,
    roomId: assignment.rooms.length > 0 ? assignment.rooms[0].id : null,
    submissionText: '',
    studentComment: '',
    screenshot: null,
    screenshotError: null,
    showExtra: false,
    submitting: false,
    submitError: null,
  }
}

function closeModal() {
  modalAssignment.value = null
}

async function joinQueue() {
  const a = modalAssignment.value
  if (!a) return
  if (!form.value.questionId) {
    form.value.submitError = 'Please select a question.'
    return
  }
  const studentQuestion = form.value.studentComment.trim()
  if (!studentQuestion) {
    form.value.submitError = 'Please enter your question.'
    return
  }
  form.value.submitting = true
  form.value.submitError = null
  try {
    const fd = new FormData()
    fd.append('question_id', String(form.value.questionId))
    fd.append('submission_text', form.value.submissionText.trim())
    fd.append('student_comment', studentQuestion)
    if (form.value.roomId != null) fd.append('queue_room_id', String(form.value.roomId))
    if (form.value.screenshot) fd.append('attachment', form.value.screenshot)
    const res = await fetch('/api/student/help/submit', { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      const detail = err.detail
      let msg: string
      if (typeof detail === 'string') {
        msg = detail
      } else if (Array.isArray(detail)) {
        // FastAPI validation errors: [{loc, msg, type}, ...]
        msg = detail
          .map((e: any) => {
            const field = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : 'field'
            return `${field}: ${e.msg}`
          })
          .join('; ')
      } else {
        msg = `HTTP ${res.status}`
      }
      throw new Error(msg)
    }
    closeModal()
    router.push({ name: 'student-queue', params: { assignmentId: a.id } })
  } catch (e) {
    form.value.submitError = e instanceof Error ? e.message : 'Failed to join queue'
    form.value.submitting = false
  }
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
                @click="openModal(assignment)"
              >
                Join Queue
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
                <td class="px-4 py-3 text-sm text-gray-500">{{ fmtUtc(req.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>

  <!-- ── Join Queue Modal ──────────────────────────────────────────────────── -->
  <Teleport to="body">
    <Transition name="modal-fade">
      <div
        v-if="modalAssignment"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @mousedown.self="closeModal"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" />

        <!-- Dialog -->
        <div
          class="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] flex flex-col overflow-hidden"
        >
          <!-- Header -->
          <div class="flex items-start justify-between px-6 py-4 border-b border-gray-100">
            <div class="min-w-0 pr-4">
              <h2 class="text-base font-semibold text-gray-900 truncate">Join Queue</h2>
              <p class="text-sm text-gray-500 mt-0.5 truncate">{{ modalAssignment.name }}</p>
            </div>
            <button
              class="flex-shrink-0 text-gray-400 hover:text-gray-600 transition-colors mt-0.5"
              @click="closeModal"
            >
              <X class="w-5 h-5" />
            </button>
          </div>

          <!-- Body -->
          <div class="flex-1 overflow-y-auto px-6 py-5 space-y-4">
            <!-- Error -->
            <div
              v-if="form.submitError"
              class="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700"
            >
              {{ form.submitError }}
            </div>

            <!-- Question -->
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">
                Question
                <span class="text-red-500">*</span>
              </label>
              <select
                v-model="form.questionId"
                required
                class="block w-full border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm px-3 py-2"
              >
                <option :value="null">Select a question…</option>
                <option v-for="q in modalAssignment.questions" :key="q.id" :value="q.id">
                  Q{{ q.question_number }}:
                  {{ q.description.length > 70 ? q.description.slice(0, 70) + '…' : q.description }}
                </option>
              </select>
            </div>

            <!-- Room -->
            <div v-if="modalAssignment.rooms.length > 0">
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Room</label>
              <select
                v-model="form.roomId"
                class="block w-full border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm px-3 py-2"
              >
                <option v-for="room in modalAssignment.rooms" :key="room.id" :value="room.id">
                  {{ room.name }}
                </option>
              </select>
            </div>

            <!-- Student question -->
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">
                Your Question
                <span class="text-red-500">*</span>
              </label>
              <textarea
                v-model="form.studentComment"
                rows="4"
                class="block w-full border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm px-3 py-2 resize-y"
                placeholder="Describe what you've tried, what isn't working, and what you want help with…"
              />
            </div>

            <!-- Optional code + screenshot -->
            <div>
              <button
                type="button"
                class="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1 transition-colors"
                @click="form.showExtra = !form.showExtra"
              >
                Add code or screenshot
                <ChevronDown v-if="!form.showExtra" class="w-4 h-4" />
                <ChevronUp v-else class="w-4 h-4" />
              </button>
              <Transition name="slide-down">
                <div v-if="form.showExtra" class="mt-2 space-y-3">
                  <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1.5">Code (optional)</label>
                    <textarea
                      v-model="form.submissionText"
                      rows="5"
                      class="block w-full border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm font-mono px-3 py-2 resize-y"
                      placeholder="Paste the code related to your question here…"
                    />
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1.5">Screenshot (optional)</label>
                    <input
                      type="file"
                      accept=".jpg,.jpeg,.png,.gif,.bmp,.webp,.pdf"
                      class="block w-full text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                      @change="onFileChange"
                    />
                    <p v-if="form.screenshotError" class="mt-1 text-xs text-red-600">
                      {{ form.screenshotError }}
                    </p>
                    <p v-else-if="form.screenshot" class="mt-1 text-xs text-emerald-600">
                      {{ form.screenshot.name }}
                    </p>
                    <p v-else class="mt-1 text-xs text-gray-400">JPG, PNG, GIF, BMP, WEBP or PDF — max 10 MB</p>
                  </div>
                </div>
              </Transition>
            </div>
          </div>

          <!-- Footer -->
          <div class="px-6 py-4 border-t border-gray-100 flex items-center justify-end gap-3 bg-gray-50">
            <button
              class="px-4 py-2 text-sm font-medium rounded-lg text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 transition-colors"
              @click="closeModal"
            >
              Cancel
            </button>
            <button
              :disabled="form.submitting"
              class="inline-flex items-center px-5 py-2 text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 shadow-sm disabled:opacity-50 transition-colors"
              @click="joinQueue"
            >
              {{ form.submitting ? 'Joining…' : 'Join Queue' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}
.modal-fade-enter-active .relative,
.modal-fade-leave-active .relative {
  transition:
    transform 0.2s ease,
    opacity 0.2s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
.modal-fade-enter-from .relative {
  transform: scale(0.95) translateY(8px);
  opacity: 0;
}

.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  max-height: 0;
}
.slide-down-enter-to,
.slide-down-leave-from {
  max-height: 200px;
}
</style>
