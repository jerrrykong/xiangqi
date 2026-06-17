/**
 * PlayerInfo — 玩家信息组件
 * 用于对局页面展示双方玩家信息（头像+名称+段位+计时器）
 * 
 * @prop side - 显示位置：opponent=上方, player=下方
 * @prop name - 玩家名称
 * @prop level - 段位/等级
 * @prop time - 剩余秒数
 * @prop isTurn - 是否轮到该玩家
 * @prop showTimer - 是否显示计时器
 */
<script setup lang="ts">
import { computed } from 'vue'
import GameTimer from './GameTimer.vue'

const baseUrl = import.meta.env.BASE_URL

const props = defineProps<{
  side: 'opponent' | 'player'
  name: string
  level?: string
  time?: number
  isTurn?: boolean
  showTimer?: boolean
}>()

const avatarText = computed(() => {
  return (props.name || (props.side === 'opponent' ? '对' : '我')).charAt(0)
})

const containerClass = computed(() => {
  return props.side === 'opponent' ? 'game-opponent' : 'game-player'
})
</script>

<template>
  <div :class="containerClass" :style="{ opacity: isTurn ? 1 : 0.75 }">
    <div class="ava" :class="{ 'ava--active': isTurn }">
      <img :src="baseUrl + 'assets/svg/ui/icon-user.svg'" alt="" class="ava-bg-icon" />
      <span class="ava-text">{{ avatarText }}</span>
    </div>
    <div class="opp-info">
      <div class="opp-name">{{ name || (side === 'opponent' ? '等待对手' : '我') }}</div>
      <div v-if="level" class="opp-level">{{ level }}</div>
    </div>
    <GameTimer v-if="showTimer && time !== undefined" :time="time" :warn-threshold="30" />
  </div>
</template>

<style scoped>
.game-opponent,
.game-player {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  transition: opacity var(--transition-fast);
}

.ava {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--color-text-muted);
  background: var(--color-bg-secondary);
  position: relative;
}

.ava-bg-icon {
  width: 24px;
  height: 24px;
  opacity: 0.12;
  position: absolute;
}

.ava-text {
  position: relative;
  z-index: 1;
  font-family: var(--font-serif);
  font-size: var(--text-lg);
  font-weight: var(--weight-bold);
  color: var(--color-wood);
}

.ava--active {
  border-color: var(--color-gold);
  box-shadow: 0 0 0 2px rgba(217, 119, 6, 0.2);
}

.game-player .ava--active {
  border-color: var(--color-gold);
}

.opp-info {
  flex: 1;
  min-width: 0;
}

.opp-name {
  font-family: var(--font-serif);
  font-size: var(--text-base);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.opp-level {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}

/* 移动端适配 */
@media (max-width: 768px) {
  .ava {
    width: 32px;
    height: 32px;
  }
  .ava-text {
    font-size: var(--text-sm);
  }
  .ava-bg-icon {
    width: 18px;
    height: 18px;
  }
}
</style>
