<!--
  ChessBoard.vue — 中国象棋棋盘组件（board-frame 模式）
  与 Demo 完全一致
-->
<template>
  <div class="game-board-area" ref="boardArea">
    <div class="board-frame" :style="{ width: displayW + 'px', height: displayH + 'px' }">
      <img src="@/assets/svg/board.svg" class="board-bg" alt="棋盘" />
      <!-- 棋子层 -->
      <div
        v-for="piece in pieces" :key="piece.id"
        class="piece-el"
        :class="{ sel: selectedPiece?.id === piece.id }"
        :style="{ left: piece.x + 'px', top: piece.y + 'px', width: piece.ds + 'px', height: piece.ds + 'px' }"
        @click="$emit('piece-select', piece)"
      >
        <img :src="pieceSvgUrl(piece)" :alt="piece.label" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  pieces: { type: Array, default: () => [] },
  selectedPiece: { type: Object, default: null },
  displayW: { type: Number, default: 540 },
  displayH: { type: Number, default: 600 },
})

defineEmits(['piece-select'])

function pieceSvgUrl(piece) {
  return new URL(`../assets/svg/pieces/${piece.svg}`, import.meta.url).href
}
</script>
