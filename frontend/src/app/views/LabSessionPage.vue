<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { queueApi } from '../api'
import { api } from '../api/client'
import type { QueueState, QueueItem } from '../types'
import { Clock, Sparkles, CheckCircle, XCircle, X, User, Check, ClipboardCheck } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const assignmentId = Number(route.params.assignmentId)

// ─── Queue state ──────────────────────────────────────────────────────────────
const state = ref<QueueState | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

let pollTimer: ReturnType<typeof setInterval> | null = null
let detailPollTimer: ReturnType<typeof setInterval> | null = null

async function loadQueue() {
  try {
    state.value = await queueApi.getState(assignmentId)
    error.value = null
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load queue'
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
  if (detailPollTimer) clearInterval(detailPollTimer)
})

// ─── Lanes: one per named queue (child), grouped across all rooms ─────────────
const lanes = computed(() => {
  if (!state.value) return []

  const waitingItems = state.value.queue_items
  const beingHelpedItems = state.value.being_helped_items

  // If we have child queues, keep the parent room lanes visible as well so
  // students already waiting in the room do not appear to disappear into an
  // "Unassigned" bucket after new named queues are added.
  const queues = (state.value as any).queues as
    | Array<{
        id: number
        name: string
        parent_room_id: number | null
        location: string | null
      }>
    | undefined

  if (queues && queues.length > 0) {
    const roomMap = Object.fromEntries(state.value!.rooms.map((r) => [r.id, r.name]))
    const knownLaneIds = new Set<number>()
    const queueLanes = state.value.rooms.map((room) => {
      knownLaneIds.add(room.id)
      return {
        id: room.id,
        name: room.name,
        subtitle: (room as any).location ?? null,
        items: waitingItems.filter((i) => i.room_id === room.id),
        helpingItems: beingHelpedItems.filter((i) => i.room_id === room.id),
      }
    })
    queues.forEach((q) => {
      knownLaneIds.add(q.id)
      queueLanes.push({
        id: q.id,
        name: q.name,
        subtitle: q.parent_room_id ? (roomMap[q.parent_room_id] ?? null) : null,
        items: waitingItems.filter((i) => i.room_id === q.id),
        helpingItems: beingHelpedItems.filter((i) => i.room_id === q.id),
      })
    })
    const unassigned = waitingItems.filter((i) => i.room_id === null || !knownLaneIds.has(i.room_id))
    const unassignedHelping = beingHelpedItems.filter((i) => i.room_id === null || !knownLaneIds.has(i.room_id))
    if (unassigned.length > 0) {
      queueLanes.push({
        id: -1,
        name: 'Unassigned',
        subtitle: null,
        items: unassigned,
        helpingItems: unassignedHelping,
      })
    } else if (unassignedHelping.length > 0) {
      queueLanes.push({
        id: -1,
        name: 'Unassigned',
        subtitle: null,
        items: [],
        helpingItems: unassignedHelping,
      })
    }
    return queueLanes
  }

  // Fallback: lanes per room (no child queues configured)
  const roomLanes = state.value.rooms.map((room) => ({
    id: room.id,
    name: room.name,
    subtitle: (room as any).location ?? null,
    items: waitingItems.filter((i) => i.room_id === room.id),
    helpingItems: beingHelpedItems.filter((i) => i.room_id === room.id),
  }))
  const unassigned = waitingItems.filter((i) => i.room_id === null)
  const unassignedHelping = beingHelpedItems.filter((i) => i.room_id === null)
  if (unassigned.length > 0) {
    roomLanes.push({
      id: -1,
      name: 'Unassigned',
      subtitle: null,
      items: unassigned,
      helpingItems: unassignedHelping,
    })
  } else if (unassignedHelping.length > 0) {
    roomLanes.push({
      id: -1,
      name: 'Unassigned',
      subtitle: null,
      items: [],
      helpingItems: unassignedHelping,
    })
  }
  return roomLanes
})

// ─── Detail panel ─────────────────────────────────────────────────────────────
const selectedId = ref<number | null>(null)
const detail = ref<any>(null)
const detailLoading = ref(false)
const panelError = ref<string | null>(null)
const editMode = ref(false)
const editText = ref('')
const actionBusy = ref(false)
const actionMsg = ref<string | null>(null)

function shouldPollDetail(payload: any): boolean {
  if (!payload) return false
  if (payload.ai_feedback) return false
  if (payload.ai_progress_status === 'error') return false
  return ['pending', 'ai_generated'].includes(payload.status)
}

function stopDetailPolling() {
  if (!detailPollTimer) return
  clearInterval(detailPollTimer)
  detailPollTimer = null
}

function syncDetailPolling() {
  if (selectedId.value === null || !shouldPollDetail(detail.value)) {
    stopDetailPolling()
    return
  }
  if (detailPollTimer) return
  detailPollTimer = setInterval(() => {
    void loadSelectedDetail(false)
  }, 3000)
}

async function loadSelectedDetail(showLoading = false) {
  if (selectedId.value === null) return
  if (showLoading) {
    detailLoading.value = true
  }
  try {
    detail.value = await api.get<any>(`/ta/request/${selectedId.value}`)
    panelError.value = null
    syncDetailPolling()
  } catch (err) {
    panelError.value = err instanceof Error ? err.message : 'Failed to load request'
    stopDetailPolling()
  } finally {
    if (showLoading) {
      detailLoading.value = false
    }
  }
}

async function selectStudent(item: QueueItem) {
  selectedId.value = item.id
  detail.value = null
  detailLoading.value = true
  panelError.value = null
  editMode.value = false
  actionMsg.value = null
  stopDetailPolling()
  await loadSelectedDetail(true)
}

function closePanel() {
  stopDetailPolling()
  selectedId.value = null
  detail.value = null
}

async function approve() {
  if (!selectedId.value) return
  actionBusy.value = true
  try {
    await api.post(`/ta/request/${selectedId.value}/approve`, {})
    actionMsg.value = 'Approved & sent to student.'
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
    actionMsg.value = 'Edited feedback sent.'
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
    actionMsg.value = 'Marked as in-person.'
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

// ─── Claim student (start helping) ────────────────────────────────────────────
const claimBusy = ref<number | null>(null)

async function claimStudent(item: QueueItem) {
  claimBusy.value = item.id
  try {
    const res = await api.post<{ ok: boolean; signoff_redirect: any }>(`/ta/request/${item.id}/claim`, {})
    if (res.signoff_redirect) {
      const r = res.signoff_redirect
      const query: Record<string, any> = {
        assignmentId: r.assignment_id,
        submissionText: item.submission_text || undefined,
      }
      if (r.type === 'group' && r.group_id) {
        query.groupId = r.group_id
        query.studentId = r.student_id
      } else {
        query.studentId = r.student_id
      }
      router.push({ name: 'sign-off', params: { courseId: r.course_id }, query })
    } else {
      await loadQueue()
      await selectStudent(item)
    }
  } catch (err) {
    panelError.value = err instanceof Error ? err.message : 'Failed to claim student'
    await loadQueue()
  } finally {
    claimBusy.value = null
  }
}
// ─── Close queue dialog ───────────────────────────────────────────────────────
const showCloseDialog = ref(false)
const closeAction = ref<'keep' | 'kick'>('keep')
const closeBusy = ref(false)

function openCloseDialog() {
  closeAction.value = 'keep'
  showCloseDialog.value = true
}

async function confirmCloseQueue() {
  closeBusy.value = true
  try {
    await api.post(`/ta/assignment/${assignmentId}/queue/close`, { action: closeAction.value })
    showCloseDialog.value = false
    await loadQueue()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to close queue'
  } finally {
    closeBusy.value = false
  }
}
function goToSignoff(item: QueueItem) {
  if (!state.value) return
  router.push({
    name: 'sign-off',
    params: { courseId: state.value.assignment.course_id },
    query: {
      studentId: item.student_id,
      assignmentId: state.value.assignment.id,
      submissionText: item.submission_text || undefined,
    },
  })
}

// ─── Wait-time gradient color ─────────────────────────────────────────────────
// green (≤10m) → yellow (10-20m) → red (≥20m), smooth RGB interpolation
function waitRgb(minutes: number): [number, number, number] {
  const green = [16, 185, 129] // emerald-500
  const yellow = [234, 179, 8] // yellow-500
  const red = [239, 68, 68] // red-500
  if (minutes <= 10) {
    const t = minutes / 10
    return [
      Math.round(green[0] + (yellow[0] - green[0]) * t),
      Math.round(green[1] + (yellow[1] - green[1]) * t),
      Math.round(green[2] + (yellow[2] - green[2]) * t),
    ]
  }
  const t = Math.min((minutes - 10) / 10, 1)
  return [
    Math.round(yellow[0] + (red[0] - yellow[0]) * t),
    Math.round(yellow[1] + (red[1] - yellow[1]) * t),
    Math.round(yellow[2] + (red[2] - yellow[2]) * t),
  ]
}

function waitColor(minutes: number): string {
  const [r, g, b] = waitRgb(minutes)
  return `rgb(${r},${g},${b})`
}

function waitBgColor(minutes: number): string {
  const [r, g, b] = waitRgb(minutes)
  return `rgba(${r},${g},${b},0.12)`
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
  <!--
    Full-height layout. We pull back the padding from RootLayout's <main>
    and fill the available viewport height minus the RootLayout header (h-16 = 4rem).
  -->
  <div
    class="flex flex-col overflow-hidden bg-gray-100 -mx-4 sm:-mx-6 lg:-mx-8 -mt-6 -mb-6"
    style="height: calc(100vh - 4rem)"
  >
    <!-- ── Loading / Error (full-page) ───────────────────────────────────── -->
    <div v-if="loading" class="flex-1 flex items-center justify-center text-gray-500 text-sm">Loading queue…</div>
    <div v-else-if="error && !state" class="flex-1 p-6">
      <div class="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
        {{ error }}
      </div>
    </div>

    <template v-else-if="state">
      <!-- ── Lab session header ────────────────────────────────────────────── -->
      <header class="bg-white border-b border-gray-200 px-4 sm:px-6 py-3 flex-shrink-0">
        <div class="flex flex-wrap items-start justify-between gap-2">
          <div class="min-w-0">
            <h1 class="text-base font-semibold text-gray-900 truncate">Lab Session: {{ state.assignment.name }}</h1>
            <p class="text-xs text-gray-500">{{ state.course?.name }} · Active Queue Management</p>
          </div>
          <div class="flex flex-wrap items-center gap-2 flex-shrink-0">
            <!-- Room chips — hidden on xs to save space -->
            <span
              v-for="room in state.rooms"
              :key="room.id"
              class="hidden sm:inline text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 font-medium"
            >
              {{ room.name }}
            </span>

            <!-- Queue status -->
            <span
              :class="[
                'text-xs px-2.5 py-1 rounded-full font-medium',
                state.assignment.queue_open ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500',
              ]"
            >
              {{ state.assignment.queue_open ? 'Open' : 'Closed' }}
            </span>

            <!-- Stats -->
            <span class="text-xs text-gray-500 hidden sm:block">
              <strong class="text-gray-900">{{ state.total_in_queue }}</strong>
              waiting ·
              <strong class="text-gray-900">{{ state.queue_items.filter((q) => q.has_ai_feedback).length }}</strong>
              AI ready
            </span>
            <!-- Close queue -->
            <button
              v-if="state.assignment.queue_open"
              :disabled="closeBusy"
              class="text-xs px-3 py-1.5 bg-red-50 text-red-600 hover:bg-red-100 border border-red-200 rounded-lg disabled:opacity-50 transition-colors"
              @click="openCloseDialog"
            >
              Close Queue
            </button>
          </div>
        </div>
        <p v-if="actionMsg" class="text-xs text-emerald-600 mt-1">{{ actionMsg }}</p>
      </header>

      <!-- ── Main: lanes + optional detail panel ───────────────────────────── -->
      <div class="flex flex-1 overflow-hidden min-h-0">
        <!-- ── Queue lanes (horizontal scroll) ────────────────────────────── -->
        <div class="flex-1 overflow-x-auto overflow-y-hidden min-w-0">
          <div class="flex gap-4 p-4 h-full">
            <!-- Empty: no open queues -->
            <div v-if="lanes.length === 0" class="flex-1 flex flex-col items-center justify-center text-gray-400 gap-3">
              <User class="w-10 h-10 opacity-40" />
              <p class="text-sm">No open queues for this assignment.</p>
            </div>

            <!-- One vertical lane per named queue (room) -->
            <div
              v-for="lane in lanes"
              :key="lane.id"
              class="w-72 flex-shrink-0 flex flex-col bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden"
            >
              <!-- Lane header -->
              <div
                class="px-4 py-3 border-b border-gray-100 bg-gray-50 flex items-center justify-between flex-shrink-0"
              >
                <div class="min-w-0">
                  <h3 class="text-sm font-semibold text-gray-800">{{ lane.name }}</h3>
                  <p v-if="lane.subtitle" class="text-xs text-gray-400 truncate mt-0.5">
                    {{ lane.subtitle }}
                  </p>
                </div>
                <span
                  class="ml-2 flex-shrink-0 text-xs font-bold w-6 h-6 rounded-full flex items-center justify-center"
                  :class="
                    lane.items.length + lane.helpingItems.length > 0
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-gray-100 text-gray-400'
                  "
                >
                  {{ lane.items.length + lane.helpingItems.length }}
                </span>
              </div>

              <!-- Lane body: scrollable student cards -->
              <div class="flex-1 overflow-y-auto p-2 space-y-2 min-h-0">
                <div
                  v-if="lane.items.length === 0 && lane.helpingItems.length === 0"
                  class="py-10 text-center text-xs text-gray-400 select-none"
                >
                  No one waiting
                </div>

                <button
                  v-for="(item, idx) in lane.items"
                  :key="item.id"
                  :class="[
                    'w-full text-left rounded-lg border p-3 transition-all',
                    selectedId === item.id
                      ? 'border-blue-400 bg-blue-50 shadow-sm'
                      : 'border-gray-200 bg-white hover:border-blue-200 hover:shadow-sm',
                  ]"
                  @click="selectStudent(item)"
                >
                  <!-- Position + name -->
                  <div class="flex items-start gap-2 mb-2">
                    <div
                      :class="[
                        'w-6 h-6 rounded-full text-white text-xs flex items-center justify-center font-bold flex-shrink-0 mt-0.5',
                        item.require_signoff
                          ? 'bg-gradient-to-br from-emerald-500 to-teal-600'
                          : 'bg-gradient-to-br from-indigo-500 to-purple-500',
                      ]"
                    >
                      {{ idx + 1 }}
                    </div>
                    <div class="min-w-0 flex-1">
                      <div class="flex items-center gap-1.5">
                        <p class="text-sm font-semibold text-gray-900 truncate leading-tight">
                          {{ item.student_name }}
                        </p>
                        <span
                          v-if="item.require_signoff"
                          class="flex-shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 font-semibold"
                        >
                          Sign-off
                        </span>
                      </div>
                      <p class="text-xs text-gray-400 mt-0.5">
                        Q{{ item.question_number ?? '?' }}
                        <span v-if="item.student_comment" class="text-gray-500">· {{ item.student_comment }}</span>
                      </p>
                    </div>
                  </div>

                  <!-- Footer -->
                  <div class="flex items-center justify-between mt-2">
                    <div class="flex items-center gap-1.5 text-xs">
                      <span :class="['px-1.5 py-0.5 rounded font-medium', statusBadge(item.status)]">
                        {{ statusLabel(item.status) }}
                      </span>
                      <span
                        :style="{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '2px',
                          fontSize: '0.75rem',
                          fontWeight: '600',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          color: waitColor(item.wait_time_minutes),
                          backgroundColor: waitBgColor(item.wait_time_minutes),
                        }"
                      >
                        <Clock class="w-3 h-3" style="color: inherit" />
                        {{ item.wait_time_minutes }}m
                      </span>
                    </div>
                    <button
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

                <div v-if="lane.helpingItems.length > 0" class="pt-2 mt-2 border-t border-dashed border-gray-200">
                  <p class="px-1 pb-2 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
                    Being Reviewed
                  </p>

                  <button
                    v-for="item in lane.helpingItems"
                    :key="`helping-${item.id}`"
                    :class="[
                      'w-full text-left rounded-lg border p-3 transition-all mb-2',
                      selectedId === item.id
                        ? 'border-emerald-400 bg-emerald-50 shadow-sm'
                        : 'border-gray-200 bg-white hover:border-emerald-200 hover:shadow-sm',
                    ]"
                    @click="selectStudent(item)"
                  >
                    <div class="flex items-start gap-2 mb-2">
                      <div
                        class="w-6 h-6 rounded-full text-white text-xs flex items-center justify-center font-bold flex-shrink-0 mt-0.5 bg-gradient-to-br from-emerald-500 to-teal-600"
                      >
                        {{ initial(item.student_name) }}
                      </div>
                      <div class="min-w-0 flex-1">
                        <div class="flex items-center gap-1.5">
                          <p class="text-sm font-semibold text-gray-900 truncate leading-tight">
                            {{ item.student_name }}
                          </p>
                          <span
                            v-if="item.require_signoff"
                            class="flex-shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 font-semibold"
                          >
                            Sign-off
                          </span>
                        </div>
                        <p class="text-xs text-gray-400 mt-0.5">
                          Q{{ item.question_number ?? '?' }}
                          <span v-if="item.assigned_ta_name" class="text-gray-500">· {{ item.assigned_ta_name }}</span>
                        </p>
                      </div>
                    </div>

                    <div class="flex items-center justify-between mt-2">
                      <div class="flex items-center gap-1.5 text-xs">
                        <span class="px-1.5 py-0.5 rounded font-medium bg-emerald-100 text-emerald-700">
                          Being reviewed
                        </span>
                        <span
                          :style="{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '2px',
                            fontSize: '0.75rem',
                            fontWeight: '600',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            color: waitColor(item.wait_time_minutes),
                            backgroundColor: waitBgColor(item.wait_time_minutes),
                          }"
                        >
                          <Clock class="w-3 h-3" style="color: inherit" />
                          {{ item.wait_time_minutes }}m
                        </span>
                      </div>
                      <span class="text-[11px] text-gray-500 font-medium">
                        {{ item.has_ai_feedback ? 'AI ready' : 'Generating…' }}
                      </span>
                    </div>
                  </button>
                </div>
              </div>
            </div>
            <!-- end lane -->
          </div>
        </div>
        <!-- end lanes area -->

        <!-- ── Detail panel ──────────────────────────────────────────────── -->
        <!-- Mobile: full-screen overlay. Desktop (md+): right side panel -->
        <aside
          v-if="selectedId !== null"
          class="fixed inset-0 z-40 flex flex-col bg-white overflow-hidden md:relative md:inset-auto md:z-auto md:w-[420px] md:flex-shrink-0 md:border-l md:border-gray-200"
        >
          <!-- Panel header -->
          <div class="px-5 py-3 border-b border-gray-200 flex items-center justify-between flex-shrink-0 bg-gray-50">
            <div class="flex items-center gap-2">
              <Sparkles class="w-4 h-4 text-blue-500" />
              <span class="text-sm font-semibold text-gray-900">Student Request</span>
            </div>
            <button class="text-gray-400 hover:text-gray-600 transition-colors" @click="closePanel">
              <X class="w-4 h-4" />
            </button>
          </div>

          <!-- Loading -->
          <div v-if="detailLoading" class="flex-1 flex items-center justify-center text-gray-400 text-sm">Loading…</div>

          <!-- Error -->
          <div v-else-if="panelError" class="p-5 text-sm text-red-600">{{ panelError }}</div>

          <!-- Content -->
          <div v-else-if="detail" class="flex-1 overflow-y-auto flex flex-col">
            <!-- Student info -->
            <div class="px-5 py-4 border-b border-gray-100 flex-shrink-0">
              <div class="flex items-center gap-3">
                <div
                  class="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 text-white text-base flex items-center justify-center font-bold flex-shrink-0"
                >
                  {{ initial(detail.student_name) }}
                </div>
                <div class="min-w-0">
                  <p class="font-semibold text-gray-900 text-sm">{{ detail.student_name }}</p>
                  <p class="text-xs text-gray-500">Q{{ detail.question?.number }} · {{ detail.assignment_name }}</p>
                </div>
              </div>
            </div>

            <!-- Submission text -->
            <div v-if="detail.submission_text" class="px-5 py-4 border-b border-gray-100 flex-shrink-0">
              <h3 class="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Submission</h3>
              <p class="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                {{ detail.submission_text }}
              </p>
            </div>

            <!-- Comment -->
            <div v-if="detail.student_comment" class="px-5 py-4 border-b border-gray-100 flex-shrink-0">
              <h3 class="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Student's Question</h3>
              <p class="text-sm text-gray-700">{{ detail.student_comment }}</p>
            </div>

            <!-- AI Feedback -->
            <div class="px-5 py-4 border-b border-gray-100 flex-shrink-0">
              <div class="flex items-center gap-2 mb-3">
                <Sparkles class="w-4 h-4 text-blue-500" />
                <h3 class="text-xs font-semibold uppercase tracking-wide text-gray-400">AI Feedback</h3>
              </div>

              <div v-if="!detail.ai_feedback" class="text-xs text-gray-400 italic py-2">
                {{ detail.ai_progress_status || 'Generating feedback…' }}
              </div>

              <template v-else>
                <!-- View mode -->
                <div
                  v-if="!editMode"
                  class="bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm text-gray-800 whitespace-pre-wrap leading-relaxed"
                >
                  {{ detail.ai_feedback }}
                </div>

                <!-- Edit mode -->
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

            <!-- Actions -->
            <div class="px-5 py-4 space-y-2 flex-shrink-0">
              <!-- Sign-off queue: go directly to sign-off page -->
              <template v-if="detail.room_is_signoff || detail.question?.require_signoff">
                <button
                  class="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium transition-colors"
                  @click="
                    goToSignoff({
                      id: selectedId!,
                      student_id: detail.student_id,
                      require_signoff: true,
                    } as any)
                  "
                >
                  <ClipboardCheck class="w-4 h-4" />
                  Go to Sign-off
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
              <template v-else-if="!editMode">
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
          <!-- end content -->
        </aside>
        <!-- end detail panel -->
      </div>
      <!-- end main body -->
    </template>
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
          <h2 class="text-base font-semibold text-gray-900">Close Queue</h2>
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
            :disabled="closeBusy"
            :class="[
              'px-5 py-2 text-sm font-medium rounded-lg text-white disabled:opacity-50',
              closeAction === 'kick' ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700',
            ]"
            @click="confirmCloseQueue"
          >
            {{ closeBusy ? 'Closing…' : 'Close Queue' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
