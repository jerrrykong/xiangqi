import api from './request'
import type {
  ApiResponse,
  RoomListResponse,
  CreateRoomResponse,
  JoinRoomResponse,
  ReadyResponse,
  RoomStatus,
} from '@/types/api'

// 创建房间
export async function createRoom(): Promise<CreateRoomResponse> {
  const response = await api.post<ApiResponse<CreateRoomResponse>>('/rooms')
  return response.data.data!
}

// 获取房间列表
export async function getRoomList(
  page = 1,
  pageSize = 20
): Promise<RoomListResponse> {
  const response = await api.get<ApiResponse<RoomListResponse>>('/rooms', {
    params: { page, page_size: pageSize },
  })
  return response.data.data!
}

// 获取房间详情
export async function getRoom(roomId: string): Promise<{
  room_id: string
  status: RoomStatus
  red_user?: { user_id: number; username: string; rating?: number }
  black_user?: { user_id: number; username: string; rating?: number }
  red_ready: boolean
  black_ready: boolean
}> {
  const response = await api.get<ApiResponse<unknown>>(`/rooms/${roomId}`)
  return response.data.data as any
}

// 加入房间
export async function joinRoom(roomId: string): Promise<JoinRoomResponse> {
  const response = await api.post<ApiResponse<JoinRoomResponse>>(`/rooms/${roomId}/join`)
  return response.data.data!
}

// 准备
export async function playerReady(roomId: string): Promise<ReadyResponse> {
  const response = await api.post<ApiResponse<ReadyResponse>>(`/rooms/${roomId}/ready`)
  return response.data.data!
}

// 离开房间
export async function leaveRoom(roomId: string): Promise<void> {
  await api.post(`/rooms/${roomId}/leave`)
}

// 删除房间 (房主)
export async function deleteRoom(roomId: string): Promise<void> {
  await api.delete(`/rooms/${roomId}`)
}
