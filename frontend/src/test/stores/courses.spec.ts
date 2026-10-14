import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useCoursesStore } from '@/app/stores/courses'
import * as api from '@/app/api'
import type { Course } from '@/app/types'

vi.mock('@/app/api', () => ({
  coursesApi: {
    list: vi.fn(),
  },
}))

const mockCourses: Course[] = [
  { id: 1, name: 'Course A', canvas_course_id: null, hidden: false, role: 'teacher' },
  { id: 2, name: 'Course B', canvas_course_id: 'canvas-2', hidden: false, role: 'student' },
]

describe('useCoursesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('starts empty', () => {
    const store = useCoursesStore()
    expect(store.courses).toEqual([])
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  describe('fetchCourses', () => {
    it('populates courses on success', async () => {
      vi.mocked(api.coursesApi.list).mockResolvedValue(mockCourses)
      const store = useCoursesStore()
      await store.fetchCourses()
      expect(store.courses).toEqual(mockCourses)
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('passes showHidden flag to the API', async () => {
      vi.mocked(api.coursesApi.list).mockResolvedValue([])
      const store = useCoursesStore()
      await store.fetchCourses(true)
      expect(api.coursesApi.list).toHaveBeenCalledWith(true)
    })

    it('sets error message on failure', async () => {
      vi.mocked(api.coursesApi.list).mockRejectedValue(new Error('Network error'))
      const store = useCoursesStore()
      await store.fetchCourses()
      expect(store.error).toBe('Network error')
      expect(store.loading).toBe(false)
    })

    it('resets loading flag on failure', async () => {
      vi.mocked(api.coursesApi.list).mockRejectedValue(new Error('fail'))
      const store = useCoursesStore()
      await store.fetchCourses()
      expect(store.loading).toBe(false)
    })
  })

  describe('getCourseById', () => {
    it('returns matching course by number id', async () => {
      vi.mocked(api.coursesApi.list).mockResolvedValue(mockCourses)
      const store = useCoursesStore()
      await store.fetchCourses()
      expect(store.getCourseById(1)).toEqual(mockCourses[0])
    })

    it('returns matching course by string id', async () => {
      vi.mocked(api.coursesApi.list).mockResolvedValue(mockCourses)
      const store = useCoursesStore()
      await store.fetchCourses()
      expect(store.getCourseById('2')).toEqual(mockCourses[1])
    })

    it('returns undefined when not found', async () => {
      vi.mocked(api.coursesApi.list).mockResolvedValue(mockCourses)
      const store = useCoursesStore()
      await store.fetchCourses()
      expect(store.getCourseById(999)).toBeUndefined()
    })
  })
})
