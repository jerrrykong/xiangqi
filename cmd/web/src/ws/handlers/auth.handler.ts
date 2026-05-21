// 认证消息处理器

import { messageRouter } from '../router'
import { WSRespType } from '../types'
import { useAuthStore } from '@/stores/auth'

export function registerAuthHandlers(): void {
  const authStore = useAuthStore()

  messageRouter.on(WSRespType.AUTH_RESULT, (data) => authStore.handleAuthResult(data))
  messageRouter.on(WSRespType.AUTH_REGISTER_RESULT, (data) => authStore.handleAuthResult(data))
  messageRouter.on(WSRespType.AUTH_TOKEN_RESULT, (data) => authStore.handleAuthTokenResult(data))
  messageRouter.on(WSRespType.AUTH_REFRESH_RESULT, (data) => authStore.handleAuthRefreshResult(data))
  messageRouter.on(WSRespType.RECONNECT_RESULT, (data) => authStore.handleReconnectResult(data))
  messageRouter.on(WSRespType.RATING_UPDATE, (data) => authStore.handleRatingUpdate(data))
  messageRouter.on(WSRespType.ERROR, (data) => authStore.handleError(data))
}
