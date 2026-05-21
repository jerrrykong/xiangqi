// 用户消息处理器

import { messageRouter } from '../router'
import { WSRespType } from '../types'
import { useAuthStore } from '@/stores/auth'

export function registerUserHandlers(): void {
  const authStore = useAuthStore()

  messageRouter.on(WSRespType.USER_ME, (data) => authStore.updateUserFromWS(data))
  messageRouter.on(WSRespType.USER_PROFILE_UPDATED, (data) => authStore.updateUserFromWS(data))
}
