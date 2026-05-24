<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { wsClient } from '@/ws/client'

const router = useRouter()
const authStore = useAuthStore()

const APP_VERSION = '1.0.0'

type SplashState = 'idle' | 'connecting' | 'connected' | 'failed' | 'token_invalid'
const splashState = ref<SplashState>('idle')
const retryCount = ref(0)
const MAX_RETRIES = 3
const statusMessage = ref('')

let abortController: AbortController | null = null

const hasToken = computed(() => !!(localStorage.getItem('token') || localStorage.getItem('session_token')))

// 按钮显示逻辑
const showLoginButton = computed(() => splashState.value === 'token_invalid' || (splashState.value === 'idle' && !hasToken.value))
const showConnectButton = computed(() => splashState.value === 'failed')
const showConnecting = computed(() => splashState.value === 'connecting')
const showConnected = computed(() => splashState.value === 'connected')

// 动画相关
const logoVisible = ref(false)
const titleVisible = ref(false)
const infoVisible = ref(false)
const actionVisible = ref(false)

onMounted(() => {
  // 入场动画
  setTimeout(() => { logoVisible.value = true }, 200)
  setTimeout(() => { titleVisible.value = true }, 600)
  setTimeout(() => {
    infoVisible.value = true
    // 动画完毕后，如果有 token 自动开始连接
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

      // 连接成功，开始认证
      statusMessage.value = '正在验证身份...'
      const result = await authStore.authenticate()

      if (result === 'ok') {
        splashState.value = 'connected'
        statusMessage.value = '连接成功'
        wsClient.onAuthSuccess()

        // 认证成功 → 跳转（in_room 由 handleAuthTokenResult/handleReconnectResult 处理导航）
        setTimeout(() => {
          if (authStore.authState !== 'in_room') {
            // 优先跳转到 redirect 指定的页面，否则大厅
            const redirect = router.currentRoute.value.query.redirect as string
            router.replace(redirect || '/lobby')
          }
        }, 500)
        return
      }

      if (result === 'credentials_invalid') {
        // Token 无效
        splashState.value = 'token_invalid'
        statusMessage.value = '登录已过期，请重新登录'
        authStore.clearAuth()
        wsClient.disconnect()
        actionVisible.value = true
        return
      }

      // 'retry' — 网络临时故障，断开后重试
      wsClient.disconnect()
    } catch (e) {
      console.warn(`[Splash] Connect attempt ${retryCount.value} failed:`, e)
      wsClient.disconnect()
    }

    // 等待一小段时间再重试
    if (retryCount.value < MAX_RETRIES) {
      statusMessage.value = `连接失败，${2}s 后重试...`
      await sleep(2000)
    }
  }

  // 3 次全部失败
  splashState.value = 'failed'
  statusMessage.value = '无法连接到服务器'
  actionVisible.value = true
}

function getWSUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws`
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function goToLogin() {
  router.push('/login')
}

// 监听 authState 变化 — 如果从其他地方（如 WS 推送）导致状态变化
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
      <!-- Logo / 图标 -->
      <div class="logo-container" :class="{ visible: logoVisible }">
        <div class="logo-icon">
          <svg viewBox="0 0 120 120" class="chess-icon">
            <!-- 棋子外圈 -->
            <circle cx="60" cy="60" r="52" fill="none" stroke="var(--color-wood-700)" stroke-width="4" />
            <circle cx="60" cy="60" r="44" fill="none" stroke="var(--color-wood-600)" stroke-width="2" />
            <!-- 帅/将 字 -->
            <text x="60" y="68" text-anchor="middle" font-size="40" font-weight="bold"
                  font-family="'Noto Serif SC', serif" fill="var(--color-piece-red)">帥</text>
          </svg>
        </div>
      </div>

      <!-- 游戏名称 -->
      <div class="title-container" :class="{ visible: titleVisible }">
        <h1 class="game-title">中国象棋</h1>
        <p class="game-subtitle">楚汉争锋 · 纵横天下</p>
      </div>

      <!-- 状态 / 版本信息 -->
      <div class="info-container" :class="{ visible: infoVisible }">
        <!-- 连接状态 -->
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

        <!-- 版本信息 -->
        <div class="version-info">v{{ APP_VERSION }}</div>
      </div>

      <!-- 操作按钮 -->
      <div class="action-container" :class="{ visible: actionVisible }">
        <button v-if="showLoginButton" class="splash-btn btn-primary" @click="goToLogin">
          登 录
        </button>
        <button v-if="showConnectButton" class="splash-btn btn-secondary" @click="startConnecting">
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
  background: linear-gradient(160deg, var(--color-wood-900) 0%, var(--color-wood-800) 40%, var(--color-wood-700) 100%);
}

/* 背景装饰圆 */
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
  background: radial-gradient(circle, var(--color-wood-300), transparent 70%);
}

.bg-circle-2 {
  width: 400px;
  height: 400px;
  bottom: -100px;
  left: -100px;
  background: radial-gradient(circle, var(--color-wood-400), transparent 70%);
}

.bg-circle-3 {
  width: 200px;
  height: 200px;
  top: 40%;
  left: 60%;
  background: radial-gradient(circle, var(--color-wood-200), transparent 70%);
}

/* 主内容 */
.splash-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
  z-index: 1;
  padding: 32px;
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
  width: 140px;
  height: 140px;
  filter: drop-shadow(0 8px 24px rgba(0, 0, 0, 0.3));
}

.chess-icon {
  width: 100%;
  height: 100%;
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

.game-title {
  font-size: 3rem;
  font-weight: 700;
  color: var(--color-wood-100);
  letter-spacing: 0.15em;
  text-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
  margin-bottom: 8px;
}

.game-subtitle {
  font-size: 1.1rem;
  color: var(--color-wood-300);
  letter-spacing: 0.3em;
  font-weight: 400;
}

/* 信息区 */
.info-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
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
  gap: 10px;
  font-size: 0.9rem;
  padding: 10px 20px;
  border-radius: 24px;
  backdrop-filter: blur(8px);
}

.status-bar.connecting {
  color: var(--color-wood-200);
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
  border-top-color: var(--color-wood-200);
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
  font-size: 0.8rem;
  color: var(--color-wood-500);
  letter-spacing: 0.1em;
}

/* 操作按钮 */
.action-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  opacity: 0;
  transform: translateY(10px);
  transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}

.action-container.visible {
  opacity: 1;
  transform: translateY(0);
}

.splash-btn {
  padding: 14px 56px;
  font-size: 1.05rem;
  font-family: 'Noto Serif SC', serif;
  font-weight: 600;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  letter-spacing: 0.2em;
  transition: all 0.25s ease;
  min-width: 200px;
}

.btn-primary {
  background: linear-gradient(135deg, var(--color-wood-400), var(--color-wood-500));
  color: #fff;
  box-shadow: 0 4px 16px rgba(180, 115, 48, 0.4);
}

.btn-primary:hover {
  background: linear-gradient(135deg, var(--color-wood-300), var(--color-wood-400));
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(180, 115, 48, 0.5);
}

.btn-primary:active {
  transform: translateY(0);
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.1);
  color: var(--color-wood-200);
  border: 1px solid var(--color-wood-500);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.15);
  border-color: var(--color-wood-400);
  transform: translateY(-1px);
}

.btn-secondary:active {
  transform: translateY(0);
}

/* 底部 */
.splash-footer {
  position: absolute;
  bottom: 24px;
  font-size: 0.75rem;
  color: var(--color-wood-500);
  letter-spacing: 0.05em;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
