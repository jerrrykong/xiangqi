// 游戏消息处理器

import { messageRouter } from '../router'
import { WSRespType } from '../types'
import { useGameStore } from '@/stores/game'
import { useAuthStore } from '@/stores/auth'

export function registerGameHandlers(): void {
  const gameStore = useGameStore()
  const authStore = useAuthStore()

  messageRouter.on(WSRespType.MOVE_RESULT, (data) => gameStore.handleMoveResult(data))
  messageRouter.on(WSRespType.OPPONENT_MOVE, (data) => gameStore.handleOpponentMove(data))
  messageRouter.on(WSRespType.AI_THINKING, () => gameStore.handleAIThinking())
  messageRouter.on(WSRespType.AI_MOVE, (data) => gameStore.handleAIMove(data))
  messageRouter.on(WSRespType.GAME_OVER, (data) => {
    gameStore.handleGameOver(data)
    authStateOnGameOver(authStore)
  })
  messageRouter.on(WSRespType.DRAW_REQUEST, (data) => gameStore.handleDrawRequest(data))
  messageRouter.on(WSRespType.DRAW_RESULT, (data) => gameStore.handleDrawResult(data))
  messageRouter.on(WSRespType.STATE_SYNC, (data) => gameStore.handleStateSync(data))
}

function authStateOnGameOver(authStore: ReturnType<typeof useAuthStore>) {
  // 游戏结束后回到 authenticated 状态
  if (authStore.authState === 'in_room') {
    authStore.setAuthState('authenticated')
  }
}
