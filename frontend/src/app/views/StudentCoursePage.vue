<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { studentApi } from '../api'
import { useCoursesStore } from '../stores/courses'
import { fmtUtc } from '../utils/time'

const route = useRoute()
const courseId = Number(route.params.courseId)
const coursesStore = useCoursesStore()

const courseName = ref('...')
const assignments = ref<any[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

onMounted(async () => {
  if (coursesStore.courses.length === 0) await coursesStore.fetchCourses()
  courseName.value = coursesStore.getCourseById(courseId)?.name ?? '...'
  try {
    const data = await studentApi.courseProgress(courseId)
    assignments.value = data.assignments
  } catch (e: any) {
    error.value = e?.message ?? 'Failed to load'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="-mx-4 sm:-mx-6 lg:-mx-8 -mt-6 px-4 sm:px-6 lg:px-8 py-8 min-h-full bg-gray-50">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-gray-900">{{ courseName }}</h1>
      <p class="text-sm text-gray-500 mt-1">Your Progress</p>
    </div>

    <div v-if="error" class="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
      {{ error }}
    </div>

    <div v-if="loading" class="text-sm text-gray-400">Loading…</div>

    <div
      v-else-if="assignments.length === 0"
      class="bg-white rounded-xl border border-gray-200 p-6 text-sm text-gray-400"
    >
      No progress data yet.
    </div>

    <div v-else class="space-y-6">
      <div
        v-for="a in assignments"
        :key="a.assignment_id"
        class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden"
      >
        <!-- Lab header -->
        <div class="px-5 py-3 bg-gray-50 border-b border-gray-200">
          <span class="font-semibold text-gray-900 text-sm">{{ a.assignment_name }}</span>
        </div>

        <!-- Sign-off points table -->
        <template v-if="a.signoff_points.length">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-100">
                <th class="text-left px-5 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Exercise
                </th>
                <th class="text-left px-5 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50">
              <tr v-for="pt in a.signoff_points" :key="pt.question_id">
                <td class="px-5 py-2.5 text-gray-700">{{ pt.label }}</td>
                <td class="px-5 py-2.5">
                  <span
                    v-if="pt.status === 'signed_off'"
                    class="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full px-2 py-0.5"
                  >
                    ✓ Signed off
                  </span>
                  <span
                    v-else-if="pt.status === 'insufficient'"
                    class="inline-flex items-center gap-1 text-xs font-medium text-yellow-700 bg-yellow-50 border border-yellow-300 rounded-full px-2 py-0.5"
                  >
                    ✗ Insufficient
                  </span>
                  <span
                    v-else
                    class="inline-flex items-center gap-1 text-xs font-medium text-gray-400 bg-gray-50 border border-gray-200 rounded-full px-2 py-0.5"
                  >
                    Not done yet
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </template>

        <!-- Help requests table -->
        <template v-if="a.requests.length">
          <div class="px-5 pt-3 pb-1 border-t border-gray-100">
            <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Help Requests</p>
          </div>
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-100">
                <th class="text-left px-5 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                <th class="text-left px-5 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">TA</th>
                <th class="text-left px-5 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Date</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50">
              <tr v-for="r in a.requests" :key="r.id">
                <td class="px-5 py-2.5">
                  <span
                    class="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full px-2 py-0.5"
                  >
                    ✓ {{ r.status }}
                  </span>
                </td>
                <td class="px-5 py-2.5 text-gray-500">{{ r.ta_name ?? '—' }}</td>
                <td class="px-5 py-2.5 text-gray-400">{{ fmtUtc(r.resolved_at) }}</td>
              </tr>
            </tbody>
          </table>
        </template>

        <div v-if="!a.signoff_points.length && !a.requests.length" class="px-5 py-4 text-xs text-gray-400">
          No activity yet.
        </div>
      </div>
    </div>
  </div>
</template>
