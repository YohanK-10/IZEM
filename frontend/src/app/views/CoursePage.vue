<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCoursesStore } from '../stores/courses'

const route = useRoute()
const router = useRouter()
const coursesStore = useCoursesStore()

const courseId = Number(route.params.courseId)

onMounted(async () => {
  if (coursesStore.courses.length === 0) {
    await coursesStore.fetchCourses()
  }
  const course = coursesStore.getCourseById(courseId)
  if (course?.role === 'student') {
    router.replace({ name: 'student-course', params: { courseId } })
  } else {
    router.replace({ name: 'rooms', params: { courseId } })
  }
})
</script>

<template>
  <div class="text-gray-400 text-sm p-8">Redirecting…</div>
</template>
