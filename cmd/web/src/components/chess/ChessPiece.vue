/**
 * ChessPiece — 单枚棋子组件
 * 使用 SVG 图片渲染，支持选中高亮和走棋动画
 * 
 * @prop piece - 棋子数据 { id, col, row, type, side }
 * @prop scale - 棋盘缩放比
 * @prop selected - 是否选中
 * @prop animating - 是否正在播放走棋动画
 * @prop animDx - 走棋动画 X 偏移量(px)
 * @prop animDy - 走棋动画 Y 偏移量(px)
 * @prop animDuration - 走棋动画时长(ms)
 */
<script setup lang="ts">
import { computed } from 'vue'

/** 棋子类型定义 */
export interface PieceData {
  id: string
  col: number
  row: number
  type: string
  side: 'red' | 'black'
}

const props = defineProps<{
  piece: PieceData
  scale: number
  selected?: boolean
  animating?: boolean
  animDx?: number
  animDy?: number
  animDuration?: number
}>()

const emit = defineEmits<{
  (e: 'select', piece: PieceData): void
}>()

/** 棋盘原生参数 */
const NATIVE_CELL = 60
const NATIVE_PAD = 30
const NATIVE_PSIZE = 48

/** SVG 文件名映射 */
const SVG_MAP: Record<string, Record<string, string>> = {
  red: {
    king: 'red-shuai',
    advisor: 'red-shi',
    bishop: 'red-xiang',
    knight: 'red-ma',
    rook: 'red-ju',
    cannon: 'red-pao',
    pawn: 'red-bing',
  },
  black: {
    king: 'black-jiang',
    advisor: 'black-shi',
    bishop: 'black-xiang',
    knight: 'black-ma',
    rook: 'black-ju',
    cannon: 'black-pao',
    pawn: 'black-zu',
  },
}

/** Vite base 路径（运行时为 '/xiangqi/'） */
const BASE = import.meta.env.BASE_URL

/** 棋子 SVG URL（基于 public 目录） */
const svgUrl = computed(() => {
  const svgName = SVG_MAP[props.piece.side]?.[props.piece.type]
  if (!svgName) return ''
  return `${BASE}assets/svg/pieces/${svgName}.svg`
})

/** 棋子位置和尺寸（根据缩放比计算） */
const pieceStyle = computed(() => {
  const s = props.scale
  const cell = NATIVE_CELL * s
  const pad = NATIVE_PAD * s
  const psize = Math.round(NATIVE_PSIZE * s)
  const poff = psize / 2

  const x = Math.round(pad + props.piece.col * cell - poff)
  const y = Math.round(pad + props.piece.row * cell - poff)

  const style: Record<string, string> = {
    left: `${x}px`,
    top: `${y}px`,
    width: `${psize}px`,
    height: `${psize}px`,
  }

  // 走棋动画
  if (props.animating && props.animDx !== undefined && props.animDy !== undefined) {
    style['--anim-dx'] = `${props.animDx * s}px`
    style['--anim-dy'] = `${props.animDy * s}px`
    style['--anim-duration'] = `${props.animDuration || 300}ms`
  }

  return style
})

function handleClick() {
  emit('select', props.piece)
}
</script>

<template>
  <div
    class="piece-el"
    :class="{
      sel: selected,
      'piece-slide-anim': animating,
    }"
    :style="pieceStyle"
    @click.stop="handleClick"
  >
    <img :src="svgUrl" :alt="piece.type" draggable="false" />
  </div>
</template>

<style scoped>
.piece-el {
  position: absolute;
  cursor: pointer;
  user-select: none;
  transition: transform var(--transition-fast), box-shadow var(--transition-fast);
  z-index: 2;
}

.piece-el img {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 3px 6px rgba(92, 58, 30, 0.35));
  pointer-events: none;
}

.piece-el:hover {
  transform: translateY(-2px);
  z-index: 3;
}

.piece-el:hover img {
  filter: drop-shadow(0 5px 10px rgba(92, 58, 30, 0.45));
}

/* 选中态：金色光晕 + 呼吸动画 */
.piece-el.sel {
  z-index: 10;
}

.piece-el.sel img {
  filter: drop-shadow(0 0 8px rgba(217, 119, 6, 0.6)) drop-shadow(0 3px 6px rgba(92, 58, 30, 0.4));
  animation: piece-glow 1.2s ease-in-out alternate infinite;
}

@keyframes piece-glow {
  from {
    filter: drop-shadow(0 0 6px rgba(217, 119, 6, 0.5)) drop-shadow(0 3px 6px rgba(92, 58, 30, 0.4));
  }
  to {
    filter: drop-shadow(0 0 14px rgba(217, 119, 6, 0.8)) drop-shadow(0 4px 8px rgba(92, 58, 30, 0.5));
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
