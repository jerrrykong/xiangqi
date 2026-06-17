<!--
  ChessPiece.vue — 单枚棋子组件
  与 Demo 中的 piece-el 一致
-->
<template>
  <div
    class="piece-el"
    :class="{ sel: selected }"
    :style="piecePosition"
    @click="$emit('select')"
  >
    <img :src="pieceSvg" :alt="pieceLabel" draggable="false" />
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  piece: { type: Object, required: true },
  cellSize: { type: Number, default: 60 },
  padding: { type: Number, default: 30 },
  selected: { type: Boolean, default: false },
  size: { type: String, default: 'md' },
  showLabel: { type: Boolean, default: false },
})

defineEmits(['select'])

const pieceNameMap = {
  red: { shuai: 'red-shuai', shi: 'red-shi', xiang: 'red-xiang', ma: 'red-ma', ju: 'red-ju', pao: 'red-pao', bing: 'red-bing' },
  black: { jiang: 'black-jiang', shi: 'black-shi', xiang: 'black-xiang', ma: 'black-ma', ju: 'black-ju', pao: 'black-pao', zu: 'black-zu' },
}

const pieceLabelMap = {
  shuai: '帥', shi: '仕', xiang: '相', ma: '馬', ju: '車', pao: '炮', bing: '兵',
  jiang: '將', shi2: '士', xiang2: '象', zu: '卒', pao2: '砲',
}

const pieceSvg = computed(() => {
  const key = pieceNameMap[props.piece.side]?.[props.piece.type]
  if (!key) return ''
  return new URL(`../assets/svg/pieces/${key}.svg`, import.meta.url).href
})

const pieceLabel = computed(() => {
  return pieceLabelMap[props.piece.type] || props.piece.type
})

const pieceSizePx = computed(() => {
  return { md: 48, sm: 34 }[props.size] || 48
})

const piecePosition = computed(() => {
  const x = props.padding + props.piece.col * props.cellSize - pieceSizePx.value / 2
  const y = props.padding + props.piece.row * props.cellSize - pieceSizePx.value / 2
  return {
    left: `${x}px`,
    top: `${y}px`,
    width: `${pieceSizePx.value}px`,
    height: `${pieceSizePx.value}px`,
  }
})
</script>
