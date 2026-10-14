<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useCoursesStore } from '../stores/courses'
import type { Course } from '../types'
import { FileText, Sparkles, Download } from 'lucide-vue-next'

const auth = useAuthStore()
const coursesStore = useCoursesStore()

onMounted(() => coursesStore.fetchCourses())

const CARD_COLORS = [
  'bg-blue-600',
  'bg-emerald-600',
  'bg-violet-600',
  'bg-amber-500',
  'bg-rose-600',
  'bg-sky-600',
  'bg-indigo-600',
  'bg-teal-600',
]

function cardColor(index: number) {
  return CARD_COLORS[index % CARD_COLORS.length]
}

const teacherCourses = computed(() => coursesStore.courses.filter((c: Course) => c.role === 'teacher'))
const taCourses = computed(() => coursesStore.courses.filter((c: Course) => c.role === 'ta'))
const studentCourses = computed(() => coursesStore.courses.filter((c: Course) => c.role === 'student'))
</script>

<template>
  <div class="-mx-4 sm:-mx-6 lg:-mx-8 -mt-6 px-4 sm:px-6 lg:px-8 py-8 min-h-full bg-gray-100">
    <!-- Page header -->
    <div class="flex items-center justify-between mb-8">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">My Courses</h1>
        <p class="text-sm text-gray-500 mt-0.5">All courses where you are enrolled</p>
      </div>
      <RouterLink
        v-if="auth.isTeacher"
        to="/settings/canvas"
        class="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 shadow-sm transition-colors"
      >
        <Download class="w-4 h-4" />
        Import from Canvas
      </RouterLink>
    </div>

    <div v-if="coursesStore.loading" class="text-gray-500 text-sm">Loading courses…</div>
    <div v-else-if="coursesStore.error" class="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
      {{ coursesStore.error }}
    </div>

    <template v-else>
      <!-- Teacher courses -->
      <section v-if="teacherCourses.length > 0" class="mb-10">
        <h2 class="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-4">Courses you teach</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          <RouterLink
            v-for="(course, idx) in teacherCourses"
            :key="course.id"
            :to="`/course/${course.id}/configure`"
            class="bg-white rounded-xl shadow-sm overflow-hidden hover:shadow-md transition-shadow block"
          >
            <div :class="[cardColor(idx), 'relative h-32 flex items-center justify-center overflow-hidden']">
              <FileText class="w-16 h-16 text-white opacity-20" />
              <div
                v-if="course.first_open_assignment_id"
                class="absolute top-2.5 right-2.5 flex items-center gap-1 text-xs font-medium bg-white/25 text-white px-2 py-0.5 rounded-full backdrop-blur-sm"
              >
                <Sparkles class="w-3 h-3" />
                AI Active
              </div>
              <span
                v-if="course.hidden"
                class="absolute bottom-2 left-2 text-xs bg-black/30 text-white px-2 py-0.5 rounded-full"
              >
                Hidden
              </span>
            </div>
            <div class="p-4">
              <h3 class="font-semibold text-gray-900 text-sm leading-snug">{{ course.name }}</h3>
              <p class="text-xs text-gray-400 mt-1">
                {{ course.assignments_count ?? 0 }} assignments · {{ course.students_count ?? 0 }} students ·
                {{ course.tas_count ?? 0 }} TAs
              </p>
              <div class="mt-3 flex items-center gap-3 text-xs font-medium">
                <span class="text-blue-600">Configure →</span>
                <span v-if="course.first_open_assignment_id" class="flex items-center gap-1 text-emerald-600">
                  <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                  Live Queue
                </span>
              </div>
            </div>
          </RouterLink>
        </div>
      </section>

      <!-- TA courses -->
      <section v-if="taCourses.length > 0" class="mb-10">
        <h2 class="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-4">
          Courses where you are a teaching assistant
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          <RouterLink
            v-for="(course, idx) in taCourses"
            :key="course.id"
            :to="`/course/${course.id}`"
            class="bg-white rounded-xl shadow-sm overflow-hidden hover:shadow-md transition-shadow block"
          >
            <div
              :class="[
                cardColor(idx + teacherCourses.length),
                'relative h-32 flex items-center justify-center overflow-hidden',
              ]"
            >
              <FileText class="w-16 h-16 text-white opacity-20" />
              <div
                v-if="course.first_open_assignment_id"
                class="absolute top-2.5 right-2.5 flex items-center gap-1 text-xs font-medium bg-white/25 text-white px-2 py-0.5 rounded-full backdrop-blur-sm"
              >
                <Sparkles class="w-3 h-3" />
                AI Active
              </div>
            </div>
            <div class="p-4">
              <h3 class="font-semibold text-gray-900 text-sm leading-snug">{{ course.name }}</h3>
              <p class="text-xs text-gray-400 mt-1">
                {{ course.assignments_count ?? 0 }} assignments · {{ course.students_count ?? 0 }} students
              </p>
              <div class="mt-3 text-xs font-medium">
                <span v-if="course.first_open_assignment_id" class="flex items-center gap-1 text-emerald-600">
                  <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                  Open Queue — View
                </span>
                <span v-else class="text-gray-400">No open queue</span>
              </div>
            </div>
          </RouterLink>
        </div>
      </section>

      <!-- Student courses -->
      <section v-if="studentCourses.length > 0" class="mb-10">
        <h2 class="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-4">
          Courses where you are a student
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          <RouterLink
            v-for="(course, idx) in studentCourses"
            :key="course.id"
            :to="`/course/${course.id}/progress`"
            class="bg-white rounded-xl shadow-sm overflow-hidden hover:shadow-md transition-shadow block"
          >
            <div
              :class="[
                cardColor(idx + teacherCourses.length + taCourses.length),
                'relative h-32 flex items-center justify-center overflow-hidden',
              ]"
            >
              <FileText class="w-16 h-16 text-white opacity-20" />
              <div
                v-if="course.first_open_assignment_id"
                class="absolute top-2.5 right-2.5 flex items-center gap-1 text-xs font-medium bg-white/25 text-white px-2 py-0.5 rounded-full backdrop-blur-sm"
              >
                <Sparkles class="w-3 h-3" />
                AI Active
              </div>
            </div>
            <div class="p-4">
              <h3 class="font-semibold text-gray-900 text-sm leading-snug">{{ course.name }}</h3>
              <p class="text-xs text-gray-400 mt-1">{{ course.assignments_count ?? 0 }} assignments</p>
              <div class="mt-3 text-xs font-medium">
                <span v-if="course.first_open_assignment_id" class="flex items-center gap-1 text-emerald-600">
                  <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                  Queue open
                </span>
                <span v-else class="text-gray-400">View course →</span>
              </div>
            </div>
          </RouterLink>
        </div>
      </section>

      <!-- Empty state -->
      <div v-if="coursesStore.courses.length === 0" class="bg-white rounded-xl shadow-sm p-12 text-center">
        <FileText class="w-10 h-10 text-gray-300 mx-auto mb-3" />
        <h3 class="text-lg font-semibold text-gray-900">No courses yet</h3>
        <p class="text-sm text-gray-500 mt-1">Import courses from Canvas or ask your teacher to add you.</p>
        <RouterLink
          v-if="auth.isTeacher"
          to="/settings/canvas"
          class="mt-4 inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700"
        >
          <Download class="w-4 h-4" />
          Import from Canvas
        </RouterLink>
      </div>
    </template>
  </div>
</template>
