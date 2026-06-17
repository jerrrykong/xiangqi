/**
 * Register — 注册页面
 * 与登录页同风格
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

const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  nickname: '',
})

const errors = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  nickname: '',
})

/** 监听输入清除错误 */
watch(() => form.username, () => { errors.username = '' })
watch(() => form.password, () => { errors.password = '' })
watch(() => form.confirmPassword, () => { errors.confirmPassword = '' })

/** 表单验证 */
function validateForm(): boolean {
  let valid = true
  errors.username = ''
  errors.password = ''
  errors.confirmPassword = ''
  errors.nickname = ''

  if (!form.username) {
    errors.username = '请输入用户名'
    valid = false
  } else if (form.username.length < 4 || form.username.length > 32) {
    errors.username = '用户名长度在 4 到 32 个字符'
    valid = false
  } else if (!/^[a-zA-Z0-9_]+$/.test(form.username)) {
    errors.username = '用户名只能包含字母、数字和下划线'
    valid = false
  }

  if (!form.password) {
    errors.password = '请输入密码'
    valid = false
  } else if (form.password.length < 8) {
    errors.password = '密码至少 8 个字符'
    valid = false
  } else if (!/^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]/.test(form.password)) {
    errors.password = '密码必须包含字母和数字'
    valid = false
  }

  if (!form.confirmPassword) {
    errors.confirmPassword = '请确认密码'
    valid = false
  } else if (form.confirmPassword !== form.password) {
    errors.confirmPassword = '两次输入的密码不一致'
    valid = false
  }

  if (form.nickname && form.nickname.length > 32) {
    errors.nickname = '昵称最多 32 个字符'
    valid = false
  }

  return valid
}

/** 提交注册 */
async function handleRegister() {
  if (!validateForm()) return

  isLoading.value = true
  try {
    await authStore.register(form.username, form.password, form.nickname || undefined)
    showToast('注册成功，请登录', 'success')
    router.push('/login')
  } catch (error: any) {
    showToast(error.message || '注册失败', 'error')
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
      <p class="game-subtitle">用户注册</p>

      <!-- 注册中提示 -->
      <div v-if="isLoading" class="login-loading">
        <div class="loading-spinner"></div>
        <span>正在注册...</span>
      </div>

      <!-- 表单 -->
      <form class="login-form" @submit.prevent="handleRegister">
        <div class="form-group">
          <label class="form-label">用户名</label>
          <input
            v-model="form.username"
            type="text"
            class="form-input"
            :class="{ 'form-input--error': errors.username }"
            placeholder="4-32位字母、数字、下划线"
            autocomplete="username"
          />
          <span v-if="errors.username" class="form-error">{{ errors.username }}</span>
        </div>

        <div class="form-group">
          <label class="form-label">昵称</label>
          <input
            v-model="form.nickname"
            type="text"
            class="form-input"
            :class="{ 'form-input--error': errors.nickname }"
            placeholder="选填，默认使用用户名"
          />
          <span v-if="errors.nickname" class="form-error">{{ errors.nickname }}</span>
        </div>

        <div class="form-group">
          <label class="form-label">密码</label>
          <input
            v-model="form.password"
            type="password"
            class="form-input"
            :class="{ 'form-input--error': errors.password }"
            placeholder="至少8位，包含字母和数字"
            autocomplete="new-password"
          />
          <span v-if="errors.password" class="form-error">{{ errors.password }}</span>
        </div>

        <div class="form-group">
          <label class="form-label">确认密码</label>
          <input
            v-model="form.confirmPassword"
            type="password"
            class="form-input"
            :class="{ 'form-input--error': errors.confirmPassword }"
            placeholder="请再次输入密码"
            autocomplete="new-password"
          />
          <span v-if="errors.confirmPassword" class="form-error">{{ errors.confirmPassword }}</span>
        </div>

        <!-- 注册按钮 -->
        <button type="submit" class="btn btn-primary btn--lg btn--block" :disabled="isLoading">
          {{ isLoading ? '注册中...' : '注 册' }}
        </button>
      </form>

      <!-- 登录入口 -->
      <div class="login-actions">
        <router-link to="/login" class="btn btn-secondary btn--lg btn--block">
          返回登录
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
  padding: var(--space-10) var(--space-8);
  background: var(--color-bg-card);
  border: 3px double var(--color-gold);
  border-radius: var(--radius-2xl);
  box-shadow: var(--shadow-xl);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-5);
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
    padding: var(--space-6) var(--space-5);
  }
  .game-title-img {
    width: 240px;
    height: 64px;
  }
}
</style>
