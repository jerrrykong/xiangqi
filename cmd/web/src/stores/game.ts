import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Position, Move } from '@/types/chess'
import { getInitialBoard, Color } from '@/types/chess'
import { moveToPos, posToMove } from '@/types/chess'
import type {
  GameStartData,
  MoveResultData,
  OpponentMoveData,
  AIMoveData,
  GameOverData,
  StateSyncData,
  DrawRequestData,
  DrawResultData,
} from '@/ws/types'
import { wsClient } from '@/ws/client'
import { WSMsgType } from '@/ws/types'
import { useAuthStore } from './auth'
import { useRoomStore } from './room'

export const useGameStore = defineStore('game', () => {
  // 棋盘状态
  const board = ref<number[][]>(getInitialBoard())

  // 游戏状态
  const currentTurn = ref<0 | 1>(0) // 0=红, 1=黑
  const redTime = ref(600) // 红方剩余时间(秒)
  const blackTime = ref(600) // 黑方剩余时间(秒)
  const yourColor = ref<0 | 1>(0) // 你的颜色

  // 游戏状态
  const isGameStarted = ref(false)
  const isGameOver = ref(false)
  const gameResult = ref<string | null>(null) // 'red' | 'black' | 'draw'
  const gameReason = ref<string | null>(null)
  const winner = ref<number | null>(null) // 0=红, 1=黑, -1=和

  // 房间信息
  const roomId = ref<string | null>(null)

  // UI 状态
  const selectedPosition = ref<Position | null>(null)
  const validMoves = ref<Position[]>([])
  const lastMove = ref<Move | null>(null)
  const isInCheck = ref(false)
  const checkPosition = ref<Position | null>(null)
  const isAIThinking = ref(false)

  // 求和请求
  const drawRequestFrom = ref<string | null>(null)

  // 计时器
  let timerInterval: number | null = null

  // 计算属性
  const isMyTurn = computed(() => currentTurn.value === yourColor.value)

  const myColorName = computed(() => (yourColor.value === Color.Red ? '红方' : '黑方'))

  const opponentColorName = computed(() => (yourColor.value === Color.Red ? '黑方' : '红方'))

  // ===== 游戏操作 =====

  // 发送走棋
  function sendMove(move: Move) {
    const { from_pos, to_pos } = moveToPos(move)
    wsClient.request(WSMsgType.GAME_MOVE, { from_pos, to_pos })
      .then((result: MoveResultData) => {
        if (result.success) {
          // 服务端确认走棋成功，更新本地棋盘
          board.value[move.to_row][move.to_col] = board.value[move.from_row][move.from_col]
          board.value[move.from_row][move.from_col] = -1
          lastMove.value = move
          currentTurn.value = currentTurn.value === 0 ? 1 : 0
        }
      })
      .catch((err) => {
        console.error('[Game] Move failed:', err.message)
      })

    selectedPosition.value = null
    validMoves.value = []
  }

  // 发送认输
  function sendResign() {
    wsClient.send({ type: WSMsgType.GAME_RESIGN, seq: 0, data: {} })
  }

  // 请求和棋
  function sendDrawRequest() {
    wsClient.send({ type: WSMsgType.GAME_DRAW_REQ, seq: 0, data: {} })
  }

  // 回应和棋
  function sendDrawAnswer(accept: boolean) {
    wsClient.send({ type: WSMsgType.GAME_DRAW_ANS, seq: 0, data: { accept } })
    drawRequestFrom.value = null
  }

  // 选择棋子
  function selectPiece(position: Position) {
    if (!isMyTurn.value || isGameOver.value) return

    const piece = board.value[position.row][position.col]
    if (piece < 0) return

    // 检查是否是己方棋子
    const pieceColor = Math.floor(piece / 10)
    if (pieceColor !== yourColor.value) return

    selectedPosition.value = position
    validMoves.value = []
  }

  // 清除选择
  function clearSelection() {
    selectedPosition.value = null
    validMoves.value = []
  }

  // ===== 推送消息处理 =====

  // 处理游戏开始
  function handleGameStart(data: GameStartData) {
    roomId.value = data.room_id
    board.value = getInitialBoard() // 从 FEN 或使用初始棋盘
    const authStore = useAuthStore()
    const userId = authStore.user?.user_id
    yourColor.value = data.red_player.user_id === userId ? 0 : 1
    redTime.value = data.initial_time
    blackTime.value = data.initial_time
    currentTurn.value = 0 // 红方先手
    isGameStarted.value = true
    isGameOver.value = false
    isAIThinking.value = false
    drawRequestFrom.value = null
    startTimer()
  }

  // 处理走棋结果 (自己的走棋确认)
  function handleMoveResult(data: MoveResultData) {
    if (data.success) {
      // 走棋已确认（本地已在 sendMove 中更新）
    } else {
      // 走棋失败，可能需要回滚
      console.warn('[Game] Move rejected:', data.message)
    }
  }

  // 处理对手走棋
  function handleOpponentMove(data: OpponentMoveData) {
    const move = posToMove(data.from_pos, data.to_pos)
    board.value[move.to_row][move.to_col] = board.value[move.from_row][move.from_col]
    board.value[move.from_row][move.from_col] = -1
    lastMove.value = move
    currentTurn.value = currentTurn.value === 0 ? 1 : 0
    isInCheck.value = false
  }

  // 处理 AI 思考中
  function handleAIThinking() {
    isAIThinking.value = true
  }

  // 处理 AI 走棋
  function handleAIMove(data: AIMoveData) {
    isAIThinking.value = false
    const move = posToMove(data.from_pos, data.to_pos)
    board.value[move.to_row][move.to_col] = board.value[move.from_row][move.from_col]
    board.value[move.from_row][move.from_col] = -1
    lastMove.value = move
    currentTurn.value = currentTurn.value === 0 ? 1 : 0
    isInCheck.value = false
  }

  // 处理游戏结束
  function handleGameOver(data: GameOverData) {
    isGameOver.value = true
    gameResult.value = data.winner // 'red' / 'black' / 'draw'
    gameReason.value = data.reason
    winner.value = data.winner === 'red' ? 0 : data.winner === 'black' ? 1 : -1
    isAIThinking.value = false
    stopTimer()
  }

  // 处理求和请求
  function handleDrawRequest(data: DrawRequestData) {
    drawRequestFrom.value = data.from_username
  }

  // 处理求和结果
  function handleDrawResult(data: DrawResultData) {
    drawRequestFrom.value = null
    if (data.accepted) {
      // 和棋已被接受，等待 game_over 推送
    }
  }

  // 处理状态同步 (断线重连)
  function handleStateSync(data: StateSyncData) {
    roomId.value = data.room_id
    yourColor.value = data.your_side === 'red' ? 0 : 1
    redTime.value = data.red_remaining_time
    blackTime.value = data.black_remaining_time

    // 更新房间状态
    const roomStore = useRoomStore()
    if (roomStore.currentRoom) {
      roomStore.currentRoom.phase = data.phase
    }

    isGameStarted.value = data.phase === 'playing'
    isGameOver.value = false
    isAIThinking.value = false

    // 从 FEN 恢复棋盘 (简单实现：使用初始棋盘)
    // TODO: 如果有 FEN 解析器，可以从 data.fen 恢复完整棋盘
    if (!isGameStarted.value) {
      board.value = getInitialBoard()
    }
  }

  // ===== 计时器 =====

  function startTimer() {
    stopTimer()
    timerInterval = window.setInterval(() => {
      if (currentTurn.value === 0) {
        redTime.value--
        if (redTime.value <= 0) {
          stopTimer()
        }
      } else {
        blackTime.value--
        if (blackTime.value <= 0) {
          stopTimer()
        }
      }
    }, 1000)
  }

  function stopTimer() {
    if (timerInterval) {
      clearInterval(timerInterval)
      timerInterval = null
    }
  }

  // 重置游戏
  function resetGame() {
    board.value = getInitialBoard()
    currentTurn.value = 0
    redTime.value = 600
    blackTime.value = 600
    isGameStarted.value = false
    isGameOver.value = false
    gameResult.value = null
    gameReason.value = null
    winner.value = null
    roomId.value = null
    selectedPosition.value = null
    validMoves.value = []
    lastMove.value = null
    isInCheck.value = false
    checkPosition.value = null
    isAIThinking.value = false
    drawRequestFrom.value = null
    stopTimer()
  }

  return {
    // 状态
    board,
    currentTurn,
    redTime,
    blackTime,
    yourColor,
    isGameStarted,
    isGameOver,
    gameResult,
    gameReason,
    winner,
    roomId,
    selectedPosition,
    validMoves,
    lastMove,
    isInCheck,
    checkPosition,
    isAIThinking,
    drawRequestFrom,
    // 计算属性
    isMyTurn,
    myColorName,
    opponentColorName,
    // 方法
    sendMove,
    sendResign,
    sendDrawRequest,
    sendDrawAnswer,
    selectPiece,
    clearSelection,
    resetGame,
    startTimer,
    // 推送处理
    handleGameStart,
    handleMoveResult,
    handleOpponentMove,
    handleAIThinking,
    handleAIMove,
    handleGameOver,
    handleDrawRequest,
    handleDrawResult,
    handleStateSync,
  }
})
