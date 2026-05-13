import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserProfile } from '@/types/api'
import * as authApi from '@/api/auth'
import * as userApi from '@/api/user'

export const useAuthStore = defineStore('auth', () => {
  // 状态
  const user = ref<UserProfile | null>(null)
  const token = ref<string | null>(localStorage.getItem('token'))
  const isLoading = ref(false)

  // 计算属性
  const isAuthenticated = computed(() => !!token.value && !!user.value)

  // 从 localStorage 恢复用户信息
  function restoreUser() {
    const savedUser = localStorage.getItem('user')
    if (savedUser) {
      try {
        user.value = JSON.parse(savedUser)
      } catch {
        localStorage.removeItem('user')
      }
    }
  }

  // 初始化
  function init() {
    restoreUser()
    // 如果有 token 但没有用户信息，尝试获取
    if (token.value && !user.value) {
      fetchCurrentUser()
    }
  }

  // 获取当前用户
  async function fetchCurrentUser() {
    try {
      isLoading.value = true
      const profile = await userApi.getCurrentUser()
      user.value = profile
      localStorage.setItem('user', JSON.stringify(profile))
    } catch (error) {
      console.error('Failed to fetch current user:', error)
      // 如果获取失败，可能是 token 过期
      logout()
    } finally {
      isLoading.value = false
    }
  }

  // 登录
  async function login(username: string, password: string): Promise<UserProfile> {
    isLoading.value = true
    try {
      const response = await authApi.login({ username, password })
      token.value = response.token
      user.value = response
      localStorage.setItem('token', response.token)
      localStorage.setItem('user', JSON.stringify(response))
      return response
    } finally {
      isLoading.value = false
    }
  }

  // 注册
  async function register(
    username: string,
    password: string,
    nickname?: string
  ): Promise<UserProfile> {
    isLoading.value = true
    try {
      return await authApi.register({ username, password, nickname })
    } finally {
      isLoading.value = false
    }
  }

  // 登出
  function logout() {
    authApi.logout()
    user.value = null
    token.value = null
  }

  // 更新用户信息
  function updateUser(profile: UserProfile) {
    user.value = profile
    localStorage.setItem('user', JSON.stringify(profile))
  }

  return {
    // 状态
    user,
    token,
    isLoading,
    // 计算属性
    isAuthenticated,
    // 方法
    init,
    fetchCurrentUser,
    login,
    register,
    logout,
    updateUser,
  }
})
