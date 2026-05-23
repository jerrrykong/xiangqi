<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useRoomStore } from '@/stores/room'
import { useGameStore } from '@/stores/game'
import { watch } from 'vue'

const router = useRouter()
const roomStore = useRoomStore()
const gameStore = useGameStore()

const currentPage = ref(1)
const pageSize = ref(20)
const hasError = ref(false)

// 监听游戏开始 → 跳转
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
    ElMessage.error(error.message || '获取房间列表失败')
  }
}

async function handleJoinRoom(room: any) {
  try {
    await roomStore.joinRoom(room.room_id)
    // 加入成功 → 跳转到 Game 页面
    router.push(`/game/${roomStore.currentRoom!.roomId}`)
  } catch (error: any) {
    ElMessage.error(error.message || '加入房间失败')
  }
}

async function handleCreateRoom() {
  try {
    await roomStore.createRoom('pvp')
    // 创建成功 → 跳转到 Game 页面等待对手
    router.push(`/game/${roomStore.currentRoom!.roomId}`)
  } catch (error: any) {
    ElMessage.error(error.message || '创建房间失败')
  }
}

function handlePageChange(page: number) {
  currentPage.value = page
  fetchRooms()
}

function getStatusTagType(phase: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' {
  switch (phase) {
    case 'waiting': return 'success'
    case 'playing': return 'danger'
    case 'finished': return 'info'
    default: return 'info'
  }
}

function getStatusText(phase: string): string {
  switch (phase) {
    case 'waiting': return '等待中'
    case 'playing': return '对战中'
    case 'finished': return '已结束'
    default: return phase
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
        <div class="header-left">
          <h1>房间列表</h1>
        </div>
        <div class="header-right">
          <el-button @click="fetchRooms">刷新</el-button>
          <el-button type="primary" @click="router.push('/lobby')">返回大厅</el-button>
        </div>
      </div>
    </header>

    <main class="room-main">
      <div class="main-content">
        <!-- 创建房间按钮 -->
        <div class="action-bar">
          <el-button type="primary" size="large" @click="handleCreateRoom">
            <span class="btn-icon">🎮</span> 创建房间
          </el-button>
        </div>

        <!-- 加载中 -->
        <div v-if="roomStore.isLoading && roomStore.roomList.length === 0" class="center-message">
          <div class="loading-spinner"></div>
          <div class="loading-text">加载中...</div>
        </div>

        <!-- 加载失败 -->
        <div v-else-if="hasError" class="center-message">
          <div class="empty-icon">❌</div>
          <div class="empty-title">加载失败</div>
          <div class="empty-text">获取房间列表失败，请重试</div>
          <el-button type="primary" class="retry-button" @click="fetchRooms">
            重新加载
          </el-button>
        </div>

        <!-- 空状态 -->
        <div v-else-if="roomStore.roomList.length === 0" class="center-message">
          <div class="empty-icon">🎯</div>
          <div class="empty-title">没有任何游戏房间</div>
          <div class="empty-text">快来创建第一个房间吧！</div>
          <el-button type="primary" class="retry-button" @click="handleCreateRoom">
            创建房间
          </el-button>
        </div>

        <!-- 房间列表 -->
        <div v-else class="room-grid">
          <div
            v-for="room in roomStore.roomList"
            :key="room.room_id"
            class="room-card"
            @click="handleJoinRoom(room)"
          >
            <!-- 房间状态标签 -->
            <div class="card-header">
              <el-tag :type="getStatusTagType(room.phase)" size="large">
                {{ getStatusText(room.phase) }}
              </el-tag>
              <span class="room-id">房间号: {{ room.room_id.slice(0, 8) }}</span>
            </div>

            <!-- 红方信息 -->
            <div class="player-row red-side">
              <div class="player-label">红方</div>
              <div class="player-info">
                <span class="player-name">
                  {{ room.red_player?.username || '等待加入...' }}
                </span>
                <span v-if="room.red_player?.rating" class="player-rating">
                  {{ room.red_player.rating }}分
                </span>
              </div>
            </div>

            <!-- VS 分隔线 -->
            <div class="vs-divider">
              <span class="vs-text">VS</span>
            </div>

            <!-- 黑方信息 -->
            <div class="player-row black-side">
              <div class="player-label">黑方</div>
              <div class="player-info">
                <span class="player-name">
                  {{ room.black_player?.username || '等待加入...' }}
                </span>
                <span v-if="room.black_player?.rating" class="player-rating">
                  {{ room.black_player.rating }}分
                </span>
              </div>
            </div>

            <!-- 房间底部信息 -->
            <div class="card-footer">
              <span class="room-time">{{ formatTime(room.created_at) }}</span>
              <el-button type="primary" size="small" @click.stop="handleJoinRoom(room)">
                加入
              </el-button>
            </div>
          </div>
        </div>

        <!-- 分页 -->
        <div v-if="roomStore.totalRooms > pageSize" class="pagination-wrapper">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="roomStore.totalRooms"
            layout="prev, pager, next"
            @current-change="handlePageChange"
          />
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.room-list-page {
  min-height: 100vh;
  background: linear-gradient(135deg, var(--color-wood-100) 0%, var(--color-wood-200) 100%);
}

.room-header {
  background: var(--color-wood-600);
  color: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.header-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-content h1 {
  font-size: 1.5rem;
  font-weight: bold;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.room-main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 16px;
}

.main-content {
  width: 100%;
}

.action-bar {
  margin-bottom: 24px;
  display: flex;
  justify-content: flex-start;
}

.action-bar .btn-icon {
  margin-right: 8px;
}

.center-message {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  text-align: center;
}

.loading-spinner {
  width: 48px;
  height: 48px;
  border: 4px solid var(--color-wood-200);
  border-top-color: var(--color-wood-500);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  color: var(--color-wood-500);
  font-size: 1rem;
}

.empty-icon { font-size: 4rem; margin-bottom: 16px; }
.empty-title { font-size: 1.5rem; font-weight: bold; color: #374151; margin-bottom: 8px; }
.empty-text { color: #6b7280; font-size: 1rem; margin-bottom: 24px; }
.retry-button { margin-top: 8px; }

.room-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

.room-card {
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(139, 90, 43, 0.15);
  overflow: hidden;
  cursor: pointer;
  transition: all 0.3s ease;
}

.room-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 30px rgba(139, 90, 43, 0.25);
}

.card-header {
  background: var(--color-wood-600);
  color: white;
  padding: 12px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.room-id { font-size: 0.875rem; opacity: 0.9; }

.player-row {
  display: flex;
  align-items: center;
  padding: 16px;
  gap: 12px;
}

.red-side { background: linear-gradient(90deg, rgba(239, 68, 68, 0.1) 0%, transparent 100%); }
.black-side { background: linear-gradient(90deg, rgba(31, 41, 55, 0.1) 0%, transparent 100%); }

.player-label {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 0.875rem;
}

.red-side .player-label { background: #ef4444; color: white; }
.black-side .player-label { background: #1f2937; color: white; }

.player-info { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.player-name { font-weight: 500; color: #374151; }
.player-rating { font-size: 0.875rem; color: #6b7280; }

.vs-divider { display: flex; align-items: center; justify-content: center; padding: 8px 0; }
.vs-text {
  background: var(--color-wood-100);
  color: var(--color-wood-600);
  padding: 4px 16px;
  border-radius: 12px;
  font-weight: bold;
  font-size: 0.875rem;
}

.card-footer {
  padding: 12px 16px;
  border-top: 1px solid #f3f4f6;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fafafa;
}

.room-time { font-size: 0.875rem; color: #9ca3af; }
.pagination-wrapper { margin-top: 32px; display: flex; justify-content: center; }
</style>
