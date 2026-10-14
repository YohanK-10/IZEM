<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Clock, Users } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const roomId = Number(route.params.roomId)

interface WaitingItem {
  id: number
  position: number
  student_name: string
  question: string
  wait_time: number
}

interface HelpedItem {
  id: number
  student_name: string
  ta_name: string
}

interface RoomState {
  room_name: string
  room_location: string | null
  assignment_name: string
  is_open: boolean
  total_waiting: number
  total_being_helped: number
  waiting: WaitingItem[]
  being_helped: HelpedItem[]
}

const state = ref<RoomState | null>(null)
const error = ref('')

let pollTimer: ReturnType<typeof setInterval> | null = null

async function fetchState() {
  try {
    const res = await fetch(`/view/room/${roomId}/status`)
    if (res.status === 404) {
      error.value = 'Room not found.'
      return
    }
    if (!res.ok) {
      error.value = 'Failed to load room.'
      return
    }
    state.value = await res.json()
    error.value = ''
  } catch {
    error.value = 'Connection error.'
  }
}

onMounted(async () => {
  await fetchState()
  pollTimer = setInterval(fetchState, 5000)
})
onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Error -->
    <div v-if="error && !state" class="flex items-center justify-center min-h-screen">
      <div class="text-center">
        <p class="text-red-600 mb-4">{{ error }}</p>
        <button class="text-blue-600 hover:underline text-sm" @click="router.push({ name: 'viewer-landing' })">
          ← Try a different room
        </button>
      </div>
    </div>

    <template v-else-if="state">
      <!-- Header -->
      <header class="bg-white border-b border-gray-200 px-6 py-5">
        <div class="max-w-3xl mx-auto flex items-start justify-between gap-4">
          <div>
            <h1 class="text-2xl font-bold text-gray-900">{{ state.room_name }}</h1>
            <p class="text-sm text-gray-500 mt-0.5">
              {{ state.assignment_name }}
              <span v-if="state.room_location">· {{ state.room_location }}</span>
            </p>
          </div>
          <div class="flex items-center gap-3 flex-shrink-0">
            <div class="flex items-center gap-4 text-sm text-gray-600">
              <span class="flex items-center gap-1.5">
                <Clock class="w-4 h-4 text-gray-400" />
                <strong class="text-gray-900">{{ state.total_waiting }}</strong>
                waiting
              </span>
              <span class="flex items-center gap-1.5">
                <Users class="w-4 h-4 text-gray-400" />
                <strong class="text-gray-900">{{ state.total_being_helped }}</strong>
                being helped
              </span>
            </div>
            <span
              :class="[
                'text-xs px-2.5 py-1 rounded-full font-medium',
                state.is_open ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500',
              ]"
            >
              {{ state.is_open ? 'Open' : 'Closed' }}
            </span>
          </div>
        </div>
        <p class="max-w-3xl mx-auto mt-2 text-xs text-gray-400">Auto-refreshes every 5 seconds</p>
      </header>

      <div class="max-w-3xl mx-auto px-6 py-6 space-y-6">
        <!-- Being Helped -->
        <div v-if="state.being_helped.length > 0">
          <div class="bg-amber-50 border border-amber-200 rounded-xl overflow-hidden shadow-sm">
            <div class="px-5 py-3 border-b border-amber-200 bg-amber-100/50">
              <h2 class="text-sm font-semibold text-amber-900">Currently Being Helped</h2>
            </div>
            <div class="divide-y divide-amber-100">
              <div
                v-for="item in state.being_helped"
                :key="item.id"
                class="px-5 py-4 flex items-center justify-between animate-pulse-slow"
              >
                <div class="flex items-center gap-3">
                  <div
                    class="w-9 h-9 rounded-full bg-amber-200 flex items-center justify-center text-amber-800 font-bold text-sm"
                  >
                    {{ item.student_name[0] }}
                  </div>
                  <div>
                    <p class="font-semibold text-gray-900 text-sm">{{ item.student_name }}</p>
                    <p class="text-xs text-amber-700">
                      Helped by
                      <strong>{{ item.ta_name }}</strong>
                    </p>
                  </div>
                </div>
                <span
                  class="text-xs px-2.5 py-1 rounded-full bg-amber-100 text-amber-800 font-medium border border-amber-200"
                >
                  ✋ Raise your hand
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- Waiting Queue -->
        <div class="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          <div class="px-5 py-3 border-b border-gray-100 bg-gray-50">
            <h2 class="text-sm font-semibold text-gray-800">Waiting in Queue</h2>
          </div>

          <!-- Empty -->
          <div v-if="state.waiting.length === 0" class="py-16 text-center">
            <div class="text-4xl mb-3">✅</div>
            <h3 class="text-base font-medium text-gray-900">Queue is empty!</h3>
            <p class="text-sm text-gray-500 mt-1">No students are currently waiting.</p>
          </div>

          <!-- List -->
          <div v-else class="divide-y divide-gray-100">
            <div v-for="item in state.waiting" :key="item.id" class="px-5 py-4 flex items-center gap-4">
              <div class="w-11 h-11 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                <span class="text-lg font-bold text-blue-600">{{ item.position }}</span>
              </div>
              <div class="min-w-0 flex-1">
                <p class="font-semibold text-gray-900">{{ item.student_name }}</p>
                <div class="flex items-center gap-3 text-xs text-gray-500 mt-0.5">
                  <span>{{ item.question }}</span>
                  <span class="flex items-center gap-0.5">
                    <Clock class="w-3 h-3" />
                    {{ item.wait_time }} min
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Back link -->
        <div class="text-center">
          <button class="text-sm text-gray-400 hover:text-gray-600" @click="router.push({ name: 'viewer-landing' })">
            ← View a different room
          </button>
        </div>
      </div>
    </template>
  </div>
</template>
