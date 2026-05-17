import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { Position, Move } from '@/types/chess'
import { getInitialBoard, Color } from '@/types/chess'
import type { ServerMessage, StateSyncMessage, GameStartMessage } from '@/types/websocket'
import wsManager from '@/api/websocket'
import { MsgType } from '@/types/websocket'
import { useAuthStore } from './auth'

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
  const gameResult = ref<string | null>(null)
  const gameReason = ref<string | null>(null)
  const winner = ref<number | null>(null)

  // 房间信息
  const roomId = ref<string | null>(null)
  const gameWsUrl = ref<string | null>(null)
  const gameToken = ref<string | null>(null)

  // UI 状态
  const selectedPosition = ref<Position | null>(null)
  const validMoves = ref<Position[]>([])
  const lastMove = ref<Move | null>(null)
  const isInCheck = ref(false)
  const checkPosition = ref<Position | null>(null)

  // 计时器
  let timerInterval: number | null = null

  // 计算属性
  const isMyTurn = computed(() => currentTurn.value === yourColor.value)

  const myColorName = computed(() => (yourColor.value === Color.Red ? '红方' : '黑方'))

  const opponentColorName = computed(() => (yourColor.value === Color.Red ? '黑方' : '红方'))

  // WebSocket 回调设置
  function setWebSocketCallbacks() {
    wsManager.setCallbacks({
      onGameStart: handleGameStart,
      onStateSync: handleStateSync,
      onOpponentMove: handleOpponentMove,
      onGameOver: handleGameOver,
      onCheck: handleCheck,
      onError: handleError,
      onDisconnect: handleDisconnect,
    })
  }

  // 连接游戏 WebSocket
  function connect(wsUrl: string, token: string) {
    gameWsUrl.value = wsUrl
    gameToken.value = token
    setWebSocketCallbacks()

    // 附加 user_id 到 WebSocket URL，供服务端识别玩家身份
    const authStore = useAuthStore()
    const userId = authStore.user?.user_id
    const urlWithUser = userId ? `${wsUrl}?token=${encodeURIComponent(token)}&user_id=${userId}` : undefined
    wsManager.connectRaw(urlWithUser || wsUrl, token)
  }

  // 断开连接
  function disconnect() {
    stopTimer()
    wsManager.disconnect()
    resetGame()
  }

  // 处理游戏开始
  function handleGameStart(data: GameStartMessage) {
    roomId.value = data.room_id
    yourColor.value = data.your_color as 0 | 1
    redTime.value = data.red_time
    blackTime.value = data.black_time
    currentTurn.value = 0 // 红方先手
    isGameStarted.value = true
    isGameOver.value = false
    startTimer()
  }

  // 处理状态同步
  function handleStateSync(data: StateSyncMessage) {
    board.value = data.board
    currentTurn.value = data.turn as 0 | 1
    redTime.value = data.red_time
    blackTime.value = data.black_time
    roomId.value = data.room_id
    yourColor.value = data.your_color as 0 | 1
  }

  // 处理对手走棋
  function handleOpponentMove(data: { move: Move; red_time: number; black_time: number }) {
    const { move, red_time, black_time } = data
    // 更新棋盘
    board.value[move.to_row][move.to_col] = board.value[move.from_row][move.from_col]
    board.value[move.from_row][move.from_col] = -1
    lastMove.value = move
    currentTurn.value = currentTurn.value === 0 ? 1 : 0
    redTime.value = red_time
    blackTime.value = black_time
  }

  // 处理游戏结束
  function handleGameOver(data: {
    result: string
    reason: string
    winner: number
  }) {
    isGameOver.value = true
    gameResult.value = data.result
    gameReason.value = data.reason
    winner.value = data.winner
    stopTimer()
  }

  // 处理将军
  function handleCheck(data: {
    from_row: number
    from_col: number
    to_row: number
    to_col: number
  }) {
    isInCheck.value = true
    checkPosition.value = { row: data.to_row, col: data.to_col }
  }

  // 处理错误
  function handleError(data: { code: number; message: string }) {
    console.error('Game error:', data.code, data.message)
  }

  // 处理断开连接
  function handleDisconnect() {
    console.log('WebSocket disconnected')
  }

  // 发送走棋
  function sendMove(move: Move) {
    wsManager.send({
      type: MsgType.Move,
      move,
    })
    // 本地更新棋盘
    board.value[move.to_row][move.to_col] = board.value[move.from_row][move.from_col]
    board.value[move.from_row][move.from_col] = -1
    lastMove.value = move
    selectedPosition.value = null
    validMoves.value = []
  }

  // 发送认输
  function sendResign() {
    wsManager.send({
      type: MsgType.Resign,
    })
  }

  // 请求和棋
  function sendDrawRequest() {
    wsManager.send({
      type: MsgType.DrawReq,
    })
  }

  // 回应和棋
  function sendDrawAnswer(accept: boolean) {
    wsManager.send({
      type: MsgType.DrawAns,
      accept,
    })
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
    // TODO: 计算合法走法
    validMoves.value = []
  }

  // 清除选择
  function clearSelection() {
    selectedPosition.value = null
    validMoves.value = []
  }

  // 计时器
  function startTimer() {
    stopTimer()
    timerInterval = window.setInterval(() => {
      if (currentTurn.value === 0) {
        redTime.value--
        if (redTime.value <= 0) {
          stopTimer()
          // 超时判负
        }
      } else {
        blackTime.value--
        if (blackTime.value <= 0) {
          stopTimer()
          // 超时判负
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
    // 计算属性
    isMyTurn,
    myColorName,
    opponentColorName,
    // 方法
    connect,
    disconnect,
    sendMove,
    sendResign,
    sendDrawRequest,
    sendDrawAnswer,
    selectPiece,
    clearSelection,
    resetGame,
    startTimer,
  }
})
