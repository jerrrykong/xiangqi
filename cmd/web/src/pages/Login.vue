/**
 * Login — 登录页面
 * 木质风格卡片 + text-logo SVG + 自定义表单
 */
<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { showToast } from '@/components/common/ui'

const router = useRouter()
const baseUrl = import.meta.env.BASE_URL
const authStore = useAuthStore()

const isLoading = ref(false)
const errorMessage = ref('')

const form = reactive({
  username: '',
  password: '',
})

/** 表单验证错误 */
const errors = reactive({
  username: '',
  password: '',
})

/** 获取 redirect 参数 */
const redirect = (router.currentRoute.value.query.redirect as string) || '/lobby'

/** 监听输入，清除错误 */
watch(() => form.username, () => {
  if (errors.username) errors.username = ''
  if (errorMessage.value) errorMessage.value = ''
})
watch(() => form.password, () => {
  if (errors.password) errors.password = ''
  if (errorMessage.value) errorMessage.value = ''
})

/** 表单验证 */
function validateForm(): boolean {
  let valid = true
  errors.username = ''
  errors.password = ''

  if (!form.username) {
    errors.username = '请输入用户名'
    valid = false
  } else if (form.username.length < 4 || form.username.length > 32) {
    errors.username = '用户名长度在 4 到 32 个字符'
    valid = false
  }

  if (!form.password) {
    errors.password = '请输入密码'
    valid = false
  } else if (form.password.length < 8) {
    errors.password = '密码至少 8 个字符'
    valid = false
  }

  return valid
}

/** 提交登录 */
async function handleLogin() {
  if (!validateForm()) return

  errorMessage.value = ''
  isLoading.value = true
  try {
    await authStore.login(form.username, form.password)
    showToast('登录成功', 'success')
    router.push(redirect)
  } catch (error: any) {
    errorMessage.value = error.message || '登录失败'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <!-- Logo -->
      <img :src="baseUrl + 'assets/svg/ui/text-logo.svg'" alt="楚汉争锋" class="game-title-img" />
      <p class="game-subtitle">中国象棋在线对战平台</p>

      <!-- 登录中提示 -->
      <div v-if="isLoading" class="login-loading">
        <div class="loading-spinner"></div>
        <span>正在登录...</span>
      </div>

      <!-- 表单 -->
      <form class="login-form" @submit.prevent="handleLogin">
        <div class="form-group">
          <label class="form-label">用户名</label>
          <input
            v-model="form.username"
            type="text"
            class="form-input"
            :class="{ 'form-input--error': errors.username }"
            placeholder="请输入用户名"
            autocomplete="username"
          />
          <span v-if="errors.username" class="form-error">{{ errors.username }}</span>
        </div>

        <div class="form-group">
          <label class="form-label">密码</label>
          <input
            v-model="form.password"
            type="password"
            class="form-input"
            :class="{ 'form-input--error': errors.password }"
            placeholder="请输入密码"
            autocomplete="current-password"
          />
          <span v-if="errors.password" class="form-error">{{ errors.password }}</span>
        </div>

        <!-- 错误消息 -->
        <div v-if="errorMessage" class="form-error-banner">
          {{ errorMessage }}
        </div>

        <!-- 登录按钮 -->
        <button type="submit" class="btn btn-primary btn--lg btn--block" :disabled="isLoading">
          {{ isLoading ? '登录中...' : '登 录' }}
        </button>
      </form>

      <!-- 注册入口 -->
      <div class="login-actions">
        <router-link to="/register" class="btn btn-secondary btn--lg btn--block">
          注 册
        </router-link>
      </div>

      <!-- 底部 -->
      <div class="login-footer">
        <span>v1.0.0 · 楚漢爭鋒工作室</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-4);
  background: linear-gradient(135deg, var(--color-bg-primary) 0%, var(--color-bg-secondary) 100%);
}

.login-card {
  width: 100%;
  max-width: 420px;
  padding: var(--space-12) var(--space-8);
  background: var(--color-bg-card);
  border: 3px double var(--color-gold);
  border-radius: var(--radius-2xl);
  box-shadow: var(--shadow-xl);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-6);
}

.game-title-img {
  width: 280px;
  height: 75px;
}

.game-subtitle {
  font-family: var(--font-serif);
  font-size: var(--text-sm);
  color: var(--color-text-tertiary);
  letter-spacing: 0.2em;
}

.login-loading {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: rgba(37, 99, 235, 0.08);
  border: 1px solid rgba(37, 99, 235, 0.2);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  color: var(--color-info);
  width: 100%;
}

.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(37, 99, 235, 0.3);
  border-top-color: var(--color-info);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.login-form {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-error-banner {
  padding: var(--space-3) var(--space-4);
  background: rgba(220, 38, 38, 0.08);
  border: 1px solid rgba(220, 38, 38, 0.2);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  color: var(--color-error);
}

.login-actions {
  width: 100%;
}

.login-footer {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  letter-spacing: 0.05em;
}

@media (max-width: 768px) {
  .login-card {
    padding: var(--space-8) var(--space-5);
  }
  .game-title-img {
    width: 240px;
    height: 64px;
  }
}
</style>
