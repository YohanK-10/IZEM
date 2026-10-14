import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Course } from '../types'
import { coursesApi } from '../api'

export const useCoursesStore = defineStore('courses', () => {
  const courses = ref<Course[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchCourses(showHidden = false) {
    loading.value = true
    error.value = null
    try {
      courses.value = await coursesApi.list(showHidden)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load courses'
    } finally {
      loading.value = false
    }
  }

  function getCourseById(id: number | string) {
    return courses.value.find((c) => c.id === Number(id))
  }

  return { courses, loading, error, fetchCourses, getCourseById }
})
