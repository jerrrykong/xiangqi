<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'
import { RouterView } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useGameStore } from './stores/game'
import { registerAuthHandlers } from './ws/handlers/auth.handler'
import { registerUserHandlers } from './ws/handlers/user.handler'
import { registerRoomHandlers } from './ws/handlers/room.handler'
import { registerGameHandlers } from './ws/handlers/game.handler'
import { registerMatchHandlers } from './ws/handlers/match.handler'
import { messageRouter } from './ws/router'
import { wsClient } from './ws/client'
import { getSoundManager } from './utils/sound'

const authStore = useAuthStore()
const gameStore = useGameStore()

onMounted(async () => {
  // 清除旧 handler（防止 HMR / 重复 mount 导致重复注册）
  messageRouter.clear()

  // 注册所有 WS 消息处理器
  registerAuthHandlers()
  registerUserHandlers()
  registerRoomHandlers()
  registerGameHandlers()
  registerMatchHandlers()

  // 初始化 (仅恢复本地用户信息，不自动连接)
  authStore.init()

  // 预加载音效
  const sound = getSoundManager()
  await sound.init()
})

// 监听 WS 连接状态变化 — 断连时保存状态用于重连后提示
watch(() => wsClient.connectionState.value, (newState, oldState) => {
  if (newState === 'disconnected' && oldState === 'connected') {
    // WS 断连：保存当前游戏阶段，标记重连状态
    const currentPhase = gameStore.phase
    authStore.markReconnecting(currentPhase)
  }
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
