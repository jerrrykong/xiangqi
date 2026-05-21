// 匹配消息处理器

import { messageRouter } from '../router'
import { WSRespType } from '../types'
import { useMatchStore } from '@/stores/match'

export function registerMatchHandlers(): void {
  const matchStore = useMatchStore()

  messageRouter.on(WSRespType.MATCH_QUEUED, (data) => matchStore.handleMatchQueued(data))
  messageRouter.on(WSRespType.MATCH_FOUND, (data) => matchStore.handleMatchFound(data))
  messageRouter.on(WSRespType.MATCH_LEFT, () => matchStore.handleMatchLeft())
}
