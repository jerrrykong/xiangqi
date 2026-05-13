import api from './request'
import type {
  ApiResponse,
  UserProfile,
  RankingsResponse,
  HistoryResponse,
} from '@/types/api'

// 获取当前用户信息
export async function getCurrentUser(): Promise<UserProfile> {
  const response = await api.get<ApiResponse<UserProfile>>('/users/me')
  return response.data.data!
}

// 更新用户资料
export async function updateProfile(data: {
  nickname?: string
  avatar?: string
}): Promise<UserProfile> {
  const response = await api.put<ApiResponse<UserProfile>>('/users/me', data)
  return response.data.data!
}

// 获取排行榜
export async function getRankings(page = 1, pageSize = 20): Promise<RankingsResponse> {
  const response = await api.get<ApiResponse<RankingsResponse>>('/users/rankings', {
    params: { page, page_size: pageSize },
  })
  return response.data.data!
}

// 获取用户对局历史
export async function getHistory(
  page = 1,
  pageSize = 20,
  type?: string
): Promise<HistoryResponse> {
  const response = await api.get<ApiResponse<HistoryResponse>>('/users/history', {
    params: { page, page_size: pageSize, type },
  })
  return response.data.data!
}

// 查看其他用户信息
export async function getUser(userId: number): Promise<UserProfile> {
  const response = await api.get<ApiResponse<UserProfile>>(`/users/${userId}`)
  return response.data.data!
}
