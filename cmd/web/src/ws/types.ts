// WS 类型定义 — 对齐 v2.0 game-service 协议

// ========== 基础消息结构 (对齐 protocol/message.py) ==========

export interface WSMessage {
  type: string
  seq: number
  data: Record<string, any>
  timestamp: number
}

// ========== 客户端→服务端消息类型 (对齐 protocol/inbound.py) ==========

export const WSMsgType = {
  // 认证
  AUTH_LOGIN: 'auth_login',
  AUTH_REGISTER: 'auth_register',
  AUTH_TOKEN: 'auth_token',
  AUTH_REFRESH: 'auth_refresh',
  RECONNECT: 'reconnect',
  // 用户
  USER_GET_ME: 'user_get_me',
  USER_UPDATE_PROFILE: 'user_update_profile',
  USER_GET_RANKINGS: 'user_get_rankings',
  USER_GET_HISTORY: 'user_get_history',
  // 房间
  ROOM_CREATE: 'room_create',
  ROOM_LIST: 'room_list',
  ROOM_JOIN: 'room_join',
  ROOM_LEAVE: 'room_leave',
  // 游戏
  GAME_MOVE: 'game_move',
  GAME_RESIGN: 'game_resign',
  GAME_DRAW_REQ: 'game_draw_req',
  GAME_DRAW_ANS: 'game_draw_ans',
  GAME_READY: 'game_ready',
  GAME_REMATCH: 'game_rematch',
  // 匹配
  MATCH_JOIN: 'match_join',
  MATCH_LEAVE: 'match_leave',
  // 管理
  ADMIN_USERS: 'admin_users',
  ADMIN_BAN: 'admin_ban',
  ADMIN_STATS: 'admin_stats',
  ADMIN_MODELS: 'admin_models',
  // 通用
  PING: 'ping',
} as const

// ========== 服务端→客户端消息类型 (对齐 protocol/outbound.py) ==========

export const WSRespType = {
  // 认证
  AUTH_RESULT: 'auth_result',
  AUTH_REGISTER_RESULT: 'auth_register_result',
  AUTH_TOKEN_RESULT: 'auth_token_result',
  AUTH_REFRESH_RESULT: 'auth_refresh_result',
  RECONNECT_RESULT: 'reconnect_result',
  // 用户
  USER_ME: 'user_me',
  USER_PROFILE_UPDATED: 'user_profile_updated',
  USER_RANKINGS: 'user_rankings',
  USER_HISTORY: 'user_history',
  RATING_UPDATE: 'rating_update',
  // 房间
  ROOM_CREATED: 'room_created',
  ROOM_LIST_RESULT: 'room_list_result',
  ROOM_JOINED: 'room_joined',
  ROOM_LEFT: 'room_left',
  ROOM_REMOVED: 'room_removed',
  ROOM_UPDATE: 'room_update',
  PLAYER_JOINED: 'player_joined',
  PLAYER_LEFT: 'player_left',
  // 游戏
  GAME_START: 'game_start',
  MOVE_RESULT: 'move_result',
  OPPONENT_MOVE: 'opponent_move',
  AI_THINKING: 'ai_thinking',
  AI_MOVE: 'ai_move',
  GAME_OVER: 'game_over',
  DRAW_REQUEST: 'draw_request',
  DRAW_RESULT: 'draw_result',
  READY_ACCEPTED: 'ready_accepted',
  OPPONENT_READY: 'opponent_ready',
  REMATCH_ACCEPTED: 'rematch_accepted',
  OPPONENT_REMATCH: 'opponent_rematch',
  // 匹配
  MATCH_QUEUED: 'match_queued',
  MATCH_LEFT: 'match_left',
  MATCH_FOUND: 'match_found',
  // 管理
  ADMIN_USERS_RESULT: 'admin_users_result',
  ADMIN_BAN_RESULT: 'admin_ban_result',
  ADMIN_STATS_RESULT: 'admin_stats_result',
  ADMIN_MODELS_RESULT: 'admin_models_result',
  // 状态同步
  STATE_SYNC: 'state_sync',
  // 通用
  PONG: 'pong',
  ERROR: 'error',
} as const

// ========== 各消息 data 接口 ==========

// ---- 认证响应 ----

export interface AuthResultData {
  success: boolean
  user_id?: number
  username?: string
  nickname?: string
  rating?: number
  games_count?: number
  is_admin?: boolean
  token?: string
  refresh_token?: string
  expires_at?: string
  session_token?: string
  error?: string
}

export interface AuthTokenResultData {
  success: boolean
  user_id?: number
  username?: string
  nickname?: string
  rating?: number
  games_count?: number
  is_admin?: boolean
  session_token?: string
  state?: string        // 'authenticated' | 'in_room'
  room_id?: string      // 当 state='in_room' 时的房间 ID
  room_phase?: string   // 'waiting' | 'playing'
  error?: string
}

export interface ReconnectResultData {
  success: boolean
  user_id?: number
  username?: string
  session_token?: string
  state?: string // 'authenticated' | 'in_room' | 'matchmaking'
  room_id?: string
  error?: string
}

// ---- 用户响应 ----

export interface UserMeData {
  id: number
  username: string
  nickname: string
  avatar: string
  rating: number
  games_count: number
  is_admin: boolean
}

export interface UserRankingsData {
  rankings: Array<{
    user_id: number
    username: string
    nickname: string
    rating: number
    games_count: number
  }>
  total: number
  page: number
  page_size: number
}

export interface UserHistoryData {
  games: Array<{
    game_id: string
    result: string
    my_side: string
    opponent: { user_id: number; username: string; rating: number }
    rating_change: number
    total_moves: number
    played_at: string
  }>
  total: number
  page: number
  page_size: number
}

export interface RatingUpdateData {
  rating: number
  change: number
  games_count: number
}

// ---- 房间响应 ----

export interface RoomCreatedData {
  room_id: string
  room_type: string
  difficulty: number
}

export interface RoomListResultData {
  rooms: Array<{
    room_id: string
    room_type: string
    phase: string
    red_player?: { user_id: number; username: string; rating: number }
    black_player?: { user_id: number; username: string; rating: number }
    created_at: string
  }>
}

export interface RoomJoinedData {
  room_id: string
  room_type: string
  players: Array<{
    user_id: number
    username: string
    nickname: string
    side: string
    rating: number
  }>
}

export interface PlayerJoinedData {
  user_id: number
  username: string
  nickname: string
  side: string
  rating: number
  phase?: string // 'ready' when entering ready phase
}

// ---- Ready / Rematch ----

export interface ReadyAcceptedData {
  // empty - just acknowledgment
}

export interface OpponentReadyData {
  user_id: number
}

export interface RematchAcceptedData {
  // empty - just acknowledgment
}

export interface OpponentRematchData {
  user_id: number
}

// ---- 游戏响应 ----

export interface GameStartData {
  room_id: string
  your_side: string // 'red' | 'black'
  red_player: { user_id: number; username: string; rating: number }
  black_player: { user_id: number; username: string; rating: number }
  initial_time: number
  increment: number
  fen: string
}

export interface MoveResultData {
  success: boolean
  fen: string
  move?: { from_pos: number[]; to_pos: number[] }
  message: string
}

export interface OpponentMoveData {
  from_pos: number[] // [row, col]
  to_pos: number[] // [row, col]
  fen: string
  captured?: { piece: number; pos: number[] }
}

export interface AIMoveData {
  from_pos: number[]
  to_pos: number[]
  fen: string
  captured?: { piece: number; pos: number[] }
  think_time_ms: number
}

export interface GameOverData {
  room_id: string
  winner: string // 'red' | 'black' | 'draw'
  reason: string // 'checkmate' | 'resign' | 'timeout' | 'draw' | 'disconnect'
  total_moves: number
  red_rating_change: number
  black_rating_change: number
}

export interface StateSyncData {
  room_id: string
  room_type: string
  phase: string // 'waiting' | 'ready' | 'playing' | 'finished'
  fen: string
  your_side: string
  red_player?: { user_id: number; username: string; rating: number }
  black_player?: { user_id: number; username: string; rating: number }
  red_remaining_time: number
  black_remaining_time: number
  moves: Array<{ from_pos: number[]; to_pos: number[] }>
  ready_players?: number[]
  rematch_players?: number[]
}

// ---- 匹配响应 ----

export interface MatchQueuedData {
  position: number
  estimated_wait: number
}

export interface MatchFoundData {
  room_id: string
  opponent: { user_id: number; username: string; rating: number }
  your_side: string
}

// ---- 求和 ----

export interface DrawRequestData {
  from_user_id: number
  from_username: string
}

export interface DrawResultData {
  accepted: boolean
  reason?: string
}

// ---- 错误 ----

export interface ErrorData {
  code: number
  message: string
}

// ========== 连接状态 (对齐 gateway/connection_state.py) ==========

export type WSConnectionState = 'disconnected' | 'connecting' | 'connected'
export type WSAuthState = 'unauthenticated' | 'restoring' | 'authenticated' | 'in_room' | 'matchmaking'
