<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle } from 'lucide-vue-next'
import { useUIStore } from '../stores/ui'

const uiStore = useUIStore()

const toneClasses = computed(() =>
  uiStore.dialog?.tone === 'danger'
    ? {
        iconWrap: 'bg-red-100 text-red-600',
        confirm: 'bg-red-600 hover:bg-red-700 focus:ring-red-500',
      }
    : {
        iconWrap: 'bg-blue-100 text-blue-600',
        confirm: 'bg-blue-600 hover:bg-blue-700 focus:ring-blue-500',
      },
)

function handleBackdropClick() {
  uiStore.dismissDialog()
}
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="uiStore.dialog"
        class="fixed inset-0 z-[70] flex items-center justify-center bg-gray-950/45 p-4"
        @mousedown.self="handleBackdropClick"
      >
        <div class="w-full max-w-md rounded-2xl bg-white shadow-2xl ring-1 ring-gray-200">
          <div class="flex items-start gap-4 px-6 py-5">
            <div :class="['mt-0.5 flex h-11 w-11 items-center justify-center rounded-full', toneClasses.iconWrap]">
              <AlertTriangle v-if="uiStore.dialog.kind === 'confirm'" class="h-5 w-5" />
              <AlertTriangle v-else class="h-5 w-5" />
            </div>
            <div class="min-w-0 flex-1">
              <h2 class="text-base font-semibold text-gray-900">{{ uiStore.dialog.title }}</h2>
              <p class="mt-2 whitespace-pre-line text-sm leading-6 text-gray-600">
                {{ uiStore.dialog.message }}
              </p>
            </div>
          </div>

          <div class="flex flex-wrap justify-end gap-3 rounded-b-2xl border-t border-gray-100 bg-gray-50 px-6 py-4">
            <button
              v-if="uiStore.dialog.cancelLabel"
              type="button"
              class="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100"
              @click="uiStore.dismissDialog()"
            >
              {{ uiStore.dialog.cancelLabel }}
            </button>
            <button
              type="button"
              :class="[
                'rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2',
                toneClasses.confirm,
              ]"
              @click="uiStore.acceptDialog()"
            >
              {{ uiStore.dialog.confirmLabel }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
