<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { taApi } from '../api'
import type { TADashboard } from '../types'
import { Users, Play, ExternalLink } from 'lucide-vue-next'
import { fmtUtc } from '../utils/time'

const router = useRouter()

const data = ref<TADashboard | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

// Open Queue modal state
const modalOpen = ref(false)
const modalAssignmentId = ref<number | null>(null)
const modalAssignmentName = ref('')
const modalLlmId = ref<number | null>(null)
const modalRooms = ref<{ name: string; is_signoff: boolean }[]>([{ name: 'Room A', is_signoff: false }])
const modalSubmitting = ref(false)
const modalError = ref<string | null>(null)
const closingAssignmentId = ref<number | null>(null)
const showCloseDialog = ref(false)
const closeTargetAssignmentId = ref<number | null>(null)
const closeTargetAssignmentName = ref('')
const closeAction = ref<'keep' | 'kick'>('keep')

async function fetchDashboard() {
  try {
    data.value = await taApi.dashboard()
    if (data.value.available_llms.length > 0) {
      modalLlmId.value = data.value.available_llms[0].id
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load dashboard'
  } finally {
    loading.value = false
  }
}

onMounted(fetchDashboard)

function openQueueModal(assignmentId: number, assignmentName: string) {
  modalAssignmentId.value = assignmentId
  modalAssignmentName.value = assignmentName
  modalRooms.value = [{ name: 'Room A', is_signoff: false }]
  modalError.value = null
  modalOpen.value = true
}

function addRoomInput() {
  modalRooms.value.push({ name: '', is_signoff: false })
}

function removeRoom(index: number) {
  if (modalRooms.value.length > 1) {
    modalRooms.value.splice(index, 1)
  }
}

async function submitOpenQueue() {
  if (!modalAssignmentId.value || !modalLlmId.value) return
  const rooms = modalRooms.value.filter((r) => r.name.trim())
  if (rooms.length === 0) {
    modalError.value = 'Enter at least one room name'
    return
  }
  modalSubmitting.value = true
  modalError.value = null
  try {
    await taApi.openQueue(modalAssignmentId.value, { llm_id: modalLlmId.value, rooms })
    modalOpen.value = false
    await fetchDashboard()
  } catch (e) {
    modalError.value = e instanceof Error ? e.message : 'Failed to open queue'
  } finally {
    modalSubmitting.value = false
  }
}

function openCloseDialog(assignmentId: number, assignmentName: string) {
  closeTargetAssignmentId.value = assignmentId
  closeTargetAssignmentName.value = assignmentName
  closeAction.value = 'keep'
  error.value = null
  showCloseDialog.value = true
}

async function confirmCloseQueue() {
  if (!closeTargetAssignmentId.value) return
  closingAssignmentId.value = closeTargetAssignmentId.value
  error.value = null
  try {
    await taApi.closeQueue(closeTargetAssignmentId.value, closeAction.value)
    showCloseDialog.value = false
    await fetchDashboard()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to close queue'
  } finally {
    closingAssignmentId.value = null
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

function goToRequest(requestId: number) {
  router.push(`/review-request/${requestId}`)
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
            @click="router.push(`/lab-session/${item.assignment_id}?room_id=${item.room_id}`)"
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
                <span class="text-sm text-gray-700">{{ assignment.name }}</span>
                <div class="flex items-center gap-2">
                  <button
                    v-if="assignment.queue_open"
                    class="inline-flex items-center px-3 py-1 text-xs font-medium rounded-md text-white bg-green-600 hover:bg-green-700"
                    @click="router.push(`/lab-session/${assignment.id}`)"
                  >
                    <span class="w-1.5 h-1.5 rounded-full bg-white mr-1.5"></span>
                    Live Queue
                  </button>
                  <button
                    v-if="assignment.queue_open"
                    :disabled="closingAssignmentId === assignment.id"
                    class="inline-flex items-center px-3 py-1 text-xs font-medium rounded-md text-red-700 bg-red-50 hover:bg-red-100 disabled:opacity-50"
                    @click="openCloseDialog(assignment.id, assignment.name)"
                  >
                    {{ closingAssignmentId === assignment.id ? 'Closing…' : 'Close Queue' }}
                  </button>
                  <button
                    v-else
                    class="inline-flex items-center px-3 py-1 text-xs font-medium rounded-md text-gray-700 bg-gray-100 hover:bg-gray-200"
                    @click="openQueueModal(assignment.id, assignment.name)"
                  >
                    <Play class="w-3 h-3 mr-1" />
                    Open Queue
                  </button>
                </div>
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
      <div v-if="data.recent_resolved.length > 0" class="mb-8">
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
                @click="goToRequest(req.id)"
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
                <td class="px-4 py-3 text-sm text-gray-500">{{ fmtUtc(req.resolved_at) }}</td>
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

  <!-- Open Queue Modal -->
  <div v-if="modalOpen" class="fixed inset-0 z-50 overflow-y-auto">
    <div class="flex items-center justify-center min-h-screen p-4">
      <div class="fixed inset-0 bg-gray-500/75" @click="modalOpen = false" />
      <div class="relative bg-white rounded-lg max-w-md w-full p-6 z-10">
        <h3 class="text-lg font-medium text-gray-900 mb-1">Open Queue</h3>
        <p class="text-sm text-gray-500 mb-4">{{ modalAssignmentName }}</p>

        <div v-if="modalError" class="mb-4 bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm text-red-700">
          {{ modalError }}
        </div>

        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">LLM for AI Feedback</label>
            <select
              v-model="modalLlmId"
              required
              class="block w-full border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 text-sm px-3 py-2"
            >
              <option v-for="llm in data?.available_llms" :key="llm.id" :value="llm.id">
                {{ llm.name }} ({{ llm.model_name }})
              </option>
            </select>
            <p v-if="!data?.available_llms.length" class="mt-1 text-xs text-red-600">
              No LLM configs available. Add one in AI Settings first.
            </p>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Room Name(s)</label>
            <div class="space-y-2">
              <div v-for="(room, i) in modalRooms" :key="i" class="flex items-center gap-2">
                <input
                  v-model="room.name"
                  type="text"
                  :placeholder="i === 0 ? 'e.g. Room A' : 'Room name'"
                  class="flex-1 block border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 text-sm px-3 py-2"
                />
                <label
                  class="flex items-center gap-1.5 text-sm text-gray-600 whitespace-nowrap cursor-pointer select-none"
                >
                  <input v-model="room.is_signoff" type="checkbox" class="accent-emerald-600 w-3.5 h-3.5" />
                  Sign-off
                </label>
                <button
                  v-if="modalRooms.length > 1"
                  class="text-gray-400 hover:text-red-500 text-sm px-1"
                  @click="removeRoom(i)"
                >
                  ✕
                </button>
              </div>
            </div>
            <button type="button" class="mt-2 text-sm text-blue-600 hover:text-blue-800" @click="addRoomInput">
              + Add another room
            </button>
          </div>
        </div>

        <div class="mt-6 flex justify-end space-x-3">
          <button
            class="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
            @click="modalOpen = false"
          >
            Cancel
          </button>
          <button
            :disabled="modalSubmitting"
            class="px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400"
            @click="submitOpenQueue"
          >
            {{ modalSubmitting ? 'Opening…' : 'Open Queue' }}
          </button>
        </div>
      </div>
    </div>
  </div>

  <Teleport to="body">
    <div
      v-if="showCloseDialog"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
      @mousedown.self="showCloseDialog = false"
    >
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div class="px-6 py-4 border-b border-gray-100">
          <h2 class="text-base font-semibold text-gray-900">Close "{{ closeTargetAssignmentName }}"</h2>
          <p class="text-sm text-gray-500 mt-0.5">What should happen to pending requests?</p>
        </div>

        <div class="px-6 py-5 space-y-3">
          <label
            class="flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors"
            :class="closeAction === 'keep' ? 'border-blue-400 bg-blue-50' : 'border-gray-200 hover:border-gray-300'"
          >
            <input v-model="closeAction" type="radio" value="keep" class="mt-0.5 accent-blue-600" />
            <div>
              <p class="text-sm font-medium text-gray-900">Keep as overtime</p>
              <p class="text-xs text-gray-500 mt-0.5">
                Move pending requests to the course overtime backlog. All TAs and the teacher can pick them up from the
                course overview.
              </p>
            </div>
          </label>

          <label
            class="flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors"
            :class="closeAction === 'kick' ? 'border-red-400 bg-red-50' : 'border-gray-200 hover:border-gray-300'"
          >
            <input v-model="closeAction" type="radio" value="kick" class="mt-0.5 accent-red-600" />
            <div>
              <p class="text-sm font-medium text-gray-900">Discard</p>
              <p class="text-xs text-gray-500 mt-0.5">
                Resolve and remove all pending requests. Students will not receive feedback.
              </p>
            </div>
          </label>
        </div>

        <div class="px-6 py-4 border-t border-gray-100 flex justify-end gap-3 bg-gray-50 rounded-b-2xl">
          <button
            class="px-4 py-2 text-sm font-medium rounded-lg text-gray-700 bg-white border border-gray-300 hover:bg-gray-50"
            @click="showCloseDialog = false"
          >
            Cancel
          </button>
          <button
            :disabled="closingAssignmentId !== null"
            :class="[
              'px-5 py-2 text-sm font-medium rounded-lg text-white disabled:opacity-50',
              closeAction === 'kick' ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700',
            ]"
            @click="confirmCloseQueue"
          >
            {{ closingAssignmentId !== null ? 'Closing…' : 'Close Queue' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
