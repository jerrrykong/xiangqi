<!--
  GameTimer.vue — 棋钟倒计时
  与 Demo 中 opp-timer 结构一致
-->
<template>
  <div
    class="opp-timer"
    :class="{ 'opp-timer--warn': time <= warnThreshold && time > 0 }"
  >
    {{ formatted }}
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  time: { type: Number, default: 600 },
  warnThreshold: { type: Number, default: 30 },
})

const formatted = computed(() => {
  const t = Math.max(0, Math.floor(props.time))
  const m = Math.floor(t / 60)
  const s = t % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
})
</script>
