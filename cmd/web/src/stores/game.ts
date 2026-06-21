import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Position, Move } from '@/types/chess'
import { getInitialBoard, Color, Piece, PieceChars, getPieceColor, BoardConfig, PieceConfig, parseFEN } from '@/types/chess'
import { moveToPos, posToMove } from '@/types/chess'
import { getSoundManager, type SoundKey } from '@/utils/sound'
import type {
  GameStartData,
  MoveResultData,
  OpponentMoveData,
  AIMoveData,
  GameOverData,
  StateSyncData,
  DrawRequestData,
  DrawResultData,
  OpponentReadyData,
  OpponentRematchData,
} from '@/ws/types'
import { wsClient } from '@/ws/client'
import { WSError } from '@/ws/request'
import { WSMsgType } from '@/ws/types'
import { showToast } from '@/components/common/ui'
import { useAuthStore } from './auth'
import { useRoomStore } from './room'
import router from '@/router'

// 语音播放完成时间追踪（用于 game over 语音等待前面的播放完成）
let lastVoiceEndTime = 0

// 走棋错误提示（用户可见）
let _moveErrorCallback: ((msg: string) => void) | null = null

/** 注册走棋错误提示回调（由 Game.vue 调用，绑定 ElMessage） */
export function onMoveError(cb: (msg: string) => void) {
  _moveErrorCallback = cb
}

function showMoveError(msg: string) {
  console.warn('[Game] Move error:', msg)
  _moveErrorCallback?.(msg)
}

// 走棋记录条目
export interface MoveRecord {
  move: Move
  piece: number
  captured: number
  notation: string
  moveNumber: number
}

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

  // 房间阶段 (waiting/ready/playing/finished)
  const phase = ref<string>('waiting')

  // Ready 状态
  const iAmReady = ref(false)
  const opponentReady = ref(false)

  // Rematch 状态
  const iWantRematch = ref(false)
  const opponentWantsRematch = ref(false)

  // 结果对话框
  const showResultDialog = ref(false)

  // 积分变化
  const myRatingChange = ref(0)

  // 棋盘冻结 (FINISHED 状态)
  const isBoardFrozen = computed(() => phase.value === 'finished')

  // 房间信息
  const roomId = ref<string | null>(null)

  // UI 状态
  const selectedPosition = ref<Position | null>(null)
  const validMoves = ref<Position[]>([])
  const lastMove = ref<Move | null>(null)
  const isInCheck = ref(false)
  const checkPosition = ref<Position | null>(null)
  const isAIThinking = ref(false)

  // 走棋历史
  const moveHistory = ref<MoveRecord[]>([])

  // 求和请求
  const drawRequestFrom = ref<string | null>(null)

  // 计时器
  let timerInterval: number | null = null

  // 待确认的走棋（发送后等待 move_result 推送确认）
  let pendingMove: Move | null = null

  // 走棋动画状态
  const animatingMove = ref<{
    from_row: number
    from_col: number
    to_row: number
    to_col: number
    duration: number
  } | null>(null)

  // 计算走棋动画时长（近处慢、远处快，整体≤800ms）
  function computeMoveDuration(move: Move): number {
    const dist = Math.sqrt(
      (move.to_row - move.from_row) ** 2 + (move.to_col - move.from_col) ** 2,
    )
    return Math.min(200 + Math.sqrt(dist) * 150, 800)
  }

  // 计算属性
  const isMyTurn = computed(() => currentTurn.value === yourColor.value)

  const myColorName = computed(() => (yourColor.value === Color.Red ? '红方' : '黑方'))

  const opponentColorName = computed(() => (yourColor.value === Color.Red ? '黑方' : '红方'))

  // ===== 合法走法计算 =====

  function getPieceAt(row: number, col: number): number {
    if (row < 0 || row >= 10 || col < 0 || col >= 9) return -1
    return board.value[row][col]
  }

  function inBoard(row: number, col: number): boolean {
    return row >= 0 && row < 10 && col >= 0 && col < 9
  }

  // 计算指定位置棋子的合法走法（已过滤送将、对将、必须应将）
  function computeValidMoves(row: number, col: number): Position[] {
    const piece = board.value[row][col]
    if (piece < 0) return []

    const color = getPieceColor(piece as any)
    if (color === Color.None) return []

    const moves: Position[] = []
    const pieceType = piece % 10 // 0=king, 1=advisor, 2=bishop, 3=knight, 4=rook, 5=cannon, 6=pawn

    switch (pieceType) {
      case 0: computeKingMoves(row, col, color, moves); break
      case 1: computeAdvisorMoves(row, col, color, moves); break
      case 2: computeBishopMoves(row, col, color, moves); break
      case 3: computeKnightMoves(row, col, color, moves); break
      case 4: computeRookMoves(row, col, color, moves); break
      case 5: computeCannonMoves(row, col, color, moves); break
      case 6: computePawnMoves(row, col, color, moves); break
    }

    // 过滤送将、对将的非法走法
    return moves.filter(pos => !wouldBeInCheck(row, col, pos.row, pos.col, color))
  }

  function canMoveTo(row: number, col: number, color: number): boolean {
    if (!inBoard(row, col)) return false
    const target = board.value[row][col]
    if (target < 0) return true
    return getPieceColor(target as any) !== color
  }

  function computeKingMoves(row: number, col: number, color: number, moves: Position[]) {
    const dirs = [[-1,0],[1,0],[0,-1],[0,1]]
    const palace = color === Color.Red
      ? { minRow: 7, maxRow: 9, minCol: 3, maxCol: 5 }
      : { minRow: 0, maxRow: 2, minCol: 3, maxCol: 5 }
    for (const [dr, dc] of dirs) {
      const nr = row + dr, nc = col + dc
      if (nr >= palace.minRow && nr <= palace.maxRow && nc >= palace.minCol && nc <= palace.maxCol) {
        if (canMoveTo(nr, nc, color)) moves.push({ row: nr, col: nc })
      }
    }
  }

  function computeAdvisorMoves(row: number, col: number, color: number, moves: Position[]) {
    const dirs = [[-1,-1],[-1,1],[1,-1],[1,1]]
    const palace = color === Color.Red
      ? { minRow: 7, maxRow: 9, minCol: 3, maxCol: 5 }
      : { minRow: 0, maxRow: 2, minCol: 3, maxCol: 5 }
    for (const [dr, dc] of dirs) {
      const nr = row + dr, nc = col + dc
      if (nr >= palace.minRow && nr <= palace.maxRow && nc >= palace.minCol && nc <= palace.maxCol) {
        if (canMoveTo(nr, nc, color)) moves.push({ row: nr, col: nc })
      }
    }
  }

  function computeBishopMoves(row: number, col: number, color: number, moves: Position[]) {
    const dirs = [[-2,-2],[-2,2],[2,-2],[2,2]]
    const blocks = [[-1,-1],[-1,1],[1,-1],[1,1]]
    for (let i = 0; i < 4; i++) {
      const nr = row + dirs[i][0], nc = col + dirs[i][1]
      const br = row + blocks[i][0], bc = col + blocks[i][1]
      if (!inBoard(nr, nc)) continue
      // 不能过河
      if (color === Color.Red && nr < 5) continue
      if (color === Color.Black && nr > 4) continue
      // 塞象眼
      if (board.value[br][bc] >= 0) continue
      if (canMoveTo(nr, nc, color)) moves.push({ row: nr, col: nc })
    }
  }

  function computeKnightMoves(row: number, col: number, color: number, moves: Position[]) {
    // 日字走法，先直后斜
    const jumps = [
      { dr: -2, dc: -1, br: -1, bc: 0 },
      { dr: -2, dc: 1, br: -1, bc: 0 },
      { dr: 2, dc: -1, br: 1, bc: 0 },
      { dr: 2, dc: 1, br: 1, bc: 0 },
      { dr: -1, dc: -2, br: 0, bc: -1 },
      { dr: -1, dc: 2, br: 0, bc: 1 },
      { dr: 1, dc: -2, br: 0, bc: -1 },
      { dr: 1, dc: 2, br: 0, bc: 1 },
    ]
    for (const j of jumps) {
      const nr = row + j.dr, nc = col + j.dc
      const blkR = row + j.br, blkC = col + j.bc
      if (!inBoard(nr, nc)) continue
      // 蹩马腿
      if (board.value[blkR][blkC] >= 0) continue
      if (canMoveTo(nr, nc, color)) moves.push({ row: nr, col: nc })
    }
  }

  function computeRookMoves(row: number, col: number, color: number, moves: Position[]) {
    const dirs = [[-1,0],[1,0],[0,-1],[0,1]]
    for (const [dr, dc] of dirs) {
      let nr = row + dr, nc = col + dc
      while (inBoard(nr, nc)) {
        const target = board.value[nr][nc]
        if (target < 0) {
          moves.push({ row: nr, col: nc })
        } else {
          if (getPieceColor(target as any) !== color) moves.push({ row: nr, col: nc })
          break
        }
        nr += dr; nc += dc
      }
    }
  }

  function computeCannonMoves(row: number, col: number, color: number, moves: Position[]) {
    const dirs = [[-1,0],[1,0],[0,-1],[0,1]]
    for (const [dr, dc] of dirs) {
      let nr = row + dr, nc = col + dc
      let jumped = false
      while (inBoard(nr, nc)) {
        const target = board.value[nr][nc]
        if (!jumped) {
          if (target < 0) {
            moves.push({ row: nr, col: nc })
          } else {
            jumped = true // 遇到炮架
          }
        } else {
          if (target >= 0) {
            if (getPieceColor(target as any) !== color) moves.push({ row: nr, col: nc })
            break // 翻山后遇到第一个棋子就停
          }
        }
        nr += dr; nc += dc
      }
    }
  }

  function computePawnMoves(row: number, col: number, color: number, moves: Position[]) {
    if (color === Color.Red) {
      // 红兵：向上走
      if (inBoard(row - 1, col) && canMoveTo(row - 1, col, color)) moves.push({ row: row - 1, col })
      // 过河后可左右
      if (row <= 4) {
        if (inBoard(row, col - 1) && canMoveTo(row, col - 1, color)) moves.push({ row, col: col - 1 })
        if (inBoard(row, col + 1) && canMoveTo(row, col + 1, color)) moves.push({ row, col: col + 1 })
      }
    } else {
      // 黑卒：向下走
      if (inBoard(row + 1, col) && canMoveTo(row + 1, col, color)) moves.push({ row: row + 1, col })
      // 过河后可左右
      if (row >= 5) {
        if (inBoard(row, col - 1) && canMoveTo(row, col - 1, color)) moves.push({ row, col: col - 1 })
        if (inBoard(row, col + 1) && canMoveTo(row, col + 1, color)) moves.push({ row, col: col + 1 })
      }
    }
  }

  // ===== 将军 / 送将 / 对将 检测 =====

  /** 在临时棋盘上检查指定颜色的将/帅是否被对方攻击 */
  function isKingAttacked(brd: number[][], color: number): boolean {
    // 找到将/帅位置
    const kingPiece = color === Color.Red ? 0 : 10
    let kr = -1, kc = -1
    for (let r = 0; r < 10; r++) {
      for (let c = 0; c < 9; c++) {
        if (brd[r][c] === kingPiece) { kr = r; kc = c; break }
      }
      if (kr >= 0) break
    }
    if (kr < 0) return true // 将/帅不在棋盘上（被吃了），视为被攻击

    const opponent = color === Color.Red ? 1 : 0

    // 检查对方棋子能否攻击到 (kr, kc)
    // 1. 车 / 将对将（直线攻击）
    // 2. 马（日字攻击）
    // 3. 炮（翻山攻击）
    // 4. 兵/卒（贴身攻击）

    // 车 & 对将检测：沿四个直线方向
    const dirs = [[-1,0],[1,0],[0,-1],[0,1]]
    for (const [dr, dc] of dirs) {
      let nr = kr + dr, nc = kc + dc
      while (inBoard(nr, nc)) {
        const p = brd[nr][nc]
        if (p >= 0) {
          const pc = getPieceColor(p as any)
          if (pc === opponent) {
            const pt = p % 10
            if (pt === 4) return true // 对方车
            if (pt === 0) return true // 对将（两将面对面，中间无子）
          }
          break // 遇到棋子就停
        }
        nr += dr; nc += dc
      }
    }

    // 炮检测：沿四个直线方向找炮架后攻击
    for (const [dr, dc] of dirs) {
      let nr = kr + dr, nc = kc + dc
      let jumped = false
      while (inBoard(nr, nc)) {
        const p = brd[nr][nc]
        if (p >= 0) {
          if (!jumped) {
            jumped = true // 第一个子作为炮架
          } else {
            // 炮架后的第一个子
            const pc = getPieceColor(p as any)
            if (pc === opponent && p % 10 === 5) return true // 对方炮
            break
          }
        }
        nr += dr; nc += dc
      }
    }

    // 马检测：检查对方马能否跳到 (kr, kc)
    // 马从 (mr, mc) 跳到 (kr, kc)，需要检查蹩腿
    const knightJumps = [
      { dr: -2, dc: -1, br: -1, bc: 0 },
      { dr: -2, dc: 1, br: -1, bc: 0 },
      { dr: 2, dc: -1, br: 1, bc: 0 },
      { dr: 2, dc: 1, br: 1, bc: 0 },
      { dr: -1, dc: -2, br: 0, bc: -1 },
      { dr: -1, dc: 2, br: 0, bc: 1 },
      { dr: 1, dc: -2, br: 0, bc: -1 },
      { dr: 1, dc: 2, br: 0, bc: 1 },
    ]
    for (const j of knightJumps) {
      const mr = kr - j.dr, mc = kc - j.dc // 马的位置
      if (!inBoard(mr, mc)) continue
      const p = brd[mr][mc]
      if (p >= 0 && getPieceColor(p as any) === opponent && p % 10 === 3) {
        // 对方马在 (mr, mc)，检查蹩腿（从马的位置出发）
        const blkR = mr + j.br, blkC = mc + j.bc
        if (inBoard(blkR, blkC) && brd[blkR][blkC] < 0) {
          return true // 马可以跳到将/帅位置
        }
      }
    }

    // 兵/卒检测：贴身攻击
    if (color === Color.Red) {
      // 红帅被黑卒攻击：黑卒在帅的上方一格，或左右一格（黑卒过河后）
      if (inBoard(kr - 1, kc) && brd[kr - 1][kc] === 16) return true // 黑卒在上方
      if (inBoard(kr, kc - 1) && brd[kr][kc - 1] === 16 && kr >= 5) return true // 黑卒在左（过河）
      if (inBoard(kr, kc + 1) && brd[kr][kc + 1] === 16 && kr >= 5) return true // 黑卒在右（过河）
    } else {
      // 黑将被红兵攻击：红兵在将的下方一格，或左右一格（红兵过河后）
      if (inBoard(kr + 1, kc) && brd[kr + 1][kc] === 6) return true // 红兵在下方
      if (inBoard(kr, kc - 1) && brd[kr][kc - 1] === 6 && kr <= 4) return true // 红兵在左（过河）
      if (inBoard(kr, kc + 1) && brd[kr][kc + 1] === 6 && kr <= 4) return true // 红兵在右（过河）
    }

    return false
  }

  /** 检查走棋后己方是否会被将军（含对将检测） */
  function wouldBeInCheck(fromRow: number, fromCol: number, toRow: number, toCol: number, color: number): boolean {
    // 在临时棋盘上模拟走棋
    const brd = board.value.map(row => [...row])
    brd[toRow][toCol] = brd[fromRow][fromCol]
    brd[fromRow][fromCol] = -1
    return isKingAttacked(brd, color)
  }

  /** 更新当前局的将军状态（走棋后调用） */
  function updateCheckState() {
    // 检查当前走棋方（刚切换后的那一方）是否被将军
    const color = currentTurn.value
    isInCheck.value = isKingAttacked(board.value, color)
    if (isInCheck.value) {
      // 找到被将军方的将/帅位置
      const kingPiece = color === Color.Red ? 0 : 10
      for (let r = 0; r < 10; r++) {
        for (let c = 0; c < 9; c++) {
          if (board.value[r][c] === kingPiece) {
            checkPosition.value = { row: r, col: c }
            return
          }
        }
      }
    } else {
      checkPosition.value = null
    }
  }

  // ===== 游戏操作 =====

  // 发送走棋（仅发请求，棋盘在 handleMoveResult 中更新）
  function sendMove(move: Move) {
    const { from_pos, to_pos } = moveToPos(move)
    console.log('[Game] Send move:', from_pos, '->', to_pos)
    pendingMove = move
    wsClient.send({ type: WSMsgType.GAME_MOVE, seq: 0, data: { from_pos, to_pos } })

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

  // 点击"开始"（READY 阶段）
  function sendReady() {
    wsClient.send({ type: WSMsgType.GAME_READY, seq: 0, data: {} })
    iAmReady.value = true
  }

  // 点击"再来一局"（FINISHED 阶段）
  async function sendRematch() {
    iWantRematch.value = true

    try {
      // 如果本地还没切到 finished，先等一下，给服务端处理留出时间
      if (phase.value !== 'finished') {
        await new Promise((r) => setTimeout(r, 200))
      }
      // 单次请求，不重试。服务端可能返回 4006（Not in finished phase）。
      await wsClient.request(WSMsgType.GAME_REMATCH, {}, 5000)
      // 成功发送并被服务器接受
      return
    } catch (err: any) {
      // 不进行重试：如果是 4006，提示用户并忽略；其他错误则清理状态并记录
      if ((err instanceof WSError && err.code === 4006) || err?.code === 4006) {
        console.warn('[Game] Rematch rejected (not finished).')
        showToast('当前局还未结束，无法再来一局', 'warning')
        // 保持 iWantRematch 的状态可由 UI 或后续同步清理，这里保持为 true 以反映用户意愿
        return
      }

      console.error('[Game] Rematch failed:', err)
      iWantRematch.value = false
      showToast('再来一局请求失败，请稍后重试', 'error')
      return
    }
  }

  // 选择棋子
  function selectPiece(position: Position) {
    if (!isMyTurn.value || isGameOver.value || !isGameStarted.value) return

    const piece = board.value[position.row][position.col]
    if (piece < 0) return

    // 检查是否是己方棋子
    const pieceColor = getPieceColor(piece as any)
    if (pieceColor !== yourColor.value) return

    // 再次点击同一棋子 → 取消选中，播放落子音效
    if (selectedPosition.value &&
        selectedPosition.value.row === position.row &&
        selectedPosition.value.col === position.col) {
      selectedPosition.value = null
      validMoves.value = []
      getSoundManager().play('putdown')
      return
    }

    selectedPosition.value = position
    validMoves.value = computeValidMoves(position.row, position.col)

    // 拾子音效
    getSoundManager().play('pickup')
  }

  // 清除选择
  function clearSelection() {
    selectedPosition.value = null
    validMoves.value = []
  }

  /** 红方列名：从右往左 一~九（col 8=一, col 0=九） */
  const RED_COL_NAMES = ['一', '二', '三', '四', '五', '六', '七', '八', '九']
  /** 黑方列名：从左往右 １~９（col 0=１, col 8=９） */
  const BLACK_COL_NAMES = ['１', '２', '３', '４', '５', '６', '７', '８', '９']

  // 生成走棋记谱（从棋子自身方的视角）
  function getMoveNotation(move: Move, piece: number): string {
    const pieceName = (PieceChars as Record<number, string>)[piece] || '?'
    const pieceType = piece % 10   // 0=将/帅, 1=士, 2=象, 3=马, 4=车, 5=炮, 6=兵
    const pieceColor = Math.floor(piece / 10)  // 0=红, 1=黑
    const isRed = pieceColor === 0

    const { from_col, to_col, from_row, to_row } = move

    // 红方列坐标从右往左一~九；黑方列坐标从左往右１~９
    const colName = (col: number) =>
      isRed ? RED_COL_NAMES[8 - col] : BLACK_COL_NAMES[col]

    // 检查走棋前同一纵线上是否存在同色同类型棋子（用于前/中/后区分）
    // 走棋后棋子已移走，需把 from_row 补回；纵向移动时 to_row 上的就是本棋子，需排除
    const sameOnCol: number[] = [from_row]
    for (let r = 0; r < 10; r++) {
      if (r === from_row) continue
      if (from_col === to_col && r === to_row) continue  // 纵向移动：to_row 上是本棋子，避免重复计算
      const p = board.value[r][from_col]
      if (p >= 0 && p % 10 === pieceType && Math.floor(p / 10) === pieceColor) {
        sameOnCol.push(r)
      }
    }

    let prefix: string
    if (sameOnCol.length >= 2) {
      // 多个同色同型棋子在同一纵线 → 用 前/中/后 区分
      // "前" 指更靠近对方半场：红方前=行号小, 黑方前=行号大
      sameOnCol.sort((a, b) => isRed ? a - b : b - a)
      const idx = sameOnCol.indexOf(from_row)
      const labels = sameOnCol.length === 2 ? ['前', '后'] : ['前', '中', '后']
      prefix = (labels[idx] || '?') + pieceName
    } else {
      prefix = pieceName + colName(from_col)
    }

    // 走法说明（从棋子自身方视角）
    // 红方 进 = 向上 (row 减小)，退 = 向下 (row 增大)
    // 黑方 进 = 向下 (row 增大)，退 = 向上 (row 减小)
    let action: string

    if (from_col === to_col) {
      // 直线移动：进N / 退N（N 为相对步数）
      const isForward = isRed ? (to_row < from_row) : (to_row > from_row)
      const steps = Math.abs(to_row - from_row)
      const stepsStr = isRed ? RED_COL_NAMES[steps - 1] : BLACK_COL_NAMES[steps - 1]
      action = (isForward ? '进' : '退') + stepsStr
    } else if (from_row === to_row) {
      // 横向移动：平
      action = '平' + colName(to_col)
    } else {
      // 斜线移动（马、士、象）：进/退 + 目标列
      const isForward = isRed ? (to_row < from_row) : (to_row > from_row)
      action = (isForward ? '进' : '退') + colName(to_col)
    }

    return prefix + action
  }

  // 添加走棋记录
  function addMoveRecord(move: Move, piece: number, captured: number) {
    const notation = getMoveNotation(move, piece)
    moveHistory.value.push({
      move,
      piece,
      captured,
      notation,
      moveNumber: moveHistory.value.length + 1,
    })
  }

  // ===== 推送消息处理 =====

  // 处理游戏开始
  function handleGameStart(data: GameStartData) {
    console.log('[Game] Game started, room=', data.room_id, 'side=', data.your_side, 'data=', JSON.stringify(data).slice(0, 200))
    try {
      roomId.value = data.room_id
      board.value = getInitialBoard()
      const authStore = useAuthStore()
      const userId = authStore.user?.user_id
      // 某些情况下（对手为 AI）服务端可能只返回一侧玩家信息，视为正常情况
      if (!data.red_player && !data.black_player) {
        console.error('[Game] Game start missing both player infos:', data)
      } else if (!data.red_player || !data.black_player) {
        console.warn('[Game] Game start: one player info missing (likely AI).', 'red=', data.red_player, 'black=', data.black_player)
      }
      yourColor.value = data.your_side === 'red' ? 0 : 1

      // 调试：验证颜色映射
      console.log('[Game] Color check: your_side=', data.your_side, 'yourColor=', yourColor.value,
        'myColor=', yourColor.value === 0 ? '红方' : '黑方',
        'board[0][4]=', board.value[0][4], '(should be BlackKing=10)',
        'board[9][4]=', board.value[9][4], '(should be RedKing=0)')

      redTime.value = data.initial_time
      blackTime.value = data.initial_time
      currentTurn.value = 0
      isGameStarted.value = true
      isGameOver.value = false
      isAIThinking.value = false
      drawRequestFrom.value = null
      moveHistory.value = []
      phase.value = 'playing'
      iAmReady.value = false
      opponentReady.value = false
      iWantRematch.value = false
      opponentWantsRematch.value = false
      showResultDialog.value = false
      myRatingChange.value = 0
      console.log('[Game] isGameStarted set to true, yourColor=', yourColor.value)
      startTimer()

      // 游戏开始语音
      const sound = getSoundManager()
      sound.play('start')
      // 如果红方先手且自己不是红方，播 your_turn
      if (yourColor.value !== 0) {
        setTimeout(() => sound.play('your_turn'), 1500)
      }
    } catch (err) {
      console.error('[Game] Error in handleGameStart:', err)
    }
  }

  // 执行走棋并播放动画
  // 音效播放顺序：
  //   对方走棋：pickup(拿起) → voice(语音) + animation(动画) → putdown(落子)
  //   自己走棋：voice + animation → putdown
  function applyMoveWithAnimation(move: Move, isOpponentMove: boolean = false) {
    const piece = board.value[move.from_row][move.from_col]
    if (piece === -1) {
      console.warn('[Game] applyMoveWithAnimation: from position is empty, skipping', move)
      return
    }

    const duration = computeMoveDuration(move)
    const sound = getSoundManager()

    // Step 1: 对方走棋时先播放拿起棋子音效
    if (isOpponentMove) {
      sound.play('pickup')
    }

    // Step 2: 开始动画 + 更新棋盘 + 播放走棋语音（语音与动画同步开始）
    // 对方走棋时稍延迟（让 pickup 音效先发出），自己走棋立即开始
    const animStartDelay = isOpponentMove ? 120 : 0
    const captured = board.value[move.to_row][move.to_col]

    setTimeout(() => {
      animatingMove.value = {
        from_row: move.from_row,
        from_col: move.from_col,
        to_row: move.to_row,
        to_col: move.to_col,
        duration,
      }

      board.value[move.to_row][move.to_col] = piece
      board.value[move.from_row][move.from_col] = -1
      lastMove.value = move
      currentTurn.value = currentTurn.value === 0 ? 1 : 0
      addMoveRecord(move, piece, captured)
      updateCheckState()

      // 走棋语音（按优先级规则播放）
      if (isInCheck.value) {
        // 规则1: 将军 - 播放将军音效+语音（优先级最高）
        sound.play('check')
        sound.play('check_voice')
        lastVoiceEndTime = Date.now() + 1200
      } else {
        // 规则2-11: 非将军时按优先级选择语音
        const voiceKey = _determineMoveVoice(move, piece, captured)
        if (voiceKey) {
          sound.play(voiceKey)
          lastVoiceEndTime = Date.now() + 1200
        }
      }
    }, animStartDelay)

    // Step 3: 动画结束后播放落子音效 + 清除动画状态
    setTimeout(() => {
      if (animatingMove.value &&
        animatingMove.value.from_row === move.from_row &&
        animatingMove.value.from_col === move.from_col) {
        animatingMove.value = null
      }
      // 落子音效（动画结束后播放）
      sound.play('putdown')
      // 吃子音效
      if (captured >= 0) {
        sound.play('capture')
      }
    }, animStartDelay + duration + 50)
  }

  // ===== 走棋语音规则（优先级从高到低）=====

  /** 规则2-11: 非将军时，根据走棋情况选择语音 */
  function _determineMoveVoice(move: Move, piece: number, captured: number): SoundKey | null {
    // 规则2: 吃子 → 播放对应的吃子语音
    if (captured >= 0) {
      return _getEatVoice(captured)
    }

    const pieceType = piece % 10   // 0=将/帅, 1=士, 2=象, 3=马, 4=车, 5=炮, 6=兵
    const pieceColor = Math.floor(piece / 10) // 0=红, 1=黑
    const isBackward = pieceColor === 0
      ? (move.to_row > move.from_row)   // 红方向下=后退
      : (move.to_row < move.from_row)   // 黑方向上=后退
    const isHorizontal = move.from_row === move.to_row

    switch (pieceType) {
      case 0: // 将/帅
        if (pieceColor == 0) {
          // 红
          if (isHorizontal) {
            return 'level_rking'
          }
          return isBackward ? 'back_rking' : 'front_rking'
        } else {
          if (isHorizontal) {
            return 'level_bking'
          }
          return isBackward ? 'back_bking' : 'front_bking'
        }
      case 1: // 士/仕
        // 规则3: 向前移动士 → voice_move_advisor
        // 规则4: 向后移动士 → voice_luo_advisor
        return isBackward ? 'drop_advisor' : 'advisor'

      case 2: // 象/相
        // 规则5: 向前走象 → voice_move_elephant
        // 规则6: 向后走象 → voice_luo_elephant
        return isBackward ? 'drop_elephant' : 'elephant'

      case 5: // 炮
        // 规则7: 炮从初始位置平移到中路 → voice_move_cannon (当头炮)
        if (_isCannonAtInitialPos(move, pieceColor) && move.to_col === 4) {
          return 'cannon'
        }
        // 规则8: 炮横向移动 → voice_ping_cannon (平炮)
        if (isHorizontal) {
          return 'level_cannon'
        } 
        // 默认: 炮其它走法 → 当头炮语音
        return isBackward ? 'back_cannon' : 'front_cannon'

      case 4: // 车
        // 规则9: 车从初始位置移动 → voice_move_chariot (出车)
        if (_isChariotAtInitialPos(move, pieceColor) && isHorizontal) {
          return 'chariot'
        }
        if (isHorizontal) {
          return 'level_chariot'
        }
        return isBackward ? 'back_chariot' : 'front_chariot'

      case 3: // 马
        // 规则10: 移动马 → voice_move_horse
        return 'horse'

      case 6: // 兵/卒
        // 规则11: 兵/卒向前移动 → voice_move_pawn
        if (!isHorizontal) {
          return pieceColor == 0 ? 'bing' : 'pawn'
        }
        // 兵/卒平移 → 无专属语音
        return null

      default:
        // 将/帅无专属走棋语音（移动将/帅造成将军时由规则1处理）
        return null
    }
  }

  /** 根据被吃棋子类型返回对应的吃子语音 (规则2) */
  function _getEatVoice(captured: number): SoundKey | null {
    const eatMap: Record<number, SoundKey> = {
      [Piece.RedAdvisor]: 'eat_advisor',
      [Piece.RedBishop]: 'eat_elephant',
      [Piece.RedKnight]: 'eat_horse',
      [Piece.RedRook]: 'eat_chariot',
      [Piece.RedCannon]: 'eat_cannon',
      [Piece.RedPawn]: 'eat_pawn',
      [Piece.BlackAdvisor]: 'eat_advisor',
      [Piece.BlackBishop]: 'eat_elephant',
      [Piece.BlackKnight]: 'eat_horse',
      [Piece.BlackRook]: 'eat_chariot',
      [Piece.BlackCannon]: 'eat_cannon',
      [Piece.BlackPawn]: 'eat_pawn',
    }
    return eatMap[captured] || null
  }

  /** 判断炮是否在初始位置 */
  function _isCannonAtInitialPos(move: Move, color: number): boolean {
    if (color === 0) { // 红方
      return move.from_row === 7 && (move.from_col === 1 || move.from_col === 7)
    } else { // 黑方
      return move.from_row === 2 && (move.from_col === 1 || move.from_col === 7)
    }
  }

  /** 判断车是否在初始位置 */
  function _isChariotAtInitialPos(move: Move, color: number): boolean {
    if (color === 0) { // 红方
      return move.from_row === 9 && (move.from_col === 0 || move.from_col === 8)
    } else { // 黑方
      return move.from_row === 0 && (move.from_col === 0 || move.from_col === 8)
    }
  }

  // 处理走棋结果 (自己的走棋确认，由服务端 push 触发)
  function handleMoveResult(data: MoveResultData) {
    if (data.success) {
      // 用服务器权威时间同步双方剩余时间（消除本地计时器漂移）
      if (data.red_remaining_time != null) redTime.value = data.red_remaining_time
      if (data.black_remaining_time != null) blackTime.value = data.black_remaining_time

      const move = pendingMove
      pendingMove = null
      if (move) {
        applyMoveWithAnimation(move, false) // 自己走棋：不需要 pickup 音效
      }
    } else {
      pendingMove = null
      showMoveError(data.message || '走棋无效')
    }
  }

  // 处理对手走棋
  function handleOpponentMove(data: OpponentMoveData) {
    console.log('[Game] Opponent move:', data.from_pos, '->', data.to_pos)
    // 用服务器权威时间同步双方剩余时间（消除本地计时器漂移）
    if (data.red_remaining_time != null) redTime.value = data.red_remaining_time
    if (data.black_remaining_time != null) blackTime.value = data.black_remaining_time

    const move = posToMove(data.from_pos, data.to_pos)
    const duration = computeMoveDuration(move)
    applyMoveWithAnimation(move, true) // 对方走棋：先播 pickup 音效
    // 对手走完后轮到自己，播 your_turn（等走棋动画和语音结束后再播）
    if (!isGameOver.value) {
      setTimeout(() => {
        getSoundManager().play('your_turn')
      }, duration + 1200 + 200)
    }
  }

  // 处理 AI 思考中
  function handleAIThinking() {
    isAIThinking.value = true
  }

  // 处理 AI 走棋
  function handleAIMove(data: AIMoveData) {
    isAIThinking.value = false
    // 用服务器权威时间同步双方剩余时间（消除本地计时器漂移）
    if (data.red_remaining_time != null) redTime.value = data.red_remaining_time
    if (data.black_remaining_time != null) blackTime.value = data.black_remaining_time

    const move = posToMove(data.from_pos, data.to_pos)
    applyMoveWithAnimation(move, true) // AI 走棋 = 对方走棋：先播 pickup 音效
  }

  // 处理游戏结束
  function handleGameOver(data: GameOverData) {
    console.log('[Game] Game over, winner=', data.winner, 'reason=', data.reason)

    // 如果最后一步走棋还没被动画展示 （move_result/opponent_move 丢失了），
    // 用服务器发来的 last_move 补播动画；若已有动画在播放则跳过
    if (data.last_move && !animatingMove.value) {
      console.log('[Game] Animating last_move from game_over:', data.last_move)
      const move: Move = {
        from_row: data.last_move.from_pos[0],
        from_col: data.last_move.from_pos[1],
        to_row: data.last_move.to_pos[0],
        to_col: data.last_move.to_pos[1],
      }
      // 清除因网络原因残留的 pendingMove，服务器消息是权威的
      pendingMove = null
      applyMoveWithAnimation(move, true) // game_over 补播最后一手：视为对方走棋
    }

    isGameOver.value = true
    gameResult.value = data.winner
    gameReason.value = data.reason
    winner.value = data.winner === 'red' ? 0 : data.winner === 'black' ? 1 : -1
    isAIThinking.value = false
    phase.value = 'finished'

    // 计算自己的积分变化
    const change = yourColor.value === 0 ? data.red_rating_change : data.black_rating_change
    myRatingChange.value = change ?? 0

    stopTimer()

    // 游戏结束音效和语音
    const sound = getSoundManager()
    const isWin = (data.winner === 'red' && yourColor.value === 0) || (data.winner === 'black' && yourColor.value === 1)
    const isDraw = data.winner === 'draw'

    // 音效立即播放
    if (isDraw) {
      sound.play('draw')
    } else if (isWin) {
      sound.play('win')
    } else {
      sound.play('lose')
    }

    // 语音等待前面的播放完成
    const voiceDelay = lastVoiceEndTime > 0
      ? Math.max(300, lastVoiceEndTime - Date.now() + 300)
      : 300
    lastVoiceEndTime = 0
    setTimeout(() => {
      if (data.winner === 'draw') {
        sound.play('draw_voice')
      } else if (data.winner === 'red') {
        sound.play('red_win')
      } else {
        sound.play('black_win')
      }
    }, voiceDelay)

    // 等待所有走棋动画完成后再显示结果弹窗
    // handleGameOver 可能在最后一手走棋消息之前到达，需要动态等待动画开始并完成
    const MIN_DIALOG_DELAY_MS = 600
    let stableChecks = 0

    function waitForAnimationAndShowResult() {
      if (animatingMove.value) {
        // 当前有动画正在播放，等待动画完成后重新检查
        stableChecks = 0
        setTimeout(waitForAnimationAndShowResult, animatingMove.value.duration + 80)
        return
      }

      stableChecks++
      if (stableChecks < 4) {
        // 动画已结束，但可能还有新的走棋消息要送达（因网络时序导致走棋延迟到达）
        // 额外检查几次确保没有新动画
        setTimeout(waitForAnimationAndShowResult, 180)
        return
      }

      // 确认所有动画完成且稳定，先用服务器的权威 FEN 确保棋盘状态正确，再显示结果弹窗
      const remaining = Math.max(MIN_DIALOG_DELAY_MS - stableChecks * 180 + 50, 50)
      setTimeout(() => {
        // 以服务器 FEN 为权威数据源，保证棋盘是最终正确状态
        if (data.fen) {
          const parsed = parseFEN(data.fen)
          if (parsed.length === 10 && parsed.every((r: number[]) => r.length === 9)) {
            board.value = parsed
          }
        }
        showResultDialog.value = true
      }, remaining)
    }

    setTimeout(waitForAnimationAndShowResult, 50)
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

  // 处理对手点击"开始"
  function handleOpponentReady(data: OpponentReadyData) {
    console.log('[Game] Opponent ready, user_id=', data.user_id)
    opponentReady.value = true
  }

  // 处理对手点击"再来一局"
  function handleOpponentRematch(data: OpponentRematchData) {
    console.log('[Game] Opponent wants rematch, user_id=', data.user_id)
    opponentWantsRematch.value = true
  }

  // 处理对手离开（回到 WAITING 状态）
  function handlePlayerLeft(data: any) {
    console.log('[Game] Opponent left, phase=', data.phase)
    if (data.phase === 'waiting') {
      phase.value = 'waiting'
      iAmReady.value = false
      opponentReady.value = false
      iWantRematch.value = false
      opponentWantsRematch.value = false
      isGameStarted.value = false
      showResultDialog.value = false
    }
  }

  // 处理状态同步 (断线重连)
  function handleStateSync(data: StateSyncData) {
    console.log('[Game] State sync, room=', data.room_id, 'phase=', data.phase, 'side=', data.your_side)

    // 判断是否为同页面重连（当前已在同一房间的 Game 页面）
    const currentPath = router.currentRoute.value.path
    const isSameGamePage = currentPath === `/game/${data.room_id}`

    // 同页面重连时保存当前对话框状态（用于恢复）
    const prevShowResultDialog = isSameGamePage ? showResultDialog.value : false
    const prevDrawRequestFrom = isSameGamePage ? drawRequestFrom.value : null

    roomId.value = data.room_id
    yourColor.value = data.your_side === 'red' ? 0 : 1
    redTime.value = data.red_remaining_time
    blackTime.value = data.black_remaining_time
    currentTurn.value = (data as any).current_side === 'black' ? 1 : 0

    // 断线重连提示：之前在 Playing 断线，重连后房间状态变了
    const authStore = useAuthStore()
    if (authStore.isReconnecting && authStore.previousAuthState === 'in_room') {
      if (authStore.phaseBeforeDisconnect === 'playing') {
        if (data.phase === 'finished') {
          authStore.reconnectMessages.push('对局已经结束！')
        } else if (data.phase !== 'playing') {
          authStore.reconnectMessages.push('你已离开房间')
        }
      }
    }

    const roomStore = useRoomStore()
    if (roomStore.currentRoom) {
      roomStore.currentRoom.phase = data.phase
      roomStore.currentRoom.yourSide = data.your_side === 'red' ? 'red' : 'black'
      roomStore.currentRoom.status = data.phase
      roomStore.currentRoom.gameStarted = data.phase === 'playing'
      const myUserId = useAuthStore().user?.user_id
      if (data.red_player && data.red_player.user_id !== myUserId) {
        roomStore.currentRoom.opponent = {
          userId: data.red_player.user_id,
          username: data.red_player.username,
          rating: data.red_player.rating,
        }
      } else if (data.black_player && data.black_player.user_id !== myUserId) {
        roomStore.currentRoom.opponent = {
          userId: data.black_player.user_id,
          username: data.black_player.username,
          rating: data.black_player.rating,
        }
      }
      roomStore.currentRoom.redReady = !!(data.red_player && data.ready_players?.includes(data.red_player.user_id))
      roomStore.currentRoom.blackReady = !!(data.black_player && data.ready_players?.includes(data.black_player.user_id))
    } else if (data.room_id) {
      const myUserId = useAuthStore().user?.user_id
      let opponent: { userId: number; username: string; rating?: number } | undefined
      if (data.red_player && data.red_player.user_id !== myUserId) {
        opponent = { userId: data.red_player.user_id, username: data.red_player.username, rating: data.red_player.rating }
      } else if (data.black_player && data.black_player.user_id !== myUserId) {
        opponent = { userId: data.black_player.user_id, username: data.black_player.username, rating: data.black_player.rating }
      }
      roomStore.setCurrentRoom({
        roomId: data.room_id,
        roomType: data.room_type,
        yourSide: data.your_side === 'red' ? 'red' : 'black',
        phase: data.phase,
        opponent,
      })
    }

    isGameStarted.value = data.phase === 'playing'
    isGameOver.value = false
    isAIThinking.value = false
    animatingMove.value = null
    phase.value = data.phase || 'waiting'
    showResultDialog.value = false
    drawRequestFrom.value = null
    iAmReady.value = false
    opponentReady.value = false
    iWantRematch.value = false
    opponentWantsRematch.value = false

    // 恢复 ready/rematch 状态
    if (data.ready_players && data.ready_players.length > 0) {
      const myUserId = useAuthStore().user?.user_id
      if (myUserId && data.ready_players.includes(myUserId)) {
        iAmReady.value = true
      }
      if (data.ready_players.some((id: number) => id !== myUserId)) {
        opponentReady.value = true
      }
    }
    if (data.rematch_players && data.rematch_players.length > 0) {
      const myUserId = useAuthStore().user?.user_id
      if (myUserId && data.rematch_players.includes(myUserId)) {
        iWantRematch.value = true
      }
      if (data.rematch_players.some((id: number) => id !== myUserId)) {
        opponentWantsRematch.value = true
      }
    }

    // FINISHED 状态下恢复
    if (data.phase === 'finished') {
      isGameOver.value = true
      // 同页面重连：如果之前结果对话框是打开的，恢复它
      // 跨页面重连：不自动弹出结果对话框
      if (isSameGamePage && prevShowResultDialog) {
        showResultDialog.value = true
      }
    }

    // 同页面重连：恢复求和请求对话框（如果断线前存在且游戏仍在进行中）
    if (isSameGamePage && prevDrawRequestFrom && data.phase === 'playing') {
      drawRequestFrom.value = prevDrawRequestFrom
    }

    // 从 FEN 恢复棋盘
    if (data.fen && data.phase === 'playing') {
      const parsed = parseFEN(data.fen)
      if (parsed.length === 10 && parsed.every(r => r.length === 9)) {
        board.value = parsed
      } else {
        board.value = getInitialBoard()
      }
      startTimer()
    } else {
      board.value = getInitialBoard()
    }

    // 恢复着法历史 (从 moves 列表重建)
    moveHistory.value = []
    if (data.moves && data.moves.length > 0) {
      const tempBoard = getInitialBoard()
      for (let i = 0; i < data.moves.length; i++) {
        const m = data.moves[i]
        const move = posToMove(m.from_pos, m.to_pos)
        const piece = tempBoard[move.from_row][move.from_col]
        const captured = tempBoard[move.to_row][move.to_col]
        // 更新临时棋盘以追踪后续走法
        tempBoard[move.to_row][move.to_col] = piece
        tempBoard[move.from_row][move.from_col] = Piece.Empty
        // 记录到历史（用 getMoveNotation 生成完整记谱，如"兵五进一"）
        const notation = piece >= 0 ? getMoveNotation(move, piece) : '?'
        moveHistory.value.push({
          move,
          piece,
          captured,
          notation,
          moveNumber: i + 1,
        })
      }
      // 设置最后一步走法
      const lastMoveData = data.moves[data.moves.length - 1]
      lastMove.value = posToMove(lastMoveData.from_pos, lastMoveData.to_pos)
    }

    // 导航到对局页面（无论 waiting 还是 playing，都在 Game 页显示）
    if (data.room_id) {
      const currentPath = router.currentRoute.value.path
      if (!currentPath.startsWith('/game/')) {
        router.replace(`/game/${data.room_id}`)
        console.log('[Game] State sync: navigating to game page, room=', data.room_id)
      }
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
    moveHistory.value = []
    animatingMove.value = null
    phase.value = 'waiting'
    iAmReady.value = false
    opponentReady.value = false
    iWantRematch.value = false
    opponentWantsRematch.value = false
    showResultDialog.value = false
    myRatingChange.value = 0
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
    moveHistory,
    animatingMove,
    phase,
    iAmReady,
    opponentReady,
    iWantRematch,
    opponentWantsRematch,
    showResultDialog,
    myRatingChange,
    isBoardFrozen,
    // 计算属性
    isMyTurn,
    myColorName,
    opponentColorName,
    // 方法
    sendMove,
    sendResign,
    sendDrawRequest,
    sendDrawAnswer,
    sendReady,
    sendRematch,
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
    handleOpponentReady,
    handleOpponentRematch,
    handlePlayerLeft,
  }
})
