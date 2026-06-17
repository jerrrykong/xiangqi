/**
 * RoomList — 房间列表页面
 * 适配新设计系统，移除 Element Plus
 */
<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useRoomStore } from '@/stores/room'
import { useGameStore } from '@/stores/game'
import { showToast } from '@/components/common/ui'

const router = useRouter()
const roomStore = useRoomStore()
const gameStore = useGameStore()

const currentPage = ref(1)
const pageSize = ref(20)
const hasError = ref(false)

/** 监听游戏开始 */
watch(() => gameStore.isGameStarted, (val) => {
  if (val && roomStore.currentRoom) {
    router.push(`/game/${roomStore.currentRoom.roomId}`)
  }
})

onMounted(async () => {
  await fetchRooms()
})

async function fetchRooms() {
  hasError.value = false
  try {
    await roomStore.fetchRoomList(currentPage.value, pageSize.value)
  } catch (error: any) {
    hasError.value = true
    showToast(error.message || '获取房间列表失败', 'error')
  }
}

async function handleJoinRoom(room: any) {
  try {
    await roomStore.joinRoom(room.room_id)
    router.push(`/game/${roomStore.currentRoom!.roomId}`)
  } catch (error: any) {
    showToast(error.message || '加入房间失败', 'error')
  }
}

async function handleCreateRoom() {
  try {
    await roomStore.createRoom('pvp')
    router.push(`/game/${roomStore.currentRoom!.roomId}`)
  } catch (error: any) {
    showToast(error.message || '创建房间失败', 'error')
  }
}

function handlePageChange(page: number) {
  currentPage.value = page
  fetchRooms()
}

function getStatusText(phase: string): string {
  switch (phase) {
    case 'waiting': return '等待中'
    case 'playing': return '对战中'
    case 'finished': return '已结束'
    default: return phase
  }
}

function getStatusClass(phase: string): string {
  switch (phase) {
    case 'waiting': return 'waiting'
    case 'playing': return 'playing'
    case 'finished': return 'finished'
    default: return ''
  }
}

function formatTime(dateStr: string): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}小时前`
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
</script>

<template>
  <div class="room-list-page">
    <!-- 顶部导航 -->
    <header class="room-header">
      <div class="header-content">
        <h1>房间列表</h1>
        <div class="header-actions">
          <button class="btn btn-secondary btn--sm" @click="fetchRooms">刷新</button>
          <button class="btn btn-primary btn--sm" @click="router.push('/lobby')">返回大厅</button>
        </div>
      </div>
    </header>

    <main class="room-main">
      <!-- 创建房间 -->
      <div class="action-bar">
        <button class="btn btn-primary" @click="handleCreateRoom">
          🎮 创建房间
        </button>
      </div>

      <!-- 加载中 -->
      <div v-if="roomStore.isLoading && roomStore.roomList.length === 0" class="center-message">
        <div class="loading-spinner"></div>
        <p class="loading-text">加载中...</p>
      </div>

      <!-- 加载失败 -->
      <div v-else-if="hasError" class="center-message">
        <p class="empty-title">加载失败</p>
        <p class="empty-text">获取房间列表失败，请重试</p>
        <button class="btn btn-primary" @click="fetchRooms">重新加载</button>
      </div>

      <!-- 空状态 -->
      <div v-else-if="roomStore.roomList.length === 0" class="center-message">
        <p class="empty-title">没有任何游戏房间</p>
        <p class="empty-text">快来创建第一个房间吧！</p>
        <button class="btn btn-primary" @click="handleCreateRoom">创建房间</button>
      </div>

      <!-- 房间列表 -->
      <div v-else class="room-grid">
        <div
          v-for="room in roomStore.roomList"
          :key="room.room_id"
          class="room-card"
          @click="handleJoinRoom(room)"
        >
          <div class="card-header">
            <span class="room-status" :class="getStatusClass(room.phase)">{{ getStatusText(room.phase) }}</span>
            <span class="room-id">{{ room.room_id.slice(0, 8) }}</span>
          </div>
          <div class="card-players">
            <div class="player-row red-side">
              <span class="side-label">红方</span>
              <span class="player-name">{{ room.red_player?.username || '等待加入...' }}</span>
            </div>
            <div class="vs-divider">VS</div>
            <div class="player-row black-side">
              <span class="side-label">黑方</span>
              <span class="player-name">{{ room.black_player?.username || '等待加入...' }}</span>
            </div>
          </div>
          <div class="card-footer">
            <span class="room-time">{{ formatTime(room.created_at) }}</span>
            <button class="btn btn-primary btn--sm" @click.stop="handleJoinRoom(room)">加入</button>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="roomStore.totalRooms > pageSize" class="pagination-wrapper">
        <button class="btn btn-secondary btn--sm" :disabled="currentPage <= 1" @click="handlePageChange(currentPage - 1)">上一页</button>
        <span class="page-info">{{ currentPage }}</span>
        <button class="btn btn-secondary btn--sm" @click="handlePageChange(currentPage + 1)">下一页</button>
      </div>
    </main>
  </div>
</template>

<style scoped>
.room-list-page {
  min-height: 100vh;
  background: var(--color-bg-primary);
}

.room-header {
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-wood-light);
  box-shadow: var(--shadow-sm);
}

.header-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: var(--space-4) var(--space-6);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-content h1 {
  font-family: var(--font-serif);
  font-size: var(--text-2xl);
  font-weight: var(--weight-bold);
  color: var(--color-text-primary);
}

.header-actions {
  display: flex;
  gap: var(--space-3);
}

.room-main {
  max-width: 1200px;
  margin: 0 auto;
  padding: var(--space-6) var(--space-4);
}

.action-bar {
  margin-bottom: var(--space-6);
}

.center-message {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  text-align: center;
  gap: var(--space-3);
}

.loading-spinner {
  width: 48px;
  height: 48px;
  border: 4px solid var(--color-wood-light);
  border-top-color: var(--color-gold);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  color: var(--color-text-tertiary);
}

.empty-title {
  font-size: var(--text-xl);
  font-weight: var(--weight-bold);
  color: var(--color-text-primary);
}

.empty-text {
  color: var(--color-text-tertiary);
}

.room-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-5);
}

.room-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-wood-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.room-card:hover {
  border-color: var(--color-gold);
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
}

.card-header {
  background: var(--color-wood);
  color: var(--color-text-inverse);
  padding: var(--space-3) var(--space-4);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.room-status {
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
}

.room-status.waiting { background: var(--color-success); }
.room-status.playing { background: var(--color-error); }
.room-status.finished { background: rgba(255,255,255,0.2); }

.room-id {
  font-size: var(--text-xs);
  opacity: 0.8;
}

.card-players {
  padding: var(--space-4);
}

.player-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) 0;
}

.side-label {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-xs);
  font-weight: var(--weight-bold);
  flex-shrink: 0;
}

.red-side .side-label {
  background: var(--color-error);
  color: white;
}

.black-side .side-label {
  background: #2D3748;
  color: white;
}

.player-name {
  font-weight: var(--weight-medium);
  color: var(--color-text-primary);
}

.vs-divider {
  text-align: center;
  padding: var(--space-1) 0;
  color: var(--color-text-muted);
  font-weight: var(--weight-bold);
  font-size: var(--text-sm);
}

.card-footer {
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--color-bg-secondary);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.room-time {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}

.pagination-wrapper {
  margin-top: var(--space-8);
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--space-4);
}

.page-info {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}
</style>
