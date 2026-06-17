<!--
  PlaybackControls.vue — 复盘播放控制条
  与 Demo 中 pb-btn 结构一致
-->
<template>
  <div class="playback-controls">
    <!-- 上一步 -->
    <button class="pb-btn" @click="$emit('prev')" title="上一步">⏮</button>

    <!-- 播放/暂停 -->
    <button class="pb-btn pb-btn--play" @click="$emit('toggle')" :title="playing ? '暂停' : '播放'">
      {{ playing ? '⏸' : '▶' }}
    </button>

    <!-- 下一步 -->
    <button class="pb-btn" @click="$emit('next')" title="下一步">⏭</button>

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
    <div class="speed-options" v-if="showSpeed">
      <button
        v-for="s in speeds" :key="s.value"
        class="speed-btn"
        :class="{ active: speed === s.value }"
        @click="$emit('speed', s.value)"
      >
        {{ s.label }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  current: { type: Number, default: 0 },
  total: { type: Number, default: 0 },
  playing: { type: Boolean, default: false },
  speed: { type: Number, default: 1 },
  showSpeed: { type: Boolean, default: true },
})

const emit = defineEmits(['prev', 'toggle', 'next', 'speed', 'seek'])

const speeds = [
  { label: '0.5x', value: 0.5 },
  { label: '1x', value: 1 },
  { label: '2x', value: 2 },
]

const progressPercent = computed(() => {
  if (props.total <= 0) return 0
  return (props.current / props.total) * 100
})

function onProgressClick(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  const pct = (e.clientX - rect.left) / rect.width
  const step = Math.round(pct * props.total)
  emit('seek', step)
}
</script>
