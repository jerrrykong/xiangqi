/**
 * ChessBoard — 中国象棋棋盘组件
 * 使用 board.svg 背景图 + SVG 图片棋子
 * 新缩放机制：JS 动态计算 displayW/displayH，不使用 CSS transform:scale
 * 
 * @prop board - 10x9 棋盘数组 (piece codes)
 * @prop selectedPosition - 当前选中位置
 * @prop validMoves - 合法走法目标列表
 * @prop lastMove - 最后一步走法
 * @prop isInCheck - 是否被将军
 * @prop checkPosition - 被将军的位置
 * @prop yourColor - 玩家颜色 (0=红, 1=黑)
 * @prop isMyTurn - 是否走棋方
 * @prop isGameStarted - 游戏是否已开始
 * @prop frozen - 是否冻结棋盘
 * @prop animatingMove - 走棋动画数据
 */
<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import type { Position, Move } from '@/types/chess'
import { getPieceColor, Color, Piece } from '@/types/chess'
import ChessPiece from './ChessPiece.vue'
import type { PieceData } from './ChessPiece.vue'

const props = defineProps<{
  board: number[][]
  selectedPosition: Position | null
  validMoves: Position[]
  lastMove: Move | null
  isInCheck: boolean
  checkPosition: Position | null
  yourColor: 0 | 1
  isMyTurn: boolean
  isGameStarted: boolean
  frozen?: boolean
  animatingMove: {
    from_row: number
    from_col: number
    to_row: number
    to_col: number
    duration: number
  } | null
}>()

const emit = defineEmits<{
  (e: 'piece-click', position: Position): void
  (e: 'position-click', position: Position): void
  (e: 'board-click'): void
}>()

/** 棋盘原生参数 */
const baseUrl = import.meta.env.BASE_URL
const NATIVE_W = 540
const NATIVE_H = 600
const CELL_N = 60
const PAD_N = 30
const PSIZE_N = 48
const POFF_N = 24
const MIN_W = 300
const MIN_H = 333

/** 是否翻转棋盘（黑方视角） */
const isFlipped = computed(() => props.yourColor === 1)

/** 棋盘区域 ref */
const boardAreaRef = ref<HTMLElement | null>(null)

/** 缩放比和显示尺寸 */
const scale = ref(1)
const displayW = ref(NATIVE_W)
const displayH = ref(NATIVE_H)

/** ResizeObserver */
let resizeObserver: ResizeObserver | null = null

/** 计算缩放比 */
function updateScale() {
  const area = boardAreaRef.value
  if (!area) return
  const availW = area.clientWidth - 16  // 8px padding × 2
  const availH = area.clientHeight - 16
  if (availW <= 0 || availH <= 0) return

  let s = Math.min(availW / NATIVE_W, availH / NATIVE_H)
  s = Math.min(s, 1)  // 不放大超过原生
  if (NATIVE_W * s < MIN_W) s = MIN_W / NATIVE_W
  if (NATIVE_H * s < MIN_H) s = Math.max(s, MIN_H / NATIVE_H)

  scale.value = s
  displayW.value = Math.round(NATIVE_W * s)
  displayH.value = Math.round(NATIVE_H * s)
}

/** 坐标转换：翻转处理 */
function flipCol(col: number): number {
  return isFlipped.value ? (8 - col) : col
}
function flipRow(row: number): number {
  return isFlipped.value ? (9 - row) : row
}

/** piece code → PieceData 映射 */
const PIECE_TYPE_MAP: Record<number, string> = {
  [Piece.RedKing]: 'king',
  [Piece.RedAdvisor]: 'advisor',
  [Piece.RedBishop]: 'bishop',
  [Piece.RedKnight]: 'knight',
  [Piece.RedRook]: 'rook',
  [Piece.RedCannon]: 'cannon',
  [Piece.RedPawn]: 'pawn',
  [Piece.BlackKing]: 'king',
  [Piece.BlackAdvisor]: 'advisor',
  [Piece.BlackBishop]: 'bishop',
  [Piece.BlackKnight]: 'knight',
  [Piece.BlackRook]: 'rook',
  [Piece.BlackCannon]: 'cannon',
  [Piece.BlackPawn]: 'pawn',
}

/** 从棋盘数据生成 PieceData 列表 */
const pieces = computed<PieceData[]>(() => {
  const s = scale.value
  const result: PieceData[] = []
  for (let row = 0; row < props.board.length; row++) {
    for (let col = 0; col < props.board[row].length; col++) {
      const piece = props.board[row][col]
      if (piece < 0) continue  // 空位
      const side = piece < 10 ? 'red' : 'black'
      const type = PIECE_TYPE_MAP[piece]
      if (!type) continue
      result.push({
        id: `${side}-${type}-${row}-${col}`,
        col: flipCol(col),
        row: flipRow(row),
        type,
        side,
      })
    }
  }
  return result
})

/** 选中的棋子 ID */
const selectedPieceId = computed(() => {
  if (!props.selectedPosition) return null
  const { row, col } = props.selectedPosition
  const piece = props.board[row]?.[col]
  if (piece === undefined || piece < 0) return null
  const side = piece < 10 ? 'red' : 'black'
  const type = PIECE_TYPE_MAP[piece]
  return `${side}-${type}-${row}-${col}`
})

/** 合法走法位置集合（用于渲染提示） */
const validMoveSet = computed(() => {
  const set = new Set<string>()
  for (const m of props.validMoves) {
    set.add(`${flipCol(m.col)},${flipRow(m.row)}`)
  }
  return set
})

/** 最后一步走法的位置集合（用于高亮） */
const lastMoveSet = computed(() => {
  if (!props.lastMove) return new Set<string>()
  const set = new Set<string>()
  set.add(`${flipCol(props.lastMove.from_col)},${flipRow(props.lastMove.from_row)}`)
  set.add(`${flipCol(props.lastMove.to_col)},${flipRow(props.lastMove.to_row)}`)
  return set
})

/** 将军位置 */
const checkPos = computed(() => {
  if (!props.isInCheck || !props.checkPosition) return null
  return `${flipCol(props.checkPosition.col)},${flipRow(props.checkPosition.row)}`
})

/** 获取走棋动画数据 */
function getAnimData(piece: PieceData) {
  if (!props.animatingMove) return null
  // 判断该棋子是否是动画目标（to_row/to_col 翻转后匹配）
  const toCol = flipCol(props.animatingMove.to_col)
  const toRow = flipRow(props.animatingMove.to_row)
  if (piece.col !== toCol || piece.row !== toRow) return null

  const fromCol = flipCol(props.animatingMove.from_col)
  const fromRow = flipRow(props.animatingMove.from_row)
  return {
    dx: fromCol - toCol,  // 格数偏移
    dy: fromRow - toRow,
    duration: props.animatingMove.duration,
  }
}

/** 计算提示点的位置（像素） */
function getHintStyle(fCol: number, fRow: number) {
  const s = scale.value
  const cell = CELL_N * s
  const pad = PAD_N * s
  return {
    left: `${Math.round(pad + fCol * cell)}px`,
    top: `${Math.round(pad + fRow * cell)}px`,
  }
}

/** 计算高亮圆的位置和尺寸 */
function getHighlightStyle(fCol: number, fRow: number) {
  const s = scale.value
  const cell = CELL_N * s
  const pad = PAD_N * s
  const psize = Math.round(PSIZE_N * s)
  return {
    left: `${Math.round(pad + fCol * cell - psize / 2 - 2)}px`,
    top: `${Math.round(pad + fRow * cell - psize / 2 - 2)}px`,
    width: `${psize + 4}px`,
    height: `${psize + 4}px`,
  }
}

/** 判断某个翻转后的坐标是否有棋子（用于提示点样式区分） */
function hasPieceAt(fCol: number, fRow: number): boolean {
  const actualCol = isFlipped.value ? (8 - fCol) : fCol
  const actualRow = isFlipped.value ? (9 - fRow) : fRow
  const p = props.board[actualRow]?.[actualCol]
  return p !== undefined && p >= 0
}

/** 点击棋子 */
function handlePieceSelect(piece: PieceData) {
  if (props.frozen) return
  // 反翻转获取实际坐标
  const actualCol = isFlipped.value ? (8 - piece.col) : piece.col
  const actualRow = isFlipped.value ? (9 - piece.row) : piece.row
  emit('piece-click', { row: actualRow, col: actualCol })
}

/** 从像素坐标计算棋盘逻辑坐标（翻转前） */
function pixelToBoardPos(clientX: number, clientY: number): Position | null {
  const frame = boardAreaRef.value?.querySelector('.board-frame') as HTMLElement
  if (!frame) return null
  const rect = frame.getBoundingClientRect()
  const x = clientX - rect.left
  const y = clientY - rect.top
  const s = scale.value
  const cell = CELL_N * s
  const pad = PAD_N * s
  const fCol = Math.round((x - pad) / cell)
  const fRow = Math.round((y - pad) / cell)
  if (fCol < 0 || fCol > 8 || fRow < 0 || fRow > 9) return null
  const actualCol = isFlipped.value ? (8 - fCol) : fCol
  const actualRow = isFlipped.value ? (9 - fRow) : fRow
  return { row: actualRow, col: actualCol }
}

/** 判断指定逻辑坐标是否在合法走法列表中 */
function isValidMoveTarget(pos: Position): boolean {
  return props.validMoves.some(m => m.row === pos.row && m.col === pos.col)
}

/** 点击棋盘区域（智能判断走棋或取消选中） */
function handleBoardClick(event: MouseEvent) {
  if (props.frozen) return

  const pos = pixelToBoardPos(event.clientX, event.clientY)
  if (!pos) {
    emit('board-click')
    return
  }

  // 如果已选中棋子，且点击位置是合法走法目标 → 走棋
  if (props.selectedPosition && isValidMoveTarget(pos)) {
    emit('position-click', pos)
    return
  }

  // 点击位置有棋子 → 当作选子
  const piece = props.board[pos.row]?.[pos.col]
  if (piece !== undefined && piece >= 0) {
    emit('piece-click', pos)
    return
  }

  // 点击空白区域 → 取消选中
  emit('board-click')
}

/** 初始化 ResizeObserver */
function setupObserver() {
  if (resizeObserver) resizeObserver.disconnect()
  updateScale()
  if (boardAreaRef.value) {
    resizeObserver = new ResizeObserver(updateScale)
    resizeObserver.observe(boardAreaRef.value)
  }
}

onMounted(() => {
  setupObserver()
})

onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
})

// 监听 yourColor 变化后重新计算
watch(() => props.yourColor, () => {
  nextTick(updateScale)
})
</script>

<template>
  <div class="game-board-area" ref="boardAreaRef">
    <div
      class="board-frame"
      :style="{ width: displayW + 'px', height: displayH + 'px' }"
      @click="handleBoardClick"
    >
      <!-- 棋盘背景 -->
      <img :src="baseUrl + 'assets/svg/board.svg'" class="board-bg" alt="棋盘" />

      <!-- 最后一步高亮 -->
      <template v-for="key in lastMoveSet" :key="'lm-' + key">
        <div
          class="highlight-circle last-move"
          :style="getHighlightStyle(Number(key.split(',')[0]), Number(key.split(',')[1]))"
        />
      </template>

      <!-- 将军高亮 -->
      <div
        v-if="checkPos"
        class="highlight-circle check-highlight"
        :style="getHighlightStyle(Number(checkPos.split(',')[0]), Number(checkPos.split(',')[1]))"
      />

      <!-- 棋子层 -->
      <template v-if="isGameStarted">
        <ChessPiece
          v-for="piece in pieces"
          :key="piece.id"
          :piece="piece"
          :scale="scale"
          :selected="selectedPieceId === piece.id"
          :animating="!!getAnimData(piece)"
          :anim-dx="(getAnimData(piece)?.dx ?? 0) * CELL_N"
          :anim-dy="(getAnimData(piece)?.dy ?? 0) * CELL_N"
          :anim-duration="getAnimData(piece)?.duration ?? 300"
          @select="handlePieceSelect"
        />

        <!-- 合法走法提示点（纯视觉指示，点击由 board-frame 统一处理） -->
        <template v-for="key in validMoveSet" :key="'vm-' + key">
          <div
            class="hint-dot"
            :class="{ 'capture-target': hasPieceAt(Number(key.split(',')[0]), Number(key.split(',')[1])) }"
            :style="getHintStyle(Number(key.split(',')[0]), Number(key.split(',')[1]))"
          />
        </template>
      </template>
    </div>
  </div>
</template>

<style scoped>
.game-board-area {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  min-height: 0;
  width: 100%;
  height: 100%;
  padding: 8px;
}

.board-frame {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-lg);
}

.board-bg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

/* 高亮圈 */
.highlight-circle {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
  z-index: 1;
}

.last-move {
  border: 2px solid rgba(100, 180, 100, 0.7);
  background: rgba(100, 180, 100, 0.08);
}

.check-highlight {
  border: 3px dashed #ff0000;
  background: rgba(255, 0, 0, 0.06);
  animation: check-pulse 1.5s ease-in-out infinite;
}

@keyframes check-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* 合法走法提示 */
.hint-dot {
  position: absolute;
  width: 20px;
  height: 20px;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: rgba(217, 119, 6, 0.45);
  z-index: 5;
  pointer-events: none;
}

.hint-dot.capture-target {
  width: 46px;
  height: 46px;
  background: none;
  border: 3px solid rgba(220, 38, 38, 0.55);
  box-sizing: border-box;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .game-board-area {
    padding: 4px;
  }
}
</style>
