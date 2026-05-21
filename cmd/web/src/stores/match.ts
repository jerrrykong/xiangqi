import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { MatchQueuedData, MatchFoundData } from '@/ws/types'
import { wsClient } from '@/ws/client'
import { WSMsgType } from '@/ws/types'
import { useAuthStore } from './auth'
import { useRoomStore } from './room'

export const useMatchStore = defineStore('match', () => {
  const isMatchmaking = ref(false)
  const matchPosition = ref(0)
  const estimatedWait = ref(30)

  // 加入匹配
  async function joinMatch(gameType: string = 'pvp') {
    const result = await wsClient.request(WSMsgType.MATCH_JOIN, { game_type: gameType })
    isMatchmaking.value = true
    matchPosition.value = result.position || 0
    estimatedWait.value = result.estimated_wait || 30
    const authStore = useAuthStore()
    authStore.setAuthState('matchmaking')
    return result
  }

  // 离开匹配
  async function leaveMatch() {
    await wsClient.request(WSMsgType.MATCH_LEAVE)
    isMatchmaking.value = false
    const authStore = useAuthStore()
    authStore.setAuthState('authenticated')
  }

  // 处理排队中
  function handleMatchQueued(data: MatchQueuedData) {
    matchPosition.value = data.position
    estimatedWait.value = data.estimated_wait
  }

  // 处理匹配成功
  function handleMatchFound(data: MatchFoundData) {
    isMatchmaking.value = false
    const authStore = useAuthStore()
    authStore.setAuthState('in_room')

    // 设置当前房间
    const roomStore = useRoomStore()
    roomStore.setCurrentRoom({
      roomId: data.room_id,
      yourSide: data.your_side as 'red' | 'black',
      opponent: {
        userId: data.opponent.user_id,
        username: data.opponent.username,
        rating: data.opponent.rating,
      },
      phase: 'playing',
    })
    // 等待 game_start 推送
  }

  // 处理离开匹配
  function handleMatchLeft() {
    isMatchmaking.value = false
    const authStore = useAuthStore()
    if (authStore.authState === 'matchmaking') {
      authStore.setAuthState('authenticated')
    }
  }

  return {
    isMatchmaking,
    matchPosition,
    estimatedWait,
    joinMatch,
    leaveMatch,
    handleMatchQueued,
    handleMatchFound,
    handleMatchLeft,
  }
})
