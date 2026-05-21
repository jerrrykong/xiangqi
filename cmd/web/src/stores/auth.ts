import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { WSAuthState, WSConnectionState, AuthResultData, AuthTokenResultData, ReconnectResultData, RatingUpdateData, ErrorData } from '@/ws/types'
import { wsClient } from '@/ws/client'
import { WSMsgType } from '@/ws/types'

export interface UserProfile {
  user_id: number
  username: string
  nickname: string
  avatar?: string
  rating: number
  games_count: number
  is_admin?: boolean
  created_at?: string
}

export const useAuthStore = defineStore('auth', () => {
  // 状态
  const user = ref<UserProfile | null>(null)
  const token = ref<string | null>(localStorage.getItem('token'))
  const sessionToken = ref<string | null>(localStorage.getItem('session_token'))
  const refreshToken = ref<string | null>(localStorage.getItem('refresh_token'))
  const isLoading = ref(false)

  // WS 认证状态
  const connectionState = ref<WSConnectionState>('disconnected')
  const authState = ref<WSAuthState>('unauthenticated')

  // 计算属性
  const isAuthenticated = computed(() => authState.value !== 'unauthenticated')

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

  // 设置认证状态
  function setAuthState(state: WSAuthState) {
    authState.value = state
  }

  // 初始化 — 建立 WS 连接 + 认证
  async function init() {
    restoreUser()

    // 同步 WS 连接状态
    connectionState.value = wsClient.connectionState.value

    // 如果 WS 已连接，不重复连接
    if (wsClient.connectionState.value === 'connected') {
      return
    }

    try {
      isLoading.value = true
      // 建立 WS 连接 (通过 Vite 代理 /ws → ws://localhost:8080/ws)
      const wsUrl = getWSUrl()
      await wsClient.connect(wsUrl)

      // 连接成功后尝试认证
      await authenticate()
    } catch (error) {
      console.error('[Auth] Init failed:', error)
      // 连接失败时仍然允许用户看到 Login 页面
    } finally {
      isLoading.value = false
    }
  }

  // 认证流程
  async function authenticate() {
    // 1. 优先尝试 session_token 重连
    if (sessionToken.value) {
      try {
        const result = await wsClient.request(WSMsgType.RECONNECT, {
          session_token: sessionToken.value,
        })
        if (result.success) {
          handleReconnectResult(result)
          return
        }
      } catch {
        // session_token 失败，回退到 JWT
      }
    }

    // 2. 尝试 JWT token 认证
    if (token.value) {
      try {
        const result = await wsClient.request(WSMsgType.AUTH_TOKEN, {
          token: token.value,
        })
        if (result.success) {
          handleAuthTokenResult(result)
          return
        }
      } catch {
        // JWT token 也失败了
      }
    }

    // 3. 无有效凭证
    clearAuth()
  }

  // 登录
  async function login(username: string, password: string): Promise<UserProfile> {
    isLoading.value = true
    try {
      // 确保 WS 已连接
      if (!wsClient.isConnected) {
        const wsUrl = getWSUrl()
        await wsClient.connect(wsUrl)
      }

      const result = await wsClient.request(WSMsgType.AUTH_LOGIN, { username, password })
      if (!result.success) {
        throw new Error(result.error || '登录失败')
      }

      handleAuthResult(result)
      return user.value!
    } finally {
      isLoading.value = false
    }
  }

  // 注册
  async function register(username: string, password: string, nickname?: string): Promise<UserProfile> {
    isLoading.value = true
    try {
      // 确保 WS 已连接
      if (!wsClient.isConnected) {
        const wsUrl = getWSUrl()
        await wsClient.connect(wsUrl)
      }

      const result = await wsClient.request(WSMsgType.AUTH_REGISTER, { username, password, nickname })
      if (!result.success) {
        throw new Error(result.error || '注册失败')
      }

      handleAuthResult(result)
      return user.value!
    } finally {
      isLoading.value = false
    }
  }

  // 登出
  function logout() {
    wsClient.disconnect()
    clearAuth()
  }

  // 清除认证状态
  function clearAuth() {
    user.value = null
    token.value = null
    sessionToken.value = null
    refreshToken.value = null
    authState.value = 'unauthenticated'
    localStorage.removeItem('token')
    localStorage.removeItem('session_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
  }

  // ===== 推送消息处理 =====

  // 处理登录/注册结果
  function handleAuthResult(data: AuthResultData) {
    if (!data.success) return

    token.value = data.token || null
    sessionToken.value = data.session_token || null
    refreshToken.value = data.refresh_token || null

    user.value = {
      user_id: data.user_id!,
      username: data.username!,
      nickname: data.nickname || data.username!,
      rating: data.rating || 1500,
      games_count: data.games_count || 0,
      is_admin: data.is_admin || false,
    }

    // 持久化
    if (data.token) localStorage.setItem('token', data.token)
    if (data.session_token) localStorage.setItem('session_token', data.session_token)
    if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token)
    localStorage.setItem('user', JSON.stringify(user.value))

    authState.value = 'authenticated'
  }

  // 处理 Token 认证结果
  function handleAuthTokenResult(data: AuthTokenResultData) {
    if (!data.success) return

    sessionToken.value = data.session_token || null

    user.value = {
      user_id: data.user_id!,
      username: data.username!,
      nickname: data.nickname || data.username!,
      rating: data.rating || 1500,
      games_count: data.games_count || 0,
      is_admin: data.is_admin || false,
    }

    if (data.session_token) localStorage.setItem('session_token', data.session_token)
    localStorage.setItem('user', JSON.stringify(user.value))

    authState.value = 'authenticated'
  }

  // 处理 Token 刷新结果
  function handleAuthRefreshResult(data: any) {
    if (data.token) {
      token.value = data.token
      localStorage.setItem('token', data.token)
    }
    if (data.session_token) {
      sessionToken.value = data.session_token
      localStorage.setItem('session_token', data.session_token)
    }
  }

  // 处理重连结果
  function handleReconnectResult(data: ReconnectResultData) {
    if (!data.success) return

    sessionToken.value = data.session_token || null
    if (data.session_token) localStorage.setItem('session_token', data.session_token)

    // 根据状态恢复
    if (data.state === 'in_room') {
      authState.value = 'in_room'
    } else if (data.state === 'matchmaking') {
      authState.value = 'matchmaking'
    } else {
      authState.value = 'authenticated'
    }
  }

  // 处理积分更新
  function handleRatingUpdate(data: RatingUpdateData) {
    if (user.value) {
      user.value.rating = data.rating
      user.value.games_count = data.games_count
      localStorage.setItem('user', JSON.stringify(user.value))
    }
  }

  // 处理错误
  function handleError(data: ErrorData) {
    console.error('[Auth] WS Error:', data.code, data.message)
    // 认证相关错误
    if (data.code === 1001 || data.code === 1002) {
      clearAuth()
    }
  }

  // 更新用户信息 (从 WS 推送)
  function updateUserFromWS(data: any) {
    if (user.value) {
      user.value = {
        ...user.value,
        user_id: data.user_id || data.id || user.value.user_id,
        username: data.username || user.value.username,
        nickname: data.nickname || user.value.nickname,
        rating: data.rating ?? user.value.rating,
        games_count: data.games_count ?? user.value.games_count,
      }
      localStorage.setItem('user', JSON.stringify(user.value))
    }
  }

  // 更新用户信息 (通用)
  function updateUser(profile: UserProfile) {
    user.value = profile
    localStorage.setItem('user', JSON.stringify(profile))
  }

  // 获取 WS URL
  function getWSUrl(): string {
    // 开发环境通过 Vite 代理，生产环境使用当前 host
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = import.meta.env.DEV ? `${protocol}//${window.location.host}` : `${protocol}//${window.location.host}`
    return `${host}/ws`
  }

  return {
    // 状态
    user,
    token,
    sessionToken,
    isLoading,
    connectionState,
    authState,
    // 计算属性
    isAuthenticated,
    // 方法
    init,
    login,
    register,
    logout,
    setAuthState,
    updateUser,
    updateUserFromWS,
    // 推送处理
    handleAuthResult,
    handleAuthTokenResult,
    handleAuthRefreshResult,
    handleReconnectResult,
    handleRatingUpdate,
    handleError,
  }
})
