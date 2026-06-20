import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { WSAuthState, WSConnectionState, AuthResultData, AuthTokenResultData, ReconnectResultData, RatingUpdateData, ErrorData } from '@/ws/types'
import { wsClient } from '@/ws/client'
import { WSMsgType } from '@/ws/types'
import router from '@/router'
import { useRoomStore } from './room'

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
  const connectionState = ref<WSConnectionState>(wsClient.connectionState.value)
  const authState = ref<WSAuthState>('unauthenticated')

  // 追踪之前的认证状态，用于断线重连场景判断
  const previousAuthState = ref<WSAuthState | null>(null)
  // 标记是否为断线重连（WS 连接断开后重新认证成功）
  const isReconnecting = ref(false)
  // 断线前的游戏阶段（由 App.vue 在 WS 断连时设置）
  const phaseBeforeDisconnect = ref<string | null>(null)

  // 断线重连时的提示信息队列（由 auth store 收集，由页面消费）
  const reconnectMessages = ref<string[]>([])

  // 计算属性
  const isAuthenticated = computed(() => authState.value !== 'unauthenticated' && authState.value !== 'restoring')

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
    previousAuthState.value = authState.value
    authState.value = state
  }

  // 标记断线重连（WS 断连时调用，同时保存断线前的游戏阶段）
  function markReconnecting(phaseBefore: string | null = null) {
    if (authState.value !== 'unauthenticated') {
      isReconnecting.value = true
      phaseBeforeDisconnect.value = phaseBefore
      reconnectMessages.value = []
    }
  }

  // 消费并清空重连提示
  function consumeReconnectMessages(): string[] {
    const msgs = [...reconnectMessages.value]
    reconnectMessages.value = []
    isReconnecting.value = false
    return msgs
  }

  // 是否有保存的凭证
  function hasCredentials(): boolean {
    return !!(token.value || sessionToken.value)
  }

  // 初始化 — 仅恢复本地用户信息，不自动连接（由 Splash 页面驱动连接流程）
  function init() {
    restoreUser()
    // 初始状态设为 unauthenticated，由 Splash 页面根据本地凭证决定是否连接
    authState.value = 'unauthenticated'
    connectionState.value = wsClient.connectionState.value
  }

  // 使用保存的凭证连接+认证
  async function authenticateWithCredentials() {
    isLoading.value = true
    try {
      const wsUrl = getWSUrl()
      await wsClient.connect(wsUrl)

      // 连接成功，立即发送认证消息 (首条消息)
      const result = await authenticate()
      if (result === 'credentials_invalid') {
        // 服务端明确表示凭证无效 → 清除凭证，显示登录页
        console.log('[Auth] Credentials invalid, clearing auth')
        clearAuth()
        wsClient.disconnect()
      } else if (result === 'ok') {
        // 凭证恢复成功 → 导航到目标页面
        console.log('[Auth] Credentials restored, user=', user.value?.username)
        const redirect = router.currentRoute.value.query.redirect as string
        if (redirect) {
          router.replace(redirect)
        } else if (router.currentRoute.value.path === '/login' || router.currentRoute.value.path === '/register') {
          router.replace('/lobby')
        }
      }
      // 'retry': 网络临时故障，保留凭证等待重连
    } catch (error) {
      console.error('[Auth] Credential auth failed:', error)
      // 连接失败 (网络不可达等) → 不清除凭证，开启自动重连
      authState.value = 'unauthenticated'
      connectionState.value = 'disconnected'
      // 设置重连回调，让 WSClient 重连成功后自动认证
      setupReconnectHandler()
      // 开启自动重连
      wsClient.enableReconnect()
    } finally {
      isLoading.value = false
    }
  }

  // 认证流程 (WS 已连接后调用，发送首条认证消息)
  // 返回值: 'ok' = 认证成功, 'credentials_invalid' = 凭证无效(应清除), 'retry' = 网络临时故障(应重试)
  async function authenticate(): Promise<'ok' | 'credentials_invalid' | 'retry'> {
    // 策略: 优先 JWT token (最可靠), 其次 session_token (仅对局中重连有意义)

    // 1. 尝试 JWT token 认证 (最可靠，不依赖服务端内存状态)
    if (token.value) {
      try {
        console.log('[Auth] Trying JWT token auth...')
        const result = await wsClient.request(WSMsgType.AUTH_TOKEN, {
          token: token.value,
        })
        if (result.success) {
          console.log('[Auth] JWT token auth success, user=', result.username)
          handleAuthTokenResult(result)
          wsClient.onAuthSuccess()
          setupReconnectHandler()
          return 'ok'
        }
        // success=false 且有 error 字段 → 凭证无效
        console.log('[Auth] JWT token auth failed:', result.error)
        if (result.error === 'token_invalid' || result.error === 'user_banned') {
          return 'credentials_invalid'
        }
      } catch (e) {
        // 网络异常 (连接断开/超时) → 临时故障，不清除凭证
        console.error('[Auth] JWT token auth network error:', e)
        return 'retry'
      }
    }

    // 2. 尝试 session_token 重连 (依赖服务端内存中有对应连接)
    if (sessionToken.value) {
      try {
        console.log('[Auth] Trying session_token reconnect...')
        const result = await wsClient.request(WSMsgType.RECONNECT, {
          session_token: sessionToken.value,
        })
        if (result.success) {
          console.log('[Auth] Session reconnect success, user=', result.username, ', state=', result.state)
          handleReconnectResult(result)
          wsClient.onAuthSuccess()
          setupReconnectHandler()
          return 'ok'
        }
        // success=false → session 已失效，但 JWT 可能仍然有效
        // 只有当没有任何其他凭证时才标记为无效
        console.log('[Auth] Session reconnect failed:', result.error)
        if (!token.value) {
          return 'credentials_invalid'
        }
      } catch (e) {
        // 网络异常
        console.error('[Auth] Session reconnect network error:', e)
        return 'retry'
      }
    }

    // 没有任何凭证可用
    return 'credentials_invalid'
  }

  // 设置重连回调 — 认证成功后断开重连时自动重新认证
  function setupReconnectHandler() {
    wsClient.setOnReconnect(async () => {
      // 重连已由 WSClient 自动完成，WS 已连接，直接认证
      try {
        const result = await authenticate()
        if (result === 'credentials_invalid') {
          // 凭证已过期/无效，清除并回到登录页
          clearAuth()
          wsClient.disconnect()
        } else if (result === 'ok') {
          // 重连成功：刷新用户最新信息
          await refreshUserInfo()

          if (authState.value === 'in_room') {
            // 在房间中 → state_sync 会自动推送并处理导航和状态恢复
            // handleAuthTokenResult / handleReconnectResult 已设置 currentRoom 并导航到 Game 页
            console.log('[Auth] Reconnect: in_room, waiting for state_sync')
          } else if (authState.value === 'matchmaking') {
            // 匹配中 → 导航到大厅（大厅会显示匹配状态）
            const currentPath = router.currentRoute.value.path
            if (currentPath !== '/lobby') {
              router.replace('/lobby')
            }
          } else {
            // 普通已认证 → 如果在游戏页面说明已不在房间，回大厅
            const currentPath = router.currentRoute.value.path
            if (currentPath.startsWith('/game/')) {
              // 用户在游戏页面但服务端说不在房间中 → 回大厅
              const roomStore = useRoomStore()
              roomStore.clearRoom()
              router.replace('/lobby')
            }
          }
        }
        // 'retry': 网络临时故障，断开 WS 让重连机制再次触发
        if (result === 'retry') {
          wsClient.disconnect()
          wsClient.enableReconnect()
        }
      } catch (error) {
        console.error('[Auth] Reconnect auth failed:', error)
        // 网络异常，断开让重连机制再次触发
        wsClient.disconnect()
        wsClient.enableReconnect()
      }
    })
  }

  // 登录 — 连接 WS 并发送 auth_login 作为首条消息
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
        // 登录失败 → 断开 WS
        wsClient.disconnect()
        throw new Error(result.error || '登录失败')
      }

      handleAuthResult(result)
      wsClient.onAuthSuccess()
      setupReconnectHandler()
      return user.value!
    } finally {
      isLoading.value = false
    }
  }

  // 注册 — 连接 WS 并发送 auth_register 作为首条消息
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
        // 注册失败 → 断开 WS
        wsClient.disconnect()
        throw new Error(result.error || '注册失败')
      }

      handleAuthResult(result)
      wsClient.onAuthSuccess()
      setupReconnectHandler()
      return user.value!
    } finally {
      isLoading.value = false
    }
  }

  // 登出
  function logout() {
    wsClient.clearOnReconnect()
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

    // 如果服务端告知用户在对局中，恢复 in_room 状态
    if (data.state === 'in_room' && data.room_id) {
      authState.value = 'in_room'
      const roomStore = useRoomStore()
      if (!roomStore.currentRoom) {
        const phase = data.room_phase || 'playing'
        roomStore.setCurrentRoom({
          roomId: data.room_id,
          roomType: 'pvp',
          yourSide: 'red', // 临时值，state_sync 会覆盖
          phase: phase,
        })
        console.log('[Auth] Token auth in_room: set currentRoom, room_id=', data.room_id, 'phase=', phase)
      }

      // 断线重连提示由 state_sync 统一处理（避免与 state_sync 重复）
      // handleAuthTokenResult 仅设置 room 状态，不添加 reconnectMessages

      // 跳转到 Game 页面（无论 waiting 还是 playing，都显示棋盘+等待/对局状态）
      if (router.currentRoute.value.path !== `/game/${data.room_id}`) {
        router.replace(`/game/${data.room_id}`)
      }
    } else {
      // 断线重连：之前在房间内，现在不在了
      if (isReconnecting.value && previousAuthState.value === 'in_room') {
        reconnectMessages.value.push('你已离开房间')
        // 清理房间状态
        const roomStore = useRoomStore()
        roomStore.clearRoom()
      }
      authState.value = 'authenticated'
    }
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

      // 断线重连提示
      if (isReconnecting.value && previousAuthState.value === 'in_room') {
        // 之前在 Playing 状态断线 — 重连后服务端会推送 state_sync，此时还不知道房间 phase
        // 先标记，等 state_sync 到达后再判断
        // 但如果 reconnect_result 自身包含 room 信息，可在此处理
      }

      // 设置 roomStore 的 currentRoom，等待后续 state_sync 推送恢复 gameStore
      if (data.room_id) {
        const roomStore = useRoomStore()
        if (!roomStore.currentRoom) {
          roomStore.setCurrentRoom({
            roomId: data.room_id,
            roomType: 'pvp',
            yourSide: 'red', // 临时值，state_sync 会覆盖
            phase: 'playing',
          })
          console.log('[Auth] Reconnect in_room: set currentRoom, waiting for state_sync, room_id=', data.room_id)
        }

        // 导航到对局页面
        if (router.currentRoute.value.path !== `/game/${data.room_id}`) {
          router.replace(`/game/${data.room_id}`)
        }
      }
    } else if (data.state === 'matchmaking') {
      // 断线重连：之前在房间内，现在变成匹配中
      if (isReconnecting.value && previousAuthState.value === 'in_room') {
        reconnectMessages.value.push('你已离开房间')
        const roomStore = useRoomStore()
        roomStore.clearRoom()
      }
      authState.value = 'matchmaking'
    } else {
      // 断线重连：之前在房间内，现在不在了
      if (isReconnecting.value && previousAuthState.value === 'in_room') {
        reconnectMessages.value.push('你已离开房间')
        const roomStore = useRoomStore()
        roomStore.clearRoom()
      }
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
    // 认证相关错误 → 清除凭证，断开连接
    if (data.code === 1001 || data.code === 1002 || data.code === 1004) {
      clearAuth()
      wsClient.disconnect()
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

  // 从服务端获取最新用户信息（重连后调用，确保 rating 等数据最新）
  async function refreshUserInfo() {
    try {
      const result = await wsClient.request(WSMsgType.USER_GET_ME, {})
      if (result && result.user_id) {
        user.value = {
          user_id: result.user_id,
          username: result.username,
          nickname: result.nickname || result.username,
          avatar: result.avatar,
          rating: result.rating || 1500,
          games_count: result.games_count || 0,
          is_admin: result.is_admin || false,
        }
        localStorage.setItem('user', JSON.stringify(user.value))
        console.log('[Auth] User info refreshed after reconnect, rating=', user.value.rating)
      }
    } catch (e) {
      console.warn('[Auth] Failed to refresh user info after reconnect:', e)
    }
  }

  // 更新用户信息 (通用)
  function updateUser(profile: UserProfile) {
    user.value = profile
    localStorage.setItem('user', JSON.stringify(profile))
  }

  // 获取 WS URL
  function getWSUrl(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = `${protocol}//${window.location.host}`
    const basePath = import.meta.env.BASE_URL.replace(/\/$/, '') // 去掉末尾斜杠
    return `${host}${basePath}/ws`
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
    markReconnecting,
    consumeReconnectMessages,
    previousAuthState,
    isReconnecting,
    reconnectMessages,
    phaseBeforeDisconnect,
    updateUser,
    updateUserFromWS,
    refreshUserInfo,
    authenticate,
    hasCredentials,
    clearAuth,
    // 推送处理
    handleAuthResult,
    handleAuthTokenResult,
    handleAuthRefreshResult,
    handleReconnectResult,
    handleRatingUpdate,
    handleError,
  }
})
