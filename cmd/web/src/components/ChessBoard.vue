<script setup lang="ts">
import { computed } from 'vue'
import type { Position, Move } from '@/types/chess'
import { PieceChars, Piece, Color, BoardConfig, PieceConfig } from '@/types/chess'

const props = defineProps<{
  board: number[][]
  selectedPosition: Position | null
  lastMove: Move | null
  isInCheck: boolean
  checkPosition: Position | null
  yourColor: 0 | 1
}>()

const emit = defineEmits<{
  (e: 'piece-click', position: Position): void
  (e: 'position-click', position: Position): void
}>()

// 棋盘尺寸配置
const boardConfig = {
  cellSize: 55, // 每格大小
  boardWidth: BoardConfig.Cols * 55, // 9 * 55 = 495
  boardHeight: BoardConfig.Rows * 55, // 10 * 55 = 550
  padding: 30, // 边距
}

// 计算 SVG 尺寸
const svgWidth = computed(() => boardConfig.boardWidth + boardConfig.padding * 2)
const svgHeight = computed(() => boardConfig.boardHeight + boardConfig.padding * 2)

// 坐标转换 (row, col) -> SVG (x, y)
function getX(col: number): number {
  return boardConfig.padding + col * boardConfig.cellSize
}

function getY(row: number): number {
  return boardConfig.padding + row * boardConfig.cellSize
}

// 九宫对角线
const palaceDiagonals = computed(() => {
  const diagonals = []
  // 红方九宫 (行 7-9, 列 3-5)
  diagonals.push({
    x1: getX(3),
    y1: getY(7),
    x2: getX(5),
    y2: getY(9),
  })
  diagonals.push({
    x1: getX(5),
    y1: getY(7),
    x2: getX(3),
    y2: getY(9),
  })
  // 黑方九宫 (行 0-2, 列 3-5)
  diagonals.push({
    x1: getX(3),
    y1: getY(0),
    x2: getX(5),
    y2: getY(2),
  })
  diagonals.push({
    x1: getX(5),
    y1: getY(0),
    x2: getX(3),
    y2: getY(2),
  })
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

// 获取棋子样式
function getPieceStyle(row: number, col: number) {
  const piece = props.board[row][col]
  if (piece < 0) return {}

  const isRed = piece < 10
  const x = getX(col) - PieceConfig.Size / 2
  const y = getY(row) - PieceConfig.Size / 2

  return {
    left: `${x}px`,
    top: `${y}px`,
    width: `${PieceConfig.Size}px`,
    height: `${PieceConfig.Size}px`,
    background: isRed ? '#fff5f5' : '#f5f5f5',
    border: isRed ? '2px solid #c41e3a' : '2px solid #1a1a1a',
    color: isRed ? '#c41e3a' : '#1a1a1a',
    fontSize: `${PieceConfig.FontSize}px`,
  }
}

// 点击棋子
function handlePieceClick(row: number, col: number) {
  emit('piece-click', { row, col })
}

// 点击空白位置
function handlePositionClick(row: number, col: number) {
  emit('position-click', { row, col })
}

// 获取棋子字符
function getPieceChar(piece: number): string {
  return PieceChars[piece as keyof typeof PieceChars] || ''
}
</script>

<template>
  <div class="chess-board-container" :style="{ width: svgWidth + 'px', height: svgHeight + 'px' }">
    <!-- 棋盘背景 -->
    <div
      class="board-background"
      :style="{ margin: boardConfig.padding + 'px' }"
    />

    <!-- SVG 棋盘线 -->
    <svg
      :width="svgWidth"
      :height="svgHeight"
      class="svg-overlay"
    >
      <!-- 定义 -->
      <defs>
        <!-- 木纹渐变 -->
        <linearGradient id="woodGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style="stop-color:#deb887;stop-opacity:1" />
          <stop offset="50%" style="stop-color:#d2a679;stop-opacity:1" />
          <stop offset="100%" style="stop-color:#c49a6c;stop-opacity:1" />
        </linearGradient>
        <!-- 棋子选中阴影 -->
        <filter id="selectedShadow" x="-50%" y="-50%" width="200%" height="200%">
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

      <!-- 背景 -->
      <rect
        :x="boardConfig.padding - 5"
        :y="boardConfig.padding - 5"
        :width="boardConfig.boardWidth + 10"
        :height="boardConfig.boardHeight + 10"
        fill="url(#woodGradient)"
        stroke="#8b5a2b"
        stroke-width="4"
        rx="4"
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

      <!-- 竖线 -->
      <line
        v-for="col in 9"
        :key="'v' + col"
        :x1="getX(col - 1)"
        :y1="getY(0)"
        :x2="getX(col - 1)"
        :y2="getY(9)"
        stroke="#8b5a2b"
        :stroke-width="col === 1 || col === 9 ? 2 : 1.5"
      />

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
        :y="getY(5) + 8"
        fill="#8b5a2b"
        font-size="24"
        font-family="'Noto Serif SC', serif"
        font-weight="bold"
      >
        楚 河
      </text>
      <text
        :x="getX(6)"
        :y="getY(4) + 8"
        fill="#8b5a2b"
        font-size="24"
        font-family="'Noto Serif SC', serif"
        font-weight="bold"
      >
        汉 界
      </text>

      <!-- 炮和兵的标记点 -->
      <g fill="#8b5a2b">
        <!-- 红方标记点 (行 3, 6) -->
        <circle v-for="col in [1, 3, 5, 7]" :key="'rp' + col" :cx="getX(col)" :cy="getY(3)" r="3" />
        <circle v-for="col in [2, 4, 6]" :key="'rpb' + col" :cx="getX(col)" :cy="getY(6)" r="3" />
        <!-- 黑方标记点 (行 6, 3) -->
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
        filter="url(#selectedShadow)"
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

    <!-- 棋子层 -->
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
          'last-move': isLastMovePosition(rowIndex, colIndex),
          'can-move': selectedPosition && !(selectedPosition.row === rowIndex && selectedPosition.col === colIndex) && piece < 0,
        }"
        :style="piece >= 0 ? getPieceStyle(rowIndex, colIndex) : {}"
        @click.stop="piece >= 0 ? handlePieceClick(rowIndex, colIndex) : handlePositionClick(rowIndex, colIndex)"
      >
        <span v-if="piece >= 0" class="piece-char">{{ getPieceChar(piece) }}</span>
      </div>
    </div>

    <!-- 可移动位置提示 -->
    <div
      v-if="selectedPosition"
      class="hint-layer"
    >
      <div
        v-for="(row, rowIndex) in board"
        :key="'hint' + rowIndex"
      >
        <div
          v-for="(piece, colIndex) in row"
          :key="'hint' + rowIndex + '-' + colIndex"
          class="hint-dot"
          :style="{
            left: getX(colIndex) - 6 + 'px',
            top: getY(rowIndex) - 6 + 'px',
          }"
        >
          <span
            v-if="piece < 0"
            class="hint-marker"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chess-board-container {
  position: relative;
  user-select: none;
}

.board-background {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border-radius: 8px;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
}

.board-background,
.svg-overlay {
  position: absolute;
  top: 0;
  left: 0;
}

.svg-overlay {
  pointer-events: none;
}

.piece-layer {
  position: absolute;
  top: 0;
  left: 0;
}

.piece-wrapper {
  position: absolute;
  cursor: pointer;
  transition: transform 150ms;
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
  box-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
}

.piece:hover {
  transform: scale(1.05);
  box-shadow: 3px 3px 6px rgba(0, 0, 0, 0.4);
}

.piece.selected {
  box-shadow: 0 0 0 3px #ffd700, 2px 2px 4px rgba(0, 0, 0, 0.3);
}

.piece.last-move {
  box-shadow: 0 0 0 2px rgba(100, 180, 100, 0.8), 2px 2px 4px rgba(0, 0, 0, 0.3);
}

.piece-char {
  line-height: 1;
}

.hint-layer {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
}

.hint-dot {
  position: absolute;
}

.hint-marker {
  display: block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: rgba(34, 197, 94, 0.6);
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
</style>
