<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { signoffAnalyticsApi } from '../api'
import type { SignoffAnalyticsData } from '../types'

const data = ref<SignoffAnalyticsData | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

const filters = ref({
  course_id: undefined as number | undefined,
  assignment_id: undefined as number | undefined,
  flow_id: undefined as number | undefined,
  grader_id: undefined as number | undefined,
  start_date: '',
  end_date: '',
})

async function load() {
  loading.value = true
  error.value = null
  try {
    data.value = await signoffAnalyticsApi.get({
      course_id: filters.value.course_id,
      assignment_id: filters.value.assignment_id,
      flow_id: filters.value.flow_id,
      grader_id: filters.value.grader_id,
      start_date: filters.value.start_date || undefined,
      end_date: filters.value.end_date || undefined,
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load sign-off analytics'
  } finally {
    loading.value = false
  }
}

function onCourseChange(e: Event) {
  const val = Number((e.target as HTMLSelectElement).value)
  filters.value.course_id = val || undefined
  // resetting dependent scopes when course changes
  filters.value.assignment_id = undefined
  filters.value.flow_id = undefined
  load()
}

function onAssignmentChange(e: Event) {
  const val = Number((e.target as HTMLSelectElement).value)
  filters.value.assignment_id = val || undefined
  if (val) filters.value.flow_id = undefined
  load()
}

function onFlowChange(e: Event) {
  const val = Number((e.target as HTMLSelectElement).value)
  filters.value.flow_id = val || undefined
  if (val) filters.value.assignment_id = undefined
  load()
}

function onGraderChange(e: Event) {
  const val = Number((e.target as HTMLSelectElement).value)
  filters.value.grader_id = val || undefined
  load()
}

function clearFilters() {
  filters.value = {
    course_id: undefined,
    assignment_id: undefined,
    flow_id: undefined,
    grader_id: undefined,
    start_date: '',
    end_date: '',
  }
  load()
}

onMounted(load)

const s = () => (data.value?.summary as any) ?? {}
const hasFilters = () =>
  !!(
    filters.value.course_id ||
    filters.value.assignment_id ||
    filters.value.flow_id ||
    filters.value.grader_id ||
    filters.value.start_date ||
    filters.value.end_date
  )

const exportUrl = computed(() => {
  const qs = new URLSearchParams()
  if (filters.value.course_id) qs.set('course_id', String(filters.value.course_id))
  if (filters.value.assignment_id) qs.set('assignment_id', String(filters.value.assignment_id))
  if (filters.value.flow_id) qs.set('flow_id', String(filters.value.flow_id))
  if (filters.value.grader_id) qs.set('grader_id', String(filters.value.grader_id))
  if (filters.value.start_date) qs.set('start_date', filters.value.start_date)
  if (filters.value.end_date) qs.set('end_date', filters.value.end_date)
  const query = qs.toString()
  return `/api/signoff-analytics/export.csv${query ? `?${query}` : ''}`
})
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Page header -->
    <div class="bg-white border-b border-gray-200 px-4 sm:px-6 lg:px-8 py-6">
      <div class="max-w-7xl mx-auto flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 class="text-2xl font-bold text-gray-900 tracking-tight">Sign-off Analytics</h1>
          <p class="text-sm text-gray-500 mt-0.5">
            {{ data?.focus?.subtitle ?? 'Sign-off outcomes across courses, flows and graders' }}
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <a
            :href="exportUrl"
            class="inline-flex items-center rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-sm font-medium text-blue-700 transition-colors hover:border-blue-300 hover:bg-blue-100"
          >
            Export CSV
          </a>
          <button
            v-if="hasFilters()"
            class="text-sm text-gray-500 hover:text-gray-800 border border-gray-300 hover:border-gray-400 rounded-lg px-3 py-1.5 transition-colors"
            @click="clearFilters"
          >
            Clear filters
          </button>
        </div>
      </div>
    </div>

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      <!-- Filters -->
      <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-4 flex flex-wrap gap-4 items-end">
        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Course</label>
          <select
            :value="filters.course_id ?? ''"
            class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition min-w-[160px]"
            @change="onCourseChange"
          >
            <option value="">All courses</option>
            <option v-for="c in data?.filters?.courses ?? []" :key="c.id" :value="c.id">
              {{ c.name }}
            </option>
          </select>
        </div>

        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Flow</label>
          <select
            :value="filters.flow_id ?? ''"
            class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition min-w-[200px]"
            @change="onFlowChange"
          >
            <option value="">All flows</option>
            <option v-for="f in data?.filters?.flows ?? []" :key="f.id" :value="f.id">
              {{ f.course_name }} – {{ f.name }} ({{ f.point_count }})
            </option>
          </select>
        </div>

        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Assignment (Q-signoff)</label>
          <select
            :value="filters.assignment_id ?? ''"
            class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition min-w-[220px]"
            @change="onAssignmentChange"
          >
            <option value="">All assignments</option>
            <option v-for="a in data?.filters?.assignments ?? []" :key="a.id" :value="a.id">
              {{ a.course_name }} – {{ a.name }}
            </option>
          </select>
        </div>

        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Grader (TA)</label>
          <select
            :value="filters.grader_id ?? ''"
            class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition min-w-[180px]"
            @change="onGraderChange"
          >
            <option value="">All TAs</option>
            <option v-for="g in data?.filters?.graders ?? []" :key="g.id" :value="g.id">
              {{ g.name }}
            </option>
          </select>
        </div>

        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">From</label>
          <input
            v-model="filters.start_date"
            type="date"
            class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
            @change="load"
          />
        </div>

        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">To</label>
          <input
            v-model="filters.end_date"
            type="date"
            class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
            @change="load"
          />
        </div>
      </div>

      <!-- Loading / Error -->
      <div v-if="loading" class="flex items-center gap-3 text-gray-500 text-sm py-8">
        <span
          class="inline-block w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"
        ></span>
        Loading sign-off analytics…
      </div>
      <div v-else-if="error" class="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl text-sm">
        {{ error }}
      </div>

      <template v-else>
        <!-- KPI grid -->
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5 border-t-4 border-t-blue-500">
            <div class="text-3xl font-extrabold text-blue-600">{{ s().total_signoffs ?? 0 }}</div>
            <div class="text-sm font-medium text-gray-700 mt-1">Total Sign-offs</div>
            <div class="text-xs text-gray-400 mt-0.5">
              {{ s().student_count ?? 0 }} students · {{ s().grader_count ?? 0 }} TAs
            </div>
          </div>

          <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5 border-t-4 border-t-emerald-500">
            <div class="text-3xl font-extrabold text-emerald-600">
              {{ s().signed_off_rate_display ?? '0%' }}
            </div>
            <div class="text-sm font-medium text-gray-700 mt-1">Signed-off Rate</div>
            <div class="text-xs text-gray-400 mt-0.5">{{ s().signed_off_count ?? 0 }} signed off</div>
          </div>

          <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5 border-t-4 border-t-rose-500">
            <div class="text-3xl font-extrabold text-rose-600">
              {{ s().insufficient_rate_display ?? '0%' }}
            </div>
            <div class="text-sm font-medium text-gray-700 mt-1">Insufficient Rate</div>
            <div class="text-xs text-gray-400 mt-0.5">{{ s().insufficient_count ?? 0 }} marked insufficient</div>
          </div>

          <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5 border-t-4 border-t-violet-500">
            <div class="text-3xl font-extrabold text-violet-600">{{ s().retry_count ?? 0 }}</div>
            <div class="text-sm font-medium text-gray-700 mt-1">Retries</div>
            <div class="text-xs text-gray-400 mt-0.5">
              {{ s().retry_rate_display ?? '0%' }} of (student, point) pairs
            </div>
          </div>

          <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5 border-t-4 border-t-sky-500">
            <div class="text-3xl font-extrabold text-sky-600">
              {{ s().avg_per_student_display ?? '—' }}
            </div>
            <div class="text-sm font-medium text-gray-700 mt-1">Avg / Student</div>
            <div class="text-xs text-gray-400 mt-0.5">Sign-off attempts per student</div>
          </div>

          <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5 border-t-4 border-t-indigo-500">
            <div class="text-3xl font-extrabold text-indigo-600">
              {{ s().avg_per_grader_display ?? '—' }}
            </div>
            <div class="text-sm font-medium text-gray-700 mt-1">Avg / TA</div>
            <div class="text-xs text-gray-400 mt-0.5">Sign-offs given per TA</div>
          </div>

          <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5 border-t-4 border-t-amber-500">
            <div class="text-3xl font-extrabold text-amber-600">
              {{ s().recent_activity_count ?? 0 }}
            </div>
            <div class="text-sm font-medium text-gray-700 mt-1">Last 7 days</div>
            <div class="text-xs text-gray-400 mt-0.5">Sign-off events</div>
          </div>

          <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5 border-t-4 border-t-orange-500">
            <div class="text-3xl font-extrabold text-orange-600">
              {{ (s().points_covered ?? 0) + (s().questions_covered ?? 0) }}
            </div>
            <div class="text-sm font-medium text-gray-700 mt-1">Targets Covered</div>
            <div class="text-xs text-gray-400 mt-0.5">
              {{ s().points_covered ?? 0 }} pts · {{ s().questions_covered ?? 0 }} questions
            </div>
          </div>
        </div>

        <!-- Status breakdown + Risk signals -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <div class="flex items-center gap-2 mb-5">
              <div class="w-2 h-2 rounded-full bg-blue-500"></div>
              <h2 class="text-sm font-bold text-gray-900 uppercase tracking-wide">Status Breakdown</h2>
              <span class="ml-auto text-xs text-gray-400">{{ s().total_signoffs ?? 0 }} total</span>
            </div>
            <div class="space-y-3">
              <div v-for="item in s().status_breakdown ?? []" :key="item.status" class="flex items-center gap-3">
                <span
                  :class="[
                    'text-xs px-2.5 py-1 rounded-full font-semibold w-28 text-center flex-shrink-0',
                    item.badge_classes,
                  ]"
                >
                  {{ item.label }}
                </span>
                <div class="flex-1 bg-gray-100 rounded-full h-2.5 overflow-hidden">
                  <div
                    class="h-2.5 rounded-full transition-all duration-500"
                    :style="{ width: `${item.percentage}%`, backgroundColor: item.chart_color }"
                  ></div>
                </div>
                <span class="text-sm font-semibold text-gray-800 w-8 text-right flex-shrink-0">{{ item.count }}</span>
                <span class="text-xs text-gray-400 w-12 text-right flex-shrink-0">{{ item.percentage_display }}</span>
              </div>
              <div v-if="!s().status_breakdown?.length" class="text-sm text-gray-400 italic text-center py-4">
                No data yet.
              </div>
            </div>
          </div>

          <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <div class="flex items-center gap-2 mb-5">
              <div class="w-2 h-2 rounded-full bg-amber-500"></div>
              <h2 class="text-sm font-bold text-gray-900 uppercase tracking-wide">Risk Signals</h2>
            </div>
            <div class="space-y-4">
              <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p class="text-sm font-semibold text-gray-800">Insufficient sign-offs</p>
                  <p class="text-xs text-gray-400 mt-0.5">Attempts marked insufficient</p>
                </div>
                <div class="text-right">
                  <div class="text-xl font-extrabold text-rose-600">
                    {{ s().insufficient_count ?? 0 }}
                  </div>
                  <div class="text-xs text-gray-400">
                    {{ s().insufficient_rate_display ?? '0%' }}
                  </div>
                </div>
              </div>
              <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p class="text-sm font-semibold text-gray-800">Repeat attempts</p>
                  <p class="text-xs text-gray-400 mt-0.5">Same student / same target, &gt; 1 record</p>
                </div>
                <div class="text-right">
                  <div class="text-xl font-extrabold text-violet-600">
                    {{ s().retry_count ?? 0 }}
                  </div>
                  <div class="text-xs text-gray-400">{{ s().retry_rate_display ?? '0%' }}</div>
                </div>
              </div>
              <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p class="text-sm font-semibold text-gray-800">TA coverage</p>
                  <p class="text-xs text-gray-400 mt-0.5">Distinct graders in scope</p>
                </div>
                <div class="text-xl font-extrabold text-blue-600">{{ s().grader_count ?? 0 }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Course stats -->
        <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div class="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
            <div class="w-2 h-2 rounded-full bg-emerald-500"></div>
            <h2 class="text-sm font-bold text-gray-900 uppercase tracking-wide">Course Statistics</h2>
            <span
              v-if="data?.course_stats?.length"
              class="ml-auto text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-medium"
            >
              {{ data.course_stats.length }}
              {{ data.course_stats.length === 1 ? 'course' : 'courses' }}
            </span>
          </div>
          <div v-if="!data?.course_stats?.length" class="px-6 py-10 text-center text-sm text-gray-400">
            No course sign-off data for the selected filters.
          </div>
          <div v-else class="overflow-x-auto">
            <table class="min-w-full text-sm">
              <thead class="bg-gray-50">
                <tr class="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  <th class="text-left px-6 py-3">Course</th>
                  <th class="text-right px-4 py-3">Total</th>
                  <th class="text-right px-4 py-3">Signed off</th>
                  <th class="text-right px-4 py-3">Insufficient</th>
                  <th class="text-right px-4 py-3">Students</th>
                  <th class="text-right px-6 py-3">Pass %</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100">
                <tr v-for="c in data.course_stats" :key="c.course_id" class="hover:bg-gray-50 transition-colors">
                  <td class="px-6 py-3.5 font-semibold text-gray-900">{{ c.course_name }}</td>
                  <td class="px-4 py-3.5 text-right font-bold text-blue-600">{{ c.total }}</td>
                  <td class="px-4 py-3.5 text-right text-emerald-600 font-medium">
                    {{ c.signed_off }}
                  </td>
                  <td class="px-4 py-3.5 text-right text-rose-600 font-medium">
                    {{ c.insufficient }}
                  </td>
                  <td class="px-4 py-3.5 text-right text-gray-500">{{ c.student_count }}</td>
                  <td class="px-6 py-3.5 text-right font-medium text-emerald-600">
                    {{ c.signed_off_rate_display }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Flow stats -->
        <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div class="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
            <div class="w-2 h-2 rounded-full bg-violet-500"></div>
            <h2 class="text-sm font-bold text-gray-900 uppercase tracking-wide">Flow Statistics</h2>
            <span
              v-if="data?.flow_stats?.length"
              class="ml-auto text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-medium"
            >
              {{ data.flow_stats.length }} {{ data.flow_stats.length === 1 ? 'flow' : 'flows' }}
            </span>
          </div>
          <div v-if="!data?.flow_stats?.length" class="px-6 py-10 text-center text-sm text-gray-400">
            No flow sign-off data in scope.
          </div>
          <div v-else class="overflow-x-auto">
            <table class="min-w-full text-sm">
              <thead class="bg-gray-50">
                <tr class="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  <th class="text-left px-6 py-3">Course</th>
                  <th class="text-left px-4 py-3">Flow</th>
                  <th class="text-right px-4 py-3">Points</th>
                  <th class="text-right px-4 py-3">Total</th>
                  <th class="text-right px-4 py-3">Signed off</th>
                  <th class="text-right px-4 py-3">Insufficient</th>
                  <th class="text-right px-4 py-3">Students</th>
                  <th class="text-right px-6 py-3">Pass %</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100">
                <tr v-for="f in data.flow_stats" :key="f.flow_id" class="hover:bg-gray-50 transition-colors">
                  <td class="px-6 py-3.5 text-gray-500 text-xs">{{ f.course_name }}</td>
                  <td class="px-4 py-3.5 font-semibold text-gray-900">{{ f.flow_name }}</td>
                  <td class="px-4 py-3.5 text-right text-gray-500">{{ f.point_count }}</td>
                  <td class="px-4 py-3.5 text-right font-bold text-blue-600">{{ f.total }}</td>
                  <td class="px-4 py-3.5 text-right text-emerald-600 font-medium">
                    {{ f.signed_off }}
                  </td>
                  <td class="px-4 py-3.5 text-right text-rose-600 font-medium">
                    {{ f.insufficient }}
                  </td>
                  <td class="px-4 py-3.5 text-right text-gray-500">{{ f.student_count }}</td>
                  <td class="px-6 py-3.5 text-right font-medium text-emerald-600">
                    {{ f.signed_off_rate_display }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Assignment stats -->
        <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div class="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
            <div class="w-2 h-2 rounded-full bg-sky-500"></div>
            <h2 class="text-sm font-bold text-gray-900 uppercase tracking-wide">
              Assignment Statistics (Question Sign-off)
            </h2>
            <span
              v-if="data?.assignment_stats?.length"
              class="ml-auto text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-medium"
            >
              {{ data.assignment_stats.length }}
              {{ data.assignment_stats.length === 1 ? 'assignment' : 'assignments' }}
            </span>
          </div>
          <div v-if="!data?.assignment_stats?.length" class="px-6 py-10 text-center text-sm text-gray-400">
            No question-based sign-off assignments in scope.
          </div>
          <div v-else class="overflow-x-auto">
            <table class="min-w-full text-sm">
              <thead class="bg-gray-50">
                <tr class="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  <th class="text-left px-6 py-3">Course</th>
                  <th class="text-left px-4 py-3">Assignment</th>
                  <th class="text-right px-4 py-3">Total</th>
                  <th class="text-right px-4 py-3">Signed off</th>
                  <th class="text-right px-4 py-3">Insufficient</th>
                  <th class="text-right px-4 py-3">Students</th>
                  <th class="text-right px-6 py-3">Pass %</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100">
                <tr
                  v-for="a in data.assignment_stats"
                  :key="a.assignment_id"
                  class="hover:bg-gray-50 transition-colors"
                >
                  <td class="px-6 py-3.5 text-gray-500 text-xs">{{ a.course_name }}</td>
                  <td class="px-4 py-3.5 font-semibold text-gray-900">{{ a.assignment_name }}</td>
                  <td class="px-4 py-3.5 text-right font-bold text-blue-600">{{ a.total }}</td>
                  <td class="px-4 py-3.5 text-right text-emerald-600 font-medium">
                    {{ a.signed_off }}
                  </td>
                  <td class="px-4 py-3.5 text-right text-rose-600 font-medium">
                    {{ a.insufficient }}
                  </td>
                  <td class="px-4 py-3.5 text-right text-gray-500">{{ a.student_count }}</td>
                  <td class="px-6 py-3.5 text-right font-medium text-emerald-600">
                    {{ a.signed_off_rate_display }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- TA performance -->
        <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div class="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
            <div class="w-2 h-2 rounded-full bg-indigo-500"></div>
            <h2 class="text-sm font-bold text-gray-900 uppercase tracking-wide">TA Sign-off Performance</h2>
            <span
              v-if="data?.grader_stats?.length"
              class="ml-auto text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-medium"
            >
              {{ data.grader_stats.length }} {{ data.grader_stats.length === 1 ? 'TA' : 'TAs' }}
            </span>
          </div>
          <div v-if="!data?.grader_stats?.length" class="px-6 py-10 text-center text-sm text-gray-400">
            No TA sign-off activity in scope.
          </div>
          <div v-else class="overflow-x-auto">
            <table class="min-w-full text-sm">
              <thead class="bg-gray-50">
                <tr class="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  <th class="text-left px-6 py-3">TA</th>
                  <th class="text-right px-4 py-3">Total</th>
                  <th class="text-right px-4 py-3">Signed off</th>
                  <th class="text-right px-4 py-3">Insufficient</th>
                  <th class="text-right px-4 py-3">Students</th>
                  <th class="text-right px-6 py-3">Pass %</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100">
                <tr v-for="ta in data.grader_stats" :key="ta.grader_id" class="hover:bg-gray-50 transition-colors">
                  <td class="px-6 py-3.5">
                    <div class="flex items-center gap-2.5">
                      <div
                        class="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-400 to-violet-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
                      >
                        {{ ta.grader_name?.charAt(0)?.toUpperCase() ?? '?' }}
                      </div>
                      <span class="font-semibold text-gray-900">{{ ta.grader_name }}</span>
                    </div>
                  </td>
                  <td class="px-4 py-3.5 text-right font-bold text-blue-600">{{ ta.total }}</td>
                  <td class="px-4 py-3.5 text-right text-emerald-600 font-medium">
                    {{ ta.signed_off }}
                  </td>
                  <td class="px-4 py-3.5 text-right text-rose-600 font-medium">
                    {{ ta.insufficient }}
                  </td>
                  <td class="px-4 py-3.5 text-right text-gray-500">{{ ta.student_count }}</td>
                  <td class="px-6 py-3.5 text-right font-medium text-emerald-600">
                    {{ ta.signed_off_rate_display }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Stuck points -->
        <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div class="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
            <div class="w-2 h-2 rounded-full bg-rose-500"></div>
            <h2 class="text-sm font-bold text-gray-900 uppercase tracking-wide">Stuck Points</h2>
            <span
              v-if="data?.stuck_points?.length"
              class="ml-auto text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-medium"
            >
              Top {{ data.stuck_points.length }}
            </span>
          </div>
          <div v-if="!data?.stuck_points?.length" class="px-6 py-10 text-center text-sm text-gray-400">
            No insufficient sign-offs in scope — nothing is stuck.
          </div>
          <div v-else class="divide-y divide-gray-100">
            <div
              v-for="(p, idx) in data.stuck_points"
              :key="idx"
              class="px-6 py-4 flex items-start gap-4 hover:bg-gray-50 transition-colors"
            >
              <div
                class="w-7 h-7 rounded-full bg-rose-50 text-rose-600 border border-rose-200 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5"
              >
                {{ idx + 1 }}
              </div>
              <div class="flex-1 min-w-0">
                <div class="font-semibold text-gray-900 text-sm">
                  {{ p.label }}
                  <span class="text-gray-400 font-normal mx-1">·</span>
                  {{ p.context }}
                </div>
                <div class="flex items-center gap-2 mt-1">
                  <span class="text-xs text-gray-400">{{ p.course_name }}</span>
                  <span class="text-gray-300">·</span>
                  <span class="text-xs text-gray-400">{{ p.scope }}</span>
                  <span class="text-gray-300">·</span>
                  <span class="text-xs text-gray-400">{{ p.student_count }} students</span>
                </div>
              </div>
              <div class="text-right flex-shrink-0">
                <div class="text-lg font-extrabold text-rose-600">
                  {{ p.insufficient_rate_display }}
                </div>
                <div class="text-xs text-gray-400">{{ p.insufficient }} / {{ p.total }} insufficient</div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
