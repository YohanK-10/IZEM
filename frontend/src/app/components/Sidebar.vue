<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useUIStore } from '../stores/ui'
import { useCoursesStore } from '../stores/courses'
import {
  LayoutDashboard,
  BarChart3,
  Settings,
  LogOut,
  DoorOpen,
  ClipboardCheck,
  BookOpen,
  TrendingUp,
  Link,
  Clock,
  SlidersHorizontal,
} from 'lucide-vue-next'
import IZEMLogo from './IZEMLogo.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const uiStore = useUIStore()
const coursesStore = useCoursesStore()

const isActive = (path: string) => {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

const activeCourseId = computed(() => uiStore.activeCourseId)
const activeCourse = computed(() => (activeCourseId.value ? coursesStore.getCourseById(activeCourseId.value) : null))

const roleColors: Record<string, string> = {
  teacher: 'bg-blue-600',
  ta: 'bg-green-600',
  student: 'bg-orange-600',
}

async function handleLogout() {
  await authStore.logout()
  router.push('/login')
}
</script>

<template>
  <aside class="hidden md:flex w-64 bg-white border-r border-gray-200 flex-col flex-shrink-0 h-full">
    <!-- Logo -->
    <div class="p-4 border-b border-gray-200">
      <div class="flex items-center gap-3">
        <IZEMLogo :size="40" />
        <div>
          <h1 class="font-semibold text-gray-900">IZEM</h1>
          <p class="text-xs text-gray-500">AI Queue Assistant</p>
        </div>
      </div>
    </div>

    <!-- User info -->
    <div class="p-4 border-b border-gray-200">
      <p class="text-sm font-medium text-gray-900">{{ authStore.user?.name }}</p>
      <p class="text-xs text-gray-500 truncate">{{ authStore.user?.email }}</p>
      <span
        v-if="authStore.user"
        :class="[
          'inline-block mt-2 text-xs text-white px-2 py-1 rounded',
          roleColors[authStore.user.role] ?? 'bg-gray-500',
        ]"
      >
        {{ authStore.user.role.toUpperCase() }}
      </span>
    </div>

    <nav class="flex-1 p-3 space-y-1 overflow-y-auto">
      <!-- ── Home (always visible) ───────────────────────────── -->
      <RouterLink
        v-if="authStore.isTeacher"
        to="/"
        :class="[
          'flex items-center gap-3 px-3 py-2 rounded transition-colors',
          route.path === '/' ? 'bg-blue-50 text-blue-600' : 'text-gray-700 hover:bg-gray-50',
        ]"
      >
        <LayoutDashboard class="w-5 h-5" />
        <span class="text-sm">Courses</span>
      </RouterLink>
      <RouterLink
        v-if="authStore.isTeacher"
        to="/analytics"
        :class="[
          'flex items-center gap-3 px-3 py-2 rounded transition-colors',
          isActive('/analytics') ? 'bg-blue-50 text-blue-600' : 'text-gray-700 hover:bg-gray-50',
        ]"
      >
        <BarChart3 class="w-5 h-5" />
        <span class="text-sm">Analytics</span>
      </RouterLink>

      <template v-else-if="authStore.isTA">
        <RouterLink
          to="/ta-dashboard"
          :class="[
            'flex items-center gap-3 px-3 py-2 rounded transition-colors',
            isActive('/ta-dashboard') ? 'bg-blue-50 text-blue-600' : 'text-gray-700 hover:bg-gray-50',
          ]"
        >
          <LayoutDashboard class="w-5 h-5" />
          <span class="text-sm">Home</span>
        </RouterLink>
        <RouterLink
          to="/"
          :class="[
            'flex items-center gap-3 px-3 py-2 rounded transition-colors',
            route.path === '/' ? 'bg-blue-50 text-blue-600' : 'text-gray-700 hover:bg-gray-50',
          ]"
        >
          <BookOpen class="w-5 h-5" />
          <span class="text-sm">Courses</span>
        </RouterLink>
      </template>

      <template v-else>
        <RouterLink
          to="/student-home"
          :class="[
            'flex items-center gap-3 px-3 py-2 rounded transition-colors',
            isActive('/student-home') ? 'bg-blue-50 text-blue-600' : 'text-gray-700 hover:bg-gray-50',
          ]"
        >
          <LayoutDashboard class="w-5 h-5" />
          <span class="text-sm">Home</span>
        </RouterLink>
        <RouterLink
          to="/"
          :class="[
            'flex items-center gap-3 px-3 py-2 rounded transition-colors',
            route.path === '/' ? 'bg-blue-50 text-blue-600' : 'text-gray-700 hover:bg-gray-50',
          ]"
        >
          <BookOpen class="w-5 h-5" />
          <span class="text-sm">Courses</span>
        </RouterLink>
      </template>

      <!-- ── Course section (visible only when a course is selected) ── -->
      <template v-if="activeCourseId">
        <div class="pt-3 pb-1 px-3">
          <p class="text-[10px] font-semibold uppercase tracking-widest text-gray-400">Course</p>
          <p v-if="activeCourse" class="text-xs font-medium text-gray-600 truncate mt-0.5">
            {{ activeCourse.name }}
          </p>
        </div>

        <!-- Student-only course links -->
        <RouterLink
          v-if="authStore.user?.role === 'student'"
          :to="`/course/${activeCourseId}/progress`"
          :class="[
            'flex items-center gap-3 px-3 py-2 rounded transition-colors',
            isActive(`/course/${activeCourseId}/progress`)
              ? 'bg-blue-50 text-blue-600'
              : 'text-gray-700 hover:bg-gray-50',
          ]"
        >
          <TrendingUp class="w-5 h-5" />
          <span class="text-sm">My Progress</span>
        </RouterLink>

        <RouterLink
          v-if="authStore.isTeacher"
          :to="`/course/${activeCourseId}/configure`"
          :class="[
            'flex items-center gap-3 px-3 py-2 rounded transition-colors',
            isActive(`/course/${activeCourseId}/configure`)
              ? 'bg-blue-50 text-blue-600'
              : 'text-gray-700 hover:bg-gray-50',
          ]"
        >
          <SlidersHorizontal class="w-5 h-5" />
          <span class="text-sm">Configure</span>
        </RouterLink>

        <RouterLink
          :to="`/course/${activeCourseId}/rooms`"
          :class="[
            'flex items-center gap-3 px-3 py-2 rounded transition-colors',
            isActive(`/course/${activeCourseId}/rooms`) || isActive('/room/')
              ? 'bg-blue-50 text-blue-600'
              : 'text-gray-700 hover:bg-gray-50',
          ]"
        >
          <DoorOpen class="w-5 h-5" />
          <span class="text-sm">Rooms</span>
        </RouterLink>

        <RouterLink
          v-if="authStore.isTeacher || authStore.isTA"
          :to="`/course/${activeCourseId}/overview`"
          :class="[
            'flex items-center gap-3 px-3 py-2 rounded transition-colors',
            isActive(`/course/${activeCourseId}/overview`)
              ? 'bg-blue-50 text-blue-600'
              : 'text-gray-700 hover:bg-gray-50',
          ]"
        >
          <Clock class="w-5 h-5" />
          <span class="text-sm">Overtime Questions</span>
        </RouterLink>

        <RouterLink
          v-if="authStore.isTeacher || authStore.isTA"
          :to="`/sign-off/${activeCourseId}`"
          :class="[
            'flex items-center gap-3 px-3 py-2 rounded transition-colors',
            isActive(`/sign-off/`) ? 'bg-blue-50 text-blue-600' : 'text-gray-700 hover:bg-gray-50',
          ]"
        >
          <ClipboardCheck class="w-5 h-5" />
          <span class="text-sm">Sign-off</span>
        </RouterLink>
      </template>

      <!-- ── Global settings (always visible for teacher) ───── -->
      <template v-if="authStore.isTeacher">
        <div class="pt-3 pb-1 px-3">
          <p class="text-[10px] font-semibold uppercase tracking-widest text-gray-400">Settings</p>
        </div>
        <RouterLink
          to="/llm-settings"
          :class="[
            'flex items-center gap-3 px-3 py-2 rounded transition-colors',
            isActive('/llm-settings') ? 'bg-blue-50 text-blue-600' : 'text-gray-700 hover:bg-gray-50',
          ]"
        >
          <Settings class="w-5 h-5" />
          <span class="text-sm">AI Settings</span>
        </RouterLink>
        <RouterLink
          to="/settings/canvas"
          :class="[
            'flex items-center gap-3 px-3 py-2 rounded transition-colors',
            isActive('/settings/canvas') ? 'bg-blue-50 text-blue-600' : 'text-gray-700 hover:bg-gray-50',
          ]"
        >
          <Link class="w-5 h-5" />
          <span class="text-sm">Canvas</span>
        </RouterLink>
      </template>
    </nav>

    <!-- Logout -->
    <div class="p-3 border-t border-gray-200">
      <button
        class="flex w-full items-center gap-3 px-3 py-2 rounded text-gray-700 hover:bg-gray-50 transition-colors"
        @click="handleLogout"
      >
        <LogOut class="w-5 h-5" />
        <span class="text-sm">Logout</span>
      </button>
    </div>
  </aside>
</template>
