/**
 * GameTimer — 棋钟倒计时组件
 * 
 * @prop time - 剩余秒数
 * @prop warnThreshold - 闪烁警告阈值（秒）
 */
<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  time: number
  warnThreshold?: number
}>()

const formatted = computed(() => {
  const t = Math.max(0, Math.floor(props.time))
  const m = Math.floor(t / 60)
  const s = t % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
})

const isWarning = computed(() => {
  return props.time > 0 && props.time <= (props.warnThreshold ?? 30)
})
</script>

<template>
  <div class="opp-timer" :class="{ 'opp-timer--warn': isWarning }">
    {{ formatted }}
  </div>
</template>

<style scoped>
.opp-timer {
  font-family: var(--font-mono);
  font-size: var(--text-2xl);
  font-weight: var(--weight-bold);
  color: var(--color-wood);
  background: var(--color-bg-secondary);
  border-radius: var(--radius-md);
  padding: var(--space-1) var(--space-3);
  min-width: 85px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.opp-timer--warn {
  color: var(--color-error);
  background: rgba(220, 38, 38, 0.08);
  animation: timer-blink 0.5s ease-in-out alternate infinite;
}

@keyframes timer-blink {
  from { opacity: 1; }
  to { opacity: 0.4; }
}
</style>
