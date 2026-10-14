<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import { Clock, ChevronRight, Inbox } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const courseId = Number(route.params.courseId)

interface OvertimeRequest {
  id: number
  student_name: string
  assignment_name: string
  question_number: number | null
  student_comment: string | null
  submission_text: string | null
  status: string
  ai_feedback: string | null
  ai_progress_status: string | null
  created_at: string | null
}

interface OvertimeData {
  course_id: number
  course_name: string
  overtime_requests: OvertimeRequest[]
}

const data = ref<OvertimeData | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

async function load() {
  try {
    data.value = await api.get<OvertimeData>(`/course/${courseId}/overtime`)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load overtime requests'
  } finally {
    loading.value = false
  }
}

onMounted(load)

function statusBadge(status: string) {
  const map: Record<string, string> = {
    pending: 'bg-amber-100 text-amber-700',
    ai_generated: 'bg-sky-100 text-sky-700',
  }
  return map[status] ?? 'bg-gray-100 text-gray-600'
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    pending: 'Pending',
    ai_generated: 'AI Ready',
  }
  return map[status] ?? status
}
</script>

<template>
  <div class="-mx-4 sm:-mx-6 lg:-mx-8 -mt-6 px-4 sm:px-6 lg:px-8 py-8 min-h-full bg-gray-100">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-gray-900">
        Course Overview
        <span v-if="data?.course_name" class="text-gray-400 font-normal">: {{ data.course_name }}</span>
      </h1>
      <p class="text-sm text-gray-500 mt-0.5">Overtime requests left over from closed queues</p>
    </div>

    <div v-if="loading" class="text-gray-500 text-sm">Loading…</div>

    <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
      {{ error }}
    </div>

    <template v-else-if="data">
      <!-- Empty state -->
      <div
        v-if="data.overtime_requests.length === 0"
        class="bg-white rounded-xl border border-gray-200 shadow-sm p-12 text-center"
      >
        <Inbox class="w-14 h-14 text-gray-300 mx-auto mb-4" />
        <h2 class="text-lg font-semibold text-gray-900 mb-1">No overtime requests</h2>
        <p class="text-sm text-gray-500">When a queue is closed with pending requests kept, they will appear here.</p>
      </div>

      <!-- Request list -->
      <div v-else class="space-y-3">
        <button
          v-for="req in data.overtime_requests"
          :key="req.id"
          class="w-full text-left bg-white rounded-xl border border-gray-200 shadow-sm p-5 hover:border-blue-300 hover:shadow-md transition-all"
          @click="
            router.push({
              path: `/review-request/${req.id}`,
              query: { from: 'overtime', courseId: String(courseId) },
            })
          "
        >
          <div class="flex items-start justify-between gap-4 flex-wrap">
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2 flex-wrap mb-1">
                <span class="font-semibold text-gray-900 text-sm">{{ req.student_name }}</span>
                <span :class="['text-xs px-2 py-0.5 rounded-full font-medium', statusBadge(req.status)]">
                  {{ statusLabel(req.status) }}
                </span>
              </div>
              <p class="text-xs text-gray-500">
                {{ req.assignment_name }}
                <span v-if="req.question_number">· Q{{ req.question_number }}</span>
              </p>
              <p v-if="req.student_comment" class="text-sm text-gray-700 mt-2 line-clamp-2">
                {{ req.student_comment }}
              </p>
              <p v-if="req.ai_feedback" class="text-xs text-emerald-700 mt-1 line-clamp-1">AI: {{ req.ai_feedback }}</p>
            </div>

            <div class="flex items-center gap-3 flex-shrink-0">
              <span v-if="req.created_at" class="flex items-center gap-1 text-xs text-gray-400">
                <Clock class="w-3.5 h-3.5" />
                {{ req.created_at }}
              </span>
              <ChevronRight class="w-4 h-4 text-gray-400" />
            </div>
          </div>
        </button>
      </div>
    </template>
  </div>
</template>
