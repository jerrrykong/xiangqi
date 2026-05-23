import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { PlayerJoinedData, RoomListResultData, GameStartData } from '@/ws/types'
import { wsClient } from '@/ws/client'
import { WSMsgType } from '@/ws/types'
import { useAuthStore } from './auth'

export const useRoomStore = defineStore('room', () => {
  // 状态
  const roomList = ref<RoomListResultData['rooms']>([])
  const totalRooms = ref(0)
  const currentRoom = ref<{
    roomId: string
    roomType: string    // pvp/pve
    phase: string       // waiting/playing/finished
    yourSide: 'red' | 'black'
    opponent?: {
      userId: number
      username: string
      rating?: number
    }
    difficulty?: number // PvE 难度
  } | null>(null)
  const isLoading = ref(false)

  // 计算属性
  const isInRoom = computed(() => !!currentRoom.value)

  // 获取房间列表
  async function fetchRoomList(page = 1, pageSize = 20) {
    isLoading.value = true
    try {
      const result = await wsClient.request(WSMsgType.ROOM_LIST, { page, page_size: pageSize })
      roomList.value = result.rooms || []
      totalRooms.value = result.total || 0
      console.log('[Room] Fetched room list:', roomList.value.length, 'rooms')
    } finally {
      isLoading.value = false
    }
  }

  // 创建房间
  async function createRoom(roomType: string = 'pvp', difficulty: number = 3) {
    isLoading.value = true
    try {
      console.log('[Room] Creating room, type=', roomType, 'difficulty=', difficulty)
      const result = await wsClient.request(WSMsgType.ROOM_CREATE, { room_type: roomType, difficulty })
      currentRoom.value = {
        roomId: result.room_id,
        roomType: result.room_type || roomType,
        phase: result.status === 'playing' ? 'playing' : 'waiting',
        yourSide: result.your_side || 'red', // 创建者默认红方
        difficulty,
      }
      console.log('[Room] Room created:', result.room_id, 'phase=', currentRoom.value.phase, 'side=', currentRoom.value.yourSide)
      // 更新认证状态
      const authStore = useAuthStore()
      authStore.setAuthState('in_room')
      return result
    } finally {
      isLoading.value = false
    }
  }

  // 加入房间
  async function joinRoom(roomId: string) {
    isLoading.value = true
    try {
      console.log('[Room] Joining room:', roomId)
      const result = await wsClient.request(WSMsgType.ROOM_JOIN, { room_id: roomId })
      console.log('[Room] Join result:', result)
      const authStore = useAuthStore()
      const userId = authStore.user?.user_id

      let yourSide: 'red' | 'black' = 'black'
      let opponent: { userId: number; username: string; rating?: number } | undefined

      if (result.players) {
        const me = result.players.find((p: any) => p.user_id === userId)
        const other = result.players.find((p: any) => p.user_id !== userId)
        if (me) yourSide = me.side === 'red' ? 'red' : 'black'
        if (other) {
          opponent = {
            userId: other.user_id,
            username: other.username,
            rating: other.rating,
          }
        }
      }

      currentRoom.value = {
        roomId: result.room_id,
        roomType: result.room_type || 'pvp',
        phase: 'playing', // PvP 手动房间加入即开始
        yourSide,
        opponent,
      }

      // 更新认证状态
      authStore.setAuthState('in_room')

      return result
    } finally {
      isLoading.value = false
    }
  }

  // 离开房间
  async function leaveRoom() {
    if (!currentRoom.value) return

    console.log('[Room] Leaving room:', currentRoom.value.roomId)
    try {
      await wsClient.request(WSMsgType.ROOM_LEAVE, { room_id: currentRoom.value.roomId })
    } finally {
      currentRoom.value = null
      const authStore = useAuthStore()
      authStore.setAuthState('authenticated')
    }
  }

  // 设置当前房间 (从匹配等外部设置)
  function setCurrentRoom(room: {
    roomId: string
    roomType?: string
    yourSide: 'red' | 'black'
    opponent?: { userId: number; username: string; rating?: number }
    phase?: string
  }) {
    currentRoom.value = {
      roomId: room.roomId,
      roomType: room.roomType || 'pvp',
      phase: room.phase || 'waiting',
      yourSide: room.yourSide,
      opponent: room.opponent,
    }
  }

  // ===== 推送消息处理 =====

  // 处理对手加入
  function handlePlayerJoined(data: PlayerJoinedData) {
    if (!currentRoom.value) return
    console.log('[Room] Player joined:', data.username, '(id=', data.user_id, ')')
    currentRoom.value.opponent = {
      userId: data.user_id,
      username: data.username,
      rating: data.rating,
    }
  }

  // 处理对手离开
  function handlePlayerLeft(_data: any) {
    if (!currentRoom.value) return
    currentRoom.value.opponent = undefined
    currentRoom.value.phase = 'waiting'
  }

  // 处理游戏开始
  function handleGameStart(_data: GameStartData) {
    if (!currentRoom.value) return
    console.log('[Room] Game started, room=', currentRoom.value.roomId)
    currentRoom.value.phase = 'playing'
    const authStore = useAuthStore()
    authStore.setAuthState('in_room')
  }

  // 处理房间列表结果 (推送)
  function handleRoomListResult(data: RoomListResultData) {
    roomList.value = data.rooms || []
  }

  // 处理房间解散
  function handleRoomRemoved() {
    currentRoom.value = null
    const authStore = useAuthStore()
    if (authStore.authState === 'in_room') {
      authStore.setAuthState('authenticated')
    }
  }

  // 处理房间变更通知 (服务端推送，自动刷新列表)
  function handleRoomUpdate() {
    // 仅在房间列表页时自动刷新
    if (!currentRoom.value) {
      console.log('[Room] Received room_update, refreshing list')
      fetchRoomList()
    }
  }

  // 清空状态
  function clearRoom() {
    currentRoom.value = null
    roomList.value = []
    totalRooms.value = 0
  }

  return {
    // 状态
    roomList,
    totalRooms,
    currentRoom,
    isLoading,
    // 计算属性
    isInRoom,
    // 方法
    fetchRoomList,
    createRoom,
    joinRoom,
    leaveRoom,
    setCurrentRoom,
    clearRoom,
    // 推送处理
    handlePlayerJoined,
    handlePlayerLeft,
    handleGameStart,
    handleRoomListResult,
    handleRoomRemoved,
    handleRoomUpdate,
  }
})
