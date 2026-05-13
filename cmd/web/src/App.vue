<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import { useAuthStore } from './stores/auth'

const authStore = useAuthStore()

onMounted(() => {
  // 初始化认证状态
  authStore.init()
})
</script>

<template>
  <RouterView />
</template>

<style>
#app {
  min-height: 100vh;
}
</style>
