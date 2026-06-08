<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useRoomStore } from '@/stores/room'
import { useMatchStore } from '@/stores/match'
import { useGameStore } from '@/stores/game'
import { wsClient } from '@/ws/client'
import { WSMsgType } from '@/ws/types'

const router = useRouter()
const authStore = useAuthStore()
const roomStore = useRoomStore()
const matchStore = useMatchStore()
const gameStore = useGameStore()

const rankings = ref<any[]>([])
const history = ref<any[]>([])
const isLoading = ref(false)

// 用户是否处于房间中（刷新恢复场景）
const isInRoom = computed(() => authStore.authState === 'in_room')

// PvP 创建房间等待状态
const isWaitingForOpponent = ref(isInRoom.value)
const isCreatingRoom = ref(false)

// PvE 难度选择
const showPvEDialog = ref(false)
const selectedDifficulty = ref(3)

// 计算胜率
const winRate = computed(() => {
  if (!authStore.user) return 0
  const games = authStore.user.games_count
  if (games === 0) return 0
  const wins = history.value.filter((h) => h.result === 'win').length
  return Math.round((wins / games) * 100)
})

// 监听匹配成功 → 跳转游戏
watch(() => matchStore.isMatchmaking, (val, oldVal) => {
  if (oldVal && !val && roomStore.currentRoom) {
    // 匹配成功，等待 game_start
  }
})

// 监听游戏开始 → 跳转
watch(() => gameStore.isGameStarted, (val, oldVal) => {
  console.log('[Lobby] isGameStarted changed:', oldVal, '->', val, 'currentRoom=', !!roomStore.currentRoom)
  if (val && roomStore.currentRoom) {
    isWaitingForOpponent.value = false
    console.log('[Lobby] Navigating to game:', roomStore.currentRoom.roomId)
    router.push(`/game/${roomStore.currentRoom.roomId}`)
  }
})

onMounted(async () => {
  // 如果用户在房间中（WAITING状态恢复），只显示等待卡片，不发大厅请求
  if (isInRoom.value) return

  // 消费断线重连提示
  const messages = authStore.consumeReconnectMessages()
  if (messages.length > 0) {
    ElMessageBox.alert(messages.join('\n'), '提示', {
      confirmButtonText: '确定',
      type: 'warning',
    })
  }

  await Promise.all([fetchRankings(), fetchHistory()])
})

onUnmounted(() => {
  // 组件卸载时不需要取消 WS 请求
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

// 创建 PvP 房间
async function handleCreateRoom() {
  isCreatingRoom.value = true
  try {
    await roomStore.createRoom('pvp')
    isWaitingForOpponent.value = true
    ElMessage.success('房间创建成功，等待对手加入...')
  } catch (error: any) {
    ElMessage.error(error.message || '创建房间失败')
  } finally {
    isCreatingRoom.value = false
  }
}

// 创建 PvE 房间
async function handleCreatePvERoom() {
  showPvEDialog.value = false
  isLoading.value = true
  try {
    await roomStore.createRoom('pve', selectedDifficulty.value)
    // PvE 创建后直接等待 game_start
    ElMessage.info('正在启动AI对局...')
  } catch (error: any) {
    ElMessage.error(error.message || '创建PvE房间失败')
  } finally {
    isLoading.value = false
  }
}

// 快速匹配
async function handleMatch() {
  try {
    await matchStore.joinMatch('pvp')
    ElMessage.info('正在匹配对手...')
  } catch (error: any) {
    ElMessage.error(error.message || '匹配失败')
  }
}

// 取消匹配
async function handleCancelMatch() {
  try {
    await matchStore.leaveMatch()
    ElMessage.info('已取消匹配')
  } catch (error: any) {
    ElMessage.error(error.message || '取消匹配失败')
  }
}

// 取消等待对手
async function handleCancelWaiting() {
  try {
    await roomStore.leaveRoom()
    isWaitingForOpponent.value = false
    ElMessage.info('已离开房间')
  } catch (error: any) {
    ElMessage.error(error.message || '离开房间失败')
  }
}

function handleLogout() {
  ElMessageBox.confirm('确定要退出登录吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(() => {
    authStore.logout()
    router.push('/login')
  })
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

function getResultType(result: string): 'success' | 'danger' | 'info' {
  switch (result) {
    case 'win':
      return 'success'
    case 'loss':
      return 'danger'
    default:
      return 'info'
  }
}
</script>

<template>
  <div class="lobby-page">
    <!-- 顶部导航 -->
    <header class="lobby-header">
      <div class="header-content">
        <h1>中国象棋</h1>
        <div class="header-right">
          <span class="username">{{ authStore.user?.nickname || authStore.user?.username }}</span>
          <el-button type="warning" size="small" @click="handleLogout">退出</el-button>
        </div>
      </div>
    </header>

    <main class="lobby-main">
      <div class="main-content">
        <div class="grid-container">
          <!-- 左侧：用户信息和操作 -->
          <div class="left-column">
            <!-- 用户信息卡片 -->
            <div class="user-card card">
              <div class="user-header">
                <div class="user-avatar">
                  {{ (authStore.user?.nickname || authStore.user?.username || '?')[0].toUpperCase() }}
                </div>
                <div class="user-info">
                  <h2>{{ authStore.user?.nickname || authStore.user?.username }}</h2>
                  <p class="text-muted">@{{ authStore.user?.username }}</p>
                </div>
              </div>
              <div class="user-stats">
                <div class="stat-item">
                  <div class="stat-value">{{ authStore.user?.rating || 1500 }}</div>
                  <div class="stat-label">积分</div>
                </div>
                <div class="stat-item">
                  <div class="stat-value">{{ authStore.user?.games_count || 0 }}</div>
                  <div class="stat-label">对局</div>
                </div>
                <div class="stat-item">
                  <div class="stat-value green">{{ winRate }}%</div>
                  <div class="stat-label">胜率</div>
                </div>
              </div>
            </div>

            <!-- 操作按钮 (仅在非房间状态下显示) -->
            <div v-if="!isInRoom" class="action-card card">
              <el-button type="primary" size="large" class="full-width" :loading="isCreatingRoom" @click="handleCreateRoom">
                创建PvP房间
              </el-button>
              <el-button type="success" size="large" class="full-width" @click="showPvEDialog = true">
                PvE 人机对战
              </el-button>
              <el-button size="large" class="full-width" @click="router.push('/rooms')">
                房间列表
              </el-button>
            </div>

            <!-- 快速匹配 (仅在非房间状态下显示) -->
            <div v-if="!isInRoom" class="match-card card">
              <h3>快速匹配</h3>
              <p class="text-muted">自动匹配实力相近的对手，开始一场紧张刺激的对局！</p>
              <el-button
                v-if="!matchStore.isMatchmaking"
                type="warning"
                size="large"
                class="full-width"
                @click="handleMatch"
              >
                开始匹配
              </el-button>
              <div v-else class="match-status">
                <div class="match-waiting">
                  <div class="loading-spinner-small"></div>
                  <span>匹配中... (约{{ matchStore.estimatedWait }}秒)</span>
                </div>
                <el-button type="info" size="large" class="full-width" @click="handleCancelMatch">
                  取消匹配
                </el-button>
              </div>
            </div>

            <!-- 等待对手 (创建房间后 或 刷新恢复) -->
            <div v-if="isWaitingForOpponent || isInRoom" class="waiting-card card">
              <h3>等待对手加入</h3>
              <p class="text-muted">房间号: {{ roomStore.currentRoom?.roomId?.slice(0, 8) }}</p>
              <div class="waiting-animation">
                <div class="loading-spinner-small"></div>
                <span>等待中...</span>
              </div>
              <el-button type="danger" size="large" class="full-width" @click="handleCancelWaiting">
                取消等待
              </el-button>
            </div>
          </div>

          <!-- 中间：排行榜 (仅在非房间状态下显示) -->
          <div v-if="!isInRoom" class="rankings-card card">
            <h3 class="section-title">
              <span class="icon">🏆</span> 排行榜
            </h3>
            <div class="rankings-list">
              <div v-for="(item, index) in rankings" :key="item.user_id" class="ranking-item">
                <span v-if="index < 3" class="rank-badge" :class="`rank-${index}`">{{ index + 1 }}</span>
                <span v-else class="rank-number">{{ index + 1 }}</span>
                <div class="ranking-info">
                  <div class="ranking-name">{{ item.nickname || item.username }}</div>
                  <div class="ranking-games text-muted">{{ item.games_count }} 局</div>
                </div>
                <div class="ranking-score">
                  <div class="score-value">{{ item.rating }}</div>
                  <div class="score-label text-muted">积分</div>
                </div>
              </div>
              <div v-if="rankings.length === 0" class="empty-state">暂无数据</div>
            </div>
          </div>

          <!-- 右侧：最近对局 (仅在非房间状态下显示) -->
          <div v-if="!isInRoom" class="history-card card">
            <h3 class="section-title">
              <span class="icon">📜</span> 最近对局
            </h3>
            <div class="history-list">
              <div v-for="item in history" :key="item.game_id" class="history-item">
                <div class="history-header">
                  <span class="history-time text-muted">{{ formatTime(new Date(item.played_at).getTime() / 1000) }}</span>
                  <el-tag :type="getResultType(item.result)" size="small">
                    {{ item.result === 'win' ? '胜' : item.result === 'loss' ? '负' : '和' }}
                  </el-tag>
                </div>
                <div class="history-detail">
                  <span class="history-side" :class="item.my_side === 'red' ? 'red' : 'black'">
                    {{ item.my_side === 'red' ? '红' : '黑' }}
                  </span>
                  <span>vs</span>
                  <span>{{ item.opponent?.username || 'AI' }}</span>
                  <span v-if="item.rating_change !== 0" class="rating-change" :class="item.rating_change > 0 ? 'positive' : 'negative'">
                    {{ item.rating_change > 0 ? '+' : '' }}{{ item.rating_change }}
                  </span>
                </div>
              </div>
              <div v-if="history.length === 0" class="empty-state">暂无对局记录</div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- PvE 难度选择弹窗 -->
    <el-dialog v-model="showPvEDialog" title="人机对战" width="400px">
      <div class="difficulty-selector">
        <p>选择AI难度：</p>
        <el-slider
          v-model="selectedDifficulty"
          :min="1"
          :max="5"
          :step="1"
          :marks="{ 1: '简单', 2: '中等', 3: '困难', 4: '大师', 5: '宗师' }"
        />
      </div>
      <template #footer>
        <el-button @click="showPvEDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreatePvERoom">开始对局</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.lobby-page {
  min-height: 100vh;
  background: linear-gradient(135deg, var(--color-wood-100) 0%, var(--color-wood-200) 100%);
}

.lobby-header {
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

.username {
  color: var(--color-wood-200);
}

.lobby-main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 16px;
}

.grid-container {
  display: grid;
  grid-template-columns: 1fr;
  gap: 24px;
}

@media (min-width: 1024px) {
  .grid-container {
    grid-template-columns: 280px 1fr 1fr;
  }
}

.card {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(139, 90, 43, 0.15);
  padding: 24px;
}

.el-button + .el-button {
  margin-left: 0 !important;   /* 取消横向间距 */
}

.left-column {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.user-card {
  padding: 24px;
}

.user-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.user-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--color-wood-200);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  font-weight: bold;
  color: var(--color-wood-600);
}

.user-info h2 {
  font-size: 1.25rem;
  font-weight: bold;
  margin-bottom: 4px;
}

.text-muted {
  color: #6b7280;
  font-size: 0.875rem;
}

.user-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  text-align: center;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: bold;
  color: var(--color-wood-600);
}

.stat-value.green {
  color: #22c55e;
}

.stat-label {
  font-size: 0.875rem;
  color: #6b7280;
}

.action-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.match-card h3 {
  font-size: 1.125rem;
  font-weight: bold;
  margin-bottom: 12px;
}

.match-card p {
  margin-bottom: 16px;
}

.match-status {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.match-waiting {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
  color: var(--color-wood-500);
}

.waiting-card {
  border: 2px solid var(--color-wood-300);
  text-align: center;
}

.waiting-card h3 {
  margin-bottom: 8px;
}

.waiting-animation {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
  margin: 16px 0;
  color: var(--color-wood-500);
}

.loading-spinner-small {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(139, 90, 43, 0.3);
  border-top-color: var(--color-wood-500);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.full-width {
  width: 100%;
}

.section-title {
  font-size: 1.25rem;
  font-weight: bold;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.icon {
  font-size: 1.25rem;
}

.rankings-list,
.history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ranking-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  transition: background-color 0.2s;
}

.ranking-item:hover {
  background: var(--color-wood-50);
}

.rank-badge {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  color: white;
}

.rank-badge.rank-0 { background: #eab308; }
.rank-badge.rank-1 { background: #9ca3af; }
.rank-badge.rank-2 { background: #b45309; }

.rank-number {
  width: 32px;
  text-align: center;
  color: #6b7280;
}

.ranking-info { flex: 1; }
.ranking-name { font-weight: 500; }
.ranking-games { font-size: 0.875rem; }
.ranking-score { text-align: right; }
.score-value { font-weight: bold; color: var(--color-wood-600); }
.score-label { font-size: 0.875rem; }

.history-item {
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  transition: border-color 0.2s;
}

.history-item:hover { border-color: var(--color-wood-300); }

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.history-time { font-size: 0.875rem; }

.history-detail {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.875rem;
}

.history-side.red { color: var(--color-piece-red); font-weight: 500; }
.history-side.black { color: #1f2937; }
.rating-change.positive { color: #22c55e; }
.rating-change.negative { color: #ef4444; }

.empty-state {
  text-align: center;
  color: #6b7280;
  padding: 32px 0;
}

.difficulty-selector {
  padding: 16px 0;
}

.difficulty-selector p {
  margin-bottom: 16px;
  font-weight: 500;
}
</style>
