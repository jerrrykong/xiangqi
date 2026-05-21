import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  RoomListItem,
  CreateRoomResponse,
  JoinRoomResponse,
  ReadyResponse,
  RoomStatus,
} from '@/types/api'
import * as roomApi from '@/api/room'
import type { RoomDetail } from '@/api/room'
import { useAuthStore } from '@/stores/auth'

export const useRoomStore = defineStore('room', () => {
  // 状态
  const roomList = ref<RoomListItem[]>([])
  const totalRooms = ref(0)
  const currentRoom = ref<{
    roomId: string
    status: RoomStatus
    yourSide: 'red' | 'black'
    opponent?: {
      userId: number
      username: string
      rating?: number
    }
    redReady: boolean
    blackReady: boolean
    gameStarted: boolean
    gameWsUrl?: string
    gameToken?: string
  } | null>(null)
  const isLoading = ref(false)

  // 计算属性
  const isInRoom = computed(() => !!currentRoom.value)

  // 获取当前房间最新状态
  async function fetchCurrentRoom(): Promise<void> {
    if (!currentRoom.value) return

    try {
      const detail: RoomDetail = await roomApi.getRoom(currentRoom.value.roomId)
      const authStore = useAuthStore()
      const userId = authStore.user?.user_id

      // 根据当前用户确定 yourSide 和 opponent
      if (detail.red_user && detail.red_user.user_id === userId) {
        currentRoom.value.yourSide = 'red'
        currentRoom.value.opponent = detail.black_user
          ? {
              userId: detail.black_user.user_id,
              username: detail.black_user.username,
              rating: detail.black_user.rating,
            }
          : undefined
      } else if (detail.black_user && detail.black_user.user_id === userId) {
        currentRoom.value.yourSide = 'black'
        currentRoom.value.opponent = detail.red_user
          ? {
              userId: detail.red_user.user_id,
              username: detail.red_user.username,
              rating: detail.red_user.rating,
            }
          : undefined
      }

      // 更新房间状态
      currentRoom.value.status = detail.status
      currentRoom.value.redReady = detail.red_ready
      currentRoom.value.blackReady = detail.black_ready

      // 注意：gameStarted/gameWsUrl/gameToken 只在 playerReady() 中更新，
      // 不在 fetchCurrentRoom 中更新，避免竞态条件
    } catch (e) {
      // 如果获取失败，清空房间状态
      currentRoom.value = null
    }
  }

  // 获取房间列表
  async function fetchRoomList(page = 1, pageSize = 20) {
    isLoading.value = true
    try {
      const response = await roomApi.getRoomList(page, pageSize)
      // 确保 rooms 是数组，避免模板渲染错误
      roomList.value = response.rooms || []
      totalRooms.value = response.total || 0
    } finally {
      isLoading.value = false
    }
  }

  // 创建房间
  async function createRoom(): Promise<CreateRoomResponse> {
    isLoading.value = true
    try {
      const response = await roomApi.createRoom()
      currentRoom.value = {
        roomId: response.room_id,
        status: response.status,
        yourSide: 'red', // 创建者默认红方
        redReady: false,
        blackReady: false,
        gameStarted: false,
      }
      return response
    } finally {
      isLoading.value = false
    }
  }

  // 加入房间
  async function joinRoom(roomId: string): Promise<JoinRoomResponse> {
    isLoading.value = true
    try {
      const response = await roomApi.joinRoom(roomId)
      currentRoom.value = {
        roomId: response.room_id,
        status: response.status,
        yourSide: response.your_side,
        opponent: response.opponent
          ? {
              userId: response.opponent.user_id,
              username: response.opponent.username,
              rating: response.opponent.rating,
            }
          : undefined,
        redReady: false,
        blackReady: false,
        gameStarted: false,
      }
      return response
    } finally {
      isLoading.value = false
    }
  }

  // 恢复已在房间内的状态（刷新页面时使用，不调用 join，只读取房间信息）
  async function restoreRoom(roomId: string): Promise<void> {
    const authStore = useAuthStore()
    const roomDetail: RoomDetail = await roomApi.getRoom(roomId)

    const userId = authStore.user?.user_id
    let yourSide: 'red' | 'black' = 'red'
    let opponent: { userId: number; username: string; rating?: number } | undefined

    if (roomDetail.red_user && roomDetail.red_user.user_id === userId) {
      yourSide = 'red'
      if (roomDetail.black_user) {
        opponent = {
          userId: roomDetail.black_user.user_id,
          username: roomDetail.black_user.username,
          rating: roomDetail.black_user.rating,
        }
      }
    } else if (roomDetail.black_user && roomDetail.black_user.user_id === userId) {
      yourSide = 'black'
      if (roomDetail.red_user) {
        opponent = {
          userId: roomDetail.red_user.user_id,
          username: roomDetail.red_user.username,
          rating: roomDetail.red_user.rating,
        }
      }
    }

    currentRoom.value = {
      roomId: roomDetail.room_id,
      status: roomDetail.status,
      yourSide,
      opponent,
      redReady: roomDetail.red_ready,
      blackReady: roomDetail.black_ready,
      gameStarted: roomDetail.status === 'playing',
      gameWsUrl: roomDetail.game_ws_url,
      gameToken: roomDetail.game_token,
    }
  }

  // 准备
  async function playerReady(): Promise<ReadyResponse> {
    if (!currentRoom.value) throw new Error('Not in a room')

    const response = await roomApi.playerReady(currentRoom.value.roomId)
    currentRoom.value.redReady = response.red_ready
    currentRoom.value.blackReady = response.black_ready
    currentRoom.value.gameStarted = response.game_started
    currentRoom.value.gameWsUrl = response.game_ws_url
    currentRoom.value.gameToken = response.game_token

    return response
  }

  // 离开房间
  async function leaveRoom() {
    if (!currentRoom.value) return

    try {
      await roomApi.leaveRoom(currentRoom.value.roomId)
    } finally {
      currentRoom.value = null
    }
  }

  // 删除房间 (房主)
  async function deleteRoom() {
    if (!currentRoom.value) return

    try {
      await roomApi.deleteRoom(currentRoom.value.roomId)
    } finally {
      currentRoom.value = null
    }
  }

  // 更新房间状态
  function updateRoomStatus(data: {
    status?: RoomStatus
    opponent?: {
      userId: number
      username: string
      rating?: number
    }
    redReady?: boolean
    blackReady?: boolean
  }) {
    if (!currentRoom.value) return

    if (data.status !== undefined) currentRoom.value.status = data.status
    if (data.opponent !== undefined) currentRoom.value.opponent = data.opponent
    if (data.redReady !== undefined) currentRoom.value.redReady = data.redReady
    if (data.blackReady !== undefined) currentRoom.value.blackReady = data.blackReady
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
    fetchCurrentRoom,
    createRoom,
    joinRoom,
    restoreRoom,
    playerReady,
    leaveRoom,
    deleteRoom,
    updateRoomStatus,
    clearRoom,
  }
})
