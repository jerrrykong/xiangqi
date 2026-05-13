// API 响应类型定义

// 统一响应格式
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data?: T
}

export interface ApiError {
  code: number
  message: string
  detail?: string
}

// 用户相关
export interface UserProfile {
  user_id: number
  username: string
  nickname: string
  avatar?: string
  rating: number
  games_count: number
  created_at?: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  password: string
  nickname?: string
}

export interface LoginResponse extends UserProfile {
  token: string
  expires_at: string
}

export interface RankingItem {
  rank: number
  user_id: number
  username: string
  nickname?: string
  rating: number
  games_count: number
}

export interface RankingsResponse {
  total: number
  page: number
  page_size: number
  rankings: RankingItem[]
}

// 房间相关
export interface RoomListItem {
  room_id: string
  created_by: number
  username: string
  created_at: string
}

export interface RoomListResponse {
  total: number
  rooms: RoomListItem[]
}

export interface CreateRoomResponse {
  room_id: string
  room_type: RoomType
  status: RoomStatus
  created_at: string
}

export interface OpponentInfo {
  user_id: number
  username: string
  rating?: number
}

export interface JoinRoomResponse {
  room_id: string
  your_side: 'red' | 'black'
  opponent?: OpponentInfo
  status: RoomStatus
}

export interface ReadyResponse {
  room_id: string
  red_ready: boolean
  black_ready: boolean
  game_started: boolean
  game_ws_url?: string
  game_token?: string
}

export type RoomType = 'pvp' | 'pve'
export type RoomStatus = 'waiting' | 'ready' | 'playing' | 'finished'

// 对局历史
export interface HistoryItem {
  game_id: string
  result: 'win' | 'loss' | 'draw'
  my_side: 'red' | 'black'
  opponent?: OpponentInfo
  rating_change: number
  total_moves: number
  played_at: string
}

export interface HistoryResponse {
  total: number
  history: HistoryItem[]
}

// 匹配相关
export interface MatchQueueResponse {
  queue_id: string
  status: 'queued' | 'matched' | 'expired'
  room_id?: string
}

// AI 难度
export type Difficulty = 1 | 2 | 3 | 4 | 5

export const DifficultyLabels: Record<Difficulty, string> = {
  1: '简单',
  2: '中等',
  3: '困难',
  4: '大师',
  5: '宗师',
}
