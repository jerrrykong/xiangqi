/**
 * MoveList — 着法记录列表组件
 * 
 * @prop moves - 着法数据（每两个元素组成一行：红方+黑方）
 * @prop currentMove - 当前激活的着法序号
 * @prop title - 标题
 */
<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'

const props = defineProps<{
  moves: Array<{ notation: string; piece: number; moveNumber: number }>
  currentMove?: number
  title?: string
}>()

const emit = defineEmits<{
  (e: 'jump', index: number): void
}>()

const listRef = ref<HTMLElement | null>(null)

const totalMoves = computed(() => props.moves.length)

/** 转换为红黑配对的行 */
const moveItems = computed(() => {
  const items: Array<{ idx: number; red: string; black: string }> = []
  for (let i = 0; i < props.moves.length; i += 2) {
    items.push({
      idx: Math.floor(i / 2) + 1,
      red: props.moves[i]?.notation || '',
      black: props.moves[i + 1]?.notation || '',
    })
  }
  return items
})

/** 当前激活的行号 */
const activeIdx = computed(() => {
  if (props.currentMove === undefined || props.currentMove <= 0) return 0
  return Math.ceil(props.currentMove / 2)
})

/** 自动滚动到激活的着法 */
watch(() => props.currentMove, () => {
  if (listRef.value) {
    const active = listRef.value.querySelector('.move-item.active')
    if (active) {
      active.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }
})

// 调试：打印接收到的 props.moves 与计算后的 moveItems
onMounted(() => {
  console.log('[MoveList] mounted: moves.length=', props.moves.length)
  console.log('[MoveList] initial moveItems=', moveItems.value.slice(0, 20))
})

watch(() => props.moves, (newVal) => {
  console.log('[MoveList] props.moves changed, length=', newVal.length)
})
</script>

<template>
  <div class="game-sidebar">
    <div class="sidebar-header">
      {{ title || '着法记录' }}
      <span class="move-count">{{ totalMoves }} 手</span>
    </div>
    <div ref="listRef" class="move-list">
      <div
        v-for="item in moveItems"
        :key="item.idx"
        class="move-item"
        :class="{ active: item.idx === activeIdx }"
      >
        <span class="move-num">{{ item.idx }}.</span>
        <span class="move-red">{{ item.red }}</span>
        <span v-if="item.black" class="move-black">{{ item.black }}</span>
      </div>
      <div v-if="moveItems.length === 0" class="move-empty">
        暂无着法记录
      </div>
    </div>
  </div>
</template>

<style scoped>
.game-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  font-family: var(--font-serif);
  font-size: var(--text-base);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
  border-bottom: 1px solid var(--color-wood-light);
  flex-shrink: 0;
}

.move-count {
  font-weight: var(--weight-normal);
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}

.move-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-2);
}

.move-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
  font-size: var(--text-sm);
}

.move-item:hover {
  background: var(--color-bg-secondary);
}

.move-item.active {
  background: rgba(217, 119, 6, 0.12);
  font-weight: var(--weight-semibold);
}

.move-num {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  min-width: 24px;
}

.move-red {
  color: var(--color-piece-red);
  min-width: 70px;
}

.move-black {
  color: var(--color-piece-black);
  min-width: 70px;
}

.move-empty {
  padding: var(--space-6);
  text-align: center;
  color: var(--color-text-muted);
  font-size: var(--text-sm);
}
</style>
