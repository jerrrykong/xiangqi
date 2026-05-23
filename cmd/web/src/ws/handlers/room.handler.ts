// 房间消息处理器

import { messageRouter } from '../router'
import { WSRespType } from '../types'
import { useRoomStore } from '@/stores/room'
import { useGameStore } from '@/stores/game'

export function registerRoomHandlers(): void {
  const roomStore = useRoomStore()
  const gameStore = useGameStore()

  messageRouter.on(WSRespType.PLAYER_JOINED, (data) => roomStore.handlePlayerJoined(data))
  messageRouter.on(WSRespType.PLAYER_LEFT, (data) => roomStore.handlePlayerLeft(data))
  messageRouter.on(WSRespType.ROOM_REMOVED, () => roomStore.handleRoomRemoved())
  messageRouter.on(WSRespType.ROOM_LIST_RESULT, (data) => roomStore.handleRoomListResult(data))
  messageRouter.on(WSRespType.ROOM_UPDATE, () => roomStore.handleRoomUpdate())
  messageRouter.on(WSRespType.GAME_START, (data) => {
    roomStore.handleGameStart(data)
    gameStore.handleGameStart(data)
  })
}
