<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useRoomStore } from '@/stores/room'
import { useGameStore } from '@/stores/game'
import { wsClient } from '@/ws/client'
import ChessBoard from '@/components/ChessBoard.vue'
import type { Position, Move } from '@/types/chess'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const roomStore = useRoomStore()
const gameStore = useGameStore()

const roomId = computed(() => route.params.id as string)

// 初始化游戏 — 不再建立独立 WS，全局 WS 已连接
onMounted(() => {
  // 如果游戏未开始但已有房间，说明正在等待 game_start 推送
  if (!gameStore.isGameStarted && roomStore.currentRoom) {
    // 等待对手加入，game_start 推送会通过消息路由触发 gameStore.handleGameStart
  }
  // 如果没有房间信息（直接访问 URL），跳回大厅
  if (!roomStore.currentRoom && !gameStore.isGameStarted) {
    router.replace('/lobby')
  }
})

onUnmounted(() => {
  // 不再 disconnect WS，全局 WS 保持连接
  gameStore.resetGame()
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

// 回应和棋
function handleDrawAnswer(accept: boolean) {
  gameStore.sendDrawAnswer(accept)
}

// 返回大厅
async function handleBack() {
  try {
    await ElMessageBox.confirm('确定要返回大厅吗？当前对局将被判负', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return // 用户取消
  }

  try {
    // 使用 leaveRoom 等待服务端确认退出后再导航
    await roomStore.leaveRoom()
    gameStore.resetGame()
    router.replace('/lobby')
  } catch (error: any) {
    // leaveRoom 失败时也允许返回 (可能服务端已清理)
    console.warn('[Game] Leave room failed, forcing navigate to lobby:', error.message)
    gameStore.resetGame()
    roomStore.clearRoom()
    const authStore = useAuthStore()
    authStore.setAuthState('authenticated')
    router.replace('/lobby')
  }
}

// 游戏结束后返回大厅
async function handleGameOverBack() {
  try {
    await roomStore.leaveRoom()
  } catch {
    // 游戏已结束，房间可能已清理，忽略错误
  }
  gameStore.resetGame()
  router.replace('/lobby')
}

// 胜负结果描述
const resultDescription = computed(() => {
  if (!gameStore.gameResult) return ''

  const isWin =
    (gameStore.gameResult === 'red' && gameStore.yourColor === 0) ||
    (gameStore.gameResult === 'black' && gameStore.yourColor === 1)

  const isDraw = gameStore.gameResult === 'draw'

  if (isDraw) return '和棋'

  const resultText = isWin ? '胜利' : '失败'

  const reasonText =
    gameStore.gameReason === 'checkmate'
      ? '将死'
      : gameStore.gameReason === 'resign'
        ? '认输'
        : gameStore.gameReason === 'timeout'
          ? '超时'
          : gameStore.gameReason === 'disconnect'
            ? '断线'
            : gameStore.gameReason === 'draw'
              ? '和棋'
              : ''

  return `${resultText} - ${reasonText}`
})

// 对手信息
const opponentName = computed(() => {
  if (!roomStore.currentRoom?.opponent) {
    // PvE 模式
    return roomStore.currentRoom?.roomType === 'pve' ? 'AI' : '等待中'
  }
  return roomStore.currentRoom.opponent.username
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

    <!-- WS 连接状态提示 -->
    <div v-if="wsClient.connectionState.value !== 'connected'" class="connection-banner">
      <div class="loading-spinner-small"></div>
      <span>{{ wsClient.connectionState.value === 'connecting' ? '正在重连...' : '连接已断开' }}</span>
    </div>

    <!-- AI 思考提示 -->
    <div v-if="gameStore.isAIThinking" class="ai-thinking-banner">
      <div class="loading-spinner-small"></div>
      <span>AI 正在思考...</span>
    </div>

    <!-- 等待对手 -->
    <div v-if="!gameStore.isGameStarted && !gameStore.isGameOver && roomStore.currentRoom?.phase === 'waiting'" class="waiting-banner">
      <div class="waiting-content">
        <div class="loading-spinner"></div>
        <span>等待对手加入...</span>
        <span class="room-id-hint">房间号: {{ roomId.slice(0, 8) }}</span>
      </div>
    </div>

    <!-- 游戏主区域 -->
    <main class="game-main">
      <div class="game-container">
        <!-- 左侧信息面板 -->
        <div class="side-panel left">
          <div class="player-card">
            <div class="player-avatar black">黑</div>
            <div class="player-info">
              <div class="player-name">{{ gameStore.yourColor === 1 ? authStore.user?.nickname : opponentName }}</div>
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
              <div class="player-name">{{ gameStore.yourColor === 0 ? authStore.user?.nickname : opponentName }}</div>
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
        <div class="result-emoji">{{ gameStore.winner === gameStore.yourColor ? '🎉' : gameStore.winner === -1 ? '🤝' : '😔' }}</div>
        <div class="result-text" :class="gameStore.winner === gameStore.yourColor ? 'win' : gameStore.winner === -1 ? 'draw' : 'lose'">
          {{ resultDescription }}
        </div>
      </div>
      <template #footer>
        <el-button type="primary" size="large" class="full-width" @click="handleGameOverBack">返回大厅</el-button>
      </template>
    </el-dialog>

    <!-- 求和请求弹窗 -->
    <el-dialog
      :model-value="!!gameStore.drawRequestFrom"
      title="和棋请求"
      width="400px"
      :close-on-click-modal="false"
      :show-close="false"
    >
      <div class="draw-dialog">
        <p>{{ gameStore.drawRequestFrom }} 请求和棋，是否同意？</p>
      </div>
      <template #footer>
        <el-button @click="handleDrawAnswer(false)">拒绝</el-button>
        <el-button type="primary" @click="handleDrawAnswer(true)">同意</el-button>
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

.connection-banner,
.ai-thinking-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 16px;
  font-size: 0.875rem;
}

.connection-banner {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.ai-thinking-banner {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.waiting-banner {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
  padding: 16px;
}

.waiting-content {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  font-size: 1rem;
  font-weight: 500;
}

.room-id-hint {
  color: #6b7280;
  font-size: 0.875rem;
  font-weight: normal;
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 3px solid rgba(59, 130, 246, 0.3);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.loading-spinner-small {
  width: 16px;
  height: 16px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
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

.side-panel.left { order: 1; }
.side-panel.right { order: 3; }

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

.player-avatar.black { background: var(--color-piece-black); }
.player-avatar.red { background: var(--color-piece-red); }
.player-name { font-weight: 500; color: #1f2937; }
.player-label { font-size: 0.875rem; color: #6b7280; }

.timer-card { text-align: center; }
.timer-value { font-size: 2rem; font-weight: bold; color: #1f2937; }
.timer-value.red { color: var(--color-piece-red); }
.timer-label { font-size: 0.875rem; color: #6b7280; }

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

.result-emoji { font-size: 4rem; margin-bottom: 16px; }

.result-text {
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 8px;
}

.result-text.win { color: #22c55e; }
.result-text.lose { color: #ef4444; }
.result-text.draw { color: #eab308; }

.full-width { width: 100%; }

.draw-dialog {
  text-align: center;
  padding: 16px 0;
}
</style>
