<script setup lang="ts">
import { Check, X } from 'lucide-vue-next'

export interface ProgressCell {
  state: 'signed_off' | 'missed' | 'not_yet' | null
}

export interface ProgressRow {
  session: string
  cells: Record<string, 'signed_off' | 'missed' | 'not_yet' | null>
}

defineProps<{
  columns: string[]
  rows: ProgressRow[]
}>()
</script>

<template>
  <div class="overflow-x-auto rounded-xl border border-gray-200">
    <table class="w-full border-collapse text-sm">
      <thead>
        <tr>
          <th
            class="text-left px-5 py-3 font-semibold text-gray-600 bg-gray-50 border-b border-r border-gray-200 w-56 sticky left-0 z-10"
          >
            Session
          </th>
          <th
            v-for="col in columns"
            :key="col"
            class="px-5 py-3 font-semibold text-gray-600 bg-gray-50 border-b border-r border-gray-200 text-center whitespace-nowrap last:border-r-0"
            style="min-width: 110px"
          >
            {{ col }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(row, rowIdx) in rows"
          :key="row.session"
          :class="rowIdx < rows.length - 1 ? 'border-b border-gray-200' : ''"
        >
          <td class="px-5 py-4 font-medium text-gray-800 border-r border-gray-200 sticky left-0 bg-white z-10">
            {{ row.session }}
          </td>
          <td
            v-for="col in columns"
            :key="col"
            class="px-5 py-4 text-center border-r border-gray-200 last:border-r-0"
            :class="{
              'bg-green-50': row.cells[col] === 'signed_off',
              'bg-yellow-50': row.cells[col] === 'missed',
              'bg-white': !row.cells[col] || row.cells[col] === 'not_yet',
            }"
          >
            <span v-if="row.cells[col] === 'signed_off'" class="flex items-center justify-center">
              <Check class="w-4 h-4 text-green-600" stroke-width="2.5" />
            </span>
            <span v-else-if="row.cells[col] === 'missed'" class="flex items-center justify-center">
              <X class="w-4 h-4 text-red-500" stroke-width="2.5" />
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
