<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { wsClient } from '@/ws/client'

const router = useRouter()
const baseUrl = import.meta.env.BASE_URL
const authStore = useAuthStore()

const APP_VERSION = '1.0.0'

type SplashState = 'idle' | 'connecting' | 'connected' | 'failed' | 'token_invalid'
const splashState = ref<SplashState>('idle')
const retryCount = ref(0)
const MAX_RETRIES = 3
const statusMessage = ref('')

let abortController: any = null

const hasToken = computed(() => !!(localStorage.getItem('token') || localStorage.getItem('session_token')))

/** 按钮显示逻辑 */
const showLoginButton = computed(() => splashState.value === 'token_invalid' || (splashState.value === 'idle' && !hasToken.value))
const showConnectButton = computed(() => splashState.value === 'failed')
const showConnecting = computed(() => splashState.value === 'connecting')
const showConnected = computed(() => splashState.value === 'connected')

/** 动画相关 */
const logoVisible = ref(false)
const titleVisible = ref(false)
const infoVisible = ref(false)
const actionVisible = ref(false)

onMounted(() => {
  setTimeout(() => { logoVisible.value = true }, 200)
  setTimeout(() => { titleVisible.value = true }, 600)
  setTimeout(() => {
    infoVisible.value = true
    if (hasToken.value) {
      startConnecting()
    } else {
      splashState.value = 'idle'
      actionVisible.value = true
    }
  }, 1000)
})

onUnmounted(() => {
  abortController?.abort()
})

async function startConnecting() {
  splashState.value = 'connecting'
  retryCount.value = 0
  actionVisible.value = false
  await attemptConnect()
}

async function attemptConnect() {
  while (retryCount.value < MAX_RETRIES) {
    retryCount.value++
    statusMessage.value = `正在连接服务器... (${retryCount.value}/${MAX_RETRIES})`

    try {
      const wsUrl = getWSUrl()
      await wsClient.connect(wsUrl)

      statusMessage.value = '正在验证身份...'
      const result = await authStore.authenticate()

      if (result === 'ok') {
        splashState.value = 'connected'
        statusMessage.value = '连接成功'
        wsClient.onAuthSuccess()

        setTimeout(() => {
          if (authStore.authState !== 'in_room') {
            const redirect = router.currentRoute.value.query.redirect as string
            router.replace(redirect || '/lobby')
          }
        }, 500)
        return
      }

      if (result === 'credentials_invalid') {
        splashState.value = 'token_invalid'
        statusMessage.value = '登录已过期，请重新登录'
        authStore.clearAuth()
        wsClient.disconnect()
        actionVisible.value = true
        return
      }

      wsClient.disconnect()
    } catch (e) {
      console.warn(`[Splash] Connect attempt ${retryCount.value} failed:`, e)
      wsClient.disconnect()
    }

    if (retryCount.value < MAX_RETRIES) {
      statusMessage.value = `连接失败，2s 后重试...`
      await sleep(2000)
    }
  }

  splashState.value = 'failed'
  statusMessage.value = '无法连接到服务器'
  actionVisible.value = true
}

function getWSUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const basePath = import.meta.env.BASE_URL.replace(/\/$/, '')
  return `${protocol}//${window.location.host}${basePath}/ws`
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function goToLogin() {
  router.push('/login')
}

import { watch } from 'vue'
watch(() => authStore.authState, (newState) => {
  if (newState === 'authenticated' && splashState.value !== 'connected') {
    splashState.value = 'connected'
    statusMessage.value = '连接成功'
    setTimeout(() => router.replace('/lobby'), 500)
  }
})
</script>

<template>
  <div class="splash-page">
    <!-- 背景装饰 -->
    <div class="bg-decoration">
      <div class="bg-circle bg-circle-1"></div>
      <div class="bg-circle bg-circle-2"></div>
      <div class="bg-circle bg-circle-3"></div>
    </div>

    <!-- 主内容 -->
    <div class="splash-content">
      <!-- Logo -->
      <div class="logo-container" :class="{ visible: logoVisible }">
        <img :src="baseUrl + 'assets/svg/ui/logo.svg'" alt="象棋" class="logo-icon" />
      </div>

      <!-- 游戏名称 -->
      <div class="title-container" :class="{ visible: titleVisible }">
        <img :src="baseUrl + 'assets/svg/ui/text-logo.svg'" alt="楚汉争锋" class="game-title-img" />
      </div>

      <!-- 状态 / 版本信息 -->
      <div class="info-container" :class="{ visible: infoVisible }">
        <div v-if="showConnecting" class="status-bar connecting">
          <div class="status-spinner"></div>
          <span>{{ statusMessage }}</span>
        </div>
        <div v-else-if="showConnected" class="status-bar connected">
          <span class="status-dot green"></span>
          <span>{{ statusMessage }}</span>
        </div>
        <div v-else-if="splashState === 'failed'" class="status-bar failed">
          <span class="status-dot red"></span>
          <span>{{ statusMessage }}</span>
        </div>
        <div v-else-if="splashState === 'token_invalid'" class="status-bar failed">
          <span class="status-dot red"></span>
          <span>{{ statusMessage }}</span>
        </div>

        <div class="version-info">v{{ APP_VERSION }}</div>
      </div>

      <!-- 操作按钮 -->
      <div class="action-container" :class="{ visible: actionVisible }">
        <button v-if="showLoginButton" class="btn btn-primary btn--lg btn--block splash-btn" @click="goToLogin">
          登 录
        </button>
        <button v-if="showConnectButton" class="btn btn-secondary btn--lg btn--block splash-btn" @click="startConnecting">
          连接服务器
        </button>
      </div>
    </div>

    <!-- 底部 -->
    <div class="splash-footer">
      <span>Powered by WebSocket</span>
    </div>
  </div>
</template>

<style scoped>
.splash-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  background: linear-gradient(160deg, var(--color-wood-dark) 0%, #5C3A1E 40%, var(--color-wood) 100%);
}

/* 背景装饰 */
.bg-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.bg-circle {
  position: absolute;
  border-radius: 50%;
  opacity: 0.06;
}

.bg-circle-1 {
  width: 600px;
  height: 600px;
  top: -200px;
  right: -150px;
  background: radial-gradient(circle, var(--color-wood-bg), transparent 70%);
}

.bg-circle-2 {
  width: 400px;
  height: 400px;
  bottom: -100px;
  left: -100px;
  background: radial-gradient(circle, var(--color-gold-light), transparent 70%);
}

.bg-circle-3 {
  width: 200px;
  height: 200px;
  top: 40%;
  left: 60%;
  background: radial-gradient(circle, var(--color-gold), transparent 70%);
}

/* 主内容 */
.splash-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-8);
  z-index: 1;
  padding: var(--space-8);
  max-width: 420px;
  width: 100%;
}

/* Logo */
.logo-container {
  opacity: 0;
  transform: scale(0.6) translateY(20px);
  transition: all 0.8s cubic-bezier(0.16, 1, 0.3, 1);
}

.logo-container.visible {
  opacity: 1;
  transform: scale(1) translateY(0);
}

.logo-icon {
  width: 120px;
  height: 120px;
  filter: drop-shadow(0 8px 24px rgba(0, 0, 0, 0.3));
}

/* 标题 */
.title-container {
  text-align: center;
  opacity: 0;
  transform: translateY(20px);
  transition: all 0.8s cubic-bezier(0.16, 1, 0.3, 1);
}

.title-container.visible {
  opacity: 1;
  transform: translateY(0);
}

.game-title-img {
  width: 280px;
  height: 75px;
  filter: drop-shadow(0 2px 8px rgba(0, 0, 0, 0.3));
}

/* 信息区 */
.info-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  min-height: 60px;
  opacity: 0;
  transform: translateY(15px);
  transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}

.info-container.visible {
  opacity: 1;
  transform: translateY(0);
}

.status-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  padding: var(--space-3) var(--space-5);
  border-radius: var(--radius-full);
  backdrop-filter: blur(8px);
}

.status-bar.connecting {
  color: var(--color-bg-primary);
  background: rgba(255, 255, 255, 0.08);
}

.status-bar.connected {
  color: #86efac;
  background: rgba(34, 197, 94, 0.1);
}

.status-bar.failed {
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.1);
}

.status-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: var(--color-bg-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.green { background: #22c55e; }
.status-dot.red { background: #ef4444; }

.version-info {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  letter-spacing: 0.1em;
}

/* 操作按钮 */
.action-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  opacity: 0;
  transform: translateY(10px);
  transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}

.action-container.visible {
  opacity: 1;
  transform: translateY(0);
}

.splash-btn {
  max-width: 280px;
  font-size: var(--text-lg);
  letter-spacing: 0.2em;
}

/* 底部 */
.splash-footer {
  position: absolute;
  bottom: var(--space-6);
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  letter-spacing: 0.05em;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 768px) {
  .game-title-img {
    width: 240px;
    height: 64px;
  }
  .logo-icon {
    width: 100px;
    height: 100px;
  }
}
</style>
