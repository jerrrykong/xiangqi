import { ref, shallowRef } from 'vue'
import type {
  ServerMessage,
  ClientMessage,
  StateSyncMessage,
  GameStartMessage,
  OpponentMoveMessage,
  GameOverMessage,
  CheckMessage,
  DrawNotifyMessage,
  ErrorMessage,
} from '@/types/websocket'
import { MsgType } from '@/types/websocket'

// WebSocket 管理器
class WebSocketManager {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private heartbeatInterval: number | null = null
  private url = ''
  private token = ''
  private useRawUrl = false  // true 当使用 connectRaw 时，重连不追加 token

  // 标记是否应该重连（某些错误码不应该重连）
  private shouldReconnect = true

  // 状态
  public isConnected = ref(false)
  public connectionState = shallowRef<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected')

  // 回调函数
  private onGameStart?: (data: GameStartMessage) => void
  private onStateSync?: (data: StateSyncMessage) => void
  private onOpponentMove?: (data: OpponentMoveMessage) => void
  private onGameOver?: (data: GameOverMessage) => void
  private onCheck?: (data: CheckMessage) => void
  private onDrawNotify?: (data: DrawNotifyMessage) => void
  private onError?: (data: ErrorMessage) => void
  private onDisconnect?: () => void

  // 设置回调
  public setCallbacks(callbacks: {
    onGameStart?: (data: GameStartMessage) => void
    onStateSync?: (data: StateSyncMessage) => void
    onOpponentMove?: (data: OpponentMoveMessage) => void
    onGameOver?: (data: GameOverMessage) => void
    onCheck?: (data: CheckMessage) => void
    onDrawNotify?: (data: DrawNotifyMessage) => void
    onError?: (data: ErrorMessage) => void
    onDisconnect?: () => void
  }) {
    this.onGameStart = callbacks.onGameStart
    this.onStateSync = callbacks.onStateSync
    this.onOpponentMove = callbacks.onOpponentMove
    this.onGameOver = callbacks.onGameOver
    this.onCheck = callbacks.onCheck
    this.onDrawNotify = callbacks.onDrawNotify
    this.onError = callbacks.onError
    this.onDisconnect = callbacks.onDisconnect
  }

  // 连接（自动拼接 token 参数）
  public connect(url: string, token: string) {
    this.url = url
    this.token = token
    this.useRawUrl = false
    this.shouldReconnect = true  // 重置重连状态
    this.reconnectAttempts = 0
    this.createConnection()
  }

  // 连接（使用完整 URL，不再拼接 token）
  public connectRaw(fullUrl: string, token: string) {
    this.url = fullUrl
    this.token = token
    this.useRawUrl = true
    this.shouldReconnect = true  // 重置重连状态
    this.reconnectAttempts = 0
    this._createWs(fullUrl)
  }

  private createConnection() {
    if (this.ws) {
      this.ws.close()
    }

    this.connectionState.value = 'connecting'

    try {
      const wsUrl = this.useRawUrl
        ? this.url
        : `${this.url}?token=${encodeURIComponent(this.token)}`
      this._createWs(wsUrl)
    } catch (e) {
      console.error('Failed to create WebSocket:', e)
      this.connectionState.value = 'error'
    }
  }

  private _createWs(wsUrl: string) {
    try {
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        this.isConnected.value = true
        this.connectionState.value = 'connected'
        this.reconnectAttempts = 0
        this.startHeartbeat()
      }

      this.ws.onmessage = (event) => {
        try {
          const message: ServerMessage = JSON.parse(event.data)
          this.handleMessage(message)
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e)
        }
      }

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        this.connectionState.value = 'error'
      }

      this.ws.onclose = () => {
        this.isConnected.value = false
        this.connectionState.value = 'disconnected'
        this.stopHeartbeat()
        this.onDisconnect?.()
        this.attemptReconnect()
      }
    } catch (e) {
      console.error('Failed to create WebSocket:', e)
      this.connectionState.value = 'error'
    }
  }

  private handleMessage(message: ServerMessage) {
    // Debug log all incoming messages
    console.debug('[WS] Incoming message:', JSON.stringify(message))

    switch (message.type) {
      case MsgType.GameStart:
        this.onGameStart?.(message as GameStartMessage)
        break
      case MsgType.StateSync:
        this.onStateSync?.(message as StateSyncMessage)
        break
      case MsgType.OpponentMove:
        this.onOpponentMove?.(message as OpponentMoveMessage)
        break
      case MsgType.GameOver:
        this.onGameOver?.(message as GameOverMessage)
        break
      case MsgType.Check:
        this.onCheck?.(message as CheckMessage)
        break
      case MsgType.DrawNotify:
        this.onDrawNotify?.(message as DrawNotifyMessage)
        break
      case MsgType.Error:
        // Defensive: ensure message has required fields
        const errorMsg = message as ErrorMessage
        if (errorMsg.code === undefined || errorMsg.message === undefined) {
          console.error('[WS] Received malformed error message:', errorMsg)
          return
        }
        this.onError?.(errorMsg)

        // 某些错误码不应该触发重连
        // 3001: Room is full (房间已满，不应该重连)
        // 3002: Room not found (房间不存在，不应该重连)
        // 4003: Room/game related errors (不应该重连)
        const nonRetryableCodes = [3001, 3002, 4003]
        if (nonRetryableCodes.includes(errorMsg.code)) {
          console.log(`[WS] Non-retryable error code ${errorMsg.code}, stopping reconnect`)
          this.shouldReconnect = false
          // 主动断开连接，防止 onclose 触发重连
          this.disconnect()
        }
        break
    }
  }

  private startHeartbeat() {
    this.stopHeartbeat()
    this.heartbeatInterval = window.setInterval(() => {
      this.send({
        type: MsgType.Ping,
        time: Date.now(),
      })
    }, 30000) // 每 30 秒发送一次心跳
  }

  private stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval)
      this.heartbeatInterval = null
    }
  }

  private attemptReconnect() {
    if (!this.shouldReconnect) {
      console.log('[WS] Reconnect disabled, skipping')
      return
    }
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('[WS] Max reconnect attempts reached')
      return
    }

    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)

    console.log(`[WS] Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`)

    setTimeout(() => {
      if (!this.isConnected.value) {
        this.createConnection()
      }
    }, delay)
  }

  // 发送消息
  public send(message: ClientMessage) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    }
  }

  // 断开连接
  public disconnect() {
    this.stopHeartbeat()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.isConnected.value = false
    this.connectionState.value = 'disconnected'
  }

  // 重置重连状态（用于外部主动触发重连）
  public resetReconnectState() {
    this.shouldReconnect = true
    this.reconnectAttempts = 0
  }
}

// 创建单例
export const wsManager = new WebSocketManager()

export default wsManager
