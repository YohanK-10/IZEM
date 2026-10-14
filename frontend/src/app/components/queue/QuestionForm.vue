<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Exercise } from '../../composables/useQueue'

const props = defineProps<{
  exercise: Exercise
  submitError: string | null
  busy: boolean
}>()

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'submit', text: string): void
}>()

const text = ref('')
const MIN = 20
const count = computed(() => text.value.length)
const canSubmit = computed(() => count.value >= MIN && !props.busy)
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Back chip + exercise label -->
    <div class="px-6 pt-5 pb-4 flex items-center gap-2 flex-shrink-0">
      <button
        class="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 font-medium transition-colors"
        @click="emit('back')"
      >
        <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        Back
      </button>
      <span class="text-gray-300">·</span>
      <span
        class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-100 text-blue-700 text-xs font-semibold"
      >
        Exercise {{ exercise.question_number }}
      </span>
      <span v-if="exercise.description" class="text-xs text-gray-500 truncate flex-1 min-w-0">
        {{ exercise.description }}
      </span>
    </div>

    <!-- Body -->
    <div class="flex-1 overflow-y-auto px-6 pb-2 space-y-3">
      <!-- Error -->
      <div v-if="submitError" class="bg-red-50 border border-red-200 rounded-lg px-4 py-2.5 text-sm text-red-700">
        {{ submitError }}
      </div>

      <label class="block text-sm font-semibold text-gray-800">Describe what you're stuck on</label>

      <div class="relative">
        <textarea
          v-model="text"
          rows="5"
          placeholder="e.g. I understand the base case but I'm not sure how to handle the recursive step…"
          class="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none leading-relaxed"
          :class="count > 0 && count < MIN ? 'border-amber-300 focus:ring-amber-400' : ''"
          autofocus
        />
        <!-- Character count -->
        <span
          :class="[
            'absolute bottom-2.5 right-3 text-xs font-medium transition-colors',
            count >= MIN ? 'text-emerald-500' : count > 0 ? 'text-amber-500' : 'text-gray-300',
          ]"
        >
          {{ count }}
          <span class="text-gray-300">/{{ MIN }}+</span>
        </span>
      </div>

      <!-- Guiding prompt -->
      <div class="bg-blue-50 border border-blue-100 rounded-lg px-4 py-3">
        <p class="text-xs text-blue-700 leading-relaxed">
          <span class="font-semibold">Tip:</span>
          Try to include:
          <em>what you tried</em>
          ,
          <em>what you expected</em>
          , and
          <em>what happened instead</em>
          .
        </p>
      </div>
    </div>

    <!-- Footer -->
    <div
      class="flex items-center justify-between px-6 py-4 border-t border-gray-100 bg-gray-50 rounded-b-2xl flex-shrink-0"
    >
      <span v-if="count > 0 && count < MIN" class="text-xs text-amber-600 font-medium">
        {{ MIN - count }} more characters needed
      </span>
      <span v-else class="text-xs text-gray-400">Be specific — it helps the TA help you faster.</span>

      <button
        :disabled="!canSubmit"
        class="px-5 py-2 text-sm font-semibold rounded-lg bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        @click="emit('submit', text)"
      >
        <svg v-if="busy" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        {{ busy ? 'Joining…' : 'Join Queue' }}
      </button>
    </div>
  </div>
</template>
