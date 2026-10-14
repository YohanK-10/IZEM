<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'
import {
  Clock,
  Sparkles,
  CheckCircle,
  XCircle,
  X,
  Plus,
  Users,
  Check,
  History,
  LogIn,
  ChevronDown,
} from 'lucide-vue-next'
import JoinQueueModal from '../components/JoinQueueModal.vue'

const authStore = useAuthStore()
const isStudent = computed(() => authStore.user?.role === 'student')
const currentUserId = computed(() => authStore.user?.id ?? null)

const route = useRoute()
const router = useRouter()
const roomId = Number(route.params.roomId)

// ─── Data types ────────────────────────────────────────────────────────────────
interface QueueItem {
  id: number
  student_id: number
  student_name: string
  question_number: number | null
  status: string
  queue_position: number | null
  wait_time_minutes: number
  student_comment: string | null
  has_ai_feedback: boolean
}

interface QueueLane {
  id: number
  name: string
  assignment_id: number | null
  assignment_name: string | null
  is_signoff: boolean
  can_delete?: boolean
  questions: {
    id: number
    question_number: number
    label?: string | null
    description: string
    require_signoff?: boolean
  }[]
  waiting: QueueItem[]
  being_helped: QueueItem[]
}

interface RoomQueueData {
  room: {
    id: number
    name: string
    location: string | null
    assignment_id: number | null
    assignment_name: string | null
    course_id: number | null
    course_name: string | null
    is_open: boolean
  }
  assignments: {
    id: number
    name: string
  }[]
  queues: QueueLane[]
  questions: {
    id: number
    question_number: number
    label?: string | null
    description: string
    require_signoff?: boolean
  }[]
  total_waiting: number
  total_being_helped: number
}

const data = ref<RoomQueueData | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

let pollTimer: ReturnType<typeof setInterval> | null = null

async function loadQueue() {
  try {
    data.value = await api.get<RoomQueueData>(`/room/${roomId}/queue`)
    error.value = null
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load room queue'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadQueue()
  pollTimer = setInterval(loadQueue, 5000)
})
onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})

// ─── Create queue dialog ───────────────────────────────────────────────────────
const showCreateDialog = ref(false)
const newQueueName = ref('')
const newQueueAssignmentId = ref<number | null>(null)
const newQueueSignoff = ref(false)
const createBusy = ref(false)
const createError = ref<string | null>(null)

async function createQueue() {
  if (!newQueueName.value.trim()) return
  if (!newQueueAssignmentId.value && !data.value?.room.assignment_id) {
    createError.value = 'Select a lab before creating a queue.'
    return
  }
  createBusy.value = true
  createError.value = null
  try {
    await api.post(`/room/${roomId}/queues`, {
      name: newQueueName.value.trim(),
      assignment_id: newQueueAssignmentId.value,
      is_signoff: newQueueSignoff.value,
    })
    newQueueName.value = ''
    newQueueAssignmentId.value = null
    newQueueSignoff.value = false
    showCreateDialog.value = false
    await loadQueue()
  } catch (err) {
    createError.value = err instanceof Error ? err.message : 'Failed to create queue'
  } finally {
    createBusy.value = false
  }
}

function openCreateDialog() {
  newQueueName.value = ''
  newQueueAssignmentId.value = data.value?.room.assignment_id ?? data.value?.assignments[0]?.id ?? null
  newQueueSignoff.value = false
  createError.value = null
  showCreateDialog.value = true
}

// ─── Close queue dialog ────────────────────────────────────────────────────────
const showCloseDialog = ref(false)
const closeTargetId = ref<number | null>(null)
const closeTargetName = ref('')
const closeTargetCanDelete = ref(true)
const closeAction = ref<'keep' | 'kick'>('keep')
const deleteBusy = ref<number | null>(null)

function openCloseDialog(queueId: number, queueName: string, canDelete = true) {
  closeTargetId.value = queueId
  closeTargetName.value = queueName
  closeTargetCanDelete.value = canDelete
  closeAction.value = 'keep'
  showCloseDialog.value = true
}

async function confirmCloseQueue() {
  if (!closeTargetId.value) return
  deleteBusy.value = closeTargetId.value
  try {
    if (closeTargetCanDelete.value) {
      await api.post(`/queue/${closeTargetId.value}/close`, { action: closeAction.value })
    } else {
      await api.post(`/room/${closeTargetId.value}/close`, { action: closeAction.value })
    }
    showCloseDialog.value = false
    await loadQueue()
  } catch (err) {
    alert(err instanceof Error ? err.message : 'Failed to close queue')
  } finally {
    deleteBusy.value = null
  }
}

// ─── Join queue (student) ─────────────────────────────────────────────────────
interface JoinTarget {
  room: { id: number; name: string; assignment_id: number | null; assignment_name: string | null }
  queueRoomId: number | null
  isSignoff: boolean
  questions: {
    id: number
    question_number: number
    label?: string | null
    description: string
    require_signoff?: boolean
  }[]
}

const joinTarget = ref<JoinTarget | null>(null)
const justJoined = ref(false)

function openJoin(lane: QueueLane) {
  if (!data.value) return
  joinTarget.value = {
    room: {
      id: data.value.room.id,
      name: data.value.room.name,
      assignment_id: lane.assignment_id ?? data.value.room.assignment_id,
      assignment_name: lane.assignment_name ?? data.value.room.assignment_name,
    },
    queueRoomId: lane.id,
    isSignoff: lane.is_signoff,
    questions: lane.questions,
  }
}

function onJoinClose() {
  joinTarget.value = null
  justJoined.value = true
  loadQueue()
  // Remove highlight after 4 seconds
  setTimeout(() => {
    justJoined.value = false
  }, 4000)
}

// ─── History tab ──────────────────────────────────────────────────────────────
type ActiveTab = 'queue' | 'history'
const activeTab = ref<ActiveTab>('queue')
const historyItems = ref<any[]>([])
const historyLoading = ref(false)

async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await api.get<{ room_name: string; history: any[] }>(`/room/${roomId}/history`)
    historyItems.value = res.history
  } catch {
    /* ignore */
  } finally {
    historyLoading.value = false
  }
}

function switchTab(tab: ActiveTab) {
  activeTab.value = tab
  if (tab === 'history') loadHistory()
}

const STATUS_LABELS: Record<string, string> = {
  approved: 'Approved',
  edited: 'Edited',
  in_person: 'In Person',
  resolved: 'Left Queue',
}
const STATUS_COLORS: Record<string, string> = {
  approved: 'bg-emerald-100 text-emerald-700',
  edited: 'bg-violet-100 text-violet-700',
  in_person: 'bg-orange-100 text-orange-700',
  resolved: 'bg-gray-100 text-gray-500',
}

// ─── Claim student (start helping) ────────────────────────────────────────────
const claimBusy = ref<number | null>(null)

async function claimStudent(item: QueueItem) {
  claimBusy.value = item.id
  try {
    await api.post(`/ta/request/${item.id}/claim`, {})
    await loadQueue()
    await selectStudent(item)
  } catch (err) {
    panelError.value = err instanceof Error ? err.message : 'Failed to claim student'
    await loadQueue()
  } finally {
    claimBusy.value = null
  }
}

// ─── Detail panel ─────────────────────────────────────────────────────────────
const selectedId = ref<number | null>(null)
const detail = ref<any>(null)
const detailLoading = ref(false)
const panelError = ref<string | null>(null)
const editMode = ref(false)
const editText = ref('')
const actionBusy = ref(false)

async function selectStudent(item: QueueItem) {
  selectedId.value = item.id
  detail.value = null
  detailLoading.value = true
  panelError.value = null
  editMode.value = false
  try {
    detail.value = await api.get<any>(`/ta/request/${item.id}`)
  } catch (err) {
    panelError.value = err instanceof Error ? err.message : 'Failed to load request'
  } finally {
    detailLoading.value = false
  }
}

function closePanel() {
  selectedId.value = null
  detail.value = null
}

async function approve() {
  if (!selectedId.value) return
  actionBusy.value = true
  try {
    await api.post(`/ta/request/${selectedId.value}/approve`, {})
    closePanel()
    await loadQueue()
  } catch (err) {
    panelError.value = err instanceof Error ? err.message : 'Failed'
  } finally {
    actionBusy.value = false
  }
}

async function sendEdit() {
  if (!selectedId.value || !editText.value.trim()) return
  actionBusy.value = true
  try {
    await api.post(`/ta/request/${selectedId.value}/edit`, { feedback: editText.value })
    closePanel()
    await loadQueue()
  } catch (err) {
    panelError.value = err instanceof Error ? err.message : 'Failed'
  } finally {
    actionBusy.value = false
  }
}

async function markInPerson() {
  if (!selectedId.value) return
  actionBusy.value = true
  try {
    await api.post(`/ta/request/${selectedId.value}/reject`, { reason: 'In-person help required' })
    closePanel()
    await loadQueue()
  } catch (err) {
    panelError.value = err instanceof Error ? err.message : 'Failed'
  } finally {
    actionBusy.value = false
  }
}

function startEdit() {
  editText.value = detail.value?.ai_feedback ?? ''
  editMode.value = true
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function statusBadge(status: string) {
  const map: Record<string, string> = {
    pending: 'bg-amber-100 text-amber-700',
    ai_generated: 'bg-sky-100 text-sky-700',
    approved: 'bg-emerald-100 text-emerald-700',
    edited: 'bg-violet-100 text-violet-700',
    rejected: 'bg-rose-100 text-rose-700',
    in_person: 'bg-orange-100 text-orange-700',
  }
  return map[status] ?? 'bg-gray-100 text-gray-600'
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    pending: 'Pending',
    ai_generated: 'AI Ready',
    approved: 'Approved',
    edited: 'Edited',
    rejected: 'Rejected',
    in_person: 'In Person',
  }
  return map[status] ?? status
}

function initial(name: string | undefined) {
  return (name ?? '?')[0].toUpperCase()
}
</script>

<template>
  <div
    class="flex flex-col overflow-hidden bg-gray-100 -mx-4 sm:-mx-6 lg:-mx-8 -mt-6 -mb-6"
    style="height: calc(100vh - 4rem)"
  >
    <!-- Loading / Error -->
    <div v-if="loading" class="flex-1 flex items-center justify-center text-gray-500 text-sm">Loading room…</div>
    <div v-else-if="error && !data" class="flex-1 p-6">
      <div class="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
        {{ error }}
      </div>
    </div>

    <template v-else-if="data">
      <!-- ── Header ──────────────────────────────────────────────────────────── -->
      <header class="bg-white border-b border-gray-200 px-4 sm:px-6 py-3 flex-shrink-0">
        <div class="flex flex-wrap items-start justify-between gap-2">
          <div class="min-w-0">
            <button
              class="text-xs text-blue-500 hover:underline block mb-0.5"
              @click="router.push(data.room.course_id ? `/course/${data.room.course_id}/rooms` : '/')"
            >
              ← Back to rooms
            </button>
            <h1 class="text-base font-semibold text-gray-900 truncate">{{ data.room.name }}</h1>
            <p class="text-xs text-gray-500">
              <span v-if="data.room.course_name">{{ data.room.course_name }}</span>
              <span v-if="data.room.assignment_name">· {{ data.room.assignment_name }}</span>
              <span v-if="data.room.location" class="text-gray-400">· {{ data.room.location }}</span>
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-2 flex-shrink-0">
            <span class="text-sm text-gray-500 hidden sm:block">
              <strong class="text-gray-900">{{ data.total_waiting }}</strong>
              waiting ·
              <strong class="text-gray-900">{{ data.total_being_helped }}</strong>
              helped
            </span>
            <span class="text-xs px-2.5 py-1 rounded-full font-medium bg-emerald-100 text-emerald-700">Open</span>

            <button
              v-if="activeTab === 'queue' && !isStudent"
              class="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
              @click="openCreateDialog"
            >
              <Plus class="w-3.5 h-3.5" />
              Add Queue
            </button>

            <!-- Tab switcher -->
            <div class="flex rounded-lg border border-gray-200 bg-gray-50 p-0.5 gap-0.5">
              <button
                :class="[
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                  activeTab === 'queue' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700',
                ]"
                @click="switchTab('queue')"
              >
                <Users class="w-3.5 h-3.5" />
                Queue
              </button>
              <button
                :class="[
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                  activeTab === 'history' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700',
                ]"
                @click="switchTab('history')"
              >
                <History class="w-3.5 h-3.5" />
                History
              </button>
            </div>
          </div>
        </div>
      </header>

      <!-- ── Main: lanes + detail panel ────────────────────────────────────── -->
      <div class="flex flex-1 overflow-hidden min-h-0">
        <!-- ── History view ─────────────────────────────────────────────────── -->
        <div v-if="activeTab === 'history'" class="flex-1 overflow-y-auto p-6">
          <div v-if="historyLoading" class="text-sm text-gray-400 text-center py-12">Loading history…</div>
          <div v-else-if="historyItems.length === 0" class="text-sm text-gray-400 text-center py-12">
            No resolved requests for this room yet.
          </div>
          <div v-else class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-100 whitespace-nowrap">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Student
                  </th>
                  <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Queue</th>
                  <th
                    v-if="!isStudent"
                    class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide"
                  >
                    Question
                  </th>
                  <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">TA</th>
                  <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Outcome
                  </th>
                  <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Wait</th>
                  <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Time</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100">
                <tr v-for="row in historyItems" :key="row.id" class="hover:bg-gray-50 transition-colors">
                  <!-- Student avatar + name -->
                  <td class="px-4 py-3">
                    <div class="flex items-center gap-2">
                      <div
                        class="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 text-white text-xs flex items-center justify-center font-bold flex-shrink-0"
                      >
                        {{ row.student_name[0] }}
                      </div>
                      <span class="text-sm text-gray-900 font-medium">{{ row.student_name }}</span>
                    </div>
                  </td>
                  <!-- Queue name -->
                  <td class="px-4 py-3 text-sm text-gray-600">{{ row.queue_name }}</td>
                  <!-- Question (hidden from students) -->
                  <td v-if="!isStudent" class="px-4 py-3 text-sm text-gray-500">
                    <span v-if="row.question_number">Q{{ row.question_number }}</span>
                    <span v-else class="text-gray-300">—</span>
                  </td>
                  <!-- TA name -->
                  <td class="px-4 py-3 text-sm text-gray-700">{{ row.ta_name }}</td>
                  <!-- Status badge -->
                  <td class="px-4 py-3">
                    <span
                      :class="[
                        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                        STATUS_COLORS[row.status] ?? 'bg-gray-100 text-gray-500',
                      ]"
                    >
                      {{ STATUS_LABELS[row.status] ?? row.status }}
                    </span>
                  </td>
                  <!-- Wait time -->
                  <td class="px-4 py-3 text-sm text-gray-400">
                    <span v-if="row.wait_minutes != null" class="flex items-center gap-1">
                      <Clock class="w-3 h-3" />
                      {{ row.wait_minutes }}m
                    </span>
                    <span v-else class="text-gray-300">—</span>
                  </td>
                  <!-- Resolved at -->
                  <td class="px-4 py-3 text-sm text-gray-400">{{ row.resolved_at ?? '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- ── Queue lanes (horizontal scroll) ─────────────────────────────── -->
        <div v-if="activeTab === 'queue'" class="flex-1 overflow-x-auto overflow-y-hidden min-w-0">
          <div class="flex gap-4 p-4 h-full">
            <!-- Empty state -->
            <div
              v-if="data.queues.length === 0"
              class="flex-1 flex flex-col items-center justify-center text-gray-400 gap-3"
            >
              <Users class="w-10 h-10 opacity-40" />
              <p class="text-sm">No queues in this room yet.</p>
              <button v-if="!isStudent" class="text-sm text-blue-600 hover:underline" @click="openCreateDialog">
                Add a queue
              </button>
            </div>

            <!-- One lane per named queue -->
            <div
              v-for="lane in data.queues"
              :key="lane.id"
              class="w-72 flex-shrink-0 flex flex-col bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden"
            >
              <!-- Lane header -->
              <div
                class="px-4 py-3 border-b border-gray-100 bg-gray-50 flex items-center justify-between flex-shrink-0"
              >
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-1.5">
                    <h3 class="text-sm font-semibold text-gray-800 truncate">{{ lane.name }}</h3>
                    <span
                      v-if="lane.is_signoff"
                      class="flex-shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 font-semibold"
                    >
                      Sign-off
                    </span>
                  </div>
                  <p v-if="lane.assignment_name" class="text-xs text-gray-400 mt-0.5">
                    Lab: {{ lane.assignment_name }}
                  </p>
                </div>
                <div class="flex items-center gap-2 flex-shrink-0 ml-2">
                  <span
                    class="text-xs font-bold w-6 h-6 rounded-full flex items-center justify-center"
                    :class="
                      lane.waiting.length + lane.being_helped.length > 0
                        ? 'bg-blue-100 text-blue-700'
                        : 'bg-gray-100 text-gray-400'
                    "
                  >
                    {{ lane.waiting.length + lane.being_helped.length }}
                  </span>
                  <!-- Student: join this queue -->
                  <button
                    v-if="isStudent"
                    class="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold transition-colors shadow-sm"
                    @click="openJoin(lane)"
                  >
                    <LogIn class="w-3 h-3" />
                    Join
                  </button>
                  <!-- TA/Teacher: close queue -->
                  <button
                    v-else
                    :disabled="deleteBusy === lane.id"
                    class="text-gray-300 hover:text-red-400 transition-colors disabled:opacity-50"
                    :title="(lane.can_delete ?? false) ? 'Close queue' : 'Close room'"
                    @click="openCloseDialog(lane.id, lane.name, lane.can_delete ?? false)"
                  >
                    <X class="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              <!-- Waiting students -->
              <div class="flex-1 overflow-y-auto p-2 space-y-2 min-h-0">
                <div
                  v-if="lane.waiting.length === 0 && lane.being_helped.length === 0"
                  class="py-10 text-center text-xs text-gray-400 select-none"
                >
                  No one waiting
                </div>

                <button
                  v-for="(item, idx) in lane.waiting"
                  :key="item.id"
                  :class="[
                    'w-full text-left rounded-lg border p-3 transition-all',
                    selectedId === item.id
                      ? 'border-blue-400 bg-blue-50 shadow-sm'
                      : isStudent && item.student_id === currentUserId
                        ? justJoined
                          ? 'border-emerald-400 bg-emerald-50 shadow-md ring-2 ring-emerald-300 cursor-default'
                          : 'border-emerald-300 bg-emerald-50 cursor-default'
                        : isStudent
                          ? 'border-gray-200 bg-white cursor-default'
                          : 'border-gray-200 bg-white hover:border-blue-200 hover:shadow-sm',
                  ]"
                  @click="!isStudent && selectStudent(item)"
                >
                  <div class="flex items-start gap-2 mb-2">
                    <div
                      class="w-6 h-6 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 text-white text-xs flex items-center justify-center font-bold flex-shrink-0 mt-0.5"
                    >
                      {{ idx + 1 }}
                    </div>
                    <div class="min-w-0 flex-1">
                      <p class="text-sm font-semibold text-gray-900 truncate leading-tight flex items-center gap-1.5">
                        {{ item.student_name }}
                        <span
                          v-if="isStudent && item.student_id === currentUserId"
                          class="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-emerald-500 text-white leading-none"
                        >
                          You
                        </span>
                      </p>
                      <!-- TA/Teacher see exercise + comment; students only see exercise number -->
                      <p class="text-xs text-gray-400 mt-0.5">
                        <span v-if="item.question_number">Q{{ item.question_number }}</span>
                        <span v-if="!isStudent && item.student_comment" class="text-gray-500">
                          · {{ item.student_comment }}
                        </span>
                      </p>
                    </div>
                  </div>
                  <div class="flex items-center justify-between mt-2">
                    <div class="flex items-center gap-1.5 text-xs text-gray-400">
                      <!-- Students don't see status badge or AI indicator -->
                      <template v-if="!isStudent">
                        <span :class="['px-1.5 py-0.5 rounded font-medium', statusBadge(item.status)]">
                          {{ statusLabel(item.status) }}
                        </span>
                      </template>
                      <span class="flex items-center gap-0.5">
                        <Clock class="w-3 h-3" />
                        {{ item.wait_time_minutes }}m
                      </span>
                    </div>
                    <button
                      v-if="!isStudent"
                      :disabled="claimBusy === item.id"
                      class="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-semibold transition-colors disabled:opacity-50 flex-shrink-0 shadow-sm"
                      title="Start helping this student"
                      @click.stop="claimStudent(item)"
                    >
                      <Check class="w-3.5 h-3.5" />
                      Help
                    </button>
                  </div>
                </button>

                <div v-if="lane.being_helped.length > 0" class="pt-2 mt-2 border-t border-dashed border-gray-200">
                  <p class="px-1 pb-2 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
                    Being Reviewed
                  </p>

                  <button
                    v-for="item in lane.being_helped"
                    :key="`helping-${item.id}`"
                    :class="[
                      'w-full text-left rounded-lg border p-3 transition-all mb-2',
                      !isStudent && selectedId === item.id
                        ? 'border-emerald-400 bg-emerald-50 shadow-sm'
                        : isStudent
                          ? 'border-emerald-100 bg-white cursor-default'
                          : 'border-gray-200 bg-white hover:border-emerald-200 hover:shadow-sm',
                    ]"
                    @click="!isStudent && selectStudent(item)"
                  >
                    <div class="flex items-start gap-2 mb-2">
                      <div
                        class="w-6 h-6 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 text-white text-xs flex items-center justify-center font-bold flex-shrink-0 mt-0.5"
                      >
                        {{ initial(item.student_name) }}
                      </div>
                      <div class="min-w-0 flex-1">
                        <p class="text-sm font-semibold text-gray-900 truncate leading-tight">
                          {{ item.student_name }}
                        </p>
                        <p class="text-xs text-gray-400 mt-0.5">
                          <span v-if="item.question_number">Q{{ item.question_number }}</span>
                        </p>
                      </div>
                    </div>

                    <div class="flex items-center justify-between mt-2">
                      <div class="flex items-center gap-1.5 text-xs">
                        <span class="px-1.5 py-0.5 rounded font-medium bg-emerald-100 text-emerald-700">
                          Being reviewed
                        </span>
                        <span class="flex items-center gap-0.5 text-gray-400">
                          <Clock class="w-3 h-3" />
                          {{ item.wait_time_minutes }}m
                        </span>
                      </div>
                      <span class="text-[11px] text-gray-500 font-medium">
                        {{ item.has_ai_feedback ? 'AI ready' : 'Generating...' }}
                      </span>
                    </div>
                  </button>
                </div>
              </div>
            </div>
            <!-- end lane -->
          </div>
        </div>
        <!-- end queue lanes -->

        <!-- ── Detail panel ─────────────────────────────────────────────────── -->
        <!-- Mobile: full-screen overlay. Desktop: right side panel -->
        <aside
          v-if="selectedId !== null && activeTab === 'queue' && !isStudent"
          class="fixed inset-0 z-40 flex flex-col bg-white overflow-hidden md:relative md:inset-auto md:z-auto md:w-[420px] md:flex-shrink-0 md:border-l md:border-gray-200"
        >
          <div class="px-5 py-3 border-b border-gray-200 flex items-center justify-between flex-shrink-0 bg-gray-50">
            <div class="flex items-center gap-2">
              <Sparkles class="w-4 h-4 text-blue-500" />
              <span class="text-sm font-semibold text-gray-900">Student Request</span>
            </div>
            <button class="text-gray-400 hover:text-gray-600 transition-colors" @click="closePanel">
              <X class="w-4 h-4" />
            </button>
          </div>

          <div v-if="detailLoading" class="flex-1 flex items-center justify-center text-gray-400 text-sm">Loading…</div>
          <div v-else-if="panelError" class="p-5 text-sm text-red-600">{{ panelError }}</div>

          <div v-else-if="detail" class="flex-1 overflow-y-auto flex flex-col">
            <div class="px-5 py-4 border-b border-gray-100 flex-shrink-0">
              <div class="flex items-center gap-3">
                <div
                  class="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 text-white text-base flex items-center justify-center font-bold flex-shrink-0"
                >
                  {{ initial(detail.student_name) }}
                </div>
                <div class="min-w-0">
                  <p class="font-semibold text-gray-900 text-sm">{{ detail.student_name }}</p>
                  <p class="text-xs text-gray-500">
                    <span v-if="detail.question?.number">Q{{ detail.question.number }} ·</span>
                    {{ detail.assignment_name }}
                  </p>
                </div>
              </div>
            </div>

            <div v-if="detail.submission_text" class="px-5 py-4 border-b border-gray-100 flex-shrink-0">
              <h3 class="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Submission</h3>
              <p class="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                {{ detail.submission_text }}
              </p>
            </div>

            <div v-if="detail.student_comment" class="px-5 py-4 border-b border-gray-100 flex-shrink-0">
              <h3 class="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Student's Question</h3>
              <p class="text-sm text-gray-700">{{ detail.student_comment }}</p>
            </div>

            <div v-if="detail.question?.official_solution" class="px-5 py-4 border-b border-gray-100 flex-shrink-0">
              <h3 class="text-xs font-semibold uppercase tracking-wide text-emerald-600 mb-2">Official Answer</h3>
              <p class="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                {{ detail.question.official_solution }}
              </p>
            </div>

            <div v-if="detail.question?.hinting_strategy" class="px-5 py-4 border-b border-gray-100 flex-shrink-0">
              <h3 class="text-xs font-semibold uppercase tracking-wide text-amber-600 mb-2">Hinting Strategy</h3>
              <p class="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                {{ detail.question.hinting_strategy }}
              </p>
            </div>

            <div class="px-5 py-4 border-b border-gray-100 flex-shrink-0">
              <div class="flex items-center gap-2 mb-3">
                <Sparkles class="w-4 h-4 text-blue-500" />
                <h3 class="text-xs font-semibold uppercase tracking-wide text-gray-400">AI Feedback</h3>
              </div>
              <div v-if="!detail.ai_feedback" class="text-xs text-gray-400 italic py-2">
                {{ detail.ai_progress_status || 'Generating feedback…' }}
              </div>
              <template v-else>
                <div
                  v-if="!editMode"
                  class="bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm text-gray-800 whitespace-pre-wrap leading-relaxed"
                >
                  {{ detail.ai_feedback }}
                </div>
                <textarea
                  v-else
                  v-model="editText"
                  rows="8"
                  class="w-full border border-blue-300 rounded-lg p-3 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none leading-relaxed"
                />
                <div class="mt-2 bg-amber-50 border border-amber-200 rounded-lg p-2">
                  <p class="text-xs text-amber-800">
                    <strong>Note:</strong>
                    AI responses are never sent automatically. You must approve.
                  </p>
                </div>
              </template>
            </div>

            <div class="px-5 py-4 space-y-2 flex-shrink-0">
              <template v-if="!editMode">
                <button
                  :disabled="actionBusy || !detail.ai_feedback"
                  class="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium disabled:opacity-40 transition-colors"
                  @click="approve"
                >
                  <CheckCircle class="w-4 h-4" />
                  Approve &amp; Send
                </button>
                <button
                  :disabled="!detail.ai_feedback"
                  class="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg border border-blue-200 bg-blue-50 hover:bg-blue-100 text-blue-700 text-sm font-medium disabled:opacity-40 transition-colors"
                  @click="startEdit"
                >
                  Edit Feedback
                </button>
                <button
                  :disabled="actionBusy"
                  class="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg border border-rose-200 bg-rose-50 hover:bg-rose-100 text-rose-700 text-sm font-medium disabled:opacity-40 transition-colors"
                  @click="markInPerson"
                >
                  <XCircle class="w-4 h-4" />
                  Mark In-Person
                </button>
              </template>
              <template v-else>
                <button
                  :disabled="actionBusy || !editText.trim()"
                  class="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium disabled:opacity-40 transition-colors"
                  @click="sendEdit"
                >
                  <CheckCircle class="w-4 h-4" />
                  Send Edited Feedback
                </button>
                <button
                  class="w-full px-4 py-2 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-medium transition-colors"
                  @click="editMode = false"
                >
                  Cancel
                </button>
              </template>
            </div>
          </div>
        </aside>
      </div>
    </template>

    <!-- ── Join Queue Modal (student) ───────────────────────────────────────── -->
    <JoinQueueModal
      v-if="joinTarget"
      :room="joinTarget.room"
      :queue-room-id="joinTarget.queueRoomId"
      :questions="joinTarget.questions"
      :is-signoff="joinTarget.isSignoff"
      @close="onJoinClose"
    />

    <!-- ── Create Queue Dialog ─────────────────────────────────────────────── -->
    <div
      v-if="showCreateDialog"
      class="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      @click.self="showCreateDialog = false"
    >
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-sm mx-4 p-6">
        <h2 class="text-base font-semibold text-gray-900 mb-1">New Queue</h2>
        <p class="text-sm text-gray-500 mb-4">Add a named queue to this room (e.g. "Questions", "Sign-off").</p>

        <label class="block text-xs font-semibold text-gray-600 mb-1 uppercase tracking-wide">Queue Name</label>
        <input
          v-model="newQueueName"
          type="text"
          placeholder="Questions, Programming Project, Sign-off…"
          class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 mb-3"
          autofocus
          @keydown.enter="createQueue"
        />

        <template v-if="data?.assignments.length">
          <label class="block text-xs font-semibold text-gray-600 mb-1 uppercase tracking-wide">Lab</label>
          <div class="relative mb-3">
            <select
              v-model="newQueueAssignmentId"
              class="w-full border border-gray-300 rounded-lg px-3 py-2 pr-8 text-sm appearance-none focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option v-for="assignment in data.assignments" :key="assignment.id" :value="assignment.id">
                {{ assignment.name }}
              </option>
            </select>
            <ChevronDown
              class="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none"
            />
          </div>
        </template>
        <p
          v-else-if="!data?.room.assignment_id"
          class="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"
        >
          Add a lab to this course or link one to the room before creating a queue.
        </p>

        <label class="flex items-center gap-2 mb-4 cursor-pointer select-none">
          <input v-model="newQueueSignoff" type="checkbox" class="accent-emerald-600 w-4 h-4" />
          <span class="text-sm text-gray-700">Sign-off queue</span>
          <span class="text-xs text-gray-400">(students pick an exercise, no problem description required)</span>
        </label>

        <div v-if="createError" class="mb-3 text-xs text-red-600">{{ createError }}</div>

        <div class="flex gap-2 justify-end">
          <button
            class="px-4 py-2 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-medium transition-colors"
            @click="showCreateDialog = false"
          >
            Cancel
          </button>
          <button
            :disabled="createBusy || !newQueueName.trim() || (!newQueueAssignmentId && !data?.room.assignment_id)"
            class="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium disabled:opacity-50 transition-colors"
            @click="createQueue"
          >
            {{ createBusy ? 'Creating…' : 'Create' }}
          </button>
        </div>
      </div>
    </div>
    <!-- ── Close Queue Dialog ─────────────────────────────────────────────── -->
    <Teleport to="body">
      <div
        v-if="showCloseDialog"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
        @mousedown.self="showCloseDialog = false"
      >
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md">
          <div class="px-6 py-4 border-b border-gray-100">
            <h2 class="text-base font-semibold text-gray-900">Close "{{ closeTargetName }}"</h2>
            <p class="text-sm text-gray-500 mt-0.5">What should happen to pending requests?</p>
          </div>

          <div class="px-6 py-5 space-y-3">
            <label
              class="flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors"
              :class="closeAction === 'keep' ? 'border-blue-400 bg-blue-50' : 'border-gray-200 hover:border-gray-300'"
            >
              <input v-model="closeAction" type="radio" value="keep" class="mt-0.5 accent-blue-600" />
              <div>
                <p class="text-sm font-medium text-gray-900">Keep as overtime questions</p>
                <p class="text-xs text-gray-500 mt-0.5">
                  Move pending requests to the course overtime backlog. All TAs and the teacher can pick them up from
                  the course overview.
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
              :disabled="!!deleteBusy"
              :class="[
                'px-5 py-2 text-sm font-medium rounded-lg text-white disabled:opacity-50',
                closeAction === 'kick' ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700',
              ]"
              @click="confirmCloseQueue"
            >
              {{ deleteBusy ? 'Closing…' : 'Close Queue' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
