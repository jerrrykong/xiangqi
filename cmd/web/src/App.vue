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
  <!-- 正在恢复凭证时显示加载页，避免闪烁到登录页 -->
  <div v-if="authStore.authState === 'restoring'" class="restoring-screen">
    <div class="restoring-spinner"></div>
    <p>正在恢复登录状态...</p>
  </div>
  <RouterView v-else />
</template>

<style>
#app {
  min-height: 100vh;
}

.restoring-screen {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #6b7280;
  font-size: 1rem;
}

.restoring-spinner {
  width: 36px;
  height: 36px;
  border: 4px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
