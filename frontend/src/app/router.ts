import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useUIStore } from './stores/ui'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('./views/LoginPage.vue'),
    },
    {
      path: '/view',
      name: 'viewer-landing',
      component: () => import('./views/ViewerLandingPage.vue'),
      meta: { public: true },
    },
    {
      path: '/view/room/:roomId',
      name: 'viewer-room',
      component: () => import('./views/ViewerQueuePage.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('./components/RootLayout.vue'),
      children: [
        {
          path: '',
          name: 'home',
          component: () => import('./views/CoursesPage.vue'), // overridden by role guard below
        },
        {
          path: 'course/:courseId',
          name: 'course',
          component: () => import('./views/CoursePage.vue'),
        },
        {
          path: 'ta-dashboard',
          name: 'ta-dashboard',
          component: () => import('./views/TADashboardPage.vue'),
          meta: { requiresRole: ['ta'] },
        },
        {
          path: 'student-home',
          name: 'student-home',
          component: () => import('./views/StudentDashboardPage.vue'),
          meta: { requiresRole: ['student'] },
        },
        {
          path: 'lab-session/:assignmentId',
          name: 'lab-session',
          component: () => import('./views/LabSessionPage.vue'),
          meta: { requiresRole: ['teacher', 'ta'] },
        },
        {
          path: 'student-queue/:assignmentId',
          name: 'student-queue',
          component: () => import('./views/StudentQueuePage.vue'),
          meta: { requiresRole: ['student'] },
        },
        {
          path: 'review-request/:requestId',
          name: 'review-request',
          component: () => import('./views/ReviewRequestPage.vue'),
          meta: { requiresRole: ['teacher', 'ta'] },
        },
        {
          path: 'student/request/:requestId',
          name: 'student-request',
          component: () => import('./views/StudentRequestPage.vue'),
          meta: { requiresRole: ['student'] },
        },
        {
          path: 'analytics',
          name: 'analytics',
          component: () => import('./views/AnalyticsPage.vue'),
          meta: { requiresRole: ['teacher'] },
        },
        {
          path: 'llm-settings',
          name: 'llm-settings',
          component: () => import('./views/LLMSettingsPage.vue'),
          meta: { requiresRole: ['teacher'] },
        },
        {
          path: 'documents/:courseId',
          name: 'documents',
          component: () => import('./views/DocumentUploadPage.vue'),
          meta: { requiresRole: ['teacher'] },
        },
        {
          path: 'sign-off/:courseId',
          name: 'sign-off',
          component: () => import('./views/SignOffPage.vue'),
          meta: { requiresRole: ['teacher', 'ta'] },
        },
        {
          path: 'course/:courseId/progress',
          name: 'student-course',
          component: () => import('./views/StudentCoursePage.vue'),
          meta: { requiresRole: ['student'] },
        },
        {
          path: 'course/:courseId/rooms',
          name: 'rooms',
          component: () => import('./views/RoomsPage.vue'),
        },
        {
          path: 'course/:courseId/overview',
          name: 'course-overview',
          component: () => import('./views/CourseOverviewPage.vue'),
          meta: { requiresRole: ['teacher', 'ta'] },
        },
        {
          path: 'course/:courseId/configure',
          name: 'course-configure',
          component: () => import('./views/CourseConfigurePage.vue'),
          meta: { requiresRole: ['teacher'] },
        },
        {
          path: 'room/:roomId',
          name: 'room-detail',
          component: () => import('./views/RoomDetailPage.vue'),
        },
        {
          path: 'settings/canvas',
          name: 'canvas-settings',
          component: () => import('./views/CanvasSettingsPage.vue'),
          meta: { requiresRole: ['teacher'] },
        },
        {
          path: ':pathMatch(.*)*',
          name: 'not-found',
          component: () => import('./views/NotFoundPage.vue'),
        },
      ],
    },
  ],
})

router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()
  const uiStore = useUIStore()

  // Track active course from any route that carries courseId.
  // For assignmentId, roomId, or courseId query param routes, preserve activeCourseId.
  if (to.params.courseId) {
    uiStore.setActiveCourse(Number(to.params.courseId))
  } else if (to.query.courseId) {
    uiStore.setActiveCourse(Number(to.query.courseId))
  } else if (!to.params.assignmentId && !to.params.roomId) {
    uiStore.setActiveCourse(null)
  }

  // Initialize auth if not done yet
  if (!authStore.initialized) {
    await authStore.checkAuth()
  }

  // Redirect unauthenticated users to login (except public routes)
  if (!to.meta.public && to.name !== 'login' && !authStore.isAuthenticated) {
    return next({ name: 'login' })
  }

  // Redirect authenticated users away from login
  if (to.name === 'login' && authStore.isAuthenticated) {
    const role = authStore.user?.role
    if (role === 'ta') return next({ name: 'ta-dashboard' })
    if (role === 'student') return next({ name: 'student-home' })
    return next({ name: 'home' })
  }

  // Role-based redirect from generic home (/) — only on first land, not explicit navigation
  if (to.name === 'home' && authStore.isAuthenticated && _from.name == null) {
    const role = authStore.user?.role
    if (role === 'ta') return next({ name: 'ta-dashboard' })
    if (role === 'student') return next({ name: 'student-home' })
    // teachers stay on CoursesPage
  }

  // Role-based access control
  const requiredRoles = to.meta.requiresRole as string[] | undefined
  if (requiredRoles && authStore.user) {
    if (!requiredRoles.includes(authStore.user.role)) {
      return next({ name: 'home' })
    }
  }

  next()
})

export default router
