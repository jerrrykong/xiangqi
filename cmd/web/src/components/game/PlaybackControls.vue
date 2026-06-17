/**
 * PlaybackControls — 复盘播放控制条
 * 
 * @prop current - 当前步数
 * @prop total - 总步数
 * @prop playing - 是否正在播放
 * @prop speed - 播放速度
 * @prop showSpeed - 是否显示速度选项
 */
<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  current: number
  total: number
  playing: boolean
  speed?: number
  showSpeed?: boolean
}>()

const emit = defineEmits<{
  (e: 'prev'): void
  (e: 'toggle'): void
  (e: 'next'): void
  (e: 'speed', value: number): void
  (e: 'seek', step: number): void
}>()

const speeds = [
  { label: '0.5x', value: 0.5 },
  { label: '1x', value: 1 },
  { label: '2x', value: 2 },
]

const progressPercent = computed(() => {
  if (props.total <= 0) return 0
  return (props.current / props.total) * 100
})

function onProgressClick(e: MouseEvent) {
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const pct = (e.clientX - rect.left) / rect.width
  const step = Math.round(pct * props.total)
  emit('seek', step)
}
</script>

<template>
  <div class="playback-controls">
    <!-- 上一步 -->
    <button class="pb-btn" @click="emit('prev')" title="上一步">⏮</button>

    <!-- 播放/暂停 -->
    <button class="pb-btn pb-btn--play" @click="emit('toggle')" :title="playing ? '暂停' : '播放'">
      {{ playing ? '⏸' : '▶' }}
    </button>

    <!-- 下一步 -->
    <button class="pb-btn" @click="emit('next')" title="下一步">⏭</button>

    <!-- 进度条 -->
    <div class="playback-progress">
      <div class="progress-bar" @click="onProgressClick">
        <div class="progress-fill" :style="{ width: progressPercent + '%' }" />
      </div>
      <div class="progress-label">
        <span>{{ current }}</span>
        <span>{{ total }}</span>
      </div>
    </div>

    <!-- 速度选项 -->
    <div v-if="showSpeed !== false" class="speed-options">
      <button
        v-for="s in speeds"
        :key="s.value"
        class="speed-btn"
        :class="{ active: speed === s.value }"
        @click="emit('speed', s.value)"
      >
        {{ s.label }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.playback-controls {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-6);
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  flex-wrap: wrap;
}

.pb-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-lg);
  background: var(--color-bg-secondary);
  color: var(--color-wood);
  border: 1px solid var(--color-wood-light);
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.pb-btn:hover {
  background: var(--color-wood-bg);
  color: var(--color-wood-dark);
}

.pb-btn--play {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, var(--color-gold-light), var(--color-gold));
  color: white;
  border-color: var(--color-gold-dark);
  font-size: var(--text-xl);
}

.pb-btn--play:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.playback-progress {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 120px;
}

.progress-bar {
  width: 100%;
  height: 6px;
  background: var(--color-bg-secondary);
  border-radius: var(--radius-full);
  overflow: hidden;
  cursor: pointer;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-gold-light), var(--color-gold));
  border-radius: var(--radius-full);
  transition: width var(--transition-normal);
}

.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
}

.speed-options {
  display: flex;
  gap: var(--space-1);
  flex-shrink: 0;
}

.speed-btn {
  padding: var(--space-1) var(--space-2);
  font-size: var(--text-xs);
  border-radius: var(--radius-xs);
  background: var(--color-bg-secondary);
  color: var(--color-text-tertiary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.speed-btn.active {
  background: var(--color-gold);
  color: white;
}

.speed-btn:hover:not(.active) {
  background: var(--color-wood-bg);
}
</style>
