<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { CheckCircle, AlertCircle, Link, Loader, Download, X } from 'lucide-vue-next'
import { settingsApi, canvasApi } from '../api'
import type { CanvasCourse } from '../api'
import { useCoursesStore } from '../stores/courses'

const coursesStore = useCoursesStore()

const hasToken = ref(false)
const canvasUserId = ref<string | null>(null)
const token = ref('')
const saving = ref(false)
const saveError = ref<string | null>(null)
const saveOk = ref(false)
const loading = ref(true)

// Import modal state
const showImport = ref(false)
const importLoading = ref(false)
const importError = ref<string | null>(null)
const canvasCourses = ref<CanvasCourse[]>([])
const importing = ref<Record<string, boolean>>({})

onMounted(async () => {
  try {
    const data = await settingsApi.get()
    hasToken.value = data.has_canvas_token
    canvasUserId.value = data.canvas_user_id
  } finally {
    loading.value = false
  }
})

async function save() {
  if (!token.value.trim()) return
  saving.value = true
  saveError.value = null
  saveOk.value = false
  try {
    await settingsApi.saveCanvasToken(token.value.trim())
    hasToken.value = true
    saveOk.value = true
    token.value = ''
    const data = await settingsApi.get()
    canvasUserId.value = data.canvas_user_id
  } catch (e: any) {
    saveError.value = e?.message ?? 'Failed to save token'
  } finally {
    saving.value = false
  }
}

async function openImportModal() {
  showImport.value = true
  importLoading.value = true
  importError.value = null
  try {
    canvasCourses.value = await canvasApi.listCourses()
  } catch (e: any) {
    importError.value = e?.message ?? 'Failed to load Canvas courses'
  } finally {
    importLoading.value = false
  }
}

async function importCourse(course: CanvasCourse) {
  importing.value[course.canvas_course_id] = true
  try {
    await canvasApi.importCourse(course.canvas_course_id, course.name)
    course.already_imported = true
    await coursesStore.fetchCourses()
  } catch (e: any) {
    importError.value = e?.message ?? 'Failed to import course'
  } finally {
    importing.value[course.canvas_course_id] = false
  }
}
</script>

<template>
  <div class="p-4 sm:p-6 lg:p-8 max-w-xl">
    <h1 class="text-2xl font-bold text-gray-900 mb-1">Canvas Integration</h1>
    <p class="text-sm text-gray-500 mb-8">Connect your Canvas account to sync courses and enrollments.</p>

    <div v-if="loading" class="text-sm text-gray-400">Loading…</div>

    <template v-else>
      <!-- Current status -->
      <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5 mb-6">
        <div class="flex items-center justify-between">
          <h2 class="text-sm font-semibold text-gray-700">Connection Status</h2>
          <button
            v-if="hasToken"
            class="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
            @click="openImportModal"
          >
            <Download class="w-4 h-4" />
            Import Courses
          </button>
        </div>
        <div class="flex items-center gap-3 mt-3">
          <CheckCircle v-if="hasToken" class="w-5 h-5 text-emerald-500 flex-shrink-0" />
          <AlertCircle v-else class="w-5 h-5 text-amber-400 flex-shrink-0" />
          <div>
            <p class="text-sm font-medium text-gray-900">
              {{ hasToken ? 'Canvas token configured' : 'No Canvas token set' }}
            </p>
            <p v-if="canvasUserId" class="text-xs text-gray-500 mt-0.5">Canvas user ID: {{ canvasUserId }}</p>
          </div>
        </div>
      </div>

      <!-- Set / replace token -->
      <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
        <h2 class="text-sm font-semibold text-gray-700 mb-1">
          {{ hasToken ? 'Replace Canvas API Token' : 'Set Canvas API Token' }}
        </h2>
        <p class="text-xs text-gray-500 mb-4">
          Generate a token in Canvas under
          <strong>Account → Settings → Approved Integrations</strong>
          . The token is validated before saving.
        </p>

        <div
          v-if="saveError"
          class="mb-3 flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700"
        >
          <AlertCircle class="w-4 h-4 flex-shrink-0 mt-0.5" />
          {{ saveError }}
        </div>

        <div
          v-if="saveOk"
          class="mb-3 flex items-center gap-2 bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-3 text-sm text-emerald-700"
        >
          <CheckCircle class="w-4 h-4 flex-shrink-0" />
          Token saved and validated successfully.
        </div>

        <div class="flex gap-3">
          <div class="relative flex-1">
            <Link class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
            <input
              v-model="token"
              type="password"
              placeholder="Paste your Canvas API token…"
              class="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              @keydown.enter="save"
            />
          </div>
          <button
            :disabled="saving || !token.trim()"
            class="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors"
            @click="save"
          >
            <Loader v-if="saving" class="w-4 h-4 animate-spin" />
            {{ saving ? 'Validating…' : 'Save' }}
          </button>
        </div>
      </div>
    </template>
  </div>

  <!-- Import Courses Modal -->
  <Teleport to="body">
    <Transition name="modal-fade">
      <div
        v-if="showImport"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @mousedown.self="showImport = false"
      >
        <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" />
        <div
          class="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] flex flex-col overflow-hidden"
        >
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-gray-100">
            <h2 class="text-base font-semibold text-gray-900">Import Canvas Courses</h2>
            <button class="text-gray-400 hover:text-gray-600 transition-colors" @click="showImport = false">
              <X class="w-5 h-5" />
            </button>
          </div>

          <!-- Body -->
          <div class="flex-1 overflow-y-auto px-6 py-4">
            <div v-if="importLoading" class="text-sm text-gray-400 py-4">Loading Canvas courses…</div>

            <div
              v-else-if="importError"
              class="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700"
            >
              {{ importError }}
            </div>

            <div v-else-if="canvasCourses.length === 0" class="text-sm text-gray-500 py-4">
              No courses found in Canvas.
            </div>

            <ul v-else class="space-y-2">
              <li
                v-for="course in canvasCourses"
                :key="course.canvas_course_id"
                class="flex items-center justify-between gap-3 p-3 rounded-lg border border-gray-200"
              >
                <span class="text-sm text-gray-900 min-w-0 truncate">{{ course.name }}</span>
                <button
                  v-if="!course.already_imported"
                  :disabled="importing[course.canvas_course_id]"
                  class="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors"
                  @click="importCourse(course)"
                >
                  <Loader v-if="importing[course.canvas_course_id]" class="w-3 h-3 animate-spin" />
                  {{ importing[course.canvas_course_id] ? 'Importing…' : 'Import' }}
                </button>
                <span v-else class="flex-shrink-0 flex items-center gap-1 text-xs text-emerald-600 font-medium">
                  <CheckCircle class="w-3.5 h-3.5" />
                  Imported
                </span>
              </li>
            </ul>
          </div>

          <!-- Footer -->
          <div class="px-6 py-4 border-t border-gray-100 bg-gray-50 flex justify-end">
            <button
              class="px-4 py-2 text-sm font-medium rounded-lg text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 transition-colors"
              @click="showImport = false"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
</style>
