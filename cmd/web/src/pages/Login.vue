<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, type RouteLocationNormalized } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const formRef = ref()
const isLoading = ref(false)

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

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  isLoading.value = true
  try {
    await authStore.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push(redirect)
  } catch (error: any) {
    const message = error.response?.data?.message || '登录失败'
    ElMessage.error(message)
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

        <el-form-item class="form-actions">
          <el-button
            type="primary"
            size="large"
            class="full-width"
            :loading="isLoading"
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
