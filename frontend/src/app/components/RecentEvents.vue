<script setup lang="ts">
export interface RecentEvent {
  id: number
  taName: string
  action: string
  blockLabel: string
  sessionName: string
  timestamp: string
}

defineProps<{
  events: RecentEvent[]
}>()
</script>

<template>
  <div class="flex flex-col gap-3 max-h-64 overflow-y-auto pr-1">
    <p v-if="events.length === 0" class="text-sm text-gray-400 italic">No recent events.</p>

    <div
      v-for="event in events"
      :key="event.id"
      class="flex items-start gap-3 py-2.5 border-b border-gray-100 last:border-b-0"
    >
      <!-- Avatar initial -->
      <div
        class="w-7 h-7 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5"
      >
        {{ event.taName[0] }}
      </div>

      <!-- Text -->
      <p class="text-sm text-gray-600 leading-relaxed">
        <span class="font-semibold text-gray-900">{{ event.taName }}</span>
        {{ ' ' }}{{ event.action }}
        {{ ' ' }}
        <span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-semibold bg-blue-50 text-blue-700">
          {{ event.blockLabel }}
        </span>
        {{ ' ' }}in {{ ' ' }}
        <span class="font-medium text-gray-800">{{ event.sessionName }}</span>
        {{ ' ' }}on {{ ' ' }}
        <span class="text-gray-400 text-xs">{{ event.timestamp }}</span>
      </p>
    </div>
  </div>
</template>
