<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { api } from '../api/client'
import { Check, X, Search, ChevronLeft, Users, User } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const courseId = Number(route.params.courseId)
const canGrade = auth.user?.role === 'teacher' || auth.user?.role === 'ta'

// ─── Types ────────────────────────────────────────────────────────────────────

interface QuestionPoint {
  id: number
  label: string
}
interface Cell {
  status: 'signed_off' | 'insufficient' | null
  comment: string | null
}
interface StudentRow {
  id: number
  name: string
  email: string
  cells: Record<number, Cell>
}
interface HistoryRecord {
  id: number
  status: string
  comment: string | null
  graded_by: string
  created_at: string
}
interface PointDetail {
  id: number
  label: string
  latest_status: string | null
  history: HistoryRecord[]
}

interface SearchResult {
  type: 'student' | 'group'
  assignment_id: number
  assignment_name: string
  student_id?: number
  student_name?: string
  group_id?: number
  category_id?: number
  group_name?: string
  category_name?: string
  member_count?: number
  label: string
}

// ─── Search ───────────────────────────────────────────────────────────────────

const searchQuery = ref('')
const searchResults = ref<SearchResult[]>([])
const searchLoading = ref(false)
const searchError = ref<string | null>(null)
let searchTimer: ReturnType<typeof setTimeout> | null = null

async function doSearch() {
  searchLoading.value = true
  searchError.value = null
  try {
    const q = encodeURIComponent(searchQuery.value.trim())
    searchResults.value = await api.get<SearchResult[]>(`/course/${courseId}/signoff/q/search?q=${q}`)
  } catch (e: any) {
    searchError.value = e?.message ?? 'Search failed'
  } finally {
    searchLoading.value = false
  }
}

watch(searchQuery, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(doSearch, 250)
})

onMounted(async () => {
  await doSearch()
  // Auto-open if redirected from queue with studentId + assignmentId
  const qStudentId = route.query.studentId ? Number(route.query.studentId) : null
  const qAssignmentId = route.query.assignmentId ? Number(route.query.assignmentId) : null
  const qSubText = route.query.submissionText ? String(route.query.submissionText) : null
  const qGroupId = route.query.groupId ? Number(route.query.groupId) : null
  if (qAssignmentId) {
    let match: SearchResult | undefined
    if (qGroupId) {
      // Group sign-off: find by group_id + assignment_id
      match = searchResults.value.find(
        (r) => r.type === 'group' && r.group_id === qGroupId && r.assignment_id === qAssignmentId,
      )
    } else if (qStudentId) {
      // Individual sign-off: find by student_id + assignment_id
      match = searchResults.value.find(
        (r) => r.type === 'student' && r.student_id === qStudentId && r.assignment_id === qAssignmentId,
      )
    }
    // Last resort: group sign-off where we only have studentId — pick any group for this assignment
    // (the TA will see the right group since there's typically one group per student per category)
    if (!match && qStudentId && qAssignmentId) {
      match = searchResults.value.find((r) => r.type === 'group' && r.assignment_id === qAssignmentId)
    }
    if (match) {
      if (qSubText) queueSubmissionText.value = qSubText
      openResult(match)
      router.replace({ query: {} })
    }
  }
})

// ─── Submission text from queue (passed via query param on TA redirect) ───────
const queueSubmissionText = ref<string | null>(null)

// ─── Grid state ───────────────────────────────────────────────────────────────

const selected = ref<SearchResult | null>(null)
const gridQuestions = ref<QuestionPoint[]>([])
const gridStudents = ref<StudentRow[]>([])
const gridAssignment = ref<{ id: number; name: string } | null>(null)
const gridLoading = ref(false)
const gridError = ref<string | null>(null)

// Full per-student history, keyed by student id then question id
const allHistory = ref<Record<number, PointDetail[]>>({})

async function openResult(result: SearchResult) {
  selected.value = result
  historyStudent.value = null
  historyQuestion.value = null
  gridLoading.value = true
  gridError.value = null
  gridStudents.value = []
  gridQuestions.value = []
  gridAssignment.value = null
  allHistory.value = {}

  try {
    if (result.type === 'student') {
      const data = await api.get<{
        assignment: any
        questions: QuestionPoint[]
        points: PointDetail[]
      }>(`/course/${courseId}/signoff/q/student/${result.student_id}?assignment_id=${result.assignment_id}`)
      gridAssignment.value = data.assignment
      gridQuestions.value = data.questions
      const cells: Record<number, Cell> = {}
      for (const p of data.points) {
        cells[p.id] = {
          status: p.latest_status as Cell['status'],
          comment: p.history[0]?.comment ?? null,
        }
      }
      gridStudents.value = [{ id: result.student_id!, name: result.student_name!, email: '', cells }]
      allHistory.value[result.student_id!] = data.points
    } else {
      // group — load signoff questions + group members in parallel
      const [data, groupData] = await Promise.all([
        api.get<{ assignment: any; questions: QuestionPoint[]; students: StudentRow[] }>(
          `/course/${courseId}/signoff/q/students?assignment_id=${result.assignment_id}`,
        ),
        api.get<{ members: Array<{ id: number; name: string; email: string }> }>(
          `/course/${courseId}/group-categories/${result.category_id}/groups/${result.group_id}/members`,
        ),
      ])
      gridAssignment.value = data.assignment
      gridQuestions.value = data.questions
      const memberIds = new Set(groupData.members.map((m) => m.id))
      gridStudents.value = data.students.filter((s) => memberIds.has(s.id))

      // Load per-student history for every group member
      await Promise.all(
        gridStudents.value.map(async (s) => {
          const d = await api.get<{ points: PointDetail[] }>(
            `/course/${courseId}/signoff/q/student/${s.id}?assignment_id=${result.assignment_id}`,
          )
          allHistory.value[s.id] = d.points
        }),
      )
    }
  } catch (e: any) {
    gridError.value = e?.message ?? 'Failed to load'
  } finally {
    gridLoading.value = false
  }
}

function backToSearch() {
  selected.value = null
  historyStudent.value = null
  historyQuestion.value = null
  gridAssignment.value = null
  gridQuestions.value = []
  gridStudents.value = []
  allHistory.value = {}
  queueSubmissionText.value = null
}

// ─── History panel ────────────────────────────────────────────────────────────

const historyStudent = ref<StudentRow | null>(null)
const historyQuestion = ref<QuestionPoint | null>(null)

interface FlatRecord extends HistoryRecord {
  questionLabel: string
  studentName: string
}

function allHistoryRecords(): FlatRecord[] {
  const flat: FlatRecord[] = []
  for (const student of gridStudents.value) {
    const points = allHistory.value[student.id] ?? []
    for (const point of points) {
      for (const rec of point.history) {
        flat.push({ ...rec, questionLabel: point.label, studentName: student.name })
      }
    }
  }
  flat.sort((a, b) => b.created_at.localeCompare(a.created_at))
  return flat
}

function selectCell(student: StudentRow, question: QuestionPoint) {
  historyStudent.value = student
  historyQuestion.value = question
  if (canGrade) openGrade(student, question)
}

// ─── Sign off all students for a question ────────────────────────────────────

const signAllBusy = ref<number | null>(null) // question id currently being bulk-signed

async function signOffAll(question: QuestionPoint) {
  if (!selected.value || !canGrade) return
  signAllBusy.value = question.id
  try {
    await Promise.all(
      gridStudents.value.map((student) =>
        api.post(`/signoff/questions/${question.id}/grade`, {
          student_id: student.id,
          status: 'signed_off',
          comment: null,
        }),
      ),
    )
    // Refresh all students' data
    await Promise.all(
      gridStudents.value.map(async (student) => {
        const d = await api.get<{ questions: QuestionPoint[]; points: PointDetail[] }>(
          `/course/${courseId}/signoff/q/student/${student.id}?assignment_id=${selected.value!.assignment_id}`,
        )
        allHistory.value[student.id] = d.points
        for (const p of d.points) {
          student.cells[p.id] = {
            status: p.latest_status as Cell['status'],
            comment: p.history[0]?.comment ?? null,
          }
        }
      }),
    )
  } catch (e: any) {
    gridError.value = e?.message ?? 'Failed to sign off all'
  } finally {
    signAllBusy.value = null
  }
}

// ─── Grade modal ──────────────────────────────────────────────────────────────

const gradeModal = ref<{ student: StudentRow; point: QuestionPoint } | null>(null)
const gradeStatus = ref<'signed_off' | 'insufficient'>('signed_off')
const gradeComment = ref('')
const gradeBusy = ref(false)
const gradeError = ref<string | null>(null)

function openGrade(student: StudentRow, point: QuestionPoint) {
  gradeModal.value = { student, point }
  gradeStatus.value = 'signed_off'
  gradeComment.value = ''
  gradeError.value = null
}

async function submitGrade() {
  if (!gradeModal.value || !selected.value) return
  gradeBusy.value = true
  gradeError.value = null
  try {
    await api.post(`/signoff/questions/${gradeModal.value.point.id}/grade`, {
      student_id: gradeModal.value.student.id,
      status: gradeStatus.value,
      comment: gradeComment.value.trim() || null,
    })
    const sid = gradeModal.value.student.id
    gradeModal.value = null
    // Refresh this student's data
    const d = await api.get<{ questions: QuestionPoint[]; points: PointDetail[] }>(
      `/course/${courseId}/signoff/q/student/${sid}?assignment_id=${selected.value.assignment_id}`,
    )
    allHistory.value[sid] = d.points
    // Update cells in gridStudents
    const student = gridStudents.value.find((s) => s.id === sid)
    if (student) {
      for (const p of d.points) {
        student.cells[p.id] = {
          status: p.latest_status as Cell['status'],
          comment: p.history[0]?.comment ?? null,
        }
      }
    }
  } catch (e: any) {
    gradeError.value = e?.message ?? 'Failed to grade'
  } finally {
    gradeBusy.value = false
  }
}
</script>

<template>
  <div class="-mx-4 sm:-mx-6 lg:-mx-8 -mt-6 min-h-full bg-gray-50 flex flex-col">
    <!-- ── Header ──────────────────────────────────────────────────────────── -->
    <div class="px-4 sm:px-6 lg:px-8 pt-8 pb-4 flex-shrink-0">
      <button
        v-if="selected"
        class="text-sm text-blue-600 hover:underline mb-1 flex items-center gap-1"
        @click="backToSearch"
      >
        <ChevronLeft class="w-4 h-4" />
        Back to search
      </button>
      <h1 class="text-2xl font-bold text-gray-900">Sign-off</h1>
      <p v-if="selected" class="text-sm text-gray-500 mt-0.5">
        <span class="font-medium text-gray-700">{{ selected.assignment_name }}</span>
        —
        <span v-if="selected.type === 'student'">{{ selected.student_name }}</span>
        <span v-else class="inline-flex items-center gap-1">
          <Users class="w-3.5 h-3.5" />
          {{ selected.group_name }}
        </span>
      </p>
    </div>

    <!-- ── Search view ─────────────────────────────────────────────────────── -->
    <template v-if="!selected">
      <div class="px-4 sm:px-6 lg:px-8 pb-4">
        <div class="relative max-w-xl">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            v-model="searchQuery"
            placeholder="Search by lab, student name, email or group…"
            class="w-full pl-9 pr-4 py-2.5 border border-gray-300 rounded-xl text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            autofocus
          />
        </div>
        <div v-if="searchError" class="mt-3 text-sm text-red-600">{{ searchError }}</div>
      </div>

      <div class="flex-1 px-4 sm:px-6 lg:px-8 pb-8">
        <div v-if="searchLoading" class="text-sm text-gray-400">Searching…</div>
        <div v-else-if="searchResults.length === 0 && !searchLoading" class="text-sm text-gray-400">
          {{ searchQuery.trim() ? 'No results.' : 'No sign-off labs configured yet.' }}
        </div>
        <div v-else class="space-y-1 max-w-xl">
          <button
            v-for="result in searchResults"
            :key="`${result.type}-${result.assignment_id}-${result.student_id ?? result.group_id}`"
            class="w-full text-left flex items-center gap-3 px-4 py-3 bg-white border border-gray-200 rounded-xl shadow-sm hover:border-blue-300 hover:bg-blue-50/40 transition-colors"
            @click="openResult(result)"
          >
            <div
              :class="[
                'w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-semibold flex-shrink-0',
                result.type === 'student' ? 'bg-blue-500' : 'bg-purple-500',
              ]"
            >
              <User v-if="result.type === 'student'" class="w-4 h-4" />
              <Users v-else class="w-4 h-4" />
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium text-gray-900 truncate">{{ result.label }}</p>
              <p class="text-xs text-gray-400 mt-0.5">
                <span v-if="result.type === 'student'">Individual</span>
                <span v-else>
                  {{ result.category_name }} · {{ result.member_count }} member{{
                    result.member_count === 1 ? '' : 's'
                  }}
                </span>
              </p>
            </div>
          </button>
        </div>
      </div>
    </template>

    <!-- ── Grid + History view ─────────────────────────────────────────────── -->
    <template v-else>
      <div
        v-if="gridError"
        class="mx-4 sm:mx-6 lg:mx-8 mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700"
      >
        {{ gridError }}
      </div>

      <div v-if="gridLoading" class="flex-1 flex items-center justify-center text-sm text-gray-400">Loading…</div>

      <div v-else-if="gridQuestions.length === 0" class="flex-1 flex items-center justify-center text-sm text-gray-400">
        No sign-off questions defined for this lab yet.
      </div>

      <!-- Two-column: grid left, history right -->
      <div v-else class="flex flex-col gap-4 px-4 sm:px-6 lg:px-8 pb-8">
        <!-- Submission from queue (shown when TA was redirected here) -->
        <div v-if="queueSubmissionText" class="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3">
          <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">Student's Submitted Answer</p>
          <pre class="text-sm text-gray-800 whitespace-pre-wrap font-mono leading-relaxed">{{
            queueSubmissionText
          }}</pre>
        </div>

        <div class="flex gap-6">
          <!-- ── Exercise grid (rows = questions, columns = students) ── -->
          <div class="flex-1 overflow-auto border border-gray-200 rounded-xl bg-white self-start">
            <table class="text-sm border-collapse w-full" style="min-width: max-content">
              <thead class="sticky top-0 z-10">
                <tr class="bg-gray-50 border-b border-gray-200">
                  <!-- Exercise label column -->
                  <th
                    class="sticky left-0 z-20 bg-gray-50 px-4 py-3 text-left font-medium text-gray-600 min-w-[120px] border-r border-gray-200 whitespace-nowrap"
                  >
                    Exercise
                  </th>
                  <!-- One column per student -->
                  <th
                    v-for="student in gridStudents"
                    :key="student.id"
                    class="px-4 py-3 text-center text-xs font-semibold text-gray-600 min-w-[120px] border-r border-gray-100 last:border-r-0 whitespace-nowrap"
                  >
                    <div class="flex flex-col items-center gap-0.5">
                      <span class="font-medium text-gray-800">{{ student.name.split(' ')[0] }}</span>
                      <span class="text-[10px] text-gray-400 font-normal">
                        {{ student.name.split(' ').slice(1).join(' ') }}
                      </span>
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="q in gridQuestions" :key="q.id" class="border-b border-gray-100 last:border-b-0 bg-white">
                  <!-- Exercise label — click to sign off all students -->
                  <td
                    :class="[
                      'sticky left-0 bg-white px-4 border-r border-gray-200 font-mono text-xs font-semibold text-gray-700 whitespace-nowrap h-12',
                      canGrade ? 'cursor-pointer hover:bg-emerald-50 select-none' : '',
                    ]"
                    :title="canGrade ? 'Sign off all students for this exercise' : ''"
                    @click="canGrade && signOffAll(q)"
                  >
                    <div class="flex items-center gap-1.5">
                      <span>{{ q.label }}</span>
                      <span v-if="signAllBusy === q.id" class="text-[10px] text-emerald-600 font-normal animate-pulse">
                        signing…
                      </span>
                    </div>
                  </td>
                  <!-- One cell per student -->
                  <td
                    v-for="student in gridStudents"
                    :key="student.id"
                    :class="[
                      'px-4 text-center border-r border-gray-100 last:border-r-0 cursor-pointer transition-colors h-12',
                      historyStudent?.id === student.id && historyQuestion?.id === q.id
                        ? 'ring-2 ring-inset ring-blue-400'
                        : '',
                      student.cells[q.id]?.status === 'signed_off'
                        ? 'bg-emerald-50 hover:bg-emerald-100'
                        : student.cells[q.id]?.status === 'insufficient'
                          ? 'bg-amber-50 hover:bg-amber-100'
                          : 'hover:bg-gray-50',
                    ]"
                    @click="selectCell(student, q)"
                  >
                    <div class="flex items-center justify-center">
                      <Check v-if="student.cells[q.id]?.status === 'signed_off'" class="w-4 h-4 text-emerald-600" />
                      <X v-else-if="student.cells[q.id]?.status === 'insufficient'" class="w-4 h-4 text-amber-500" />
                      <span v-else class="w-4 h-4 block rounded-full border-2 border-gray-200" />
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- ── History panel ─────────────────────────────────────────── -->
          <div
            class="w-72 flex-shrink-0 border border-gray-200 rounded-xl bg-white flex flex-col self-start sticky top-0"
            style="max-height: calc(100vh - 10rem)"
          >
            <div class="px-4 py-3 border-b border-gray-100 flex-shrink-0">
              <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Sign-off History</p>
            </div>

            <div class="overflow-y-auto flex-1 min-h-0">
              <!-- Has history -->
              <template v-if="allHistoryRecords().length > 0">
                <div
                  v-for="rec in allHistoryRecords()"
                  :key="rec.id"
                  class="px-4 py-3 border-b border-gray-50 last:border-b-0"
                >
                  <div class="flex items-start justify-between gap-2 mb-0.5">
                    <div class="flex items-center gap-1.5 min-w-0">
                      <Check
                        v-if="rec.status === 'signed_off'"
                        class="w-3.5 h-3.5 text-emerald-500 flex-shrink-0 mt-px"
                      />
                      <X v-else class="w-3.5 h-3.5 text-amber-500 flex-shrink-0 mt-px" />
                      <span
                        :class="[
                          'text-xs font-semibold',
                          rec.status === 'signed_off' ? 'text-emerald-700' : 'text-amber-700',
                        ]"
                      >
                        {{ rec.status === 'signed_off' ? 'Signed off' : 'Insufficient' }}
                      </span>
                    </div>
                    <span class="text-[11px] text-gray-400 flex-shrink-0">{{ rec.created_at }}</span>
                  </div>
                  <p class="text-xs text-gray-600">
                    <span class="font-mono font-semibold">{{ rec.questionLabel }}</span>
                    <template v-if="gridStudents.length > 1">· {{ rec.studentName }}</template>
                  </p>
                  <p class="text-xs text-gray-500 mt-0.5">
                    by
                    <span class="font-medium text-gray-700">{{ rec.graded_by }}</span>
                  </p>
                  <p v-if="rec.comment" class="text-xs text-gray-600 mt-1 italic leading-relaxed">
                    {{ rec.comment }}
                  </p>
                </div>
              </template>

              <!-- No history yet -->
              <div v-else class="flex items-center justify-center h-32 text-xs text-gray-400 text-center px-4">
                No sign-off records yet
              </div>
            </div>
          </div>
        </div>
        <!-- end inner flex row -->
      </div>
      <!-- end outer flex col -->
    </template>
  </div>

  <!-- ── Grade Modal ───────────────────────────────────────────────────────── -->
  <Teleport to="body">
    <div
      v-if="gradeModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
      @mousedown.self="gradeModal = null"
    >
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-sm">
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <h2 class="text-base font-semibold text-gray-900">Grade: {{ gradeModal.point.label }}</h2>
            <p class="text-xs text-gray-500 mt-0.5">{{ gradeModal.student.name }}</p>
          </div>
          <button class="text-gray-400 hover:text-gray-600" @click="gradeModal = null">
            <X class="w-5 h-5" />
          </button>
        </div>
        <div class="px-6 py-5 space-y-4">
          <div v-if="gradeError" class="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-sm text-red-700">
            {{ gradeError }}
          </div>
          <div class="flex gap-3">
            <button
              :class="[
                'flex-1 flex items-center justify-center gap-2 py-3 rounded-xl border-2 font-medium text-sm transition-colors',
                gradeStatus === 'signed_off'
                  ? 'border-emerald-500 bg-emerald-50 text-emerald-700'
                  : 'border-gray-200 text-gray-500 hover:border-gray-300',
              ]"
              @click="gradeStatus = 'signed_off'"
            >
              <Check class="w-4 h-4" />
              Signed off
            </button>
            <button
              :class="[
                'flex-1 flex items-center justify-center gap-2 py-3 rounded-xl border-2 font-medium text-sm transition-colors',
                gradeStatus === 'insufficient'
                  ? 'border-amber-400 bg-amber-50 text-amber-700'
                  : 'border-gray-200 text-gray-500 hover:border-gray-300',
              ]"
              @click="gradeStatus = 'insufficient'"
            >
              <X class="w-4 h-4" />
              Insufficient
            </button>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">
              Comment
              <span class="text-gray-400 font-normal">(optional)</span>
            </label>
            <textarea
              v-model="gradeComment"
              rows="3"
              placeholder="Add feedback for the student…"
              class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-100 flex justify-end gap-3 bg-gray-50 rounded-b-2xl">
          <button
            class="px-4 py-2 text-sm font-medium rounded-lg text-gray-700 bg-white border border-gray-300 hover:bg-gray-50"
            @click="gradeModal = null"
          >
            Cancel
          </button>
          <button
            :disabled="gradeBusy"
            class="px-5 py-2 text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
            @click="submitGrade"
          >
            {{ gradeBusy ? 'Saving…' : 'Save' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
