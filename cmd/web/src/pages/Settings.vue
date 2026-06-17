/**
 * Settings — 系统设置页面
 * 框架阶段：仅布局与交互，后端逻辑后续接入
 *
 * 布局结构：
 * - settings-header: 返回 + 标题
 * - settings-section × 3: 对局设置 / 账号 / 关于
 * - 退出登录按钮
 * - 底部 logo + 版本号
 */
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { showConfirm, showToast } from '@/components/common/ui'

const router = useRouter()
const baseUrl = import.meta.env.BASE_URL
const authStore = useAuthStore()

/** 对局设置 */
const soundEnabled = ref(true)
const boardTheme = ref('传统木质')
const moveConfirm = ref(false)

/** 退出登录 */
async function handleLogout() {
  const ok = await showConfirm('确定要退出登录吗？', '提示', { type: 'warning' })
  if (ok) {
    authStore.logout()
    router.push('/login')
    showToast('已退出登录', 'info')
  }
}

/** 返回上一页 */
function goBack() {
  router.back()
}
</script>

<template>
  <div class="settings-page">
    <!-- 顶部 -->
    <div class="settings-header">
      <button class="btn btn-text" @click="goBack">
        <img :src="baseUrl + 'assets/svg/ui/icon-back.svg'" alt="返回" class="btn-icon-sm" />
        返回
      </button>
      <h1 class="settings-title">系统设置</h1>
    </div>

    <!-- 对局设置 -->
    <div class="settings-section">
      <h2 class="settings-section-title">对局设置</h2>
      <div class="settings-group">
        <div class="settings-item">
          <div>
            <div class="item-label">音效</div>
            <div class="item-desc">走棋与系统提示音效</div>
          </div>
          <label class="toggle">
            <input type="checkbox" v-model="soundEnabled" />
            <span class="toggle-track"></span>
          </label>
        </div>

        <div class="settings-item">
          <div>
            <div class="item-label">棋盘主题</div>
            <div class="item-desc">更换棋盘外观风格</div>
          </div>
          <span class="item-value">{{ boardTheme }} ›</span>
        </div>

        <div class="settings-item">
          <div>
            <div class="item-label">走棋确认</div>
            <div class="item-desc">走棋前需二次确认</div>
          </div>
          <label class="toggle">
            <input type="checkbox" v-model="moveConfirm" />
            <span class="toggle-track"></span>
          </label>
        </div>
      </div>
    </div>

    <!-- 账号 -->
    <div class="settings-section">
      <h2 class="settings-section-title">账号</h2>
      <div class="settings-group">
        <div class="settings-item">
          <div class="item-label">昵称</div>
          <span class="item-value">{{ authStore.user?.nickname || authStore.user?.username || '—' }}</span>
        </div>
        <div class="settings-item">
          <div class="item-label">修改密码</div>
          <span class="item-value">›</span>
        </div>
      </div>
    </div>

    <!-- 关于 -->
    <div class="settings-section">
      <h2 class="settings-section-title">关于</h2>
      <div class="settings-group">
        <div class="settings-item">
          <div class="item-label">版本</div>
          <span class="item-value">v1.0.0</span>
        </div>
        <div class="settings-item">
          <div class="item-label">开发者</div>
          <span class="item-value">楚漢爭鋒工作室</span>
        </div>
      </div>
    </div>

    <!-- 退出登录 -->
    <div class="settings-section" style="text-align: center">
      <button class="btn btn-danger btn--block" @click="handleLogout">退出登录</button>
    </div>

    <!-- 底部 -->
    <div class="settings-about">
      <img :src="baseUrl + 'assets/svg/ui/text-logo.svg'" alt="楚汉争锋" class="about-logo-img" />
      <div>v1.0.0</div>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 640px;
  margin: 0 auto;
  padding: var(--space-10) var(--space-6);
  min-height: 100vh;
  background: var(--color-bg-primary);
}

.settings-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 0;
  margin-bottom: 24px;
}

.settings-title {
  font-family: var(--font-serif);
  font-size: var(--text-3xl);
  font-weight: var(--weight-bold);
  color: var(--color-wood-dark);
}

.btn-icon-sm {
  width: 18px;
  height: 18px;
  vertical-align: middle;
}

.settings-section {
  margin-bottom: 32px;
}

.settings-section-title {
  font-family: var(--font-serif);
  font-size: var(--text-lg);
  font-weight: var(--weight-bold);
  color: var(--color-wood-dark);
  margin-bottom: 16px;
}

.settings-group {
  background: var(--color-bg-card);
  border: 1px solid var(--color-wood-light);
  border-radius: 12px;
  overflow: hidden;
}

.settings-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid var(--color-bg-secondary);
  transition: background 0.15s;
}

.settings-item:last-child {
  border-bottom: none;
}

.settings-item:hover {
  background: var(--color-bg-secondary);
}

.settings-item .item-label {
  font-size: 15px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.settings-item .item-desc {
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-top: 2px;
}

.settings-item .item-value {
  font-size: 13px;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}

/* 开关组件 — 使用全局 .toggle / .toggle-track（见 forms.css） */

.settings-about {
  margin-top: 24px;
  text-align: center;
  font-size: 12px;
  color: var(--color-text-muted);
}

.settings-about .about-logo-img {
  width: 240px;
  height: 64px;
  margin: 0 auto 8px;
  display: block;
}

@media (max-width: 768px) {
  .settings-page {
    padding: var(--space-4) var(--space-4);
  }
}
</style>
