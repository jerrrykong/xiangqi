// WebSocket 消息类型定义

import type { Move } from './chess'

// 消息类型常量
export const MsgType = {
  // Client -> Server
  Move: 'move',
  Resign: 'resign',
  DrawReq: 'draw_req',
  DrawAns: 'draw_ans',
  Ping: 'ping',
  Reconnect: 'reconnect',

  // Server -> Client
  StateSync: 'state_sync',
  OpponentMove: 'opponent_move',
  GameStart: 'game_start',
  GameOver: 'game_over',
  Check: 'check',
  DrawNotify: 'draw_notify',
  Error: 'error',
  Pong: 'pong',
} as const

export type MsgTypeValue = typeof MsgType[keyof typeof MsgType]

// ============ Client -> Server 消息 ============

// 走棋消息
export interface MoveMessage {
  type: typeof MsgType.Move
  move: Move
}

// 认输消息
export interface ResignMessage {
  type: typeof MsgType.Resign
}

// 请求和棋
export interface DrawReqMessage {
  type: typeof MsgType.DrawReq
}

// 和棋应答
export interface DrawAnsMessage {
  type: typeof MsgType.DrawAns
  accept: boolean
}

// 心跳
export interface PingMessage {
  type: typeof MsgType.Ping
  time: number
}

// 重连
export interface ReconnectMessage {
  type: typeof MsgType.Reconnect
  token: string
}

// Client 发送的消息联合类型
export type ClientMessage =
  | MoveMessage
  | ResignMessage
  | DrawReqMessage
  | DrawAnsMessage
  | PingMessage
  | ReconnectMessage

// ============ Server -> Client 消息 ============

// 状态同步
export interface StateSyncMessage {
  type: typeof MsgType.StateSync
  board: number[][] // 10x9 棋盘数组
  turn: number // 0=红, 1=黑
  red_time: number // 红方剩余时间(秒)
  black_time: number // 黑方剩余时间(秒)
  room_id: string
  your_color: number // 你的颜色
}

// 对手走棋
export interface OpponentMoveMessage {
  type: typeof MsgType.OpponentMove
  move: Move
  red_time: number
  black_time: number
}

// 游戏开始
export interface GameStartMessage {
  type: typeof MsgType.GameStart
  room_id: string
  your_color: number
  red_time: number
  black_time: number
}

// 游戏结束
export interface GameOverMessage {
  type: typeof MsgType.GameOver
  result: string // RED_WINS, BLACK_WINS, DRAW 等
  reason: string
  winner: number // -1=无, 0=红, 1=黑
}

// 将军提醒
export interface CheckMessage {
  type: typeof MsgType.Check
  by_piece: number
  from_row: number
  from_col: number
  to_row: number
  to_col: number
}

// 和棋通知
export interface DrawNotifyMessage {
  type: typeof MsgType.DrawNotify
  from: string
  token?: string
}

// 错误消息
export interface ErrorMessage {
  type: typeof MsgType.Error
  code: number
  message: string
}

// 心跳响应
export interface PongMessage {
  type: typeof MsgType.Pong
  time: number
}

// Server 发送的消息联合类型
export type ServerMessage =
  | StateSyncMessage
  | OpponentMoveMessage
  | GameStartMessage
  | GameOverMessage
  | CheckMessage
  | DrawNotifyMessage
  | ErrorMessage
  | PongMessage

// 错误码 (与后端 shared/errors.go 保持一致)
export const ErrorCode = {
  // 4xxx: 游戏错误
  Game: 4000,
  InvalidMove: 4001,
  MoveNotYourTurn: 4002,
  GameNotStarted: 4003,
  GameAlreadyOver: 4004,
  Check: 4005,
  ReconnectFailed: 4006,
  NotYourTurn: 4007,
  AlreadyReady: 4008,
  NotReady: 4009,
} as const

export type ErrorCodeType = typeof ErrorCode[keyof typeof ErrorCode]
