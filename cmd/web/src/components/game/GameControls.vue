/**
 * GameControls — 对局操作按钮组
 * 
 * @prop phase - 对局阶段：playing | finished | ready
 * @prop canRematch - 是否可以再来一局
 * @prop iWantRematch - 我方是否已请求再来一局
 * @prop opponentWantsRematch - 对方是否请求再来一局
 * @prop isGameOver - 对局是否已结束
 */
<script setup lang="ts">
const baseUrl = import.meta.env.BASE_URL

defineProps<{
  phase: 'playing' | 'finished' | 'ready'
  canRematch?: boolean
  iWantRematch?: boolean
  opponentWantsRematch?: boolean
  isGameOver?: boolean
}>()

const emit = defineEmits<{
  (e: 'draw'): void
  (e: 'resign'): void
  (e: 'undo'): void
  (e: 'exit'): void
  (e: 'rematch'): void
  (e: 'ready'): void
}>()
</script>

<template>
  <div class="game-actions-inline">
    <!-- 游戏进行中 -->
    <template v-if="phase === 'playing'">
      <button class="btn btn-secondary btn--sm" @click="emit('draw')" :disabled="isGameOver">
        <img :src="baseUrl + 'assets/svg/ui/icon-undo.svg'" alt="" class="btn-icon-xs" />
        求和
      </button>
      <button class="btn btn-secondary btn--sm" @click="emit('resign')" :disabled="isGameOver">
        <img :src="baseUrl + 'assets/svg/ui/icon-flag.svg'" alt="" class="btn-icon-xs" />
        认输
      </button>
      <button class="btn btn-text btn--sm" @click="emit('exit')">
        <img :src="baseUrl + 'assets/svg/ui/icon-exit.svg'" alt="" class="btn-icon-xs" />
        退出
      </button>
    </template>

    <!-- 游戏结束 -->
    <template v-else-if="phase === 'finished'">
      <button
        v-if="canRematch !== false"
        class="btn btn-primary btn--sm"
        @click="emit('rematch')"
        :disabled="iWantRematch"
      >
        <img :src="baseUrl + 'assets/svg/ui/icon-refresh.svg'" alt="" class="btn-icon-xs" />
        {{ iWantRematch ? (opponentWantsRematch ? '开始...' : '等待对方...') : '再来一局' }}
      </button>
      <button class="btn btn-secondary btn--sm" @click="emit('exit')">
        <img :src="baseUrl + 'assets/svg/ui/icon-back.svg'" alt="" class="btn-icon-xs" />
        返回大厅
      </button>
    </template>

    <!-- 等待开始 -->
    <template v-else-if="phase === 'ready'">
      <button class="btn btn-primary btn--sm" @click="emit('ready')">
        <img :src="baseUrl + 'assets/svg/ui/icon-play.svg'" alt="" class="btn-icon-xs" />
        开始
      </button>
      <button class="btn btn-text btn--sm" @click="emit('exit')">
        <img :src="baseUrl + 'assets/svg/ui/icon-exit.svg'" alt="" class="btn-icon-xs" />
        退出
      </button>
    </template>
  </div>
</template>

<style scoped>
.game-actions-inline {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  flex-wrap: wrap;
}

.btn-icon-xs {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}
</style>
