<!--
  MoveList.vue — 着法记录列表
  与 Demo 中 move-item 结构一致
-->
<template>
  <div class="game-sidebar">
    <div class="sidebar-header">
      {{ title }}
      <span style="font-weight: 400; font-size: 12px; color: var(--color-text-tertiary); margin-left: auto;">{{ totalMoves }} 手</span>
    </div>
    <div class="move-list" ref="listRef">
      <div
        v-for="item in moveItems" :key="item.idx"
        class="move-item"
        :class="{ active: item.idx === currentMove }"
        @click="$emit('jump', item.idx)"
      >
        <span class="move-num">{{ item.idx }}.</span>
        <span class="move-red">{{ item.red }}</span>
        <span v-if="item.black" class="move-black">{{ item.black }}</span>
      </div>
      <div v-if="moveItems.length === 0" style="padding: var(--space-6); text-align: center; color: var(--color-text-muted); font-size: var(--text-sm);">
        暂无着法记录
      </div>
    </div>
    <slot name="actions" />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  moves: { type: Array, default: () => [] },
  currentMove: { type: Number, default: 0 },
  title: { type: String, default: '着法记录' },
})

defineEmits(['jump'])

const listRef = ref(null)

const totalMoves = computed(() => props.moves.length)

/* 转换为红黑配对的行（与 Demo 一致） */
const moveItems = computed(() => {
  const items = []
  for (let i = 0; i < props.moves.length; i += 2) {
    items.push({
      idx: Math.floor(i / 2) + 1,
      red: props.moves[i] || '',
      black: props.moves[i + 1] || '',
    })
  }
  return items
})

watch(() => props.currentMove, () => {
  if (listRef.value) {
    const active = listRef.value.querySelector('.move-item.active')
    if (active) {
      active.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }
})
</script>
