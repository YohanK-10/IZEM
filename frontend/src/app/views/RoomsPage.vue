<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { DoorOpen, Clock, Users, ChevronRight, Plus, X, ChevronDown } from 'lucide-vue-next'

const authStore = useAuthStore()
const isStudent = authStore.user?.role === 'student'

const route = useRoute()
const router = useRouter()
const courseId = Number(route.params.courseId)

interface Room {
  id: number
  name: string
  location: string | null
  assignment_id: number
  assignment_name: string
  waiting: number
  being_helped: number
  opened_at: string | null
  is_open: boolean
}

interface CourseRooms {
  course_id: number
  course_name: string
  rooms: Room[]
  assignments: { id: number; name: string }[]
}

const data = ref<CourseRooms | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null
let notificationRefreshTimer: ReturnType<typeof setTimeout> | null = null

async function loadRooms(options: { silent?: boolean } = {}) {
  const { silent = false } = options
  try {
    data.value = await api.get<CourseRooms>(`/course/${courseId}/rooms`)
    error.value = null
  } catch (err) {
    if (!silent || !data.value) {
      error.value = err instanceof Error ? err.message : 'Failed to load rooms'
    }
  } finally {
    loading.value = false
  }
}

function handleNotificationsUpdated() {
  void loadRooms({ silent: true })
  if (notificationRefreshTimer) clearTimeout(notificationRefreshTimer)
  notificationRefreshTimer = setTimeout(() => {
    void loadRooms({ silent: true })
  }, 750)
}

onMounted(async () => {
  await loadRooms()
  pollTimer = setInterval(() => {
    void loadRooms({ silent: true })
  }, 5000)
  window.addEventListener('izem:notifications-updated', handleNotificationsUpdated)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (notificationRefreshTimer) clearTimeout(notificationRefreshTimer)
  window.removeEventListener('izem:notifications-updated', handleNotificationsUpdated)
})
function openRooms(rooms: Room[]) {
  return rooms.filter((r) => r.is_open)
}
function closedRooms(rooms: Room[]) {
  return rooms.filter((r) => !r.is_open)
}

// ─── Create room ──────────────────────────────────────────────────────────────
const showCreate = ref(false)
const createName = ref('')
const createLocation = ref('')
const createAssignId = ref<number | null>(null)
const createBusy = ref(false)
const createError = ref<string | null>(null)

function openCreateDialog() {
  createName.value = ''
  createLocation.value = ''
  createAssignId.value = data.value?.assignments[0]?.id ?? null
  createError.value = null
  showCreate.value = true
}

async function createRoom() {
  if (!createName.value.trim()) {
    createError.value = 'Room name is required'
    return
  }
  createBusy.value = true
  createError.value = null
  try {
    await api.post(`/course/${courseId}/rooms`, {
      name: createName.value.trim(),
      location: createLocation.value.trim() || null,
      assignment_id: createAssignId.value,
    })
    showCreate.value = false
    await loadRooms()
  } catch (e) {
    createError.value = e instanceof Error ? e.message : 'Failed to create room'
  } finally {
    createBusy.value = false
  }
}

// ─── Close room ───────────────────────────────────────────────────────────────
const showCloseDialog = ref(false)
const closeTargetId = ref<number | null>(null)
const closeTargetName = ref('')
const closeAction = ref<'keep' | 'kick'>('keep')
const closeBusy = ref<number | null>(null)

function openCloseDialog(room: Room) {
  closeTargetId.value = room.id
  closeTargetName.value = room.name
  closeAction.value = 'keep'
  showCloseDialog.value = true
}

async function confirmCloseRoom() {
  if (!closeTargetId.value) return
  closeBusy.value = closeTargetId.value
  try {
    await api.post(`/room/${closeTargetId.value}/close`, { action: closeAction.value })
    showCloseDialog.value = false
    await loadRooms()
  } catch (e) {
    alert(e instanceof Error ? e.message : 'Failed to close room')
  } finally {
    closeBusy.value = null
  }
}
</script>

<template>
  <div class="-mx-4 sm:-mx-6 lg:-mx-8 -mt-6 px-4 sm:px-6 lg:px-8 py-8 min-h-full bg-gray-100">
    <div class="flex flex-wrap items-start justify-between gap-4 mb-8">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">
          Rooms
          <span v-if="data?.course_name" class="text-gray-400 font-normal">: {{ data.course_name }}</span>
        </h1>
        <p class="text-sm text-gray-500 mt-0.5">Lab room management and live queue status</p>
      </div>
      <button
        v-if="data && !isStudent"
        class="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg shadow-sm transition-colors"
        @click="openCreateDialog"
      >
        <Plus class="w-4 h-4" />
        Create Room
      </button>
    </div>

    <div v-if="loading" class="text-gray-500 text-sm">Loading rooms…</div>

    <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
      {{ error }}
    </div>

    <template v-else-if="data">
      <div v-if="data.rooms.length === 0" class="bg-white rounded-xl border border-gray-200 shadow-sm p-12 text-center">
        <DoorOpen class="w-16 h-16 text-gray-300 mx-auto mb-4" />
        <h2 class="text-xl font-semibold text-gray-900 mb-2">No rooms yet</h2>
        <p class="text-gray-500 text-sm max-w-md mx-auto mb-6">
          {{
            isStudent ? 'No rooms are open for this course right now.' : 'Create a room to start managing lab queues.'
          }}
        </p>
        <button
          v-if="!isStudent"
          class="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
          @click="openCreateDialog"
        >
          <Plus class="w-4 h-4" />
          Create Room
        </button>
      </div>

      <template v-else>
        <section class="mb-10">
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div
              v-for="room in openRooms(data.rooms)"
              :key="room.id"
              class="bg-white rounded-xl shadow-sm border border-gray-200 p-5 flex flex-col"
            >
              <div class="flex items-start justify-between mb-3">
                <div class="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center flex-shrink-0">
                  <DoorOpen class="w-5 h-5 text-emerald-600" />
                </div>
                <div class="flex items-center gap-2">
                  <span
                    class="flex items-center gap-1 text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full"
                  >
                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    Open
                  </span>
                  <button
                    v-if="!isStudent"
                    :disabled="closeBusy === room.id"
                    class="text-xs text-red-500 hover:text-red-700 border border-red-200 hover:border-red-300 bg-white rounded-md px-2 py-0.5 transition-colors disabled:opacity-50"
                    title="Close room"
                    @click="openCloseDialog(room)"
                  >
                    {{ closeBusy === room.id ? 'Closing…' : 'Close' }}
                  </button>
                </div>
              </div>

              <h3 class="font-semibold text-gray-900 text-base leading-snug">{{ room.name }}</h3>
              <p class="text-xs text-gray-500 mt-0.5">{{ room.assignment_name }}</p>
              <p v-if="room.location" class="text-xs text-gray-400 mt-0.5">{{ room.location }}</p>

              <div class="mt-4 flex items-center gap-4 text-sm text-gray-600">
                <span class="flex items-center gap-1.5">
                  <Clock class="w-4 h-4 text-gray-400" />
                  <strong class="text-gray-900">{{ room.waiting }}</strong>
                  waiting
                </span>
                <span class="flex items-center gap-1.5">
                  <Users class="w-4 h-4 text-gray-400" />
                  <strong class="text-gray-900">{{ room.being_helped }}</strong>
                  being helped
                </span>
              </div>

              <div v-if="room.opened_at" class="mt-2 text-xs text-gray-400">Opened at {{ room.opened_at }}</div>

              <button
                class="mt-4 flex items-center text-xs font-medium hover:underline"
                :class="isStudent ? 'text-blue-600 hover:text-blue-700' : 'text-emerald-600 hover:text-emerald-700'"
                @click="router.push(`/room/${room.id}`)"
              >
                Join room
                <ChevronRight class="w-3.5 h-3.5 ml-1" />
              </button>
            </div>
          </div>
        </section>
        <section v-if="closedRooms(data.rooms).length > 0">
          <h2 class="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-4">Closed rooms</h2>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div
              v-for="room in closedRooms(data.rooms)"
              :key="room.id"
              class="bg-white rounded-xl shadow-sm border border-gray-200 p-5 opacity-60"
            >
              <div class="flex items-start justify-between mb-3">
                <div class="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center flex-shrink-0">
                  <DoorOpen class="w-5 h-5 text-gray-400" />
                </div>
                <span class="text-xs font-medium text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">Closed</span>
              </div>
              <h3 class="font-semibold text-gray-700 text-base leading-snug">{{ room.name }}</h3>
              <p class="text-xs text-gray-400 mt-0.5">{{ room.assignment_name }}</p>
              <p v-if="room.location" class="text-xs text-gray-400 mt-0.5">{{ room.location }}</p>
            </div>
          </div>
        </section>
      </template>
    </template>
  </div>

  <Teleport to="body">
    <div
      v-if="showCreate"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
      @mousedown.self="showCreate = false"
    >
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 class="text-base font-semibold text-gray-900">Create Room</h2>
          <button class="text-gray-400 hover:text-gray-600" @click="showCreate = false">
            <X class="w-5 h-5" />
          </button>
        </div>

        <div class="px-6 py-5 space-y-4">
          <div v-if="createError" class="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-sm text-red-700">
            {{ createError }}
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">
              Room name
              <span class="text-red-500">*</span>
            </label>
            <input
              v-model="createName"
              type="text"
              placeholder="e.g. Room A, Lab 101…"
              class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              autofocus
              @keydown.enter="createRoom"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">
              Location
              <span class="text-gray-400 font-normal">(optional)</span>
            </label>
            <input
              v-model="createLocation"
              type="text"
              placeholder="e.g. Building 2, Floor 3"
              class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div v-if="data?.assignments.length">
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Assignment</label>
            <div class="relative">
              <select
                v-model="createAssignId"
                class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm appearance-none focus:outline-none focus:ring-2 focus:ring-blue-500 pr-8"
              >
                <option :value="null" disabled>Select an assignment</option>
                <option v-for="a in data.assignments" :key="a.id" :value="a.id">
                  {{ a.name }}
                </option>
              </select>
              <ChevronDown
                class="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none"
              />
            </div>
          </div>
        </div>

        <div class="px-6 py-4 border-t border-gray-100 flex justify-end gap-3 bg-gray-50 rounded-b-2xl">
          <button
            class="px-4 py-2 text-sm font-medium rounded-lg text-gray-700 bg-white border border-gray-300 hover:bg-gray-50"
            @click="showCreate = false"
          >
            Cancel
          </button>
          <button
            :disabled="createBusy || !createName.trim() || !createAssignId"
            class="px-5 py-2 text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
            @click="createRoom"
          >
            {{ createBusy ? 'Creating…' : 'Create Room' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>

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
            :disabled="!!closeBusy"
            :class="[
              'px-5 py-2 text-sm font-medium rounded-lg text-white disabled:opacity-50',
              closeAction === 'kick' ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700',
            ]"
            @click="confirmCloseRoom"
          >
            {{ closeBusy ? 'Closing…' : 'Close Room' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
