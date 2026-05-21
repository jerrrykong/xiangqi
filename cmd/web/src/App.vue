<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { registerAuthHandlers } from './ws/handlers/auth.handler'
import { registerUserHandlers } from './ws/handlers/user.handler'
import { registerRoomHandlers } from './ws/handlers/room.handler'
import { registerGameHandlers } from './ws/handlers/game.handler'
import { registerMatchHandlers } from './ws/handlers/match.handler'

const authStore = useAuthStore()

onMounted(() => {
  // 注册所有 WS 消息处理器
  registerAuthHandlers()
  registerUserHandlers()
  registerRoomHandlers()
  registerGameHandlers()
  registerMatchHandlers()

  // 初始化认证 (建立 WS 连接 + 认证)
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
