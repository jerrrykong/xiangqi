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

  // 获取房间列表
  async function fetchRoomList(page = 1, pageSize = 20) {
    isLoading.value = true
    try {
      const response = await roomApi.getRoomList(page, pageSize)
      roomList.value = response.rooms
      totalRooms.value = response.total
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
    createRoom,
    joinRoom,
    playerReady,
    leaveRoom,
    deleteRoom,
    updateRoomStatus,
    clearRoom,
  }
})
