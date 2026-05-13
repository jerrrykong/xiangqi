<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useRoomStore } from '@/stores/room'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const roomStore = useRoomStore()

const roomId = computed(() => route.params.id as string)
const isOwner = computed(() => {
  if (!roomStore.currentRoom) return false
  return authStore.user?.user_id !== undefined
})

// 轮询房间状态
let pollInterval: number | null = null

onMounted(async () => {
  // 如果没有房间信息，获取房间详情
  if (!roomStore.currentRoom || roomStore.currentRoom.roomId !== roomId.value) {
    try {
      await roomStore.joinRoom(roomId.value)
    } catch (error: any) {
      ElMessage.error('房间不存在或已关闭')
      router.push('/lobby')
      return
    }
  }

  // 轮询房间状态
  pollInterval = window.setInterval(pollRoomStatus, 3000)
})

onUnmounted(() => {
  if (pollInterval) {
    clearInterval(pollInterval)
  }
})

async function pollRoomStatus() {
  // 如果游戏已开始，跳转到游戏页面
  if (roomStore.currentRoom?.gameStarted && roomStore.currentRoom?.gameWsUrl) {
    router.push(`/game/${roomId.value}`)
  }
}

async function handleReady() {
  try {
    const response = await roomStore.playerReady()
    if (response.game_started) {
      ElMessage.success('游戏开始！')
      // 等待一小段时间让后端准备好 WebSocket
      setTimeout(() => {
        router.push(`/game/${roomId.value}`)
      }, 1000)
    }
  } catch (error: any) {
    const message = error.response?.data?.message || '准备失败'
    ElMessage.error(message)
  }
}

async function handleLeave() {
  await ElMessageBox.confirm('确定要离开房间吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })

  try {
    await roomStore.leaveRoom()
    ElMessage.success('已离开房间')
    router.push('/lobby')
  } catch (error: any) {
    ElMessage.error('离开房间失败')
  }
}

async function handleDeleteRoom() {
  await ElMessageBox.confirm('确定要解散房间吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })

  try {
    await roomStore.deleteRoom()
    ElMessage.success('房间已解散')
    router.push('/lobby')
  } catch (error: any) {
    ElMessage.error('解散房间失败')
  }
}

function getReadyStatus(isReady: boolean, side: 'red' | 'black') {
  if (isReady) return '已准备'
  return side === roomStore.currentRoom?.yourSide ? '等待准备' : '等待加入'
}
</script>

<template>
  <div class="room-page">
    <!-- 顶部导航 -->
    <header class="room-header">
      <div class="header-content">
        <div class="header-left">
          <h1>游戏房间</h1>
          <span class="room-id">房间号: {{ roomId.slice(0, 8) }}</span>
        </div>
        <div class="header-right">
          <el-button @click="handleLeave">离开房间</el-button>
        </div>
      </div>
    </header>

    <main class="room-main">
      <div class="room-container">
        <div class="room-card card">
          <!-- 房间状态 -->
          <div class="room-status">
            <div class="status-badge" :class="roomStore.currentRoom?.status">
              {{
                roomStore.currentRoom?.status === 'waiting'
                  ? '等待玩家加入'
                  : roomStore.currentRoom?.status === 'ready'
                  ? '双方已就绪'
                  : '游戏进行中'
              }}
            </div>
          </div>

          <!-- 对局信息 -->
          <div class="players-container">
            <!-- 红方 -->
            <div class="player-box" :class="{ 'is-you': roomStore.currentRoom?.yourSide === 'red' }">
              <div class="player-emoji">🔴</div>
              <div class="player-title">
                {{ roomStore.currentRoom?.yourSide === 'red' ? '你 (红方)' : '红方' }}
              </div>
              <div v-if="roomStore.currentRoom?.redReady" class="ready-text">
                <span class="check">✓</span> 已准备
              </div>
              <div v-else class="waiting-text">等待中...</div>
            </div>

            <!-- VS -->
            <div class="vs-text">VS</div>

            <!-- 黑方 -->
            <div class="player-box black" :class="{ 'is-you': roomStore.currentRoom?.yourSide === 'black' }">
              <div class="player-emoji">⚫</div>
              <div class="player-title">
                {{ roomStore.currentRoom?.yourSide === 'black' ? '你 (黑方)' : '黑方' }}
              </div>
              <div v-if="roomStore.currentRoom?.opponent" class="opponent-name">
                {{ roomStore.currentRoom.opponent.username }}
              </div>
              <div v-else-if="roomStore.currentRoom?.blackReady" class="ready-text">
                <span class="check">✓</span> 已准备
              </div>
              <div v-else class="waiting-text">等待加入...</div>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="actions">
            <template v-if="!roomStore.currentRoom?.gameStarted">
              <el-button
                v-if="!roomStore.currentRoom?.redReady || !roomStore.currentRoom?.blackReady"
                type="primary"
                size="large"
                class="full-width"
                @click="handleReady"
              >
                {{ roomStore.currentRoom?.yourSide === 'red' && !roomStore.currentRoom?.redReady ? '准备' : '等待对方' }}
              </el-button>
            </template>

            <el-button
              v-if="roomStore.currentRoom?.gameStarted"
              type="success"
              size="large"
              class="full-width"
              @click="router.push(`/game/${roomId}`)"
            >
              进入对局
            </el-button>

            <div class="button-row" v-if="isOwner">
              <el-button type="danger" size="large" class="flex-1" @click="handleDeleteRoom">
                解散房间
              </el-button>
            </div>
          </div>

          <!-- 提示 -->
          <div class="tips">
            <p>红方先行，双方准备后游戏开始</p>
            <p>每方限时 10 分钟，超时判负</p>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.room-page {
  min-height: 100vh;
  background: linear-gradient(135deg, var(--color-wood-100) 0%, var(--color-wood-200) 100%);
}

.room-header {
  background: var(--color-wood-600);
  color: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.header-content {
  max-width: 800px;
  margin: 0 auto;
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left h1 {
  font-size: 1.5rem;
  font-weight: bold;
}

.room-id {
  color: var(--color-wood-200);
  font-size: 0.875rem;
}

.room-main {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px 16px;
}

.room-container {
  max-width: 600px;
  margin: 0 auto;
}

.room-card {
  padding: 32px;
}

.card {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(139, 90, 43, 0.15);
}

.room-status {
  text-align: center;
  margin-bottom: 32px;
}

.status-badge {
  display: inline-block;
  padding: 12px 24px;
  border-radius: 9999px;
  font-size: 1.125rem;
  font-weight: bold;
}

.status-badge.waiting {
  background: #fef3c7;
  color: #a16207;
}

.status-badge.ready {
  background: #dbeafe;
  color: #1e40af;
}

.status-badge.playing {
  background: #d1fae5;
  color: #047857;
}

.players-container {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 24px;
  align-items: center;
  margin-bottom: 24px;
}

.player-box {
  text-align: center;
  padding: 24px;
  border-radius: 12px;
  background: #f9fafb;
}

.player-box.is-you {
  background: #fef2f2;
  border: 2px solid #fca5a5;
}

.player-box.black {
  background: #f3f4f6;
}

.player-box.black.is-you {
  background: #1f2937;
  color: white;
  border: 2px solid #6b7280;
}

.player-emoji {
  font-size: 3rem;
  margin-bottom: 8px;
}

.player-title {
  font-weight: bold;
  font-size: 1.125rem;
  margin-bottom: 8px;
}

.ready-text {
  color: #22c55e;
  font-weight: 500;
}

.ready-text .check {
  margin-right: 4px;
}

.waiting-text {
  color: #9ca3af;
}

.opponent-name {
  color: #6b7280;
}

.vs-text {
  font-size: 2.5rem;
  font-weight: bold;
  color: var(--color-wood-400);
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 32px;
}

.full-width {
  width: 100%;
}

.button-row {
  display: flex;
  gap: 16px;
}

.flex-1 {
  flex: 1;
}

.tips {
  margin-top: 32px;
  text-align: center;
  color: #6b7280;
  font-size: 0.875rem;
}

.tips p {
  margin-bottom: 4px;
}
</style>
