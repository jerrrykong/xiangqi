<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useRoomStore } from '@/stores/room'
import { useGameStore, type MoveRecord, onMoveError } from '@/stores/game'
import { wsClient } from '@/ws/client'
import ChessBoard from '@/components/ChessBoard.vue'
import type { Position, Move } from '@/types/chess'
import { getPieceColor, Color, PieceChars } from '@/types/chess'
import { getSoundManager } from '@/utils/sound'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const roomStore = useRoomStore()
const gameStore = useGameStore()
const sound = getSoundManager()

const roomId = computed(() => route.params.id as string)
const soundEnabled = ref(true)

// 监听断线重连提示（state_sync 可能在 mount 后到达）
let _reconnectMsgWatchStop: (() => void) | null = null
_reconnectMsgWatchStop = watch(() => [...authStore.reconnectMessages], (msgs) => {
  if (msgs.length > 0 && gameStore.phase !== 'playing') {
    showReconnectMessages()
  }
})

// 走棋历史滚动
const moveHistoryRef = ref<HTMLElement | null>(null)
const showMoveHistoryMobile = ref(false)
const chessBoardRef = ref<InstanceType<typeof ChessBoard> | null>(null)

// 宽屏面板高度与棋盘对齐
const panelHeight = ref<string>('auto')

function syncPanelHeight() {
  const boardEl = document.querySelector('.desktop-layout .board-container')
  if (boardEl && boardEl.clientHeight > 0) {
    panelHeight.value = `${boardEl.clientHeight}px`
  }
}

// 当游戏开始后棋盘可能变化
watch(() => gameStore.isGameStarted, () => nextTick(syncPanelHeight))

watch(() => gameStore.moveHistory.length, async () => {
  await nextTick()
  if (moveHistoryRef.value) {
    moveHistoryRef.value.scrollTop = moveHistoryRef.value.scrollHeight
  }
})

// 初始化游戏
onMounted(() => {
  onMoveError((msg) => ElMessage.warning(msg))
  if (!gameStore.isGameStarted && roomStore.currentRoom) {
    // 等待对手加入
  }
  if (!roomStore.currentRoom && !gameStore.isGameStarted) {
    router.replace('/lobby')
  }
  nextTick(syncPanelHeight)
  window.addEventListener('resize', () => {
    requestAnimationFrame(syncPanelHeight)
  })

  // 消费断线重连提示
  showReconnectMessages()
})

onUnmounted(() => {
  onMoveError(null as any) // 清除回调
  gameStore.resetGame()
  window.removeEventListener('resize', syncPanelHeight)
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

// 点击棋盘空白区域取消选择
function handleBoardClick() {
  gameStore.clearSelection()
}

// 显示断线重连提示弹窗
function showReconnectMessages() {
  const messages = authStore.consumeReconnectMessages()
  if (messages.length > 0) {
    ElMessageBox.alert(messages.join('\n'), '提示', {
      confirmButtonText: '确定',
      type: 'warning',
    })
  }
}

// 认输
async function handleResign() {
  sound.play('button_click')
  await ElMessageBox.confirm('确定要认输吗？', '确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
  gameStore.sendResign()
}

// 请求和棋
function handleDrawRequest() {
  sound.play('button_click')
  gameStore.sendDrawRequest()
  ElMessage.info('已发送和棋请求')
}

// 回应和棋
function handleDrawAnswer(accept: boolean) {
  sound.play('button_click')
  gameStore.sendDrawAnswer(accept)
}

// 返回大厅
async function handleBack() {
  const currentPhase = gameStore.phase

  let confirmMsg = '确定要返回大厅吗？'
  if (currentPhase === 'playing') {
    confirmMsg = '确定要返回大厅吗？当前对局将被判负（逃跑）'
  } else if (currentPhase === 'ready') {
    confirmMsg = '确定要返回大厅吗？'
  } else if (currentPhase === 'finished') {
    confirmMsg = '确定要返回大厅吗？'
  }

  try {
    await ElMessageBox.confirm(confirmMsg, '确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }

  try {
    await roomStore.leaveRoom()
    gameStore.resetGame()
    router.replace('/lobby')
  } catch (error: any) {
    console.warn('[Game] Leave room failed, forcing navigate to lobby:', error.message)
    gameStore.resetGame()
    roomStore.clearRoom()
    const authStore = useAuthStore()
    authStore.setAuthState('authenticated')
    router.replace('/lobby')
  }
}

// 游戏结束后返回大厅（从结果对话框）
async function handleGameOverBack() {
  try {
    await roomStore.leaveRoom()
  } catch {
    // 游戏已结束，房间可能已清理
  }
  gameStore.resetGame()
  router.replace('/lobby')
}

// 点击"开始"按钮（READY 阶段）
function handleStartGame() {
  sound.play('button_click')
  gameStore.sendReady()
}

// 点击"再来一局"按钮（FINISHED 阶段）
function handleRematch() {
  sound.play('button_click')
  gameStore.sendRematch()
}

// 关闭结果对话框
function handleResultDialogClose() {
  gameStore.showResultDialog = false
}

// 胜负结果描述
const resultDescription = computed(() => {
  if (!gameStore.gameResult) return ''

  const isWin =
    (gameStore.gameResult === 'red' && gameStore.yourColor === 0) ||
    (gameStore.gameResult === 'black' && gameStore.yourColor === 1)

  const isDraw = gameStore.gameResult === 'draw'

  if (isDraw) return '和棋'

  const resultText = isWin ? '你赢了' : '你输了'

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

// 积分变化描述
const ratingChangeText = computed(() => {
  const change = gameStore.myRatingChange
  if (change === 0) return '积分不变'
  return change > 0 ? `积分 +${change}` : `积分 ${change}`
})

// 对手信息
const opponentName = computed(() => {
  if (!roomStore.currentRoom?.opponent) {
    return roomStore.currentRoom?.roomType === 'pve' ? 'AI' : '等待中'
  }
  return roomStore.currentRoom.opponent.username
})

// 对手颜色
const opponentColor = computed(() => gameStore.yourColor === 0 ? 'black' : 'red')
const myColor = computed(() => gameStore.yourColor === 0 ? 'red' : 'black')

// 对手计时
const opponentTime = computed(() =>
  gameStore.yourColor === 0 ? gameStore.blackTime : gameStore.redTime
)
const myTime = computed(() =>
  gameStore.yourColor === 0 ? gameStore.redTime : gameStore.blackTime
)

// 对手是否在思考（走棋方=对手）
const opponentThinking = computed(() => !gameStore.isMyTurn && gameStore.isGameStarted && !gameStore.isGameOver)

// 音效开关
function toggleSound() {
  const enabled = !sound.isEnabled
  sound.setEnabled(enabled)
  soundEnabled.value = enabled
  if (enabled) sound.play('button_click')
}

// 走棋历史文本
function formatMoveRecord(record: MoveRecord, index: number): string {
  const isRed = record.piece < 10
  const colorTag = isRed ? '红' : '黑'
  return `${record.moveNumber}. ${colorTag} ${record.notation}`
}
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
          <button class="sound-toggle" @click="toggleSound" :title="soundEnabled ? '关闭音效' : '开启音效'">
            {{ soundEnabled ? '🔊' : '🔇' }}
          </button>
        </div>
      </div>
    </header>

    <!-- 浮动提示区域（WS连接/AI思考/等待对手/等待开始） -->
    <div class="floating-banners">
      <div v-if="wsClient.connectionState.value !== 'connected'" class="floating-banner connection">
        <div class="loading-spinner-small"></div>
        <span>{{ wsClient.connectionState.value === 'connecting' ? '正在重连...' : '连接已断开' }}</span>
      </div>
      <div v-else-if="gameStore.isAIThinking" class="floating-banner ai-thinking">
        <div class="loading-spinner-small"></div>
        <span>AI 正在思考...</span>
      </div>
      <div v-else-if="!gameStore.isGameStarted && !gameStore.isGameOver && gameStore.phase === 'waiting'" class="floating-banner waiting">
        <div class="loading-spinner-small"></div>
        <span>等待对手加入...</span>
      </div>
      <div v-else-if="gameStore.phase === 'ready' && !gameStore.isGameStarted && gameStore.iAmReady" class="floating-banner ready-waiting">
        <div class="loading-spinner-small"></div>
        <span>等待对方开始...</span>
      </div>
      <div v-else-if="gameStore.phase === 'ready' && !gameStore.isGameStarted && gameStore.opponentReady" class="floating-banner opponent-ready">
        <span>对方已开始</span>
      </div>
    </div>

    <!-- ====== 宽屏布局 ====== -->
    <main class="game-main desktop-layout">
      <!-- 左侧面板：对手信息 + 自己信息 -->
      <div class="left-panel" :style="{ height: panelHeight }">
        <!-- 对手 -->
        <div class="player-card" :class="{ active: opponentThinking }">
          <div class="player-row">
            <div class="player-avatar" :class="opponentColor">
              {{ opponentColor === 'red' ? '红' : '黑' }}
            </div>
            <div class="player-info">
              <div class="player-name">{{ opponentName }}</div>
              <div class="player-label">对手</div>
            </div>
          </div>
          <div class="timer-card">
            <div class="timer-value" :class="{ red: opponentColor === 'red' }">
              {{ formatTime(opponentTime) }}
            </div>
          </div>
        </div>

        <!-- 弹性间隔 -->
        <div class="panel-spacer"></div>

        <!-- 自己 -->
        <div class="player-card" :class="{ active: gameStore.isMyTurn }">
          <div class="player-row">
            <div class="player-avatar" :class="myColor">
              {{ myColor === 'red' ? '红' : '黑' }}
            </div>
            <div class="player-info">
              <div class="player-name">{{ authStore.user?.nickname || authStore.user?.username }}</div>
              <div class="player-label">你</div>
            </div>
          </div>
          <div class="timer-card">
            <div class="timer-value" :class="{ red: myColor === 'red' }">
              {{ formatTime(myTime) }}
            </div>
          </div>
        </div>
      </div>

      <!-- 棋盘 -->
      <div class="board-container">
        <ChessBoard
          ref="chessBoardRef"
          :board="gameStore.board"
          :selected-position="gameStore.selectedPosition"
          :valid-moves="gameStore.validMoves"
          :last-move="gameStore.lastMove"
          :is-in-check="gameStore.isInCheck"
          :check-position="gameStore.checkPosition"
          :your-color="gameStore.yourColor"
          :is-my-turn="gameStore.isMyTurn && !gameStore.isBoardFrozen && gameStore.isGameStarted"
          :is-game-started="gameStore.isGameStarted"
          :frozen="gameStore.isBoardFrozen"
          :animating-move="gameStore.animatingMove"
          @piece-click="handlePieceClick"
          @position-click="handlePositionClick"
          @board-click="handleBoardClick"
        />
        <div v-if="gameStore.isInCheck" class="check-alert">将军！</div>
        <!-- 开始游戏浮动按钮（棋盘中央） -->
        <div v-if="gameStore.phase === 'ready' && !gameStore.isGameStarted && !gameStore.iAmReady" class="floating-start">
          <el-button size="large" @click="handleStartGame" class="start-btn">开始</el-button>
        </div>
      </div>

      <!-- 右侧面板：操作按钮 + 走棋历史 -->
      <div class="right-panel" :style="{ height: panelHeight }">
        <div class="action-buttons">
          <template v-if="gameStore.phase === 'finished'">
            <el-button type="primary" @click="handleRematch" :disabled="gameStore.iWantRematch">
              {{ gameStore.iWantRematch ? (gameStore.opponentWantsRematch ? '开始新一局...' : '等待对方...') : '再来一局' }}
            </el-button>
            <el-button @click="handleBack">返回大厅</el-button>
          </template>
          <template v-else-if="gameStore.phase === 'ready'">
            <el-button @click="handleBack">返回大厅</el-button>
          </template>
          <template v-else>
            <el-button type="danger" :disabled="gameStore.isGameOver" @click="handleResign">认输</el-button>
            <el-button type="warning" :disabled="gameStore.isGameOver" @click="handleDrawRequest">求和</el-button>
            <el-button @click="handleBack">返回大厅</el-button>
          </template>
        </div>
        <div class="move-history-panel">
          <div class="move-history-title">历史着法</div>
          <div ref="moveHistoryRef" class="move-history-list">
            <div
              v-for="(record, index) in gameStore.moveHistory"
              :key="index"
              class="move-item"
              :class="{ latest: index === gameStore.moveHistory.length - 1 }"
            >
              {{ formatMoveRecord(record, index) }}
            </div>
            <div v-if="gameStore.moveHistory.length === 0" class="move-empty">暂无走棋记录</div>
          </div>
        </div>
      </div>
    </main>

    <!-- ====== 窄屏布局 ====== -->
    <main class="game-main mobile-layout">
      <!-- 对方信息（一行） -->
      <div class="mobile-player-bar opponent">
        <div class="mobile-player-info">
          <div class="player-avatar small" :class="opponentColor">
            {{ opponentColor === 'red' ? '红' : '黑' }}
          </div>
          <span class="mobile-player-name">{{ opponentName }}</span>
        </div>
        <div class="mobile-timer" :class="{ red: opponentColor === 'red' }">
          {{ formatTime(opponentTime) }}
        </div>
      </div>

      <!-- 棋盘 -->
      <div class="board-container mobile board-fit">
        <ChessBoard
          :board="gameStore.board"
          :selected-position="gameStore.selectedPosition"
          :valid-moves="gameStore.validMoves"
          :last-move="gameStore.lastMove"
          :is-in-check="gameStore.isInCheck"
          :check-position="gameStore.checkPosition"
          :your-color="gameStore.yourColor"
          :is-my-turn="gameStore.isMyTurn && !gameStore.isBoardFrozen && gameStore.isGameStarted"
          :is-game-started="gameStore.isGameStarted"
          :frozen="gameStore.isBoardFrozen"
          :animating-move="gameStore.animatingMove"
          @piece-click="handlePieceClick"
          @position-click="handlePositionClick"
          @board-click="handleBoardClick"
        />
        <div v-if="gameStore.isInCheck" class="check-alert">将军！</div>
        <!-- 开始游戏浮动按钮（棋盘中央） -->
        <div v-if="gameStore.phase === 'ready' && !gameStore.isGameStarted && !gameStore.iAmReady" class="floating-start">
          <el-button size="large" @click="handleStartGame" class="start-btn">开始</el-button>
        </div>
      </div>

      <!-- 自己信息（一行） -->
      <div class="mobile-player-bar self">
        <div class="mobile-player-info">
          <div class="player-avatar small" :class="myColor">
            {{ myColor === 'red' ? '红' : '黑' }}
          </div>
          <span class="mobile-player-name">{{ authStore.user?.nickname || authStore.user?.username }}</span>
        </div>
        <div class="mobile-timer" :class="{ red: myColor === 'red' }">
          {{ formatTime(myTime) }}
        </div>
      </div>

      <!-- 操作按钮区 -->
      <div class="mobile-actions">
        <template v-if="gameStore.phase === 'finished'">
          <el-button type="primary" @click="handleRematch" :disabled="gameStore.iWantRematch">
            {{ gameStore.iWantRematch ? (gameStore.opponentWantsRematch ? '开始...' : '等待对方...') : '再来一局' }}
          </el-button>
          <el-button @click="handleBack">返回大厅</el-button>
        </template>
        <template v-else-if="gameStore.phase === 'ready'">
          <el-button @click="handleBack">返回大厅</el-button>
        </template>
        <template v-else>
          <el-button type="danger" :disabled="gameStore.isGameOver" @click="handleResign">认输</el-button>
          <el-button type="warning" :disabled="gameStore.isGameOver" @click="handleDrawRequest">求和</el-button>
          <el-button @click="showMoveHistoryMobile = true">
          历史着法 ({{ gameStore.moveHistory.length }})
          </el-button>
          <el-button @click="handleBack">返回大厅</el-button>
        </template>
      </div>
    </main>

    <!-- 游戏结束弹窗 -->
    <el-dialog
      v-model="gameStore.showResultDialog"
      title="对局结束"
      width="400px"
      :close-on-click-modal="false"
      :show-close="true"
      @close="handleResultDialogClose"
    >
      <div class="result-dialog">
        <div class="result-emoji">{{ gameStore.winner === gameStore.yourColor ? '🎉' : gameStore.winner === -1 ? '🤝' : '😔' }}</div>
        <div class="result-text" :class="gameStore.winner === gameStore.yourColor ? 'win' : gameStore.winner === -1 ? 'draw' : 'lose'">
          {{ resultDescription }}
        </div>
        <div class="rating-change" :class="{ positive: gameStore.myRatingChange > 0, negative: gameStore.myRatingChange < 0 }">
          {{ ratingChangeText }}
        </div>
      </div>
      <template #footer>
        <el-button type="primary" size="large" @click="handleRematch" :disabled="gameStore.iWantRematch">
          {{ gameStore.iWantRematch ? '等待对方...' : '再来一局' }}
        </el-button>
        <el-button size="large" @click="handleGameOverBack">返回大厅</el-button>
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

    <!-- 窄屏走棋历史弹窗 -->
    <el-dialog
      v-model="showMoveHistoryMobile"
      title="走棋记录"
      width="100%"
      high = "100%"
      class="mobile-history-dialog"
    >
      <div class="move-history-list mobile">
        <div
          v-for="(record, index) in gameStore.moveHistory"
          :key="index"
          class="move-item"
          :class="{ latest: index === gameStore.moveHistory.length - 1 }"
        >
          {{ formatMoveRecord(record, index) }}
        </div>
        <div v-if="gameStore.moveHistory.length === 0" class="move-empty">暂无走棋记录</div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.game-page {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  position: relative;
  background: linear-gradient(135deg, var(--color-wood-100) 0%, var(--color-wood-200) 100%);
}

.game-header {
  background: var(--color-wood-600);
  color: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  flex-shrink: 0;
}

.header-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 8px 16px;
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
  font-size: 1.1rem;
  font-weight: bold;
}

.room-id {
  color: var(--color-wood-200);
  font-size: 0.8rem;
}

.my-turn {
  color: #4ade80;
  font-weight: bold;
}

.sound-toggle {
  background: none;
  border: none;
  font-size: 1.2rem;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: background 0.2s;
  line-height: 1;
}
.sound-toggle:hover {
  background: rgba(255, 255, 255, 0.15);
}

/* 浮动提示区域：定位在顶部信息栏下方，棋盘正上方 */
.floating-banners {
  position: fixed;
  top: 44px;
  left: 0;
  right: 0;
  display: flex;
  justify-content: center;
  z-index: 100;
  pointer-events: none;
}

.floating-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 6px 20px;
  font-size: 0.85rem;
  border-radius: 10px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  pointer-events: auto;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.floating-banner.connection {
  background: rgba(239, 68, 68, 0.8);
  color: white;
}

.floating-banner.ai-thinking {
  background: rgba(59, 130, 246, 0.8);
  color: white;
}

.floating-banner.waiting {
  background: rgba(59, 130, 246, 0.8);
  color: white;
}

.floating-banner.ready-waiting {
  background: rgba(34, 197, 94, 0.8);
  color: white;
}

.floating-banner.opponent-ready {
  background: rgba(34, 197, 94, 0.75);
  color: white;
}

/* 开始游戏浮动按钮：相对棋盘居中 */
.floating-start {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  z-index: 25;
  background: transparent;
  padding: 0;
}

.room-id-hint {
  color: rgba(255, 255, 255, 0.8);
  font-size: 0.8rem;
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
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ===== 宽屏布局 (>=1024px) ===== */
.desktop-layout {
  display: none;
}

@media (min-width: 1024px) {
  .desktop-layout {
    display: flex;
    flex: 1;
    align-items: flex-start;
    justify-content: center;
    padding: 16px;
    gap: 16px;
  }

  .mobile-layout {
    display: none !important;
  }

  /* 左面板：与棋盘等高，对手卡上对齐，自己卡下对齐 */
  .left-panel {
    display: flex;
    flex-direction: column;
    width: 180px;
    flex-shrink: 0;
  }

  .panel-spacer {
    flex: 1;
  }

  /* 右面板：与棋盘等高 */
  .right-panel {
    display: flex;
    flex-direction: column;
    width: 200px;
    gap: 12px;
    flex-shrink: 0;
  }

  .board-container {
    position: relative;
    flex-shrink: 0;
  }

  .player-card {
    background: rgba(255, 255, 255, 0.95);
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(139, 90, 43, 0.15);
    padding: 12px;
    transition: box-shadow 0.3s;
  }

  .player-card.active {
    box-shadow: 0 4px 20px rgba(139, 90, 43, 0.3), 0 0 0 2px rgba(34, 197, 94, 0.5);
  }

  .player-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
  }

  .player-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: bold;
    font-size: 0.85rem;
    flex-shrink: 0;
  }

  .player-avatar.small {
    width: 28px;
    height: 28px;
    font-size: 0.75rem;
  }

  .player-avatar.black { background: var(--color-piece-black); }
  .player-avatar.red { background: var(--color-piece-red); }

  .player-name { font-weight: 500; color: #1f2937; font-size: 0.9rem; }
  .player-label { font-size: 0.75rem; color: #9ca3af; }

  .timer-card {
    text-align: center;
    background: rgba(0, 0, 0, 0.04);
    border-radius: 8px;
    padding: 6px;
  }

  .timer-value {
    font-size: 1.6rem;
    font-weight: bold;
    color: #1f2937;
    font-variant-numeric: tabular-nums;
  }

  .timer-value.red { color: var(--color-piece-red); }

  .action-buttons {
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex-shrink: 0;
  }

  .action-buttons .el-button {
    width: 100%;
  }

  .move-history-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    background: rgba(255, 255, 255, 0.95);
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(139, 90, 43, 0.15);
    overflow: hidden;
    min-height: 0;
  }

  .move-history-title {
    padding: 10px 12px;
    font-weight: 600;
    color: #1f2937;
    border-bottom: 1px solid #e5e7eb;
    font-size: 0.85rem;
    flex-shrink: 0;
  }

  .move-history-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
  }
}

/* ===== 窄屏布局 (<1024px) ===== */
.mobile-layout {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  padding: 8px;
  gap: 8px;
}

@media (min-width: 1024px) {
  .mobile-layout {
    display: none !important;
  }
}

/* 窄屏棋盘容器 - 限制宽度不超出屏幕 */
.board-container.mobile.board-fit {
  position: relative;
  width: 100%;
  max-width: calc(100vw - 16px);
  display: flex;
  justify-content: center;
}

.mobile-player-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  max-width: 520px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 10px;
  padding: 8px 14px;
  box-shadow: 0 2px 10px rgba(139, 90, 43, 0.12);
}

.mobile-player-bar.self {
  border-left: 3px solid #22c55e;
}

.mobile-player-bar.opponent {
  border-left: 3px solid #ef4444;
}

.mobile-player-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mobile-player-name {
  font-weight: 500;
  color: #1f2937;
  font-size: 0.9rem;
}

.mobile-timer {
  font-size: 1.3rem;
  font-weight: bold;
  color: #1f2937;
  font-variant-numeric: tabular-nums;
}

.mobile-timer.red {
  color: var(--color-piece-red);
}

.mobile-actions {
  display: flex;
  gap: 8px;
  width: 100%;
  max-width: 520px;
  flex-wrap: wrap;
}

.mobile-actions .el-button {
  flex: 1;
  min-width: 0;
}

.move-history-list.mobile {
  max-height: 60vh;
  overflow-y: auto;
}

/* 公共样式 */
.move-item {
  padding: 4px 8px;
  font-size: 0.8rem;
  color: #4b5563;
  border-radius: 4px;
  font-variant-numeric: tabular-nums;
}

.move-item.latest {
  background: rgba(34, 197, 94, 0.15);
  color: #166534;
  font-weight: 600;
}

.move-empty {
  text-align: center;
  color: #9ca3af;
  padding: 20px;
  font-size: 0.8rem;
}

.check-alert {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  padding: 6px 20px;
  background: #ef4444;
  color: white;
  border-radius: 9999px;
  font-weight: bold;
  font-size: 0.9rem;
  animation: pulse 1.5s infinite;
  z-index: 10;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
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

.rating-change {
  font-size: 1.1rem;
  font-weight: 600;
  margin-top: 8px;
}

.rating-change.positive { color: #22c55e; }
.rating-change.negative { color: #ef4444; }

.start-btn {
  font-size: 1.3rem;
  padding: 14px 56px;
  font-weight: bold;
  color: #1f2937;
  background: linear-gradient(180deg, #ffffff 0%, #f3f4f6 100%);
  border: 2px solid #d1d5db;
  border-bottom: 4px solid #9ca3af;
  border-radius: 12px;
  box-shadow:
    0 4px 16px rgba(0, 0, 0, 0.25),
    0 2px 4px rgba(0, 0, 0, 0.15),
    inset 0 1px 0 rgba(255, 255, 255, 0.8);
  transition: transform 0.1s, box-shadow 0.1s;
}
.start-btn:hover {
  background: linear-gradient(180deg, #f9fafb 0%, #e5e7eb 100%);
  box-shadow:
    0 6px 20px rgba(0, 0, 0, 0.3),
    0 2px 4px rgba(0, 0, 0, 0.15),
    inset 0 1px 0 rgba(255, 255, 255, 0.8);
  transform: translateY(-1px);
}
.start-btn:active {
  border-bottom-width: 2px;
  transform: translateY(2px);
  box-shadow:
    0 2px 8px rgba(0, 0, 0, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.6);
}

.full-width { width: 100%; }

.draw-dialog {
  text-align: center;
  padding: 16px 0;
}
</style>
