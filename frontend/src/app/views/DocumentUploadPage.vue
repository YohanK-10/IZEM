<script setup lang="ts">
import { useRoute } from 'vue-router'
import { useCoursesStore } from '../stores/courses'
import { computed } from 'vue'

const route = useRoute()
const coursesStore = useCoursesStore()

const courseId = Number(route.params.courseId)
const course = computed(() => coursesStore.getCourseById(courseId))
</script>

<template>
  <div class="p-4 sm:p-6 lg:p-8">
    <h1 class="text-2xl font-bold text-gray-900 mb-2">Document Upload</h1>
    <p v-if="course" class="text-sm text-gray-600 mb-6">{{ course.name }}</p>

    <div class="bg-blue-50 border border-blue-200 rounded-lg p-6 text-sm text-blue-700">
      Document management for RAG (retrieval-augmented generation) is handled through the
      <a href="/teacher/courses" class="underline">teacher course setup</a>
      in the backend.
    </div>
  </div>
</template>
