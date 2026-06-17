<!--
  PlayerInfo.vue — 玩家信息
  与 Demo 中 game-opponent/game-player 结构一致
-->
<template>
  <!-- 对手 -->
  <div v-if="side === 'opponent'" class="game-opponent">
    <div class="ava">{{ avatarText }}</div>
    <div class="opp-info">
      <div class="opp-name">{{ name || '等待对手' }}</div>
      <div class="opp-level" v-if="level">{{ level }}</div>
    </div>
    <GameTimer v-if="showTimer" :time="time" :warn-threshold="30" />
  </div>

  <!-- 我方 -->
  <div v-else class="game-player">
    <div class="ava">{{ avatarText }}</div>
    <div class="opp-info">
      <div class="opp-name">{{ name || '我' }}</div>
      <div class="opp-level" v-if="level">{{ level }}</div>
    </div>
    <GameTimer v-if="showTimer" :time="time" :warn-threshold="30" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import GameTimer from './GameTimer.vue'

const props = defineProps({
  side: { type: String, default: 'player', validator: v => ['player', 'opponent'].includes(v) },
  name: { type: String, default: '' },
  level: { type: String, default: '' },
  avatar: { type: String, default: '' },
  time: { type: Number, default: 600 },
  isTurn: { type: Boolean, default: false },
  showTimer: { type: Boolean, default: true },
})

const avatarText = computed(() => {
  if (props.avatar) return ''
  return (props.name || (props.side === 'opponent' ? '对' : '我')).charAt(0)
})
</script>
