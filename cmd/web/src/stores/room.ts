import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { PlayerJoinedData, RoomListResultData, GameStartData } from '@/ws/types'
import { wsClient } from '@/ws/client'
import { WSMsgType } from '@/ws/types'
import { useAuthStore } from './auth'
import { useGameStore } from './game'

export const useRoomStore = defineStore('room', () => {
  // 状态
  const roomList = ref<RoomListResultData['rooms']>([])
  const totalRooms = ref(0)
  const currentRoom = ref<{
    roomId: string
    roomType: string    // pvp/pve
    phase: string       // waiting/ready/playing/finished
    yourSide: 'red' | 'black'
    opponent?: {
      userId: number
      username: string
      rating?: number
    }
    difficulty?: number // PvE 难度
    status?: string
    redReady?: boolean
    blackReady?: boolean
    gameStarted?: boolean
    gameWsUrl?: string
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
      const phase = result.status === 'playing' ? 'playing' : 'waiting'
      currentRoom.value = {
        roomId: result.room_id,
        roomType: result.room_type || roomType,
        phase,
        yourSide: result.your_side || 'red', // 创建者默认红方
        difficulty,
      }
      console.log('[Room] Room created:', result.room_id, 'phase=', phase, 'side=', currentRoom.value.yourSide)
      // 同步 gameStore.phase
      const gameStore = useGameStore()
      gameStore.phase = phase
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
        const validPlayers = result.players.filter((p: any) => p != null)
        const me = validPlayers.find((p: any) => p.user_id === userId)
        const other = validPlayers.find((p: any) => p.user_id !== userId)
        if (me) yourSide = me.side === 'red' ? 'red' : 'black'
        if (other) {
          opponent = {
            userId: other.user_id,
            username: other.username,
            rating: other.rating,
          }
        }
      }

      const phase = result.phase || 'ready'
      currentRoom.value = {
        roomId: result.room_id,
        roomType: result.room_type || 'pvp',
        phase,
        yourSide,
        opponent,
      }

      // 同步 gameStore.phase（加入后进入 ready 阶段）
      const gameStore = useGameStore()
      gameStore.phase = phase

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
    const phase = room.phase || 'waiting'
    currentRoom.value = {
      roomId: room.roomId,
      roomType: room.roomType || 'pvp',
      phase,
      yourSide: room.yourSide,
      opponent: room.opponent,
      status: phase,
      gameStarted: phase === 'playing',
      redReady: false,
      blackReady: false,
    }
    // 同步 gameStore.phase
    const gameStore = useGameStore()
    gameStore.phase = phase
  }

  function updateRoomDetail(detail: {
    room_id: string
    status: string
    type: string
    red_ready?: boolean
    black_ready?: boolean
    game_ws_url?: string
    your_side?: string
    red_user?: { user_id: number; username: string; rating?: number }
    black_user?: { user_id: number; username: string; rating?: number }
  }) {
    const phase = detail.status || 'waiting'
    const myUserId = useAuthStore().user?.user_id
    const opponent = detail.red_user && detail.red_user.user_id !== myUserId
      ? { userId: detail.red_user.user_id, username: detail.red_user.username, rating: detail.red_user.rating }
      : detail.black_user && detail.black_user.user_id !== myUserId
        ? { userId: detail.black_user.user_id, username: detail.black_user.username, rating: detail.black_user.rating }
        : undefined

    currentRoom.value = {
      roomId: detail.room_id,
      roomType: detail.type || 'pvp',
      phase,
      yourSide: detail.your_side === 'black' ? 'black' : 'red',
      opponent,
      status: detail.status,
      redReady: detail.red_ready,
      blackReady: detail.black_ready,
      gameStarted: detail.status === 'playing',
      gameWsUrl: detail.game_ws_url,
    }
    const gameStore = useGameStore()
    gameStore.phase = phase
  }

  async function restoreRoom(roomId: string) {
    const token = localStorage.getItem('token')
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers.Authorization = `Bearer ${token}`
    const response = await fetch('/rooms/me', { method: 'GET', headers })
    if (!response.ok) {
      throw response
    }
    const data = await response.json()
    if (data.room_id !== roomId) {
      throw new Error('room mismatch')
    }
    updateRoomDetail(data)
    return data
  }

  async function fetchCurrentRoom(roomId: string) {
    const token = localStorage.getItem('token')
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers.Authorization = `Bearer ${token}`
    const response = await fetch(`/rooms/${roomId}`, { method: 'GET', headers })
    if (!response.ok) {
      throw response
    }
    const data = await response.json()
    updateRoomDetail(data)
    return data
  }

  async function playerReady() {
    const result = await wsClient.request(WSMsgType.GAME_READY, {})
    return result
  }

  async function deleteRoom() {
    if (!currentRoom.value) {
      throw new Error('No room to delete')
    }
    const token = localStorage.getItem('token')
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers.Authorization = `Bearer ${token}`
    const response = await fetch(`/rooms/${currentRoom.value.roomId}`, { method: 'DELETE', headers })
    if (!response.ok) {
      throw response
    }
    currentRoom.value = null
    const authStore = useAuthStore()
    if (authStore.authState === 'in_room') {
      authStore.setAuthState('authenticated')
    }
    return response.json()
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
    // 对手加入后进入 ready 阶段
    if (data.phase === 'ready') {
      currentRoom.value.phase = 'ready'
      currentRoom.value.status = 'ready'
      // 同步更新 gameStore.phase，因为 Game.vue 使用 gameStore.phase 判断阶段
      const gameStore = useGameStore()
      gameStore.phase = 'ready'
    }
  }

  // 处理对手离开
  function handlePlayerLeft(_data: any) {
    if (!currentRoom.value) return
    currentRoom.value.opponent = undefined
    if (_data?.phase === 'waiting') {
      currentRoom.value.phase = 'waiting'
      currentRoom.value.status = 'waiting'
    }
  }

  // 处理游戏开始
  function handleGameStart(data: GameStartData) {
    if (!currentRoom.value) return
    console.log('[Room] Game started, room=', currentRoom.value.roomId)
    currentRoom.value.phase = 'playing'
    currentRoom.value.status = 'playing'
    currentRoom.value.gameStarted = true
    const authStore = useAuthStore()
    authStore.setAuthState('in_room')

    // 从 game_start 数据恢复对手信息
    const myUserId = authStore.user?.user_id
    if (data.red_player && data.red_player.user_id !== myUserId) {
      currentRoom.value.opponent = {
        userId: data.red_player.user_id,
        username: data.red_player.username,
        rating: data.red_player.rating,
      }
    } else if (data.black_player && data.black_player.user_id !== myUserId) {
      currentRoom.value.opponent = {
        userId: data.black_player.user_id,
        username: data.black_player.username,
        rating: data.black_player.rating,
      }
    }
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
    restoreRoom,
    fetchCurrentRoom,
    playerReady,
    deleteRoom,
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
