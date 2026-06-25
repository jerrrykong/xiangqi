/**
 * Lobby — 游戏大厅页面
 * 单列居中布局 + 自定义 overlay 弹窗
 */
<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useRoomStore } from '@/stores/room'
import { useMatchStore } from '@/stores/match'
import { useGameStore } from '@/stores/game'
import { wsClient } from '@/ws/client'
import { WSMsgType } from '@/ws/types'
import { showToast, showConfirm } from '@/components/common/ui'

const router = useRouter()
const baseUrl = import.meta.env.BASE_URL
const authStore = useAuthStore()
const roomStore = useRoomStore()
const matchStore = useMatchStore()
const gameStore = useGameStore()

const rankings = ref<any[]>([])
const history = ref<any[]>([])

/** 解析头像引用，返回 SVG 路径；非系统头像或无头像返回空 */
const avatarImgSrc = computed(() => {
  const avatar = authStore.user?.avatar
  if (!avatar) return ''
  if (avatar.startsWith('sys:')) {
    return baseUrl + `assets/svg/headicon/${avatar.slice(4)}.svg`
  }
  return ''
})

/** 头像 fallback 文字 */
const avatarText = computed(() => {
  return (authStore.user?.nickname || authStore.user?.username || '?')[0]
})

/** 用户是否处于房间中 */
const isInRoom = computed(() => authStore.authState === 'in_room')

const isCreatingRoom = ref(false)

/** PvE 难度选择 */
const showPvEDialog = ref(false)
const selectedDifficulty = ref(3)

/** Overlay 弹窗 */
const activeOverlay = ref<'' | 'rankings' | 'history' | 'matchmaking' | 'joinRoom'>('')

/** 胜率 */
const winRate = computed(() => {
  if (!authStore.user) return 0
  const games = authStore.user.games_count
  if (games === 0) return 0
  const wins = history.value.filter((h) => h.result === 'win').length
  return Math.round((wins / games) * 100)
})

// ===== 快速匹配：等待计时 =====
const matchStartTime = ref<number>(0)
const matchElapsed = ref('00:00')
let matchTimerHandle: ReturnType<typeof setInterval> | null = null

/** 格式化经过秒数为 mm:ss */
function formatElapsed(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const m = String(Math.floor(totalSec / 60)).padStart(2, '0')
  const s = String(totalSec % 60).padStart(2, '0')
  return `${m}:${s}`
}

function startMatchTimer() {
  matchStartTime.value = Date.now()
  matchTimerHandle = setInterval(() => {
    matchElapsed.value = formatElapsed(Date.now() - matchStartTime.value)
  }, 1000)
  matchElapsed.value = '00:00'
}

function stopMatchTimer() {
  if (matchTimerHandle) {
    clearInterval(matchTimerHandle)
    matchTimerHandle = null
  }
}

// ===== 加入房间 =====
const availableRooms = ref<any[]>([])
const selectedRoomId = ref<string>('')
const isJoiningRoom = ref(false)
const isFetchingRooms = ref(false)

/** 监听匹配成功 → 导航到对局界面 */
watch(() => gameStore.isGameStarted, (val) => {
  if (val && roomStore.currentRoom) {
    stopMatchTimer()
    activeOverlay.value = ''
    router.push(`/game/${roomStore.currentRoom.roomId}`)
  }
})

/** 监听匹配离开确认（服务端推送） */
watch(() => matchStore.isMatchmaking, (val) => {
  if (!val && activeOverlay.value === 'matchmaking') {
    stopMatchTimer()
    activeOverlay.value = ''
  }
})

/** 监听 WS 重连成功后刷新数据 */
watch(() => wsClient.connectionState.value, (newState, oldState) => {
  if (newState === 'connected' && oldState === 'disconnected') {
    fetchRankings()
    fetchHistory()
  }
})

onMounted(async () => {
  if (isInRoom.value) return
  const messages = authStore.consumeReconnectMessages()
  if (messages.length > 0) {
    await showConfirm(messages.join('\n'), '提示', { confirmText: '确定', type: 'warning' })
  }
  await Promise.all([fetchRankings(), fetchHistory()])
})

onUnmounted(() => {
  stopMatchTimer()
})

async function fetchRankings() {
  try {
    const result = await wsClient.request(WSMsgType.USER_GET_RANKINGS, { page: 1, page_size: 10 })
    rankings.value = result.rankings || []
  } catch (error) {
    console.error('Failed to fetch rankings:', error)
  }
}

async function fetchHistory() {
  try {
    const result = await wsClient.request(WSMsgType.USER_GET_HISTORY, { page: 1, page_size: 10 })
    history.value = result.games || []
  } catch (error) {
    console.error('Failed to fetch history:', error)
  }
}

/** 创建 PvP 房间 */
async function handleCreateRoom() {
  isCreatingRoom.value = true
  try {
    await roomStore.createRoom('pvp')
    router.push(`/game/${roomStore.currentRoom!.roomId}`)
  } catch (error: any) {
    showToast(error.message || '创建房间失败', 'error')
  } finally {
    isCreatingRoom.value = false
  }
}

/** 创建 PvE 房间 */
async function handleCreatePvERoom() {
  showPvEDialog.value = false
  try {
    await roomStore.createRoom('pve', selectedDifficulty.value)
    showToast('正在启动AI对局...', 'info')
  } catch (error: any) {
    showToast(error.message || '创建PvE房间失败', 'error')
  }
}

/** 快速匹配 — 打开全屏匹配 overlay */
async function handleMatch() {
  activeOverlay.value = 'matchmaking'
  try {
    await matchStore.joinMatch('pvp')
    startMatchTimer()
  } catch (error: any) {
    activeOverlay.value = ''
    showToast(error.message || '匹配失败', 'error')
  }
}

/** 取消匹配 — 等待服务端确认后自动关闭 overlay（通过 watcher） */
async function handleCancelMatch() {
  try {
    await matchStore.leaveMatch()
    showToast('已取消匹配', 'info')
  } catch (error: any) {
    showToast(error.message || '取消匹配失败', 'error')
  }
}

/** 打开加入房间 overlay */
async function handleOpenJoinRoom() {
  activeOverlay.value = 'joinRoom'
  selectedRoomId.value = ''
  isFetchingRooms.value = true
  try {
    await roomStore.fetchRoomList()
    availableRooms.value = roomStore.roomList
  } catch (error) {
    console.error('Failed to fetch room list:', error)
  } finally {
    isFetchingRooms.value = false
  }
}

/** 确认加入选中房间 */
async function handleJoinSelectedRoom() {
  if (!selectedRoomId.value) {
    showToast('请先选择一个房间', 'warning')
    return
  }
  isJoiningRoom.value = true
  try {
    await roomStore.joinRoom(selectedRoomId.value)
    activeOverlay.value = ''
    router.push(`/game/${roomStore.currentRoom!.roomId}`)
  } catch (error: any) {
    showToast(error.message || '加入房间失败', 'error')
  } finally {
    isJoiningRoom.value = false
  }
}

/** 退出登录 */
async function handleLogout() {
  const ok = await showConfirm('确定要退出登录吗？', '提示', { type: 'warning' })
  if (ok) {
    authStore.logout()
    router.push('/login')
  }
}

/** 前往设置 */
function goToSettings() {
  router.push('/settings')
}

function formatTime(seconds: number): string {
  const date = new Date(seconds * 1000)
  return date.toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getResultLabel(result: string): string {
  switch (result) {
    case 'win': return '胜'
    case 'loss': return '负'
    default: return '和'
  }
}

function getResultClass(result: string): string {
  switch (result) {
    case 'win': return 'win'
    case 'loss': return 'lose'
    default: return 'draw'
  }
}
</script>

<template>
  <div class="lobby-page">
    <!-- 顶部导航 -->
    <header class="lobby-header">
      <img :src="baseUrl + 'assets/svg/ui/text-logo.svg'" alt="楚汉争锋" class="brand-name-img" />
      <div class="header-links">
        <button class="header-link-btn" @click="activeOverlay = 'rankings'">
          <img :src="baseUrl + 'assets/svg/ui/icon-trophy.svg'" alt="" class="btn-icon-sm" />
          <span>排行榜</span>
        </button>
        <button class="header-link-btn" @click="activeOverlay = 'history'">
          <img :src="baseUrl + 'assets/svg/ui/icon-clock.svg'" alt="" class="btn-icon-sm" />
          <span>历史记录</span>
        </button>
        <button class="header-link-btn" @click="goToSettings">
          <img :src="baseUrl + 'assets/svg/ui/icon-settings.svg'" alt="" class="btn-icon-sm" />
          <span>设置</span>
        </button>
      </div>
    </header>

    <main class="lobby-main">
      <!-- 玩家信息卡 -->
      <div class="lobby-player-card">
        <div class="avatar">
          <img v-if="avatarImgSrc" :src="avatarImgSrc" alt="" class="avatar-img" />
          <template v-else>
            <img :src="baseUrl + 'assets/svg/ui/icon-user.svg'" alt="" class="avatar-icon" />
            <span class="avatar-text">{{ avatarText }}</span>
          </template>
        </div>
        <div class="player-detail">
          <div class="player-name">{{ authStore.user?.nickname || authStore.user?.username }}</div>
          <div class="player-stats">
            <span class="stat">{{ authStore.user?.rating || 1500 }} 积分</span>
            <span class="stat">{{ authStore.user?.games_count || 0 }} 对局</span>
            <span class="stat win-rate">{{ winRate }}% 胜率</span>
          </div>
        </div>
      </div>

      <!-- 操作按钮区 -->
      <div v-if="!isInRoom" class="lobby-actions">
        <button class="lobby-action-btn" @click="handleCreateRoom" :disabled="isCreatingRoom">
          <img :src="baseUrl + 'assets/svg/ui/icon-sword.svg'" alt="" class="btn-icon-w" />
          <span class="btn-label">{{ isCreatingRoom ? '创建中...' : '开始对局' }}</span>
        </button>

        <button class="lobby-action-btn" @click="handleOpenJoinRoom">
          <img :src="baseUrl + 'assets/svg/ui/icon-plus.svg'" alt="" class="btn-icon-w" />
          <span class="btn-label">加入对局</span>
        </button>

        <button class="lobby-action-btn" @click="handleMatch" :disabled="matchStore.isMatchmaking">
          <img :src="baseUrl + 'assets/svg/ui/icon-refresh.svg'" alt="" class="btn-icon-w" />
          <span class="btn-label">快速匹配</span>
        </button>

        <button class="lobby-action-btn" @click="showPvEDialog = true">
          <img :src="baseUrl + 'assets/svg/ui/icon-ai.svg'" alt="" class="btn-icon-w" />
          <span class="btn-label">人机对弈</span>
        </button>

        <button class="lobby-action-btn" @click="goToSettings">
          <img :src="baseUrl + 'assets/svg/ui/icon-settings.svg'" alt="" class="btn-icon-w" />
          <span class="btn-label">系统设置</span>
        </button>
      </div>

      <!-- 底部快捷链接 -->
      <div v-if="!isInRoom" class="lobby-links">
        <button class="lobby-link-item" @click="activeOverlay = 'rankings'">
          <img :src="baseUrl + 'assets/svg/ui/icon-trophy.svg'" alt="" class="link-icon" />
          排行榜
        </button>
        <button class="lobby-link-item" @click="activeOverlay = 'history'">
          <img :src="baseUrl + 'assets/svg/ui/icon-clock.svg'" alt="" class="link-icon" />
          历史记录
        </button>
        <button class="lobby-link-item" @click="handleLogout">
          <img :src="baseUrl + 'assets/svg/ui/icon-exit.svg'" alt="" class="link-icon" />
          退出登录
        </button>
      </div>
    </main>

    <!-- 快速匹配全屏 overlay -->
    <Transition name="overlay">
      <div v-if="activeOverlay === 'matchmaking'" class="lobby-overlay">
        <div class="match-overlay-content">
          <div class="match-spinner"></div>
          <h3 class="match-title">正在查找对手中......</h3>
          <div class="match-timer">{{ matchElapsed }}</div>
          <button
            class="btn btn-secondary match-cancel-btn"
            :disabled="!matchStore.isMatchmaking"
            @click="handleCancelMatch"
          >
            取消匹配
          </button>
        </div>
      </div>
    </Transition>

    <!-- 加入房间全屏 overlay -->
    <Transition name="overlay">
      <div v-if="activeOverlay === 'joinRoom'" class="lobby-overlay">
        <div class="overlay-header">
          <h3 class="overlay-title">
            <img :src="baseUrl + 'assets/svg/ui/icon-plus.svg'" alt="" class="title-icon" />
            加入房间
          </h3>
          <button class="overlay-close" @click="activeOverlay = ''">
            <img :src="baseUrl + 'assets/svg/ui/icon-close.svg'" alt="关闭" />
          </button>
        </div>
        <div class="overlay-body room-list-body">
          <!-- 加载中 -->
          <div v-if="isFetchingRooms" class="room-list-loading">
            <div class="loading-spinner"></div>
            <span>正在获取房间列表...</span>
          </div>
          <!-- 房间列表 -->
          <div v-else-if="availableRooms.length > 0" class="room-list-grid">
            <button
              v-for="room in availableRooms"
              :key="room.room_id"
              class="room-card"
              :class="{ selected: selectedRoomId === room.room_id }"
              @click="selectedRoomId = room.room_id"
            >
              <div class="room-card-header">
                <span class="room-card-id">#{{ room.room_id.slice(0, 8) }}</span>
                <span class="room-card-phase" :class="room.phase">{{ room.phase === 'waiting' ? '等待中' : room.phase === 'ready' ? '已就绪' : '对局中' }}</span>
              </div>
              <div class="room-card-players">
                <div v-if="room.red_player" class="room-card-player">
                  <span class="player-side red">红</span>
                  <span class="player-name">{{ room.red_player.username }}</span>
                  <span class="player-rating">{{ room.red_player.rating }}</span>
                </div>
                <div v-else class="room-card-player empty">
                  <span class="player-side red">红</span>
                  <span class="player-name">空位</span>
                </div>
                <div v-if="room.black_player" class="room-card-player">
                  <span class="player-side black">黑</span>
                  <span class="player-name">{{ room.black_player.username }}</span>
                  <span class="player-rating">{{ room.black_player.rating }}</span>
                </div>
                <div v-else class="room-card-player empty">
                  <span class="player-side black">黑</span>
                  <span class="player-name">空位</span>
                </div>
              </div>
            </button>
          </div>
          <!-- 空列表 -->
          <div v-else class="empty-hint">暂无可加入的房间</div>
        </div>
        <div class="overlay-footer">
          <button class="btn btn-secondary" @click="activeOverlay = ''">取消</button>
          <button class="btn btn-primary" :disabled="!selectedRoomId || isJoiningRoom" @click="handleJoinSelectedRoom">
            {{ isJoiningRoom ? '加入中...' : '确定' }}
          </button>
        </div>
      </div>
    </Transition>

    <!-- PvE 难度选择弹窗 -->
    <Transition name="overlay">
      <div v-if="showPvEDialog" class="lobby-overlay" @click.self="showPvEDialog = false">
        <div class="overlay-header">
          <h3 class="overlay-title">
            <img :src="baseUrl + 'assets/svg/ui/icon-ai.svg'" alt="" class="title-icon" />
            人机对战
          </h3>
          <button class="overlay-close" @click="showPvEDialog = false">
            <img :src="baseUrl + 'assets/svg/ui/icon-close.svg'" alt="关闭" />
          </button>
        </div>
        <div class="overlay-body">
          <p class="form-label">选择AI难度</p>
          <div class="difficulty-options">
            <button
              v-for="d in 5"
              :key="d"
              class="difficulty-btn"
              :class="{ active: selectedDifficulty === d }"
              @click="selectedDifficulty = d"
            >
              {{ ['', '简单', '中等', '困难', '大师', '宗师'][d] }}
            </button>
          </div>
        </div>
        <div class="overlay-footer">
          <button class="btn btn-secondary" @click="showPvEDialog = false">取消</button>
          <button class="btn btn-primary" @click="handleCreatePvERoom">开始对局</button>
        </div>
      </div>
    </Transition>

    <!-- 排行榜弹窗 -->
    <Transition name="overlay">
      <div v-if="activeOverlay === 'rankings'" class="lobby-overlay" @click.self="activeOverlay = ''">
        <div class="overlay-header">
          <h3 class="overlay-title">
            <img :src="baseUrl + 'assets/svg/ui/icon-trophy.svg'" alt="" class="title-icon" />
            排行榜
          </h3>
          <button class="overlay-close" @click="activeOverlay = ''">
            <img :src="baseUrl + 'assets/svg/ui/icon-close.svg'" alt="关闭" />
          </button>
        </div>
        <div class="overlay-body">
          <div v-for="(item, index) in rankings" :key="item.user_id" class="popup-rank-item">
            <span v-if="index < 3" class="popup-rank" :class="`rank-${index}`">{{ index + 1 }}</span>
            <span v-else class="popup-rank-text">{{ index + 1 }}</span>
            <div class="popup-rank-name">{{ item.nickname || item.username }}</div>
            <div class="popup-rank-score">{{ item.rating }}</div>
          </div>
          <div v-if="rankings.length === 0" class="empty-hint">暂无数据</div>
        </div>
      </div>
    </Transition>

    <!-- 历史对局弹窗 -->
    <Transition name="overlay">
      <div v-if="activeOverlay === 'history'" class="lobby-overlay" @click.self="activeOverlay = ''">
        <div class="overlay-header">
          <h3 class="overlay-title">
            <img :src="baseUrl + 'assets/svg/ui/icon-clock.svg'" alt="" class="title-icon" />
            历史对局
          </h3>
          <button class="overlay-close" @click="activeOverlay = ''">
            <img :src="baseUrl + 'assets/svg/ui/icon-close.svg'" alt="关闭" />
          </button>
        </div>
        <div class="overlay-body">
          <div v-for="item in history" :key="item.game_id" class="popup-history-item">
            <span class="popup-result" :class="getResultClass(item.result)">{{ getResultLabel(item.result) }}</span>
            <span class="popup-opponent">{{ item.opponent?.username || 'AI' }}</span>
            <span class="popup-date">{{ formatTime(new Date(item.played_at).getTime() / 1000) }}</span>
          </div>
          <div v-if="history.length === 0" class="empty-hint">暂无对局记录</div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.lobby-page {
  min-height: 100vh;
  background: var(--color-bg-primary);
}

.lobby-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-6);
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-wood-light);
  box-shadow: var(--shadow-sm);
}

.brand-name-img {
  width: 180px;
  height: 48px;
}

.header-links {
  display: flex;
  align-items: center;
  gap: 4px;
}

.header-link-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--color-text-secondary);
  background: none;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
}

.header-link-btn:hover {
  color: var(--color-gold-dark);
  background: rgba(217, 119, 6, 0.08);
}

.btn-icon-sm {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.lobby-main {
  max-width: 480px;
  margin: 0 auto;
  padding: var(--space-6) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

/* 玩家信息卡 */
.lobby-player-card {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-5);
  background: var(--color-bg-card);
  border: 2px solid var(--color-gold);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md), 0 0 0 1px var(--color-gold-light);
}

.player-detail {
  flex: 1;
  min-width: 0;
}

.player-name {
  font-family: var(--font-serif);
  font-size: var(--text-xl);
  font-weight: var(--weight-bold);
  color: var(--color-text-primary);
  margin-bottom: var(--space-1);
}

.player-stats {
  display: flex;
  gap: var(--space-3);
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}

.avatar-img {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
}

.win-rate {
  color: var(--color-success);
  font-weight: var(--weight-semibold);
}

/* 操作按钮区 */
.lobby-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
}

.lobby-action-btn {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  max-width: 360px;
  padding: var(--space-4) var(--space-5);
  background: var(--color-bg-card);
  border: 1px solid var(--color-wood-light);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--transition-fast);
  min-height: 52px;
}

.lobby-action-btn:hover {
  border-color: var(--color-gold);
  background: var(--color-bg-secondary);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.lobby-action-btn:active {
  transform: translateY(0);
}

.lobby-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.btn-icon-w {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
}

.btn-label {
  font-family: var(--font-serif);
  font-size: var(--text-lg);
  font-weight: var(--weight-semibold);
  color: var(--color-wood);
}

/* 匹配全屏 overlay */
.match-overlay-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: var(--space-5);
  padding: var(--space-8);
}

.match-spinner {
  width: 56px;
  height: 56px;
  border: 4px solid var(--color-wood-light);
  border-top-color: var(--color-gold);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.match-title {
  font-family: var(--font-serif);
  font-size: var(--text-xl);
  font-weight: var(--weight-bold);
  color: var(--color-text-primary);
}

.match-timer {
  font-family: var(--font-mono);
  font-size: var(--text-3xl);
  font-weight: var(--weight-bold);
  color: var(--color-gold);
  letter-spacing: 0.05em;
}

.match-cancel-btn {
  margin-top: var(--space-4);
  min-width: 160px;
}

/* 加入房间 overlay */
.room-list-body {
  display: flex;
  flex-direction: column;
}

.room-list-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-8) 0;
  color: var(--color-text-tertiary);
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--color-wood-light);
  border-top-color: var(--color-gold);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.room-list-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-3);
  overflow-y: auto;
  flex: 1;
}

.room-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4);
  background: var(--color-bg-card);
  border: 2px solid var(--color-wood-light);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
  font-family: inherit;
  font-size: inherit;
  color: inherit;
}

.room-card:hover {
  border-color: var(--color-gold);
  background: var(--color-bg-secondary);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.room-card.selected {
  border-color: var(--color-gold);
  background: rgba(217, 119, 6, 0.06);
  box-shadow: 0 0 0 1px var(--color-gold);
}

.room-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.room-card-id {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.room-card-phase {
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
}

.room-card-phase.waiting {
  background: rgba(217, 119, 6, 0.1);
  color: var(--color-warning);
}

.room-card-phase.ready {
  background: rgba(37, 99, 235, 0.1);
  color: var(--color-info);
}

.room-card-phase.playing {
  background: rgba(5, 150, 105, 0.1);
  color: var(--color-success);
}

.room-card-players {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.room-card-player {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
}

.room-card-player.empty {
  color: var(--color-text-muted);
}

.player-side {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  font-weight: var(--weight-bold);
  color: white;
  flex-shrink: 0;
}

.player-side.red { background: #dc2626; }
.player-side.black { background: #1f2937; }

.room-card-player .player-name {
  flex: 1;
  color: var(--color-text-primary);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.room-card-player .player-rating {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}

/* 底部链接 */
.lobby-links {
  display: flex;
  justify-content: center;
  gap: var(--space-6);
  flex-wrap: wrap;
}

.lobby-link-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
  background: none;
  border: none;
}

.lobby-link-item:hover {
  color: var(--color-gold-dark);
  background: rgba(217, 119, 6, 0.06);
}

.link-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

/* 弹窗 — 排行榜/历史 */
.lobby-overlay {
  position: fixed;
  inset: 0;
  background: var(--color-bg-primary);
  z-index: var(--z-modal);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.overlay-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-5) var(--space-6);
  border-bottom: 1px solid var(--color-wood-light);
  flex-shrink: 0;
}

.overlay-header h3 {
  font-family: var(--font-serif);
  font-size: var(--text-xl);
  font-weight: var(--weight-bold);
  color: var(--color-text-primary);
}

.overlay-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.title-icon {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
}

.overlay-close {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--transition-fast);
  background: var(--color-bg-secondary);
}

.overlay-close img {
  width: 18px;
  height: 18px;
}

.overlay-close:hover {
  background: var(--color-wood-bg);
}

.overlay-body {
  flex: 1;
  padding: var(--space-4) var(--space-6);
}

.overlay-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-6);
  border-top: 1px solid var(--color-wood-light);
}

/* 排行条目 */
.popup-rank-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  transition: background var(--transition-fast);
}

.popup-rank-item:hover {
  background: var(--color-bg-secondary);
}

.popup-rank {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: var(--weight-bold);
  color: white;
  font-size: var(--text-sm);
  flex-shrink: 0;
}

.popup-rank.rank-0 { background: #eab308; }
.popup-rank.rank-1 { background: #9ca3af; }
.popup-rank.rank-2 { background: #b45309; }

.popup-rank-text {
  width: 32px;
  text-align: center;
  color: var(--color-text-tertiary);
  font-size: var(--text-sm);
  flex-shrink: 0;
}

.popup-rank-name {
  flex: 1;
  font-weight: var(--weight-medium);
  color: var(--color-text-primary);
}

.popup-rank-score {
  font-family: var(--font-mono);
  font-weight: var(--weight-bold);
  color: var(--color-wood);
}

/* 历史条目 */
.popup-history-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-bg-secondary);
}

.popup-result {
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
  flex-shrink: 0;
}

.popup-result.win { background: rgba(5, 150, 105, 0.1); color: var(--color-success); }
.popup-result.lose { background: rgba(220, 38, 38, 0.1); color: var(--color-error); }
.popup-result.draw { background: rgba(217, 119, 6, 0.1); color: var(--color-warning); }

.popup-opponent {
  flex: 1;
  color: var(--color-text-primary);
}

.popup-date {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}

.empty-hint {
  text-align: center;
  color: var(--color-text-muted);
  padding: var(--space-8) 0;
}

/* 难度选择 */
.difficulty-options {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.difficulty-btn {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-wood-light);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
}

.difficulty-btn.active {
  background: var(--color-gold);
  color: white;
  border-color: var(--color-gold-dark);
}

.difficulty-btn:hover:not(.active) {
  border-color: var(--color-gold);
  background: var(--color-wood-bg);
}

/* Overlay 动画 */
.overlay-enter-active {
  transition: all 0.3s ease-out;
}
.overlay-leave-active {
  transition: all 0.2s ease-in;
}
.overlay-enter-from {
  opacity: 0;
  transform: translateX(100%);
}
.overlay-leave-to {
  opacity: 0;
  transform: translateX(100%);
}

@media (max-width: 768px) {
  .lobby-header {
    flex-direction: column;
    gap: var(--space-3);
  }
  .brand-name-img {
    width: 150px;
    height: 40px;
  }
  .header-link-btn span {
    display: none;
  }
  .header-link-btn {
    padding: 8px;
  }
  .btn-icon-sm {
    width: 22px;
    height: 22px;
  }
  .lobby-action-btn {
    max-width: 100%;
  }
  .lobby-links {
    flex-direction: column;
    align-items: center;
  }
}

@media (min-width: 640px) {
  .room-list-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 1024px) {
  .room-list-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
