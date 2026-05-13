import api from './request'
import type { ApiResponse, MatchQueueResponse } from '@/types/api'
import type { Difficulty } from '@/types/api'

// 加入匹配队列 (PvP)
export async function joinMatchQueue(): Promise<MatchQueueResponse> {
  const response = await api.post<ApiResponse<MatchQueueResponse>>('/match/queue')
  return response.data.data!
}

// 离开匹配队列
export async function leaveMatchQueue(): Promise<void> {
  await api.delete('/match/queue')
}

// 查询匹配状态
export async function getMatchStatus(): Promise<MatchQueueResponse> {
  const response = await api.get<ApiResponse<MatchQueueResponse>>('/match/status')
  return response.data.data!
}

// 加入 PvE 匹配
export async function joinPveQueue(difficulty: Difficulty): Promise<{
  queue_id: string
  status: 'queued' | 'matched'
  room_id?: string
}> {
  const response = await api.post<ApiResponse<{
    queue_id: string
    status: 'queued' | 'matched'
    room_id?: string
  }>>('/match/pve', { difficulty })
  return response.data.data!
}
