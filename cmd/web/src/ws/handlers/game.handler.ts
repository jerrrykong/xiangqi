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
    // 不再自动退出 in_room 状态 - 房间持续存在用于 rematch
  })
  messageRouter.on(WSRespType.DRAW_REQUEST, (data) => gameStore.handleDrawRequest(data))
  messageRouter.on(WSRespType.DRAW_RESULT, (data) => gameStore.handleDrawResult(data))
  messageRouter.on(WSRespType.STATE_SYNC, (data) => gameStore.handleStateSync(data))
  messageRouter.on(WSRespType.READY_ACCEPTED, () => {
    // Server confirmed our ready - nothing extra to do
  })
  messageRouter.on(WSRespType.REMATCH_ACCEPTED, () => {
    // Server confirmed our rematch request - nothing extra to do
  })
}
