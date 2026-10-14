<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client'
import { Plus, Trash2, ChevronDown, ChevronUp, Pencil, Check, X } from 'lucide-vue-next'
import { useUIStore } from '@/app/stores/ui'
const uiStore = useUIStore()

const route = useRoute()
const courseId = Number(route.params.courseId)

// ── Types ──────────────────────────────────────────────────────────────────────
type QuestionDraft = {
  label: string
  problem_description: string
  official_solution: string
  hinting_strategy: string
  require_signoff: boolean
}

type Question = {
  id: number
  question_number: number
  label: string | null
  problem_description: string
  official_solution: string | null
  hinting_strategy: string | null
  require_signoff: boolean
  editing: boolean
  draft: QuestionDraft
}

type Assignment = {
  id: number
  name: string
  description: string | null
  is_signoff: boolean
  signoff_group_category_id: number | null
  llm_config_id: number | null
  questions: Question[]
  expanded: boolean
  editingName: boolean
  nameDraft: string
  addingQuestion: boolean
  newQuestion: QuestionDraft
}

// ── State ──────────────────────────────────────────────────────────────────────
const courseName = ref('')
const assignments = ref<Assignment[]>([])
const tas = ref<{ id: number; name: string; email: string }[]>([])
const groupCategories = ref<{ id: number; name: string }[]>([])
const availableLlms = ref<{ id: number; name: string; model_name: string }[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const saving = ref(false)

// ── Sign-off picker modal ──────────────────────────────────────────────────────
const signoffModal = ref<Assignment | null>(null)
const signoffPick = ref<number | 'individual' | null>(null) // null = not chosen yet

function openSignoffModal(a: Assignment) {
  if (a.is_signoff) {
    // Already enabled — disable it
    setSignoff(a, false, null)
    return
  }
  signoffModal.value = a
  signoffPick.value = null
}

async function setSignoff(a: Assignment, enabled: boolean, categoryId: number | null) {
  saving.value = true
  try {
    await api.put(`/course/${courseId}/assignments/${a.id}`, {
      is_signoff: enabled,
      signoff_group_category_id: categoryId,
    })
    a.is_signoff = enabled
    a.signoff_group_category_id = categoryId
    signoffModal.value = null
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to update'
  } finally {
    saving.value = false
  }
}

function confirmSignoffPick() {
  if (!signoffModal.value || signoffPick.value === null) return
  const categoryId = signoffPick.value === 'individual' ? null : signoffPick.value
  setSignoff(signoffModal.value, true, categoryId)
}

// ── Question modal ─────────────────────────────────────────────────────────────
type ModalState = { assignment: Assignment; question: Question; editing: boolean }
const modal = ref<ModalState | null>(null)

function openQuestion(a: Assignment, q: Question) {
  modal.value = { assignment: a, question: q, editing: false }
}

function openQuestionEdit(a: Assignment, q: Question) {
  q.draft = {
    label: q.label ?? '',
    problem_description: q.problem_description,
    official_solution: q.official_solution ?? '',
    hinting_strategy: q.hinting_strategy ?? '',
    require_signoff: q.require_signoff,
  }
  modal.value = { assignment: a, question: q, editing: true }
}

function closeModal() {
  if (modal.value) {
    modal.value.question.editing = false
  }
  modal.value = null
}

function emptyDraft(): QuestionDraft {
  return {
    label: '',
    problem_description: '',
    official_solution: '',
    hinting_strategy: '',
    require_signoff: false,
  }
}

function makeQuestion(raw: any): Question {
  return reactive({
    id: raw.id,
    question_number: raw.question_number,
    label: raw.label ?? null,
    problem_description: raw.problem_description,
    official_solution: raw.official_solution ?? null,
    hinting_strategy: raw.hinting_strategy ?? null,
    require_signoff: raw.require_signoff ?? false,
    editing: false,
    draft: emptyDraft(),
  })
}

function makeAssignment(raw: any): Assignment {
  return reactive({
    id: raw.id,
    name: raw.name,
    description: raw.description ?? null,
    is_signoff: raw.is_signoff ?? false,
    signoff_group_category_id: raw.signoff_group_category_id ?? null,
    llm_config_id: raw.llm_config_id ?? null,
    questions: (raw.questions ?? []).map(makeQuestion),
    expanded: true,
    editingName: false,
    nameDraft: raw.name,
    addingQuestion: false,
    newQuestion: emptyDraft(),
  })
}

// ── Load ───────────────────────────────────────────────────────────────────────
async function load() {
  try {
    const data = await api.get<any>(`/course/${courseId}/configure`)
    courseName.value = data.course_name
    assignments.value = data.assignments.map(makeAssignment)
    tas.value = data.tas ?? []
    groupCategories.value = data.group_categories ?? []
    availableLlms.value = data.available_llms ?? []
    error.value = null
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load'
  } finally {
    loading.value = false
  }
}

onMounted(load)

function cancelAddQuestion(a: Assignment) {
  a.addingQuestion = false
  a.newQuestion = emptyDraft()
}

// ── Lab edit modal ─────────────────────────────────────────────────────────────
type LabModalState = { assignment: Assignment | null; nameDraft: string; llmDraft: number | null }
const labModal = ref<LabModalState | null>(null)

function openLabModal(a: Assignment) {
  labModal.value = { assignment: a, nameDraft: a.name, llmDraft: a.llm_config_id }
}

function openNewLabModal() {
  labModal.value = { assignment: null, nameDraft: '', llmDraft: null }
}

function closeLabModal() {
  labModal.value = null
}

async function saveLabModal() {
  if (!labModal.value) return
  const name = labModal.value.nameDraft.trim()
  if (!name) return
  saving.value = true
  try {
    if (labModal.value.assignment) {
      const a = labModal.value.assignment
      await api.put(`/course/${courseId}/assignments/${a.id}`, {
        name,
        llm_config_id: labModal.value.llmDraft,
      })
      a.name = name
      a.nameDraft = name
      a.llm_config_id = labModal.value.llmDraft
    } else {
      const res = await api.post<any>(`/course/${courseId}/assignments`, {
        name,
        llm_config_id: labModal.value.llmDraft,
      })
      assignments.value.push(makeAssignment({ ...res, llm_config_id: labModal.value.llmDraft }))
    }
    labModal.value = null
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to save'
  } finally {
    saving.value = false
  }
}

// ── Assignments ────────────────────────────────────────────────────────────────
async function deleteAssignment(a: Assignment) {
  // Use the uiStore confirmation dialog
  const confirmed = await uiStore.confirm({
    title: 'Delete assignment',
    message: `Delete "${a.name}" and all its questions?`,
    confirmLabel: 'Delete Assignment',
    tone: 'danger',
  })

  if (!confirmed) return

  saving.value = true
  try {
    await api.delete(`/course/${courseId}/assignments/${a.id}`)
    const idx = assignments.value.findIndex((x) => x.id === a.id)
    if (idx !== -1) assignments.value.splice(idx, 1)
  } catch (e) {
    // Use the uiStore alert for errors
    await uiStore.alert({
      title: 'Assignment could not be deleted',
      message: e instanceof Error ? e.message : 'Failed to delete',
      tone: 'danger',
    })
  } finally {
    saving.value = false
  }
}

// ── Questions ──────────────────────────────────────────────────────────────────
async function addQuestion(a: Assignment) {
  const d = a.newQuestion
  const desc = d.problem_description.trim()
  if (!desc) return
  saving.value = true
  try {
    const res = await api.post<any>(`/course/${courseId}/assignments/${a.id}/questions`, {
      label: d.label.trim() || null,
      problem_description: desc,
      official_solution: d.official_solution.trim() || null,
      hinting_strategy: d.hinting_strategy.trim() || null,
      require_signoff: d.require_signoff,
    })
    a.questions.push(makeQuestion(res))
    a.newQuestion = emptyDraft()
    a.addingQuestion = false
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to add question'
  } finally {
    saving.value = false
  }
}

function cancelEditQuestion(q: Question) {
  q.draft = emptyDraft()
  if (modal.value) modal.value.editing = false
}

async function saveQuestion(a: Assignment, q: Question) {
  const desc = q.draft.problem_description.trim()
  if (!desc) return
  saving.value = true
  try {
    await api.put(`/course/${courseId}/assignments/${a.id}/questions/${q.id}`, {
      label: q.draft.label.trim() || null,
      problem_description: desc,
      official_solution: q.draft.official_solution.trim() || null,
      hinting_strategy: q.draft.hinting_strategy.trim() || null,
      require_signoff: q.draft.require_signoff,
    })
    q.label = q.draft.label.trim() || null
    q.problem_description = desc
    q.official_solution = q.draft.official_solution.trim() || null
    q.hinting_strategy = q.draft.hinting_strategy.trim() || null
    q.require_signoff = q.draft.require_signoff
    q.draft = emptyDraft()
    modal.value = null
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to save question'
  } finally {
    saving.value = false
  }
}

async function deleteQuestion(a: Assignment, q: Question) {
  saving.value = true
  try {
    await api.delete(`/course/${courseId}/assignments/${a.id}/questions/${q.id}`)
    const idx = a.questions.findIndex((x) => x.id === q.id)
    if (idx !== -1) a.questions.splice(idx, 1)
    modal.value = null
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to delete question'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="max-w-5xl mx-auto p-6">
    <!-- Header -->
    <div class="mb-6 flex items-start justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Configure</h1>
        <p v-if="courseName" class="text-sm text-gray-500 mt-0.5">{{ courseName }}</p>
      </div>
    </div>

    <div v-if="loading" class="text-gray-500 text-sm">Loading…</div>

    <div
      v-if="error"
      class="bg-red-50 border border-red-200 text-red-800 p-4 rounded-lg text-sm mb-4 flex items-start justify-between gap-2"
    >
      <span>{{ error }}</span>
      <button class="underline flex-shrink-0" @click="error = null">Dismiss</button>
    </div>

    <template v-if="!loading">
      <div class="flex gap-8 items-start">
        <!-- Left: assignments -->
        <div class="flex-1 min-w-0">
          <div class="space-y-4">
            <div
              v-for="a in assignments"
              :key="a.id"
              class="bg-white border border-gray-200 rounded-xl overflow-hidden"
            >
              <!-- Assignment header -->
              <div class="flex items-center gap-2 px-4 py-3 bg-gray-50 border-b border-gray-200">
                <span class="flex-1 font-semibold text-gray-900 text-sm">{{ a.name }}</span>
                <span
                  v-if="a.llm_config_id"
                  class="text-xs text-purple-600 bg-purple-50 border border-purple-200 rounded-full px-2 py-0.5"
                >
                  {{ availableLlms.find((l) => l.id === a.llm_config_id)?.name }}
                </span>

                <!-- Sign-off badge -->
                <button
                  :title="a.is_signoff ? 'Sign-off lab (click to disable)' : 'Not a sign-off lab (click to enable)'"
                  :class="[
                    'flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full border transition-colors',
                    a.is_signoff
                      ? 'bg-emerald-50 border-emerald-300 text-emerald-700 hover:bg-emerald-100'
                      : 'bg-gray-50 border-gray-200 text-gray-400 hover:bg-gray-100 hover:text-gray-600',
                  ]"
                  @click.stop="openSignoffModal(a)"
                >
                  <Check v-if="a.is_signoff" class="w-3 h-3" />
                  Sign-off
                  <span v-if="a.is_signoff" class="ml-0.5 opacity-60">
                    ·
                    {{
                      a.signoff_group_category_id
                        ? groupCategories.find((c) => c.id === a.signoff_group_category_id)?.name
                        : 'Individual'
                    }}
                  </span>
                </button>

                <button class="text-gray-400 hover:text-gray-600" title="Edit lab" @click="openLabModal(a)">
                  <Pencil class="w-3.5 h-3.5" />
                </button>

                <button class="text-gray-400 hover:text-gray-600 ml-1" @click="a.expanded = !a.expanded">
                  <ChevronUp v-if="a.expanded" class="w-4 h-4" />
                  <ChevronDown v-else class="w-4 h-4" />
                </button>
                <button
                  class="text-red-400 hover:text-red-600 ml-1"
                  title="Delete assignment"
                  @click="deleteAssignment(a)"
                >
                  <Trash2 class="w-4 h-4" />
                </button>
              </div>

              <!-- Questions -->
              <div v-if="a.expanded" class="divide-y divide-gray-100">
                <!-- Existing questions -->
                <button
                  v-for="q in a.questions"
                  :key="q.id"
                  class="w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors"
                  @click="openQuestion(a, q)"
                >
                  <div class="flex items-center gap-2">
                    <div class="flex-1 min-w-0">
                      <span v-if="q.label" class="text-xs text-gray-400 font-medium mr-2">{{ q.label }}</span>
                      <span class="text-sm text-gray-800">
                        {{
                          q.problem_description.length > 100
                            ? q.problem_description.slice(0, 100) + '…'
                            : q.problem_description
                        }}
                      </span>
                    </div>
                    <div class="flex gap-2 text-xs flex-shrink-0 items-center">
                      <span v-if="q.require_signoff && a.is_signoff" class="text-violet-600 font-medium">Sign-off</span>
                      <span v-if="q.official_solution" class="text-emerald-600">✓ Answer</span>
                      <span v-if="q.hinting_strategy" class="text-amber-600">✓ Hints</span>
                    </div>
                  </div>
                </button>

                <!-- Add question form -->
                <div v-if="a.addingQuestion" class="px-4 py-3 bg-blue-50">
                  <div class="space-y-2">
                    <div class="flex gap-2">
                      <div class="w-24">
                        <label class="block text-xs text-gray-500 mb-0.5">Exercise</label>
                        <input
                          v-model="a.newQuestion.label"
                          placeholder="1.1"
                          class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                      <div class="flex-1">
                        <label class="block text-xs text-gray-500 mb-0.5">
                          Question
                          <span class="text-red-500">*</span>
                        </label>
                        <textarea
                          v-model="a.newQuestion.problem_description"
                          rows="2"
                          placeholder="Write the question or exercise prompt…"
                          class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
                        ></textarea>
                      </div>
                    </div>
                    <div>
                      <label class="block text-xs text-gray-500 mb-0.5">
                        Official Answer
                        <span class="text-gray-400">(optional)</span>
                      </label>
                      <textarea
                        v-model="a.newQuestion.official_solution"
                        rows="2"
                        placeholder="The correct answer or solution…"
                        class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
                      ></textarea>
                    </div>
                    <div>
                      <label class="block text-xs text-gray-500 mb-0.5">
                        Hinting Strategy
                        <span class="text-gray-400">(optional)</span>
                      </label>
                      <textarea
                        v-model="a.newQuestion.hinting_strategy"
                        rows="2"
                        placeholder="How to guide the student without giving away the answer…"
                        class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
                      ></textarea>
                    </div>
                    <label v-if="a.is_signoff" class="flex items-center gap-2 text-sm cursor-pointer">
                      <input
                        v-model="a.newQuestion.require_signoff"
                        type="checkbox"
                        class="rounded border-gray-300 text-violet-600 focus:ring-violet-500"
                      />
                      <span class="text-gray-700">Requires sign-off</span>
                    </label>
                    <div class="flex gap-2 pt-1">
                      <button
                        :disabled="saving || !a.newQuestion.problem_description.trim()"
                        class="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-medium px-3 py-1.5 rounded transition-colors"
                        @click="addQuestion(a)"
                      >
                        Add Question
                      </button>
                      <button
                        class="text-xs text-gray-500 hover:text-gray-700 px-2 py-1.5"
                        @click="cancelAddQuestion(a)"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>

                <!-- Add question button -->
                <div v-if="!a.addingQuestion" class="px-4 py-2">
                  <button
                    class="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
                    @click="a.addingQuestion = true"
                  >
                    <Plus class="w-3.5 h-3.5" />
                    Add question
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Add assignment -->
          <div class="mt-6">
            <button
              class="inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700 font-medium border border-dashed border-blue-300 hover:border-blue-500 rounded-xl px-4 py-3 w-full justify-center transition-colors"
              @click="openNewLabModal"
            >
              <Plus class="w-4 h-4" />
              New Assignment
            </button>
          </div>
        </div>

        <!-- Right: TAs -->
        <div class="w-64 flex-shrink-0">
          <div class="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div class="px-4 py-3 bg-gray-50 border-b border-gray-200">
              <h2 class="text-sm font-semibold text-gray-700">Teaching Assistants</h2>
            </div>
            <div v-if="tas.length === 0" class="px-4 py-4 text-sm text-gray-400">No TAs assigned.</div>
            <div v-else class="divide-y divide-gray-100">
              <div v-for="ta in tas" :key="ta.id" class="px-4 py-3">
                <p class="text-sm font-medium text-gray-900">{{ ta.name }}</p>
                <p class="text-xs text-gray-400 truncate">{{ ta.email }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
      <!-- end flex row -->
    </template>
  </div>

  <!-- ── Lab edit / create modal ───────────────────────────────────────── -->
  <Teleport to="body">
    <div
      v-if="labModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      @mousedown.self="closeLabModal"
    >
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-sm">
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 class="text-base font-semibold text-gray-900">
            {{ labModal.assignment ? 'Edit Lab' : 'New Lab' }}
          </h2>
          <button class="text-gray-400 hover:text-gray-600" @click="closeLabModal">
            <X class="w-5 h-5" />
          </button>
        </div>
        <div class="px-6 py-5 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              v-model="labModal.nameDraft"
              placeholder="Lab name…"
              class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              autofocus
              @keydown.enter="saveLabModal"
              @keydown.escape="closeLabModal"
            />
          </div>
          <div v-if="availableLlms.length">
            <label class="block text-sm font-medium text-gray-700 mb-1">AI Model</label>
            <select
              v-model="labModal.llmDraft"
              class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option :value="null">No AI</option>
              <option v-for="llm in availableLlms" :key="llm.id" :value="llm.id">
                {{ llm.name }}
                <span class="text-gray-400">({{ llm.model_name }})</span>
              </option>
            </select>
          </div>
          <p v-else class="text-xs text-gray-400">
            No AI models configured yet. Add one in
            <RouterLink to="/llm-settings" class="underline text-blue-600">LLM Settings</RouterLink>
            .
          </p>
        </div>
        <div class="flex justify-end gap-2 px-6 py-4 border-t border-gray-100">
          <button class="text-sm text-gray-600 hover:text-gray-800 px-4 py-2 rounded-lg" @click="closeLabModal">
            Cancel
          </button>
          <button
            :disabled="saving || !labModal.nameDraft.trim()"
            class="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
            @click="saveLabModal"
          >
            {{ labModal.assignment ? 'Save' : 'Create' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- ── Sign-off type picker modal ─────────────────────────────────────── -->
  <Teleport to="body">
    <div
      v-if="signoffModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      @mousedown.self="signoffModal = null"
    >
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-sm">
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <h2 class="text-base font-semibold text-gray-900">Sign-off lab</h2>
            <p class="text-xs text-gray-500 mt-0.5 truncate max-w-[16rem]">
              {{ signoffModal.name }}
            </p>
          </div>
          <button class="text-gray-400 hover:text-gray-600" @click="signoffModal = null">
            <X class="w-5 h-5" />
          </button>
        </div>
        <div class="px-6 py-5">
          <p class="text-sm text-gray-600 mb-4">How will students be signed off?</p>
          <div class="space-y-2">
            <button
              :class="[
                'w-full flex items-center gap-3 px-4 py-3 rounded-xl border-2 text-left transition-colors',
                signoffPick === 'individual' ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300',
              ]"
              @click="signoffPick = 'individual'"
            >
              <div
                :class="[
                  'w-4 h-4 rounded-full border-2 flex-shrink-0 flex items-center justify-center',
                  signoffPick === 'individual' ? 'border-blue-500' : 'border-gray-300',
                ]"
              >
                <div v-if="signoffPick === 'individual'" class="w-2 h-2 rounded-full bg-blue-500" />
              </div>
              <div>
                <p class="text-sm font-medium text-gray-900">Individual</p>
                <p class="text-xs text-gray-400">Each student is signed off separately</p>
              </div>
            </button>
            <button
              v-for="cat in groupCategories"
              :key="cat.id"
              :class="[
                'w-full flex items-center gap-3 px-4 py-3 rounded-xl border-2 text-left transition-colors',
                signoffPick === cat.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300',
              ]"
              @click="signoffPick = cat.id"
            >
              <div
                :class="[
                  'w-4 h-4 rounded-full border-2 flex-shrink-0 flex items-center justify-center',
                  signoffPick === cat.id ? 'border-blue-500' : 'border-gray-300',
                ]"
              >
                <div v-if="signoffPick === cat.id" class="w-2 h-2 rounded-full bg-blue-500" />
              </div>
              <div>
                <p class="text-sm font-medium text-gray-900">{{ cat.name }}</p>
                <p class="text-xs text-gray-400">Groups from this category</p>
              </div>
            </button>
            <p v-if="groupCategories.length === 0" class="text-xs text-gray-400 px-1">
              No group categories yet. Import groups from Canvas first.
            </p>
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-100 flex justify-end gap-3 bg-gray-50 rounded-b-2xl">
          <button
            class="px-4 py-2 text-sm font-medium rounded-lg text-gray-700 bg-white border border-gray-300 hover:bg-gray-50"
            @click="signoffModal = null"
          >
            Cancel
          </button>
          <button
            :disabled="signoffPick === null || saving"
            class="px-5 py-2 text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
            @click="confirmSignoffPick"
          >
            {{ saving ? 'Saving…' : 'Confirm' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- ── Question modal ───────────────────────────────────────────────────── -->
  <Teleport to="body">
    <div
      v-if="modal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      @mousedown.self="closeModal"
    >
      <div
        class="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col overflow-hidden"
        style="max-height: 90vh"
      >
        <!-- Header -->
        <div class="flex items-start justify-between px-6 py-4 border-b border-gray-100 flex-shrink-0">
          <div class="min-w-0 pr-4">
            <p v-if="modal.question.label" class="text-xs text-gray-400 font-medium mb-0.5">
              {{ modal.question.label }}
            </p>
            <h2 class="text-base font-semibold text-gray-900">
              {{ modal.editing ? 'Edit Question' : 'Question' }}
            </h2>
          </div>
          <button class="text-gray-400 hover:text-gray-600 flex-shrink-0 mt-0.5" @click="closeModal">
            <X class="w-5 h-5" />
          </button>
        </div>

        <!-- View mode -->
        <template v-if="!modal.editing">
          <div class="flex-1 overflow-y-auto px-6 py-5 space-y-4">
            <div>
              <p class="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
                {{ modal.question.problem_description }}
              </p>
              <span
                v-if="modal.question.require_signoff && modal.assignment.is_signoff"
                class="inline-block mt-2 text-xs font-medium bg-violet-50 text-violet-700 border border-violet-200 px-2 py-0.5 rounded-full"
              >
                Requires sign-off
              </span>
            </div>
            <div v-if="modal.question.official_solution" class="bg-emerald-50 border border-emerald-200 rounded-lg p-4">
              <p class="text-xs font-semibold text-emerald-700 uppercase tracking-wide mb-1">Official Answer</p>
              <p class="text-sm text-emerald-900 whitespace-pre-wrap leading-relaxed">
                {{ modal.question.official_solution }}
              </p>
            </div>
            <div v-if="modal.question.hinting_strategy" class="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <p class="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-1">Hinting Strategy</p>
              <p class="text-sm text-amber-900 whitespace-pre-wrap leading-relaxed">
                {{ modal.question.hinting_strategy }}
              </p>
            </div>
          </div>
          <div class="px-6 py-4 border-t border-gray-100 bg-gray-50 flex items-center justify-between flex-shrink-0">
            <button
              :disabled="saving"
              class="text-sm text-red-500 hover:text-red-700 font-medium disabled:opacity-50 transition-colors"
              @click="deleteQuestion(modal.assignment, modal.question)"
            >
              Delete
            </button>
            <button
              class="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 transition-colors"
              @click="openQuestionEdit(modal.assignment, modal.question)"
            >
              <Pencil class="w-3.5 h-3.5" />
              Edit
            </button>
          </div>
        </template>

        <!-- Edit mode -->
        <template v-else>
          <div class="flex-1 overflow-y-auto px-6 py-5 space-y-3">
            <div class="flex gap-2">
              <div class="w-24">
                <label class="block text-xs text-gray-500 mb-0.5">Exercise</label>
                <input
                  v-model="modal.question.draft.label"
                  placeholder="1.1"
                  class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div class="flex-1">
                <label class="block text-xs text-gray-500 mb-0.5">
                  Question
                  <span class="text-red-500">*</span>
                </label>
                <textarea
                  v-model="modal.question.draft.problem_description"
                  rows="3"
                  class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
                ></textarea>
              </div>
            </div>
            <div>
              <label class="block text-xs text-gray-500 mb-0.5">
                Official Answer
                <span class="text-gray-400">(optional — only visible to TAs)</span>
              </label>
              <textarea
                v-model="modal.question.draft.official_solution"
                rows="3"
                placeholder="The correct answer or solution…"
                class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
              ></textarea>
            </div>
            <div>
              <label class="block text-xs text-gray-500 mb-0.5">
                Hinting Strategy
                <span class="text-gray-400">(optional — only visible to TAs)</span>
              </label>
              <textarea
                v-model="modal.question.draft.hinting_strategy"
                rows="3"
                placeholder="How to guide the student without giving away the answer…"
                class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
              ></textarea>
            </div>
            <label v-if="modal.assignment.is_signoff" class="flex items-center gap-2 text-sm cursor-pointer">
              <input
                v-model="modal.question.draft.require_signoff"
                type="checkbox"
                class="rounded border-gray-300 text-violet-600 focus:ring-violet-500"
              />
              <span class="text-gray-700">Requires sign-off</span>
            </label>
          </div>
          <div class="px-6 py-4 border-t border-gray-100 bg-gray-50 flex items-center justify-end gap-3 flex-shrink-0">
            <button
              class="text-sm text-gray-500 hover:text-gray-700 px-3 py-2"
              @click="cancelEditQuestion(modal.question)"
            >
              Cancel
            </button>
            <button
              :disabled="saving || !modal.question.draft.problem_description.trim()"
              class="px-5 py-2 text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-colors"
              @click="saveQuestion(modal.assignment, modal.question)"
            >
              {{ saving ? 'Saving…' : 'Save' }}
            </button>
          </div>
        </template>
      </div>
    </div>
  </Teleport>
</template>
