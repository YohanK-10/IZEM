<script setup lang="ts">
import type { Exercise } from '../../composables/useQueue'

defineProps<{
  exercises: Exercise[]
  loading: boolean
  modelValue: number | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', id: number): void
  (e: 'next'): void
  (e: 'cancel'): void
}>()
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Body: exercise list -->
    <div class="flex-1 overflow-y-auto px-6 py-5 space-y-2">
      <div v-if="loading" class="py-12 text-center text-sm text-gray-400">Loading exercises…</div>

      <div v-else-if="exercises.length === 0" class="py-12 text-center text-sm text-gray-400">
        No exercises found for this assignment.
      </div>

      <button
        v-for="ex in exercises"
        :key="ex.id"
        :class="[
          'w-full text-left rounded-xl border-2 px-4 py-3.5 transition-all group',
          modelValue === ex.id
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-200 bg-white hover:border-blue-200 hover:bg-gray-50',
        ]"
        @click="emit('update:modelValue', ex.id)"
      >
        <div class="flex items-start gap-3">
          <!-- Number bubble -->
          <span
            :class="[
              'flex-shrink-0 w-7 h-7 rounded-full text-xs font-bold flex items-center justify-center mt-0.5 transition-colors',
              modelValue === ex.id
                ? 'bg-blue-500 text-white'
                : 'bg-gray-100 text-gray-500 group-hover:bg-blue-100 group-hover:text-blue-600',
            ]"
          >
            {{ ex.question_number }}
          </span>

          <div class="min-w-0 flex-1">
            <p
              :class="['text-sm font-semibold leading-snug', modelValue === ex.id ? 'text-blue-800' : 'text-gray-900']"
            >
              Exercise {{ ex.question_number }}
            </p>
            <p v-if="ex.description" class="text-xs text-gray-500 mt-0.5 line-clamp-2 leading-relaxed">
              {{ ex.description }}
            </p>
          </div>

          <!-- Selected indicator -->
          <div
            v-if="modelValue === ex.id"
            class="flex-shrink-0 w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center mt-0.5"
          >
            <svg class="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
        </div>
      </button>
    </div>

    <!-- Footer -->
    <div
      class="flex items-center justify-between px-6 py-4 border-t border-gray-100 bg-gray-50 rounded-b-2xl flex-shrink-0"
    >
      <button
        class="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800 transition-colors"
        @click="emit('cancel')"
      >
        Cancel
      </button>
      <button
        :disabled="modelValue === null"
        class="px-5 py-2 text-sm font-semibold rounded-lg bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        @click="emit('next')"
      >
        Next →
      </button>
    </div>
  </div>
</template>
