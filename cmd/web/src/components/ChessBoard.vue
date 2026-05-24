<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, getCurrentInstance } from 'vue'
import type { Position, Move } from '@/types/chess'
import { PieceChars, Piece, Color, BoardConfig, PieceConfig, getPieceColor } from '@/types/chess'

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

const CELL_SIZE = 55
const BORDER_WIDTH = 30 // 3D边框总宽度（需>=棋子半径25，确保棋子不超出边框）
const PADDING = Math.round(CELL_SIZE * 0.75) + BORDER_WIDTH // 41 + 30 = 71px

// 每个组件实例的唯一 ID 前缀，避免同页面多实例时 SVG id 冲突
const uid = getCurrentInstance()?.uid ?? 0
const gid = (name: string) => `${name}_${uid}`

// 棋盘尺寸配置
const boardConfig = {
  cellSize: CELL_SIZE,
  boardWidth: (BoardConfig.Cols - 1) * CELL_SIZE, // 8 * 55 = 440
  boardHeight: (BoardConfig.Rows - 1) * CELL_SIZE, // 9 * 55 = 495
  padding: PADDING,
}

// 计算 SVG 逻辑尺寸
const svgWidth = computed(() => boardConfig.boardWidth + boardConfig.padding * 2)
const svgHeight = computed(() => boardConfig.boardHeight + boardConfig.padding * 2)

// 暴露棋盘逻辑尺寸供父组件使用（不含缩放）
defineExpose({
  logicalWidth: svgWidth,
  logicalHeight: svgHeight,
  boardWidth: computed(() => boardConfig.boardWidth),
  boardHeight: computed(() => boardConfig.boardHeight),
})

// 是否翻转棋盘（黑方视角）
const isFlipped = computed(() => props.yourColor === 1)

// 响应式缩放
const containerRef = ref<HTMLElement | null>(null)
const scale = ref(1)

function updateScale() {
  if (!containerRef.value) return
  const parent = containerRef.value.parentElement
  if (!parent) return
  const available = parent.clientWidth
  // 父元素隐藏时 (display:none) clientWidth=0，不应更新 scale，保留当前值
  if (available === 0) return
  const needed = svgWidth.value
  if (available < needed) {
    scale.value = Math.floor((available / needed) * 1000) / 1000 // 保留3位小数
  } else {
    scale.value = 1
  }
}

// 窄屏缩放时，wrapper 需要收缩实际占位
const wrapperStyle = computed(() => ({
  transform: `scale(${scale.value})`,
  transformOrigin: 'top left' as const,
  width: scale.value < 1 ? `${Math.ceil(svgWidth.value * scale.value)}px` : `${svgWidth.value}px`,
  height: scale.value < 1 ? `${Math.ceil(svgHeight.value * scale.value)}px` : `${svgHeight.value}px`,
}))

onMounted(() => {
  updateScale()
  window.addEventListener('resize', () => {
    requestAnimationFrame(updateScale)
  })
})

onUnmounted(() => {
  window.removeEventListener('resize', updateScale)
})

// 坐标转换 (row, col) -> SVG (x, y)，黑方时翻转
function getX(col: number): number {
  const c = isFlipped.value ? (8 - col) : col
  return boardConfig.padding + c * boardConfig.cellSize
}

function getY(row: number): number {
  const r = isFlipped.value ? (9 - row) : row
  return boardConfig.padding + r * boardConfig.cellSize
}

// 九宫对角线
const palaceDiagonals = computed(() => {
  const diagonals = []
  diagonals.push({ x1: getX(3), y1: getY(7), x2: getX(5), y2: getY(9) })
  diagonals.push({ x1: getX(5), y1: getY(7), x2: getX(3), y2: getY(9) })
  diagonals.push({ x1: getX(3), y1: getY(0), x2: getX(5), y2: getY(2) })
  diagonals.push({ x1: getX(5), y1: getY(0), x2: getX(3), y2: getY(2) })
  return diagonals
})

// 判断是否被选中
function isSelected(row: number, col: number): boolean {
  return props.selectedPosition?.row === row && props.selectedPosition?.col === col
}

// 判断是否是最后一步的起点或终点
function isLastMovePosition(row: number, col: number): boolean {
  if (!props.lastMove) return false
  return (
    (props.lastMove.from_row === row && props.lastMove.from_col === col) ||
    (props.lastMove.to_row === row && props.lastMove.to_col === col)
  )
}

// 判断是否是合法目标位置
function isValidMoveTarget(row: number, col: number): boolean {
  return props.validMoves.some(m => m.row === row && m.col === col)
}

// 判断棋子是否是己方的
function isOwnPiece(row: number, col: number): boolean {
  const piece = props.board[row][col]
  if (piece < 0) return false
  return getPieceColor(piece as any) === props.yourColor
}

// 获取棋子样式
function getPieceStyle(row: number, col: number) {
  const piece = props.board[row][col]
  if (piece < 0) return {}

  const isRed = piece < 10
  const x = getX(col) - PieceConfig.Size / 2
  const y = getY(row) - PieceConfig.Size / 2
  const selected = isSelected(row, col)

  return {
    left: `${x}px`,
    top: `${y}px`,
    width: `${PieceConfig.Size}px`,
    height: `${PieceConfig.Size}px`,
    background: isRed
      ? 'radial-gradient(circle at 35% 35%, #fff8f0, #f5e6d0 40%, #e8d0b0 70%, #d4b896)'
      : 'radial-gradient(circle at 35% 35%, #f5f5f0, #e8e4dc 40%, #d8d0c4 70%, #c4b8a8)',
    border: isRed ? '2px solid #c41e3a' : '2px solid #1a1a1a',
    color: isRed ? '#c41e3a' : '#1a1a1a',
    fontSize: `${PieceConfig.FontSize}px`,
  }
}

// 获取空位样式（可点击区域）
function getEmptyCellStyle(row: number, col: number) {
  return {
    left: `${getX(col) - CELL_SIZE / 2}px`,
    top: `${getY(row) - CELL_SIZE / 2}px`,
    width: `${CELL_SIZE}px`,
    height: `${CELL_SIZE}px`,
  }
}

// 判断该位置的棋子是否正在播放走棋动画
function isAnimatingTarget(row: number, col: number): boolean {
  if (!props.animatingMove) return false
  return row === props.animatingMove.to_row && col === props.animatingMove.to_col
}

// 获取走棋动画样式（目标位置棋子从原位置滑入）
function getAnimatingStyle(row: number, col: number): Record<string, string> {
  const anim = props.animatingMove
  if (!anim || !isAnimatingTarget(row, col)) return {}

  const dx = getX(anim.from_col) - getX(anim.to_col)
  const dy = getY(anim.from_row) - getY(anim.to_row)

  return {
    '--anim-dx': `${dx}px`,
    '--anim-dy': `${dy}px`,
    '--anim-duration': `${anim.duration}ms`,
  }
}

// 点击棋子
function handlePieceClick(row: number, col: number) {
  if (props.frozen) return
  // 非走棋方，点击无效果
  if (!props.isMyTurn) return
  // 已选中棋子且该位置是合法走法目标 → 走棋（吃子）
  if (props.selectedPosition && isValidMoveTarget(row, col)) {
    emit('position-click', { row, col })
    return
  }
  emit('piece-click', { row, col })
}

// 点击空白位置
function handlePositionClick(row: number, col: number) {
  if (props.frozen) return
  if (!props.isMyTurn) return
  if (props.selectedPosition) {
    emit('position-click', { row, col })
  }
}

// 点击空白区域（非棋子、非格子位置）取消选择
function handleBoardClick() {
  emit('board-click')
}

// 获取棋子字符
function getPieceChar(piece: number): string {
  return PieceChars[piece as keyof typeof PieceChars] || ''
}

// 河界中心Y坐标
const riverCenterY = computed(() => (getY(4) + getY(5)) / 2)
</script>

<template>
  <div ref="containerRef" class="chess-board-wrapper" :style="wrapperStyle">
    <div class="chess-board-container" :style="{ width: svgWidth + 'px', height: svgHeight + 'px' }" @click="handleBoardClick">
      <!-- SVG 棋盘线 -->
      <svg
        :width="svgWidth"
        :height="svgHeight"
        class="svg-overlay"
      >
        <!-- 定义 -->
        <defs>
          <linearGradient :id="gid('woodGradient')" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#deb887;stop-opacity:1" />
            <stop offset="30%" style="stop-color:#d2a679;stop-opacity:1" />
            <stop offset="60%" style="stop-color:#c49a6c;stop-opacity:1" />
            <stop offset="100%" style="stop-color:#b8895a;stop-opacity:1" />
          </linearGradient>
          <linearGradient :id="gid('border3DTop')" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" style="stop-color:#d4a574;stop-opacity:1" />
            <stop offset="100%" style="stop-color:#a07040;stop-opacity:1" />
          </linearGradient>
          <filter :id="gid('board3DShadow')" x="-5%" y="-5%" width="115%" height="115%">
            <feGaussianBlur in="SourceAlpha" stdDeviation="4" />
            <feOffset dx="3" dy="4" result="offsetblur" />
            <feFlood flood-color="rgba(0,0,0,0.35)" />
            <feComposite in2="offsetblur" operator="in" />
            <feMerge>
              <feMergeNode />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter :id="gid('selectedShadow')" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceAlpha" stdDeviation="3" />
            <feOffset dx="0" dy="0" result="offsetblur" />
            <feFlood flood-color="#ffd700" />
            <feComposite in2="offsetblur" operator="in" />
            <feMerge>
              <feMergeNode />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <!-- 棋盘3D外框 (底部深色投影) -->
        <rect
          :x="boardConfig.padding - BORDER_WIDTH + 3"
          :y="boardConfig.padding - BORDER_WIDTH + 3"
          :width="boardConfig.boardWidth + BORDER_WIDTH * 2 + 4"
          :height="boardConfig.boardHeight + BORDER_WIDTH * 2 + 4"
          fill="#5a3520"
          rx="8"
          ry="8"
          :filter="`url(#${gid('board3DShadow')})`"
        />
        <!-- 棋盘3D外框 (顶部浅色凸起) -->
        <rect
          :x="boardConfig.padding - BORDER_WIDTH"
          :y="boardConfig.padding - BORDER_WIDTH"
          :width="boardConfig.boardWidth + BORDER_WIDTH * 2"
          :height="boardConfig.boardHeight + BORDER_WIDTH * 2"
          :fill="`url(#${gid('border3DTop')})`"
          rx="6"
          ry="6"
        />
        <!-- 棋盘内部凹陷效果 -->
        <rect
          :x="boardConfig.padding - 10"
          :y="boardConfig.padding - 10"
          :width="boardConfig.boardWidth + 20"
          :height="boardConfig.boardHeight + 20"
          fill="#7a5230"
          rx="2"
        />

        <!-- 棋盘背景 -->
        <rect
          :x="boardConfig.padding - 8"
          :y="boardConfig.padding - 8"
          :width="boardConfig.boardWidth + 16"
          :height="boardConfig.boardHeight + 16"
          :fill="`url(#${gid('woodGradient')})`"
          rx="2"
        />

        <!-- 横线 -->
        <line
          v-for="row in 10"
          :key="'h' + row"
          :x1="getX(0)"
          :y1="getY(row - 1)"
          :x2="getX(8)"
          :y2="getY(row - 1)"
          stroke="#8b5a2b"
          stroke-width="1.5"
        />

        <!-- 竖线（中间列在河界断开） -->
        <template v-for="col in 9">
          <line
            v-if="col === 1 || col === 9"
            :key="'v' + col"
            :x1="getX(col - 1)"
            :y1="getY(0)"
            :x2="getX(col - 1)"
            :y2="getY(9)"
            stroke="#8b5a2b"
            stroke-width="2"
          />
          <template v-else>
            <line
              :key="'vu' + col"
              :x1="getX(col - 1)"
              :y1="getY(0)"
              :x2="getX(col - 1)"
              :y2="getY(4)"
              stroke="#8b5a2b"
              stroke-width="1.5"
            />
            <line
              :key="'vd' + col"
              :x1="getX(col - 1)"
              :y1="getY(5)"
              :x2="getX(col - 1)"
              :y2="getY(9)"
              stroke="#8b5a2b"
              stroke-width="1.5"
            />
          </template>
        </template>

        <!-- 九宫对角线 -->
        <line
          v-for="(diag, index) in palaceDiagonals"
          :key="'diag' + index"
          :x1="diag.x1"
          :y1="diag.y1"
          :x2="diag.x2"
          :y2="diag.y2"
          stroke="#8b5a2b"
          stroke-width="1.5"
        />

        <!-- 楚河汉界 -->
        <text
          :x="getX(2)"
          :y="riverCenterY + 8"
          fill="#8b5a2b"
          font-size="22"
          font-family="'Noto Serif SC', serif"
          font-weight="bold"
          text-anchor="middle"
          dominant-baseline="middle"
          :transform="isFlipped ? 'rotate(180,' + getX(2) + ',' + (riverCenterY + 8) + ')' : ''"
        >
          楚 河
        </text>
        <text
          :x="getX(6)"
          :y="riverCenterY + 8"
          fill="#8b5a2b"
          font-size="22"
          font-family="'Noto Serif SC', serif"
          font-weight="bold"
          text-anchor="middle"
          dominant-baseline="middle"
          :transform="isFlipped ? 'rotate(180,' + getX(6) + ',' + (riverCenterY + 8) + ')' : ''"
        >
          汉 界
        </text>

        <!-- 炮和兵的标记点 -->
        <g fill="#8b5a2b">
          <circle v-for="col in [1, 3, 5, 7]" :key="'rp' + col" :cx="getX(col)" :cy="getY(3)" r="3" />
          <circle v-for="col in [2, 4, 6]" :key="'rpb' + col" :cx="getX(col)" :cy="getY(6)" r="3" />
          <circle v-for="col in [1, 3, 5, 7]" :key="'bp' + col" :cx="getX(col)" :cy="getY(6)" r="3" />
          <circle v-for="col in [2, 4, 6]" :key="'bpb' + col" :cx="getX(col)" :cy="getY(3)" r="3" />
        </g>

        <!-- 选中高亮 -->
        <circle
          v-if="selectedPosition"
          :cx="getX(selectedPosition.col)"
          :cy="getY(selectedPosition.row)"
          :r="PieceConfig.Size / 2 + 3"
          fill="none"
          stroke="#ffd700"
          stroke-width="3"
          :filter="`url(#${gid('selectedShadow')})`"
        />

        <!-- 最后一步高亮 -->
        <circle
          v-if="lastMove"
          :cx="getX(lastMove.from_col)"
          :cy="getY(lastMove.from_row)"
          :r="PieceConfig.Size / 2 + 3"
          fill="none"
          stroke="rgba(100, 180, 100, 0.8)"
          stroke-width="2"
        />
        <circle
          v-if="lastMove"
          :cx="getX(lastMove.to_col)"
          :cy="getY(lastMove.to_row)"
          :r="PieceConfig.Size / 2 + 3"
          fill="none"
          stroke="rgba(100, 180, 100, 0.8)"
          stroke-width="2"
        />

        <!-- 将军高亮 -->
        <circle
          v-if="isInCheck && checkPosition"
          :cx="getX(checkPosition.col)"
          :cy="getY(checkPosition.row)"
          :r="PieceConfig.Size / 2 + 6"
          fill="none"
          stroke="#ff0000"
          stroke-width="3"
          stroke-dasharray="5,3"
          class="pulse-animation"
        />
      </svg>

      <!-- 棋子层（waiting 时不渲染） -->
      <template v-if="isGameStarted">
        <div
          v-for="(row, rowIndex) in board"
          :key="'row' + rowIndex"
          class="piece-layer"
        >
          <div
            v-for="(piece, colIndex) in row"
            :key="'piece' + rowIndex + '-' + colIndex"
            class="piece-wrapper"
            :class="{
              'piece': piece >= 0,
              'selected': isSelected(rowIndex, colIndex),
              'lifted': isSelected(rowIndex, colIndex),
              'last-move': isLastMovePosition(rowIndex, colIndex),
              'own-piece': piece >= 0 && isOwnPiece(rowIndex, colIndex),
              'valid-target': piece < 0 && isValidMoveTarget(rowIndex, colIndex),
              'piece-slide-anim': piece >= 0 && isAnimatingTarget(rowIndex, colIndex),
            }"
            :style="{ ...(piece >= 0 ? getPieceStyle(rowIndex, colIndex) : getEmptyCellStyle(rowIndex, colIndex)), ...getAnimatingStyle(rowIndex, colIndex) }"
            @click.stop="piece >= 0 ? handlePieceClick(rowIndex, colIndex) : handlePositionClick(rowIndex, colIndex)"
          >
            <span v-if="piece >= 0" class="piece-char">{{ getPieceChar(piece) }}</span>
          </div>
        </div>

        <!-- 可移动位置提示 -->
        <div class="hint-layer">
          <template v-for="(row, rowIndex) in board" :key="'hint' + rowIndex">
            <div
              v-for="(piece, colIndex) in row"
              :key="'hint' + rowIndex + '-' + colIndex"
              class="hint-dot"
              :class="{
                'capture-target': piece >= 0,
              }"
              v-show="selectedPosition && isValidMoveTarget(rowIndex, colIndex)"
              :style="{
                left: getX(colIndex) + 'px',
                top: getY(rowIndex) + 'px',
              }"
            />
          </template>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.chess-board-wrapper {
  display: inline-block;
}

.chess-board-container {
  position: relative;
  user-select: none;
}

.svg-overlay {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
}

.piece-layer {
  position: absolute;
  top: 0;
  left: 0;
}

.piece-wrapper {
  position: absolute;
  cursor: default;
  transition: transform 150ms, box-shadow 150ms;
}

.piece {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-family: 'Noto Serif SC', serif;
  font-weight: 700;
  cursor: pointer;
  user-select: none;
  box-shadow:
    2px 3px 6px rgba(0, 0, 0, 0.35),
    0 1px 2px rgba(0, 0, 0, 0.2),
    inset 0 1px 1px rgba(255, 255, 255, 0.3),
    inset 0 -1px 1px rgba(0, 0, 0, 0.1);
}

/* 己方棋子在走棋时才可交互 */
.own-piece {
  cursor: pointer;
}

/* 空位的合法走法目标 */
.valid-target {
  cursor: pointer;
}

/* 非走棋方时，己方棋子也不可点击 */
.own-piece:not(.selected) {
  /* 默认允许 hover，但交互由 handlePieceClick 中的 isMyTurn 控制 */
}

.piece.own-piece:hover:not(.lifted) {
  transform: scale(1.05);
  box-shadow:
    3px 4px 8px rgba(0, 0, 0, 0.4),
    0 1px 3px rgba(0, 0, 0, 0.25),
    inset 0 1px 1px rgba(255, 255, 255, 0.4),
    inset 0 -1px 1px rgba(0, 0, 0, 0.15);
}

/* 提起状态（选中棋子） */
.piece.lifted {
  transform: translateY(-4px) scale(1.08);
  box-shadow:
    0 0 0 3px #ffd700,
    4px 8px 16px rgba(0, 0, 0, 0.5),
    0 2px 4px rgba(0, 0, 0, 0.3),
    inset 0 1px 1px rgba(255, 255, 255, 0.4);
  z-index: 10;
}

.piece.last-move {
  box-shadow:
    0 0 0 2px rgba(100, 180, 100, 0.8),
    2px 3px 6px rgba(0, 0, 0, 0.35),
    0 1px 2px rgba(0, 0, 0, 0.2),
    inset 0 1px 1px rgba(255, 255, 255, 0.3);
}

.piece-char {
  line-height: 1;
}

.hint-layer {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
  z-index: 5;
}

.hint-dot {
  position: absolute;
  width: 14px;
  height: 14px;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: rgba(34, 197, 94, 0.5);
}

.hint-dot.capture-target {
  width: 52px;
  height: 52px;
  background: none;
  border: 3px solid rgba(239, 68, 68, 0.6);
  box-sizing: border-box;
}

.pulse-animation {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

/* 走棋滑入动画 */
.piece-slide-anim {
  animation: piece-slide-in var(--anim-duration) cubic-bezier(0.25, 0.1, 0.25, 1);
  z-index: 20 !important;
}

@keyframes piece-slide-in {
  from {
    transform: translate(var(--anim-dx), var(--anim-dy));
  }
  to {
    transform: translate(0, 0);
  }
}
</style>
