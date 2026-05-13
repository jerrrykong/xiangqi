<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useRoomStore } from '@/stores/room'
import { useGameStore } from '@/stores/game'
import ChessBoard from '@/components/ChessBoard.vue'
import type { Position, Move } from '@/types/chess'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const roomStore = useRoomStore()
const gameStore = useGameStore()

const roomId = computed(() => route.params.id as string)

// 初始化游戏
onMounted(async () => {
  // 获取房间信息和 WebSocket 连接
  if (!roomStore.currentRoom || roomStore.currentRoom.roomId !== roomId.value) {
    try {
      await roomStore.joinRoom(roomId.value)
    } catch (error) {
      ElMessage.error('无法加入房间')
      router.push('/lobby')
      return
    }
  }

  // 连接游戏 WebSocket
  if (roomStore.currentRoom?.gameWsUrl && roomStore.currentRoom?.gameToken) {
    gameStore.connect(roomStore.currentRoom.gameWsUrl, roomStore.currentRoom.gameToken)
  } else {
    ElMessage.error('游戏连接信息不完整')
    router.push('/lobby')
  }
})

onUnmounted(() => {
  gameStore.disconnect()
})

// 格式化时间
function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

// 处理棋子点击
function handlePieceClick(position: Position) {
  gameStore.selectPiece(position)
}

// 处理位置点击
function handlePositionClick(position: Position) {
  if (!gameStore.isMyTurn || gameStore.isGameOver) return

  const { selectedPosition } = gameStore
  if (selectedPosition) {
    // 发送走棋
    const move: Move = {
      from_col: selectedPosition.col,
      from_row: selectedPosition.row,
      to_col: position.col,
      to_row: position.row,
    }
    gameStore.sendMove(move)
  }
}

// 认输
async function handleResign() {
  await ElMessageBox.confirm('确定要认输吗？', '确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
  gameStore.sendResign()
}

// 请求和棋
function handleDrawRequest() {
  gameStore.sendDrawRequest()
  ElMessage.info('已发送和棋请求')
}

// 返回大厅
function handleBack() {
  ElMessageBox.confirm('确定要返回大厅吗？当前对局将被判负', '警告', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(() => {
    gameStore.sendResign()
    router.push('/lobby')
  })
}

// 胜负结果描述
const resultDescription = computed(() => {
  if (!gameStore.gameResult) return ''

  const isWin =
    (gameStore.gameResult === 'RED_WINS' && gameStore.yourColor === 0) ||
    (gameStore.gameResult === 'BLACK_WINS' && gameStore.yourColor === 1)

  const resultText = isWin ? '胜利' : '失败'

  const reasonText =
    gameStore.gameReason === 'CHECKMATE'
      ? '将死'
      : gameStore.gameReason === 'RESIGN'
      ? '对手认输'
      : gameStore.gameReason === 'TIMEOUT'
      ? '超时'
      : ''

  return `${resultText} - ${reasonText}`
})
</script>

<template>
  <div class="game-page">
    <!-- 顶部信息栏 -->
    <header class="game-header">
      <div class="header-content">
        <div class="header-left">
          <h1>对局中</h1>
          <span class="room-id">房间号: {{ roomId.slice(0, 8) }}</span>
        </div>
        <div class="header-right">
          <span :class="{ 'my-turn': gameStore.isMyTurn }">
            {{ gameStore.isMyTurn ? '你的回合' : '对手回合' }}
          </span>
        </div>
      </div>
    </header>

    <!-- 游戏主区域 -->
    <main class="game-main">
      <div class="game-container">
        <!-- 左侧信息面板 -->
        <div class="side-panel left">
          <div class="player-card">
            <div class="player-avatar black">黑</div>
            <div class="player-info">
              <div class="player-name">{{ gameStore.yourColor === 1 ? authStore.user?.nickname : roomStore.currentRoom?.opponent?.username || '等待中' }}</div>
              <div class="player-label">{{ gameStore.yourColor === 1 ? '你' : '对手' }}</div>
            </div>
          </div>
          <div class="timer-card">
            <div class="timer-value">{{ formatTime(gameStore.blackTime) }}</div>
            <div class="timer-label">黑方剩余时间</div>
          </div>
        </div>

        <!-- 棋盘 -->
        <div class="board-container">
          <ChessBoard
            :board="gameStore.board"
            :selected-position="gameStore.selectedPosition"
            :last-move="gameStore.lastMove"
            :is-in-check="gameStore.isInCheck"
            :check-position="gameStore.checkPosition"
            :your-color="gameStore.yourColor"
            @piece-click="handlePieceClick"
            @position-click="handlePositionClick"
          />
          <!-- 将军提示 -->
          <div v-if="gameStore.isInCheck" class="check-alert">将军！</div>
        </div>

        <!-- 右侧信息面板 -->
        <div class="side-panel right">
          <div class="player-card">
            <div class="player-avatar red">红</div>
            <div class="player-info">
              <div class="player-name">{{ gameStore.yourColor === 0 ? authStore.user?.nickname : roomStore.currentRoom?.opponent?.username || '等待中' }}</div>
              <div class="player-label">{{ gameStore.yourColor === 0 ? '你' : '对手' }}</div>
            </div>
          </div>
          <div class="timer-card">
            <div class="timer-value red">{{ formatTime(gameStore.redTime) }}</div>
            <div class="timer-label">红方剩余时间</div>
          </div>
        </div>
      </div>
    </main>

    <!-- 底部操作栏 -->
    <footer class="game-footer">
      <div class="footer-content">
        <el-button type="danger" size="large" :disabled="gameStore.isGameOver" @click="handleResign">认输</el-button>
        <el-button type="warning" size="large" :disabled="gameStore.isGameOver" @click="handleDrawRequest">求和</el-button>
        <el-button size="large" @click="handleBack">返回大厅</el-button>
      </div>
    </footer>

    <!-- 游戏结束弹窗 -->
    <el-dialog
      v-model="gameStore.isGameOver"
      title="对局结束"
      width="400px"
      :close-on-click-modal="false"
      :show-close="false"
    >
      <div class="result-dialog">
        <div class="result-emoji">{{ gameStore.winner === gameStore.yourColor ? '🎉' : '😔' }}</div>
        <div class="result-text" :class="gameStore.winner === gameStore.yourColor ? 'win' : 'lose'">
          {{ resultDescription }}
        </div>
        <div class="result-reason">
          {{ gameStore.gameReason === 'CHECKMATE' ? '对方无子可走' : gameStore.gameReason === 'RESIGN' ? '对手认输' : '对局结束' }}
        </div>
      </div>
      <template #footer>
        <el-button type="primary" size="large" class="full-width" @click="router.push('/lobby')">返回大厅</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.game-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, var(--color-wood-100) 0%, var(--color-wood-200) 100%);
}

.game-header {
  background: var(--color-wood-600);
  color: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.header-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 12px 16px;
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
  font-size: 1.25rem;
  font-weight: bold;
}

.room-id {
  color: var(--color-wood-200);
  font-size: 0.875rem;
}

.my-turn {
  color: #4ade80;
  font-weight: bold;
}

.game-main {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.game-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
}

@media (min-width: 1024px) {
  .game-container {
    flex-direction: row;
  }
}

.side-panel {
  display: flex;
  flex-direction: row;
  gap: 16px;
  width: 100%;
}

@media (min-width: 1024px) {
  .side-panel {
    flex-direction: column;
    width: 200px;
  }
}

.side-panel.left {
  order: 1;
}

.side-panel.right {
  order: 3;
}

.board-container {
  position: relative;
  order: 2;
}

.player-card,
.timer-card {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(139, 90, 43, 0.15);
  padding: 16px;
}

.player-card {
  display: flex;
  align-items: center;
  gap: 12px;
}

.player-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: bold;
}

.player-avatar.black {
  background: var(--color-piece-black);
}

.player-avatar.red {
  background: var(--color-piece-red);
}

.player-name {
  font-weight: 500;
  color: #1f2937;
}

.player-label {
  font-size: 0.875rem;
  color: #6b7280;
}

.timer-card {
  text-align: center;
}

.timer-value {
  font-size: 2rem;
  font-weight: bold;
  color: #1f2937;
}

.timer-value.red {
  color: var(--color-piece-red);
}

.timer-label {
  font-size: 0.875rem;
  color: #6b7280;
}

.check-alert {
  position: absolute;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  padding: 8px 24px;
  background: #ef4444;
  color: white;
  border-radius: 9999px;
  font-weight: bold;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.game-footer {
  background: white;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
}

.footer-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.result-dialog {
  text-align: center;
  padding: 24px 0;
}

.result-emoji {
  font-size: 4rem;
  margin-bottom: 16px;
}

.result-text {
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 8px;
}

.result-text.win {
  color: #22c55e;
}

.result-text.lose {
  color: #ef4444;
}

.result-reason {
  color: #6b7280;
}

.full-width {
  width: 100%;
}
</style>
