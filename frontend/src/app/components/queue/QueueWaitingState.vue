<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'

const props = defineProps<{
  requestId: number
  initialPosition: number
  questionText: string
  pollFn: (id: number) => Promise<{ status: string; final_feedback: string | null }>
}>()

const emit = defineEmits<{
  (e: 'left'): void
  (e: 'resolved', feedback: string): void
}>()

const position = ref(props.initialPosition)
const expanded = ref(false)
const confirmLeave = ref(false)
const leaveBusy = ref(false)

let countdownTimer: ReturnType<typeof setInterval> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null

function stopTimers() {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startCountdown() {
  countdownTimer = setInterval(() => {
    if (position.value > 1) position.value -= 1
  }, 15_000)
}

async function poll() {
  try {
    const res = await props.pollFn(props.requestId)
    if (['approved', 'edited', 'in_person', 'resolved'].includes(res.status)) {
      stopTimers()
      emit('resolved', res.final_feedback ?? '')
    }
  } catch {
    // Ignore transient network hiccups while polling.
  }
}

onMounted(() => {
  startCountdown()
  void poll()
  pollTimer = setInterval(poll, 5_000)
})

onUnmounted(() => {
  stopTimers()
})

const truncatedText = computed(() =>
  props.questionText.length > 160 && !expanded.value ? props.questionText.slice(0, 160) + '...' : props.questionText,
)

function ordinal(n: number) {
  const s = ['th', 'st', 'nd', 'rd']
  const v = n % 100
  return n + (s[(v - 20) % 10] || s[v] || s[0])
}

const posClass = computed(() => {
  if (position.value === 1) return 'text-emerald-600 bg-emerald-50 border-emerald-200'
  if (position.value <= 3) return 'text-amber-600 bg-amber-50 border-amber-200'
  return 'text-blue-600 bg-blue-50 border-blue-200'
})

async function doLeave() {
  leaveBusy.value = true
  try {
    stopTimers()
    emit('left')
  } finally {
    leaveBusy.value = false
    confirmLeave.value = false
  }
}
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="flex-1 overflow-y-auto px-6 py-6 flex flex-col items-center gap-6">
      <div class="check-anim flex items-center justify-center w-16 h-16 rounded-full bg-emerald-100">
        <svg class="w-8 h-8 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
          <path class="check-path" stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      </div>

      <div class="text-center">
        <h2 class="text-xl font-bold text-gray-900">You're in the queue!</h2>
        <p class="text-sm text-gray-500 mt-1">A TA will be with you soon.</p>
      </div>

      <div :class="['flex flex-col items-center gap-1 rounded-2xl border-2 px-8 py-4 transition-colors', posClass]">
        <span class="text-xs font-semibold uppercase tracking-widest opacity-70">Your position</span>
        <span class="text-4xl font-extrabold leading-none">#{{ position }}</span>
        <span class="text-xs opacity-60">{{ ordinal(position) }} in line</span>
      </div>

      <div class="w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-4 space-y-3">
        <div class="flex items-center gap-2">
          <span class="text-xs font-semibold text-gray-400 uppercase tracking-wide">Your question</span>
        </div>
        <p class="text-sm text-gray-700 leading-relaxed">{{ truncatedText }}</p>
        <button
          v-if="questionText.length > 160"
          class="text-xs text-blue-600 hover:underline"
          @click="expanded = !expanded"
        >
          {{ expanded ? 'Show less' : 'Show more' }}
        </button>
      </div>

      <p class="text-xs text-gray-400 text-center">Updates every 5 seconds</p>
    </div>

    <div class="px-6 py-4 border-t border-gray-100 bg-gray-50 rounded-b-2xl flex-shrink-0">
      <template v-if="!confirmLeave">
        <button
          class="w-full py-2 text-sm font-medium rounded-lg border-2 border-red-200 text-red-500 hover:bg-red-50 hover:border-red-400 hover:text-red-700 transition-all"
          @click="confirmLeave = true"
        >
          Leave Queue
        </button>
      </template>
      <template v-else>
        <p class="text-sm text-gray-700 text-center mb-3">Are you sure you want to leave the queue?</p>
        <div class="flex gap-2">
          <button
            class="flex-1 py-2 text-sm font-medium rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-100 transition-colors"
            @click="confirmLeave = false"
          >
            Stay
          </button>
          <button
            :disabled="leaveBusy"
            class="flex-1 py-2 text-sm font-semibold rounded-lg bg-red-500 hover:bg-red-600 text-white disabled:opacity-50 transition-colors"
            @click="doLeave"
          >
            Yes, Leave
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.check-anim {
  animation: pop 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) both;
}

@keyframes pop {
  0% {
    transform: scale(0);
    opacity: 0;
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

.check-path {
  stroke-dasharray: 30;
  stroke-dashoffset: 30;
  animation: draw 0.4s 0.3s ease-out forwards;
}

@keyframes draw {
  to {
    stroke-dashoffset: 0;
  }
}
</style>
