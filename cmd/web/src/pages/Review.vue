/**
 * Review — 棋局复盘页面
 * 框架阶段：棋盘展示 + 播放控制 + 弹出面板（着法/信息）
 * 后端复盘数据与播放逻辑后续接入
 *
 * 布局结构：
 * - review-header: 返回 + 标题 + 导入棋谱按钮
 * - review-main: review-board-area（棋盘 + PlaybackControls + toggle-bar）
 * - review-overlay + review-popup: 着法记录/对局信息弹出面板
 */
<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showToast } from '@/components/common/ui'
import ChessBoard from '@/components/chess/ChessBoard.vue'
import PlaybackControls from '@/components/game/PlaybackControls.vue'
import type { Position, Move } from '@/types/chess'

const router = useRouter()
const route = useRoute()
const baseUrl = import.meta.env.BASE_URL

/** 游戏ID */
const gameId = computed(() => (route.params.gameId as string) || '')

/** 初始棋盘（框架阶段用空棋盘占位） */
const emptyBoard = computed(() => {
  const board: number[][] = []
  for (let r = 0; r < 10; r++) {
    board.push(new Array(9).fill(0))
  }
  return board
})

/** 播放状态 */
const reviewStep = ref(0)
const reviewTotal = ref(47) // 占位
const playing = ref(false)
const speed = ref(1)
let playTimer: ReturnType<typeof setInterval> | null = null

/** 弹出面板 */
const activePopup = ref<'' | 'moves' | 'info'>('')

/** 着法数据占位 */
const sampleMoves = [
  { idx: 1, red: '炮二平五', black: '马8进7' },
  { idx: 2, red: '马二进三', black: '车9平8' },
  { idx: 3, red: '车一平二', black: '马2进3' },
  { idx: 4, red: '兵七进一', black: '卒7进1' },
  { idx: 5, red: '马八进七', black: null },
]

/** ── 播放控制 ── */
function handlePrev() {
  reviewStep.value = Math.max(0, reviewStep.value - 1)
}

function handleNext() {
  reviewStep.value = Math.min(reviewTotal.value, reviewStep.value + 1)
}

function handleToggle() {
  playing.value = !playing.value
  if (playing.value) {
    playTimer = setInterval(() => {
      if (reviewStep.value >= reviewTotal.value) {
        playing.value = false
        if (playTimer) clearInterval(playTimer)
        return
      }
      reviewStep.value++
    }, 1000 / speed.value)
  } else {
    if (playTimer) {
      clearInterval(playTimer)
      playTimer = null
    }
  }
}

function handleSpeed(val: number) {
  speed.value = val
  // 若正在播放，重置定时器
  if (playing.value) {
    if (playTimer) clearInterval(playTimer)
    playTimer = setInterval(() => {
      if (reviewStep.value >= reviewTotal.value) {
        playing.value = false
        if (playTimer) clearInterval(playTimer)
        return
      }
      reviewStep.value++
    }, 1000 / speed.value)
  }
}

function handleSeek(step: number) {
  reviewStep.value = Math.max(0, Math.min(reviewTotal.value, step))
}

/** 返回 */
function goBack() {
  router.back()
}

/** 生命周期 */
onUnmounted(() => {
  if (playTimer) clearInterval(playTimer)
})
</script>

<template>
  <div class="review-page">
    <!-- 顶部 -->
    <header class="review-header">
      <button class="btn btn-text" @click="goBack">
        <img :src="baseUrl + 'assets/svg/ui/icon-back.svg'" alt="返回" class="btn-icon-sm" />
        返回
      </button>
      <h1 class="review-title">棋局复盘</h1>
      <div class="header-actions">
        <button class="btn btn-secondary btn--sm" @click="showToast('导入功能开发中', 'info')">
          📥 导入棋谱
        </button>
      </div>
    </header>

    <!-- 主体 -->
    <div class="review-main">
      <div class="review-board-area">
        <!-- 棋盘 -->
        <ChessBoard
          :board="emptyBoard"
          :selectedPosition="null"
          :validMoves="[]"
          :lastMove="null"
          :isInCheck="false"
          :checkPosition="null"
          :yourColor="0"
          :isMyTurn="false"
          :isGameStarted="true"
          :frozen="true"
          :animatingMove="null"
        />

        <!-- 播放控制 -->
        <PlaybackControls
          :current="reviewStep"
          :total="reviewTotal"
          :playing="playing"
          :speed="speed"
          :showSpeed="true"
          @prev="handlePrev"
          @toggle="handleToggle"
          @next="handleNext"
          @speed="handleSpeed"
          @seek="handleSeek"
        />

        <!-- 切换按钮行 -->
        <div class="review-toggle-bar">
          <button
            class="toggle-item"
            :class="{ active: activePopup === 'moves' }"
            @click="activePopup = activePopup === 'moves' ? '' : 'moves'"
          >
            📜 着法记录
          </button>
          <button
            class="toggle-item"
            :class="{ active: activePopup === 'info' }"
            @click="activePopup = activePopup === 'info' ? '' : 'info'"
          >
            📊 对局信息
          </button>
        </div>
      </div>
    </div>

    <!-- 着法记录弹出面板 -->
    <Transition name="overlay">
      <div v-if="activePopup === 'moves'" class="review-overlay" @click.self="activePopup = ''">
        <div class="review-popup">
          <div class="popup-header">
            <span class="popup-title">📜 着法记录</span>
            <button class="popup-close" @click="activePopup = ''">✕</button>
          </div>
          <div class="popup-body">
            <div class="move-list">
              <div
                v-for="m in sampleMoves"
                :key="m.idx"
                class="move-item"
                :class="{ active: reviewStep === m.idx }"
              >
                <span class="move-num">{{ m.idx }}.</span>
                <span class="move-red">{{ m.red }}</span>
                <span v-if="m.black" class="move-black">{{ m.black }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 对局信息弹出面板 -->
    <Transition name="overlay">
      <div v-if="activePopup === 'info'" class="review-overlay" @click.self="activePopup = ''">
        <div class="review-popup">
          <div class="popup-header">
            <span class="popup-title">📊 对局信息</span>
            <button class="popup-close" @click="activePopup = ''">✕</button>
          </div>
          <div class="popup-body">
            <div class="game-info-card">
              <div class="info-row">
                <span class="info-label">对局ID</span>
                <span class="info-value">{{ gameId || '—' }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">红方</span>
                <span class="info-value">—</span>
              </div>
              <div class="info-row">
                <span class="info-label">黑方</span>
                <span class="info-value">—</span>
              </div>
              <div class="info-row">
                <span class="info-label">结果</span>
                <span class="info-value">—</span>
              </div>
              <div class="info-row">
                <span class="info-label">总手数</span>
                <span class="info-value">{{ reviewTotal }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.review-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: var(--max-width-content, 1440px);
  margin: 0 auto;
  overflow: hidden;
  background: var(--color-bg-primary);
}

/* ── 头部 ── */
.review-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background: var(--color-bg-secondary);
  border-bottom: 1px solid var(--color-wood-light);
  flex-shrink: 0;
}

.review-title {
  font-family: var(--font-serif);
  font-size: var(--text-lg);
  font-weight: var(--weight-bold);
  color: var(--color-wood-dark);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.btn-icon-sm {
  width: 18px;
  height: 18px;
  vertical-align: middle;
}

/* ── 主体 ── */
.review-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.review-board-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding: var(--space-6);
  gap: 20px;
  overflow-y: auto;
  min-height: 0;
}

/* ── 切换按钮行 ── */
.review-toggle-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  flex-shrink: 0;
}

.review-toggle-bar .toggle-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-wood);
  background: var(--color-bg-secondary);
  transition: all 0.15s;
  cursor: pointer;
  border: none;
}

.review-toggle-bar .toggle-item:hover {
  background: var(--color-wood-bg);
}

.review-toggle-bar .toggle-item.active {
  background: var(--color-gold);
  color: #fff;
}

/* ── 弹出面板 ── */
.review-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: var(--color-bg-overlay);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-6);
}

.review-popup {
  background: var(--color-bg-card);
  border: 2px solid var(--color-gold-light);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  width: 100%;
  max-width: 520px;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.review-popup .popup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid var(--color-wood-light);
  flex-shrink: 0;
}

.review-popup .popup-title {
  font-family: var(--font-serif);
  font-size: var(--text-base);
  font-weight: var(--weight-bold);
  color: var(--color-wood-dark);
}

.review-popup .popup-close {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 18px;
  color: var(--color-text-tertiary);
  transition: all 0.15s;
  cursor: pointer;
  background: none;
  border: none;
}

.review-popup .popup-close:hover {
  background: var(--color-bg-secondary);
  color: var(--color-wood);
}

.review-popup .popup-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px 16px;
}

/* ── 着法记录 ── */
.move-list {
  display: flex;
  flex-direction: column;
  padding: 8px;
}

.move-item {
  display: flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 6px;
  transition: background 0.15s;
}

.move-item:hover {
  background: var(--color-bg-secondary);
}

.move-item.active {
  background: rgba(217, 119, 6, 0.12);
  font-weight: var(--weight-bold);
}

.move-num {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--color-text-tertiary);
  min-width: 24px;
  flex-shrink: 0;
}

.move-red {
  color: var(--color-piece-red);
  min-width: 80px;
  font-size: var(--text-sm);
}

.move-black {
  color: var(--color-piece-black);
  font-size: var(--text-sm);
}

/* ── 对局信息卡 ── */
.game-info-card {
  padding: 16px 24px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-wood-light);
  border-radius: 12px;
}

.game-info-card .info-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  font-size: 13px;
  border-bottom: 1px solid var(--color-bg-secondary);
}

.game-info-card .info-row:last-child {
  border-bottom: none;
}

.game-info-card .info-label {
  color: var(--color-text-tertiary);
}

.game-info-card .info-value {
  font-weight: 500;
  color: var(--color-text-primary);
}

/* ── Overlay 动画 ── */
.overlay-enter-active {
  transition: all 0.25s ease-out;
}
.overlay-leave-active {
  transition: all 0.2s ease-in;
}
.overlay-enter-from {
  opacity: 0;
}
.overlay-leave-to {
  opacity: 0;
}

/* ── 移动端 ── */
@media (max-width: 768px) {
  .review-header {
    padding: 10px 12px;
  }

  .review-title {
    font-size: var(--text-base);
  }

  .review-board-area {
    padding: 12px;
    gap: 12px;
  }

  .review-overlay {
    align-items: flex-end;
    padding: 0;
  }

  .review-popup {
    max-width: 100%;
    max-height: 55vh;
    border-radius: 16px 16px 0 0;
  }
}
</style>
