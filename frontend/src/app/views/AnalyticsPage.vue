<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { analyticsApi } from '../api'
import SignoffAnalyticsPage from './SignoffAnalyticsPage.vue'

type AnalyticsView = 'requests' | 'signoff'
const view = ref<AnalyticsView>('requests')

const data = ref<any>(null)
const loading = ref(true)
const error = ref<string | null>(null)

const filters = ref({
  course_id: undefined as number | undefined,
  assignment_id: undefined as number | undefined,
  start_date: '',
  end_date: '',
})

async function loadAnalytics() {
  loading.value = true
  error.value = null
  try {
    data.value = await analyticsApi.get({
      course_id: filters.value.course_id,
      assignment_id: filters.value.assignment_id,
      start_date: filters.value.start_date || undefined,
      end_date: filters.value.end_date || undefined,
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load analytics'
  } finally {
    loading.value = false
  }
}

function onCourseChange(e: Event) {
  const val = Number((e.target as HTMLSelectElement).value)
  filters.value.course_id = val || undefined
  filters.value.assignment_id = undefined
  loadAnalytics()
}

function onAssignmentChange(e: Event) {
  const val = Number((e.target as HTMLSelectElement).value)
  filters.value.assignment_id = val || undefined
  loadAnalytics()
}

function clearFilters() {
  filters.value = { course_id: undefined, assignment_id: undefined, start_date: '', end_date: '' }
  loadAnalytics()
}

onMounted(loadAnalytics)

const s = () => data.value?.summary ?? {}
const hasFilters = () =>
  !!(filters.value.course_id || filters.value.assignment_id || filters.value.start_date || filters.value.end_date)
const exportUrl = computed(() => {
  const qs = new URLSearchParams()
  if (filters.value.course_id) qs.set('course_id', String(filters.value.course_id))
  if (filters.value.assignment_id) qs.set('assignment_id', String(filters.value.assignment_id))
  if (filters.value.start_date) qs.set('start_date', filters.value.start_date)
  if (filters.value.end_date) qs.set('end_date', filters.value.end_date)
  const query = qs.toString()
  return `/api/analytics/export.csv${query ? `?${query}` : ''}`
})
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- View toggle (Requests vs Sign-offs) -->
    <div class="bg-white border-b border-gray-200 px-4 sm:px-6 lg:px-8 pt-4 pb-3">
      <div class="max-w-7xl mx-auto">
        <div class="inline-flex bg-gray-100 rounded-lg p-1">
          <button
            type="button"
            :class="[
              'px-4 py-1.5 text-sm font-medium rounded-md transition-colors',
              view === 'requests' ? 'bg-white shadow-sm text-blue-600' : 'text-gray-600 hover:text-gray-900',
            ]"
            @click="view = 'requests'"
          >
            Requests
          </button>
          <button
            type="button"
            :class="[
              'px-4 py-1.5 text-sm font-medium rounded-md transition-colors',
              view === 'signoff' ? 'bg-white shadow-sm text-blue-600' : 'text-gray-600 hover:text-gray-900',
            ]"
            @click="view = 'signoff'"
          >
            Sign-offs
          </button>
        </div>
      </div>
    </div>

    <SignoffAnalyticsPage v-if="view === 'signoff'" />

    <template v-else>
      <!-- Page header -->
      <div class="bg-white border-b border-gray-200 px-4 sm:px-6 lg:px-8 py-6">
        <div class="max-w-7xl mx-auto flex items-end justify-between flex-wrap gap-4">
          <div>
            <h1 class="text-2xl font-bold text-gray-900 tracking-tight">Analytics</h1>
            <p class="text-sm text-gray-500 mt-0.5">Performance metrics and request insights</p>
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
            <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Assignment</label>
            <select
              :value="filters.assignment_id ?? ''"
              class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition min-w-[200px]"
              @change="onAssignmentChange"
            >
              <option value="">All assignments</option>
              <option v-for="a in data?.filters?.assignments ?? []" :key="a.id" :value="a.id">
                {{ a.course_name }} – {{ a.name }}
              </option>
            </select>
          </div>

          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">From</label>
            <input
              v-model="filters.start_date"
              type="date"
              class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
              @change="loadAnalytics"
            />
          </div>

          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">To</label>
            <input
              v-model="filters.end_date"
              type="date"
              class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
              @change="loadAnalytics"
            />
          </div>
        </div>

        <!-- Loading / Error -->
        <div v-if="loading" class="flex items-center gap-3 text-gray-500 text-sm py-8">
          <span
            class="inline-block w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"
          ></span>
          Loading analytics…
        </div>
        <div v-else-if="error" class="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl text-sm">
          {{ error }}
        </div>

        <template v-else>
          <!-- KPI grid -->
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <!-- Total requests -->
            <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5 border-t-4 border-t-blue-500">
              <div class="text-3xl font-extrabold text-blue-600">{{ s().total_requests ?? 0 }}</div>
              <div class="text-sm font-medium text-gray-700 mt-1">Total Requests</div>
              <div class="text-xs text-gray-400 mt-0.5">{{ s().student_count ?? 0 }} students</div>
            </div>

            <!-- Resolution rate -->
            <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5 border-t-4 border-t-emerald-500">
              <div class="text-3xl font-extrabold text-emerald-600">
                {{ s().closed_rate_display ?? '0%' }}
              </div>
              <div class="text-sm font-medium text-gray-700 mt-1">Resolution Rate</div>
              <div class="text-xs text-gray-400 mt-0.5">{{ s().closed_requests ?? 0 }} closed</div>
            </div>

            <!-- Avg resolution -->
            <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5 border-t-4 border-t-violet-500">
              <div class="text-3xl font-extrabold text-violet-600">
                {{ s().avg_resolution_display ?? '—' }}
              </div>
              <div class="text-sm font-medium text-gray-700 mt-1">Avg Resolution</div>
              <div class="text-xs text-gray-400 mt-0.5">
                <template v-if="s().avg_resolution_display">Creation → resolved</template>
                <template v-else>No resolved requests yet</template>
              </div>
            </div>

            <!-- Avg queue wait -->
            <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5 border-t-4 border-t-sky-500">
              <div class="text-3xl font-extrabold text-sky-600">
                {{ s().avg_queue_wait_display ?? '—' }}
              </div>
              <div class="text-sm font-medium text-gray-700 mt-1">Avg Queue Wait</div>
              <div class="text-xs text-gray-400 mt-0.5">
                <template v-if="s().avg_queue_wait_display">Join → claimed</template>
                <template v-else>No claimed requests yet</template>
              </div>
            </div>

            <!-- Avg time to AI -->
            <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5 border-t-4 border-t-amber-500">
              <div class="text-3xl font-extrabold text-amber-600">
                {{ s().avg_time_to_ai_display ?? '—' }}
              </div>
              <div class="text-sm font-medium text-gray-700 mt-1">Avg Time to AI</div>
              <div class="text-xs text-gray-400 mt-0.5">
                <template v-if="s().avg_time_to_ai_display">Submit → AI ready</template>
                <template v-else>No AI feedback recorded yet</template>
              </div>
            </div>

            <!-- AI approval rate -->
            <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5 border-t-4 border-t-indigo-500">
              <div class="text-3xl font-extrabold text-indigo-600">
                {{ s().ai_approval_rate_display ?? '0%' }}
              </div>
              <div class="text-sm font-medium text-gray-700 mt-1">AI Approval Rate</div>
              <div class="text-xs text-gray-400 mt-0.5">
                {{ s().approved_count ?? 0 }} approved · {{ s().edited_count ?? 0 }} edited
              </div>
            </div>

            <!-- Avg session -->
            <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5 border-t-4 border-t-orange-500">
              <div class="text-3xl font-extrabold text-orange-600">
                {{ s().avg_session_duration_display ?? '—' }}
              </div>
              <div class="text-sm font-medium text-gray-700 mt-1">Avg Session</div>
              <div class="text-xs text-gray-400 mt-0.5">
                <template v-if="s().avg_session_duration_display">
                  {{ s().completed_session_count ?? 0 }}/{{ s().session_count ?? 0 }} sessions
                </template>
                <template v-else>No completed sessions yet</template>
              </div>
            </div>

            <!-- Fast approvals -->
            <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5 border-t-4 border-t-rose-500">
              <div class="text-3xl font-extrabold text-rose-600">
                {{ s().fast_approvals_count ?? 0 }}
              </div>
              <div class="text-sm font-medium text-gray-700 mt-1">Fast Approvals</div>
              <div class="text-xs text-gray-400 mt-0.5">
                {{ s().fast_approval_rate_display ?? '0%' }} under {{ s().fast_approval_threshold_minutes ?? 2 }}min
              </div>
            </div>
          </div>

          <!-- Status breakdown + Risk signals -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <!-- Status breakdown -->
            <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
              <div class="flex items-center gap-2 mb-5">
                <div class="w-2 h-2 rounded-full bg-blue-500"></div>
                <h2 class="text-sm font-bold text-gray-900 uppercase tracking-wide">Status Breakdown</h2>
                <span class="ml-auto text-xs text-gray-400">{{ s().total_requests ?? 0 }} total</span>
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

            <!-- Risk signals -->
            <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
              <div class="flex items-center gap-2 mb-5">
                <div class="w-2 h-2 rounded-full bg-amber-500"></div>
                <h2 class="text-sm font-bold text-gray-900 uppercase tracking-wide">Risk Signals</h2>
              </div>
              <div class="space-y-4">
                <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div>
                    <p class="text-sm font-semibold text-gray-800">Edited after AI</p>
                    <p class="text-xs text-gray-400 mt-0.5">Requests where TA edited AI feedback</p>
                  </div>
                  <div class="text-right">
                    <div class="text-xl font-extrabold text-violet-600">
                      {{ s().edited_count ?? 0 }}
                    </div>
                    <div class="text-xs text-gray-400">{{ s().edit_rate_display ?? '0%' }}</div>
                  </div>
                </div>
                <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div>
                    <p class="text-sm font-semibold text-gray-800">Avg AI review time</p>
                    <p class="text-xs text-gray-400 mt-0.5">AI generation to TA decision</p>
                  </div>
                  <div class="text-xl font-extrabold text-amber-600">
                    {{ s().avg_ai_review_display ?? '—' }}
                  </div>
                </div>
                <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div>
                    <p class="text-sm font-semibold text-gray-800">Team coverage</p>
                    <p class="text-xs text-gray-400 mt-0.5">TAs active in this scope</p>
                  </div>
                  <div class="text-xl font-extrabold text-blue-600">{{ s().ta_count ?? 0 }}</div>
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
              No course analytics available for the selected filters.
            </div>
            <div v-else class="overflow-x-auto">
              <table class="min-w-full text-sm">
                <thead class="bg-gray-50">
                  <tr class="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    <th class="text-left px-6 py-3">Course</th>
                    <th class="text-right px-4 py-3">Total</th>
                    <th class="text-right px-4 py-3">Closed</th>
                    <th class="text-right px-4 py-3">Open</th>
                    <th class="text-right px-4 py-3">Avg Resolution</th>
                    <th class="text-right px-4 py-3">Avg Wait</th>
                    <th class="text-right px-6 py-3">AI Approval</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                  <tr v-for="c in data.course_stats" :key="c.course_id" class="hover:bg-gray-50 transition-colors">
                    <td class="px-6 py-3.5 font-semibold text-gray-900">{{ c.course_name }}</td>
                    <td class="px-4 py-3.5 text-right font-bold text-blue-600">
                      {{ c.total_requests }}
                    </td>
                    <td class="px-4 py-3.5 text-right text-emerald-600 font-medium">
                      {{ c.closed_requests }}
                    </td>
                    <td class="px-4 py-3.5 text-right text-amber-600 font-medium">
                      {{ c.open_requests }}
                    </td>
                    <td class="px-4 py-3.5 text-right text-gray-500">
                      {{ c.avg_resolution_display }}
                    </td>
                    <td class="px-4 py-3.5 text-right text-gray-500">
                      {{ c.avg_queue_wait_display }}
                    </td>
                    <td class="px-6 py-3.5 text-right font-medium text-indigo-600">
                      {{ c.ai_approval_rate_display }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Assignment stats -->
          <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div class="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
              <div class="w-2 h-2 rounded-full bg-violet-500"></div>
              <h2 class="text-sm font-bold text-gray-900 uppercase tracking-wide">Assignment Statistics</h2>
              <span
                v-if="data?.assignment_stats?.length"
                class="ml-auto text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-medium"
              >
                {{ data.assignment_stats.length }}
                {{ data.assignment_stats.length === 1 ? 'assignment' : 'assignments' }}
              </span>
            </div>
            <div v-if="!data?.assignment_stats?.length" class="px-6 py-10 text-center text-sm text-gray-400">
              No assignment analytics available for the selected filters.
            </div>
            <div v-else class="overflow-x-auto">
              <table class="min-w-full text-sm">
                <thead class="bg-gray-50">
                  <tr class="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    <th class="text-left px-6 py-3">Course</th>
                    <th class="text-left px-4 py-3">Assignment</th>
                    <th class="text-right px-4 py-3">Total</th>
                    <th class="text-right px-4 py-3">Closed</th>
                    <th class="text-right px-4 py-3">Avg Resolution</th>
                    <th class="text-right px-4 py-3">Avg Wait</th>
                    <th class="text-right px-6 py-3">Avg to AI</th>
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
                    <td class="px-4 py-3.5 text-right font-bold text-blue-600">
                      {{ a.total_requests }}
                    </td>
                    <td class="px-4 py-3.5 text-right text-emerald-600 font-medium">
                      {{ a.closed_requests }}
                    </td>
                    <td class="px-4 py-3.5 text-right text-gray-500">
                      {{ a.avg_resolution_display }}
                    </td>
                    <td class="px-4 py-3.5 text-right text-gray-500">
                      {{ a.avg_queue_wait_display }}
                    </td>
                    <td class="px-6 py-3.5 text-right text-gray-500">
                      {{ a.avg_time_to_ai_display }}
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
              <h2 class="text-sm font-bold text-gray-900 uppercase tracking-wide">TA Performance</h2>
              <span
                v-if="data?.ta_stats?.length"
                class="ml-auto text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-medium"
              >
                {{ data.ta_stats.length }} {{ data.ta_stats.length === 1 ? 'TA' : 'TAs' }}
              </span>
            </div>
            <div v-if="!data?.ta_stats?.length" class="px-6 py-10 text-center text-sm text-gray-400">
              No TA assignments found for this filter scope.
            </div>
            <div v-else class="overflow-x-auto">
              <table class="min-w-full text-sm">
                <thead class="bg-gray-50">
                  <tr class="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    <th class="text-left px-6 py-3">TA</th>
                    <th class="text-right px-4 py-3">Handled</th>
                    <th class="text-right px-4 py-3">Approved</th>
                    <th class="text-right px-4 py-3">Edited</th>
                    <th class="text-right px-4 py-3">In Person</th>
                    <th class="text-right px-4 py-3">Approve %</th>
                    <th class="text-right px-4 py-3">Avg Review</th>
                    <th class="text-right px-6 py-3">Fast</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                  <tr v-for="ta in data.ta_stats" :key="ta.ta_id" class="hover:bg-gray-50 transition-colors">
                    <td class="px-6 py-3.5">
                      <div class="flex items-center gap-2.5">
                        <div
                          class="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-400 to-violet-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
                        >
                          {{ ta.ta_name?.charAt(0)?.toUpperCase() ?? '?' }}
                        </div>
                        <span class="font-semibold text-gray-900">{{ ta.ta_name }}</span>
                      </div>
                    </td>
                    <td class="px-4 py-3.5 text-right font-bold text-blue-600">
                      {{ ta.total_requests }}
                    </td>
                    <td class="px-4 py-3.5 text-right text-emerald-600 font-medium">
                      {{ ta.approved_count }}
                    </td>
                    <td class="px-4 py-3.5 text-right text-violet-600 font-medium">
                      {{ ta.edited_count }}
                    </td>
                    <td class="px-4 py-3.5 text-right text-orange-600 font-medium">
                      {{ ta.in_person_count }}
                    </td>
                    <td class="px-4 py-3.5 text-right font-semibold text-indigo-600">
                      {{ ta.ai_approval_rate_display }}
                    </td>
                    <td class="px-4 py-3.5 text-right text-gray-500">
                      {{ ta.avg_ai_review_display }}
                    </td>
                    <td class="px-6 py-3.5 text-right text-rose-600 font-medium">
                      {{ ta.fast_approval_rate_display }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Common problems -->
          <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div class="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
              <div class="w-2 h-2 rounded-full bg-rose-500"></div>
              <h2 class="text-sm font-bold text-gray-900 uppercase tracking-wide">Common Problems</h2>
              <span
                v-if="data?.common_problems?.length"
                class="ml-auto text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-medium"
              >
                Top {{ data.common_problems.length }}
              </span>
            </div>
            <div v-if="!data?.common_problems?.length" class="px-6 py-10 text-center text-sm text-gray-400">
              No common-problem trends available yet.
            </div>
            <div v-else class="divide-y divide-gray-100">
              <div
                v-for="(problem, idx) in data.common_problems"
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
                    {{ problem.question_label }}
                    <span class="text-gray-400 font-normal mx-1">·</span>
                    {{ problem.assignment_name }}
                  </div>
                  <div class="text-xs text-gray-500 mt-0.5 truncate">
                    {{ problem.problem_summary }}
                  </div>
                  <div class="flex items-center gap-2 mt-1">
                    <span class="text-xs text-gray-400">{{ problem.course_name }}</span>
                    <span class="text-gray-300">·</span>
                    <span class="text-xs text-gray-400">Avg resolution: {{ problem.avg_resolution_display }}</span>
                  </div>
                </div>
                <div class="text-right flex-shrink-0">
                  <div class="text-lg font-extrabold text-rose-600">
                    {{ problem.request_count }}
                  </div>
                  <div class="text-xs text-gray-400">{{ problem.request_share_display }}</div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </template>
  </div>
</template>
