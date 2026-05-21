<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const formRef = ref()
const isLoading = ref(false)
const errorMessage = ref('')

const form = reactive({
  username: '',
  password: '',
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 4, max: 32, message: '用户名长度在 4 到 32 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少 8 个字符', trigger: 'blur' },
  ],
}

// 获取 redirect 参数
const redirect = (router.currentRoute.value.query.redirect as string) || '/lobby'

// 监听输入，清除错误消息
watch(() => form.username, () => {
  if (errorMessage.value) errorMessage.value = ''
})
watch(() => form.password, () => {
  if (errorMessage.value) errorMessage.value = ''
})

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  errorMessage.value = ''
  isLoading.value = true
  try {
    await authStore.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push(redirect)
  } catch (error: any) {
    errorMessage.value = error.message || '登录失败'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card card">
      <h1 class="auth-title">中国象棋</h1>
      <p class="auth-subtitle">用户登录</p>

      <!-- WS 连接状态提示 -->
      <div v-if="authStore.connectionState === 'disconnected' || authStore.connectionState === 'connecting'" class="connection-status">
        <div class="loading-spinner-small"></div>
        <span>{{ authStore.connectionState === 'connecting' ? '正在连接服务器...' : '连接已断开，正在重连...' }}</span>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="handleLogin"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            size="large"
            prefix-icon="User"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            prefix-icon="Lock"
            show-password
          />
        </el-form-item>

        <!-- 错误消息 -->
        <div v-if="errorMessage" class="error-message">
          <span class="error-icon">⚠️</span>
          <span class="error-text">{{ errorMessage }}</span>
        </div>

        <el-form-item class="form-actions">
          <el-button
            type="primary"
            size="large"
            class="full-width"
            :loading="isLoading"
            :disabled="authStore.connectionState !== 'connected'"
            native-type="submit"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>

      <div class="auth-footer">
        <span class="footer-text">还没有账号？</span>
        <router-link to="/register" class="footer-link">
          立即注册
        </router-link>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: linear-gradient(135deg, var(--color-wood-100) 0%, var(--color-wood-200) 100%);
}

.auth-card {
  width: 100%;
  max-width: 448px;
  padding: 48px 32px;
}

.card {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(139, 90, 43, 0.2);
}

.auth-title {
  font-size: 1.875rem;
  font-weight: bold;
  text-align: center;
  margin-bottom: 8px;
  color: var(--color-wood-600);
}

.auth-subtitle {
  text-align: center;
  color: #6b7280;
  margin-bottom: 32px;
}

.full-width {
  width: 100%;
}

.form-actions {
  margin-top: 24px;
}

.connection-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 0.875rem;
  color: #3b82f6;
}

.loading-spinner-small {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(59, 130, 246, 0.3);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-message {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  margin-bottom: 16px;
}

.error-icon {
  font-size: 1rem;
}

.error-text {
  color: #dc2626;
  font-size: 0.875rem;
}

.auth-footer {
  text-align: center;
  margin-top: 16px;
}

.footer-text {
  color: #6b7280;
}

.footer-link {
  color: var(--color-wood-500);
  margin-left: 4px;
  text-decoration: none;
  transition: color 0.2s;
}

.footer-link:hover {
  color: var(--color-wood-600);
}
</style>
