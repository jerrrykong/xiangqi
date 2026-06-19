/**
 * Game — 对局页面
 * 新布局：topbar + center(opponent+board+controls+player) + sidebar(moves)
 * 移动端：column + bottom sheet
 */
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useRoomStore } from '@/stores/room'
import { useGameStore, type MoveRecord, onMoveError } from '@/stores/game'
import { wsClient } from '@/ws/client'
import ChessBoard from '@/components/chess/ChessBoard.vue'
import PlayerInfo from '@/components/game/PlayerInfo.vue'
import GameControls from '@/components/game/GameControls.vue'
import MoveList from '@/components/chess/MoveList.vue'
import type { Position, Move } from '@/types/chess'
import { getPieceColor, Color, PieceChars } from '@/types/chess'
import { getSoundManager } from '@/utils/sound'
import { showConfirm, showToast } from '@/components/common/ui'

const router = useRouter()
const route = useRoute()
const baseUrl = import.meta.env.BASE_URL
const authStore = useAuthStore()
const roomStore = useRoomStore()
const gameStore = useGameStore()
const sound = getSoundManager()

const roomId = computed(() => route.params.id as string)
const soundEnabled = ref(true)

/** 监听断线重连提示 */
let _reconnectMsgWatchStop: (() => void) | null = null
_reconnectMsgWatchStop = watch(() => [...authStore.reconnectMessages], (msgs) => {
  if (msgs.length > 0 && gameStore.phase !== 'playing') {
    showReconnectMessages()
  }
})

/** 移动端底部面板 */
const mobilePanel = ref<'' | 'moves'>('')

// 保证传给 MoveList 的 moves 是普通数组（解包拷贝），避免在 Transition/移动面板中出现渲染空白
const moveList = computed(() => {
  // gameStore.moveHistory 可能是响应式引用，拷贝一份确保子组件能收到稳定的数组值
  return gameStore.moveHistory ? [...gameStore.moveHistory] : []
})

/** 初始化游戏 */
onMounted(() => {
  onMoveError((msg) => showToast(msg, 'warning'))
  if (!roomStore.currentRoom && !gameStore.isGameStarted) {
    router.replace('/lobby')
  }
})

onUnmounted(() => {
  onMoveError(null as any)
  gameStore.resetGame()
})

/** 处理棋子点击（选子或吃子走棋） */
function handlePieceClick(position: Position) {
  // 已选中棋子且点击的是合法走法目标（吃子）→ 走棋
  if (gameStore.selectedPosition) {
    const isValidTarget = gameStore.validMoves.some(
      m => m.row === position.row && m.col === position.col
    )
    if (isValidTarget) {
      const move: Move = {
        from_row: gameStore.selectedPosition.row,
        from_col: gameStore.selectedPosition.col,
        to_row: position.row,
        to_col: position.col,
      }
      gameStore.sendMove(move)
      return
    }
  }
  // 否则视为选子
  gameStore.selectPiece(position)
}

/** 处理位置点击 */
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

/** 点击棋盘空白区域取消选择 */
function handleBoardClick() {
  gameStore.clearSelection()
}

/** 显示断线重连提示 */
async function showReconnectMessages() {
  const messages = authStore.consumeReconnectMessages()
  if (messages.length > 0) {
    await showConfirm(messages.join('\n'), '提示', { type: 'warning' })
  }
}

/** 认输 */
async function handleResign() {
  sound.play('button_click')
  const ok = await showConfirm('确定要认输吗？', '确认', { type: 'danger' })
  if (ok) {
    gameStore.sendResign()
  }
}

/** 请求和棋 */
function handleDrawRequest() {
  sound.play('button_click')
  gameStore.sendDrawRequest()
  showToast('已发送和棋请求', 'info')
}

/** 回应和棋 */
function handleDrawAnswer(accept: boolean) {
  sound.play('button_click')
  gameStore.sendDrawAnswer(accept)
}

/** 返回大厅 */
async function handleBack() {
  const currentPhase = gameStore.phase
  let confirmMsg = '确定要返回大厅吗？'
  if (currentPhase === 'playing') {
    confirmMsg = '确定要返回大厅吗？当前对局将被判负（逃跑）'
  }

  const ok = await showConfirm(confirmMsg, '确认', { type: 'warning' })
  if (!ok) return

  try {
    await roomStore.leaveRoom()
    gameStore.resetGame()
    router.replace('/lobby')
  } catch (error: any) {
    console.warn('[Game] Leave room failed, forcing navigate to lobby:', error.message)
    gameStore.resetGame()
    roomStore.clearRoom()
    authStore.setAuthState('authenticated')
    router.replace('/lobby')
  }
}

/** 游戏结束后返回大厅 */
async function handleGameOverBack() {
  try {
    await roomStore.leaveRoom()
  } catch {
    // 游戏已结束，房间可能已清理
  }
  gameStore.resetGame()
  router.replace('/lobby')
}

/** 开始游戏 */
function handleStartGame() {
  sound.play('button_click')
  gameStore.sendReady()
}

/** 再来一局 */
function handleRematch() {
  sound.play('button_click')
  gameStore.sendRematch()
}

/** 关闭结果对话框 */
function handleResultDialogClose() {
  gameStore.showResultDialog = false
}

/** 胜负结果描述 */
const resultDescription = computed(() => {
  if (!gameStore.gameResult) return ''
  const isWin =
    (gameStore.gameResult === 'red' && gameStore.yourColor === 0) ||
    (gameStore.gameResult === 'black' && gameStore.yourColor === 1)
  const isDraw = gameStore.gameResult === 'draw'
  if (isDraw) return '和棋'
  const resultText = isWin ? '你赢了' : '你输了'
  const reasonText =
    gameStore.gameReason === 'checkmate' ? '将死'
    : gameStore.gameReason === 'resign' ? '认输'
    : gameStore.gameReason === 'timeout' ? '超时'
    : gameStore.gameReason === 'disconnect' ? '断线'
    : gameStore.gameReason === 'draw' ? '和棋'
    : ''
  return `${resultText} - ${reasonText}`
})

/** 积分变化 */
const ratingChangeText = computed(() => {
  const change = gameStore.myRatingChange
  if (change === 0) return '积分不变'
  return change > 0 ? `积分 +${change}` : `积分 ${change}`
})

/** 对手信息 */
const opponentIsAI = computed(() => {
  // 判断为 AI 的条件：房间类型为 pve，或对手 userId 为 0（服务端 bot id）
  if (!roomStore.currentRoom) return false
  if (roomStore.currentRoom.roomType === 'pve') return true
  const opp = roomStore.currentRoom.opponent
  return !!(opp && opp.userId === 0)
})

const opponentName = computed(() => {
  if (!roomStore.currentRoom?.opponent) {
    return roomStore.currentRoom?.roomType === 'pve' ? '电脑' : '等待中'
  }
  // 当对手为 AI 时，显示友好的名称 "电脑"
  if (opponentIsAI.value) return '电脑'
  return roomStore.currentRoom.opponent.username
})

const opponentColor = computed(() => gameStore.yourColor === 0 ? 'black' : 'red')
const myColor = computed(() => gameStore.yourColor === 0 ? 'red' : 'black')

/** 计时 */
const opponentTime = computed(() =>
  gameStore.yourColor === 0 ? gameStore.blackTime : gameStore.redTime
)
const myTime = computed(() =>
  gameStore.yourColor === 0 ? gameStore.redTime : gameStore.blackTime
)

/** 轮次指示 */
const turnText = computed(() => {
  if (!gameStore.isGameStarted || gameStore.isGameOver) return ''
  return gameStore.isMyTurn ? '你的回合' : '对手回合'
})

const turnClass = computed(() => {
  if (!gameStore.isGameStarted) return ''
  return gameStore.isMyTurn ? 'turn-red' : 'turn-black'
})

/** 对局阶段（传给 GameControls） */
const controlsPhase = computed<'playing' | 'finished' | 'ready'>(() => {
  if (gameStore.isGameOver || gameStore.phase === 'finished') return 'finished'
  if (gameStore.phase === 'ready' || gameStore.phase === 'waiting') return 'ready'
  return 'playing'
})

/** 音效开关 */
function toggleSound() {
  const enabled = !sound.isEnabled
  sound.setEnabled(enabled)
  soundEnabled.value = enabled
  if (enabled) sound.play('button_click')
}

/** 格式化时间 */
function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}
</script>

<template>
  <div class="game-page">
    <!-- 顶部信息栏 -->
    <header class="game-topbar">
      <div class="topbar-info" style="margin-left: 0">
        <span class="topbar-room">房间 #{{ roomId.slice(0, 8) }}</span>
        <span v-if="gameStore.isGameStarted" class="turn-indicator" :class="turnClass">
          <span class="turn-dot"></span>
          {{ turnText }}
        </span>
      </div>
      <div class="topbar-actions">
        <button class="sound-toggle" @click="toggleSound" :title="soundEnabled ? '关闭音效' : '开启音效'">
          <img :src="baseUrl + 'assets/svg/ui/icon-sound-' + (soundEnabled ? 'on' : 'off') + '.svg'" alt="" class="sound-toggle-icon" />
        </button>
      </div>
    </header>

    <!-- 浮动提示 -->
    <div class="floating-banners">
      <div v-if="wsClient.connectionState.value !== 'connected'" class="floating-banner connection">
        <div class="spinner-small"></div>
        <span>{{ wsClient.connectionState.value === 'connecting' ? '正在重连...' : '连接已断开' }}</span>
      </div>
      <div v-else-if="gameStore.isAIThinking" class="floating-banner ai-thinking">
        <div class="spinner-small"></div>
        <span>AI 正在思考...</span>
      </div>
      <div v-else-if="!gameStore.isGameStarted && !gameStore.isGameOver && gameStore.phase === 'waiting'" class="floating-banner waiting">
        <div class="spinner-small"></div>
        <span>等待对手加入...</span>
      </div>
      <div v-else-if="gameStore.phase === 'ready' && !gameStore.isGameStarted && gameStore.iAmReady" class="floating-banner ready">
        <div class="spinner-small"></div>
        <span>等待对方开始...</span>
      </div>
    </div>

    <!-- 主体 -->
    <div class="game-main">
      <!-- 中央区域 -->
      <div class="game-center">
        <!-- 对手信息 -->
        <PlayerInfo
          side="opponent"
          :name="opponentName"
          :level="opponentIsAI ? 'AI' : undefined"
          :time="opponentTime"
          :is-turn="!gameStore.isMyTurn && gameStore.isGameStarted && !gameStore.isGameOver"
          :show-timer="gameStore.isGameStarted"
        />

        <!-- 棋盘 -->
        <div class="game-board-area">
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
          <!-- 将军提示 -->
          <div v-if="gameStore.isInCheck" class="check-alert">将军！</div>
          <!-- 开始按钮 -->
          <div v-if="gameStore.phase === 'ready' && !gameStore.isGameStarted && !gameStore.iAmReady" class="floating-start">
            <button class="btn btn-primary btn--lg" @click="handleStartGame">开始</button>
          </div>
        </div>

        <!-- 操作按钮 -->
        <GameControls
          :phase="controlsPhase"
          :can-rematch="gameStore.phase === 'finished'"
          :i-want-rematch="gameStore.iWantRematch"
          :opponent-wants-rematch="gameStore.opponentWantsRematch"
          :is-game-over="gameStore.isGameOver"
          @draw="handleDrawRequest"
          @resign="handleResign"
          @exit="handleBack"
          @rematch="handleRematch"
          @ready="handleStartGame"
        />

        <!-- 自己信息 -->
        <PlayerInfo
          side="player"
          :name="authStore.user?.nickname || authStore.user?.username || '我'"
          :time="myTime"
          :is-turn="gameStore.isMyTurn && gameStore.isGameStarted && !gameStore.isGameOver"
          :show-timer="gameStore.isGameStarted"
        />
      </div>

      <!-- 侧边栏：着法记录（桌面端） -->
      <div class="game-sidebar-desktop">
        <MoveList
          :moves="moveList"
          :title="'着法记录'"
        />
      </div>
    </div>

    <!-- 移动端底部切换栏 -->
    <div class="mobile-toggle-bar">
      <button
        class="mobile-toggle-btn"
        :class="{ active: mobilePanel === 'moves' }"
        @click="mobilePanel = mobilePanel === 'moves' ? '' : 'moves'"
      >
        <img :src="baseUrl + 'assets/svg/ui/icon-clock.svg'" alt="" class="toggle-icon" />
        着法记录 ({{ gameStore.moveHistory.length }})
      </button>
    </div>

    <!-- 移动端底部面板 -->
    <Transition name="sheet">
      <div v-if="mobilePanel" class="mobile-panel-overlay" @click="mobilePanel = ''">
        <div class="mobile-panel-sheet" @click.stop>
          <div class="mobile-panel-handle"></div>
          <MoveList
            :moves="moveList"
            :title="'着法记录'"
          />
        </div>
      </div>
    </Transition>

    <!-- 游戏结束弹窗 -->
    <Transition name="overlay">
      <div v-if="gameStore.showResultDialog" class="review-overlay" @click.self="handleResultDialogClose">
        <div class="review-popup result-popup">
          <div class="result-icon">
            <img v-if="gameStore.winner === gameStore.yourColor" :src="baseUrl + 'assets/svg/ui/icon-trophy.svg'" alt="胜利" class="result-icon-img" />
            <span v-else-if="gameStore.winner === -1" class="result-draw-text">和</span>
            <img v-else :src="baseUrl + 'assets/svg/ui/icon-flag.svg'" alt="败北" class="result-icon-img" />
          </div>
          <div class="result-text" :class="gameStore.winner === gameStore.yourColor ? 'win' : gameStore.winner === -1 ? 'draw' : 'lose'">
            {{ resultDescription }}
          </div>
          <div class="result-rating" :class="{ positive: gameStore.myRatingChange > 0, negative: gameStore.myRatingChange < 0 }">
            {{ ratingChangeText }}
          </div>
          <div class="result-actions">
            <button class="btn btn-primary" @click="handleResultDialogClose">确认</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 求和请求弹窗 -->
    <Transition name="overlay">
      <div v-if="!!gameStore.drawRequestFrom" class="review-overlay">
        <div class="review-popup draw-popup">
          <h3 class="popup-title">
            <img :src="baseUrl + 'assets/svg/ui/icon-undo.svg'" alt="" class="title-icon" />
            和棋请求
          </h3>
          <p>{{ gameStore.drawRequestFrom }} 请求和棋，是否同意？</p>
          <div class="popup-actions">
            <button class="btn btn-secondary" @click="handleDrawAnswer(false)">拒绝</button>
            <button class="btn btn-primary" @click="handleDrawAnswer(true)">同意</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.game-page {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  position: relative;
  background: var(--color-bg-primary);
}

/* 顶部栏 */
.game-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-wood-light);
  box-shadow: var(--shadow-sm);
  flex-shrink: 0;
}

.topbar-logo {
  width: 180px;
  height: 48px;
}

.topbar-info {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.topbar-room {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}

.turn-indicator {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-weight: var(--weight-semibold);
}

.turn-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.turn-red { color: var(--color-error); }
.turn-red .turn-dot { background: var(--color-error); }
.turn-black { color: #2D3748; }
.turn-black .turn-dot { background: #2D3748; }

.topbar-actions {
  display: flex;
  gap: var(--space-2);
}

.sound-toggle {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-wood-light);
  transition: all var(--transition-fast);
}

.sound-toggle-icon {
  width: 20px;
  height: 20px;
}

.sound-toggle:hover {
  background: var(--color-wood-bg);
}

/* 浮动提示 */
.floating-banners {
  position: fixed;
  top: 56px;
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
  gap: var(--space-2);
  padding: var(--space-2) var(--space-5);
  font-size: var(--text-sm);
  border-radius: var(--radius-full);
  box-shadow: var(--shadow-lg);
  pointer-events: auto;
  backdrop-filter: blur(8px);
}

.floating-banner.connection { background: rgba(220, 38, 38, 0.85); color: white; }
.floating-banner.ai-thinking { background: rgba(37, 99, 235, 0.85); color: white; }
.floating-banner.waiting { background: rgba(37, 99, 235, 0.85); color: white; }
.floating-banner.ready { background: rgba(5, 150, 105, 0.85); color: white; }

.spinner-small {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 主体布局 */
.game-main {
  flex: 1;
  display: flex;
  gap: 0;
  min-height: 0;
}

.game-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  min-width: 0;
  padding: var(--space-2);
  gap: var(--space-2);
}

.game-board-area {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  flex: 1;
  min-height: 0;
  width: 100%;
}

/* 开始游戏浮动按钮 */
.floating-start {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 25;
}

.check-alert {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  padding: var(--space-2) var(--space-5);
  background: var(--color-error);
  color: white;
  border-radius: var(--radius-full);
  font-weight: var(--weight-bold);
  font-size: var(--text-sm);
  animation: check-pulse 1.5s ease-in-out infinite;
  z-index: 10;
}

@keyframes check-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

/* 侧边栏（桌面端） */
.game-sidebar-desktop {
  width: 280px;
  flex-shrink: 0;
  background: var(--color-bg-card);
  border-left: 1px solid var(--color-wood-light);
  display: none; /* 默认隐藏，桌面端显示 */
}

/* 移动端底部切换栏 */
.mobile-toggle-bar {
  display: flex;
  justify-content: center;
  padding: var(--space-2) var(--space-4);
  background: var(--color-bg-card);
  border-top: 1px solid var(--color-wood-light);
  flex-shrink: 0;
}

.mobile-toggle-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-4);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-wood-light);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.toggle-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.mobile-toggle-btn.active {
  background: var(--color-gold);
  color: white;
  border-color: var(--color-gold-dark);
}

/* 移动端底部面板 */
.mobile-panel-overlay {
  position: fixed;
  inset: 0;
  background: var(--color-bg-overlay);
  z-index: var(--z-modal-backdrop);
  display: flex;
  align-items: flex-end;
}

.mobile-panel-sheet {
  width: 100%;
  max-height: 60vh;
  background: var(--color-bg-card);
  border-radius: var(--radius-xl) var(--radius-xl) 0 0;
  padding: var(--space-3) var(--space-4);
  overflow-y: auto;
}

.mobile-panel-handle {
  width: 36px;
  height: 4px;
  background: var(--color-text-muted);
  border-radius: var(--radius-full);
  margin: 0 auto var(--space-3);
}

/* 结果弹窗 */
.result-popup {
  text-align: center;
  padding: var(--space-8) var(--space-6);
  max-width: 360px;
}

.result-icon {
  margin-bottom: var(--space-3);
  display: flex;
  align-items: center;
  justify-content: center;
}

.result-icon-img {
  width: 56px;
  height: 56px;
}

.result-draw-text {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-serif);
  font-size: 32px;
  font-weight: var(--weight-bold);
  color: var(--color-warning);
  border: 2px solid var(--color-warning);
  border-radius: 50%;
}

.result-text {
  font-family: var(--font-serif);
  font-size: var(--text-2xl);
  font-weight: var(--weight-bold);
  margin-bottom: var(--space-2);
}

.result-text.win { color: var(--color-success); }
.result-text.lose { color: var(--color-error); }
.result-text.draw { color: var(--color-warning); }

.result-rating {
  font-size: var(--text-lg);
  font-weight: var(--weight-semibold);
  margin-bottom: var(--space-6);
}

.result-rating.positive { color: var(--color-success); }
.result-rating.negative { color: var(--color-error); }

.result-actions {
  display: flex;
  gap: var(--space-3);
  justify-content: center;
}

/* 求和弹窗 */
.draw-popup {
  text-align: center;
  padding: var(--space-6);
  max-width: 360px;
}

.popup-title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  font-family: var(--font-serif);
  font-size: var(--text-lg);
  font-weight: var(--weight-bold);
  color: var(--color-text-primary);
  margin-bottom: var(--space-3);
}

.title-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.draw-popup p {
  color: var(--color-text-secondary);
  margin-bottom: var(--space-4);
}

.popup-actions {
  display: flex;
  gap: var(--space-3);
  justify-content: center;
}

/* 桌面端 */
@media (min-width: 769px) {
  .game-sidebar-desktop {
    display: flex;
    flex-direction: column;
  }
  .mobile-toggle-bar {
    display: none;
  }
}

/* Overlay 动画 */
.overlay-enter-active { transition: all 0.25s ease-out; }
.overlay-leave-active { transition: all 0.2s ease-in; }
.overlay-enter-from { opacity: 0; }
.overlay-enter-from .review-popup { transform: scale(0.9); }
.overlay-leave-to { opacity: 0; }
.overlay-leave-to .review-popup { transform: scale(0.95); }

/* Sheet 动画 */
.sheet-enter-active { transition: all 0.3s ease-out; }
.sheet-leave-active { transition: all 0.2s ease-in; }
.sheet-enter-from .mobile-panel-overlay { opacity: 0; }
.sheet-enter-from .mobile-panel-sheet { transform: translateY(100%); }
.sheet-leave-to .mobile-panel-overlay { opacity: 0; }
.sheet-leave-to .mobile-panel-sheet { transform: translateY(100%); }
</style>
