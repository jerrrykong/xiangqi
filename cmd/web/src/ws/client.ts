// WS Client 核心模块 — 全局唯一 WebSocket 客户端，管理连接生命周期

import { ref } from 'vue'
import type { WSMessage, WSConnectionState, WSAuthState } from './types'
import { WSMsgType, WSRespType } from './types'
import { wsRequestManager } from './request'
import { messageRouter } from './router'

class WSClient {
  // === 连接管理 ===
  private ws: WebSocket | null = null
  private url: string = ''

  // === 状态 ===
  public connectionState = ref<WSConnectionState>('disconnected')
  public authState = ref<WSAuthState>('unauthenticated')

  // === 重连 ===
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private baseReconnectDelay = 2000
  private shouldReconnect = false  // 默认不自动重连，仅认证成功后才开启

  // === 心跳 ===
  private heartbeatInterval: number | null = null
  private heartbeatTimeout = 30000 // 30s

  // === 连接就绪 Promise ===
  private connectResolve: (() => void) | null = null

  // === 连接 ===
  connect(url: string): Promise<void> {
    this.url = url
    // 连接时不开启自动重连，认证成功后才开启

    return new Promise((resolve, reject) => {
      const originalResolve = resolve
      this.connectResolve = () => {
        clearTimeout(timeout)
        originalResolve()
      }

      this.createConnection()

      // 连接超时
      const timeout = setTimeout(() => {
        this.connectResolve = null
        reject(new Error('Connection timeout'))
      }, 10000)
    })
  }

  private createConnection(): void {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }

    this.connectionState.value = 'connecting'

    try {
      this.ws = new WebSocket(this.url)

      this.ws.onopen = () => {
        console.log('[WS] Connected to', this.url)
        this.connectionState.value = 'connected'
        this.reconnectAttempts = 0
        // 注意: 心跳在认证成功后启动

        if (this.connectResolve) {
          // 主动连接 → resolve promise
          this.connectResolve()
          this.connectResolve = null
        } else if (this.shouldReconnect) {
          // 自动重连 → 通知上层重新认证
          this.onReconnectCallback?.()
        }
      }

      this.ws.onmessage = (event) => {
        try {
          const message: WSMessage = JSON.parse(event.data)
          this.handleMessage(message)
        } catch (e) {
          console.error('[WS] Failed to parse message:', e, event.data)
        }
      }

      this.ws.onerror = (error) => {
        console.error('[WS] Connection error, readyState=', this.ws?.readyState)
      }

      this.ws.onclose = (event) => {
        console.log('[WS] Disconnected: code=', event.code, 'reason=', event.reason, 'wasClean=', event.wasClean)
        this.connectionState.value = 'disconnected'
        this.authState.value = 'unauthenticated'
        this.stopHeartbeat()

        // 清理所有挂起请求
        wsRequestManager.clearAll('WebSocket disconnected')

        // 仅在已认证状态下自动重连
        this.attemptReconnect()
      }
    } catch (e) {
      console.error('[WS Client] Failed to create connection:', e)
      this.connectionState.value = 'disconnected'
    }
  }

  // === 认证成功后调用 ===
  onAuthSuccess(): void {
    console.log('[WS] Auth success, enabling auto-reconnect + heartbeat')
    this.authState.value = 'authenticated'
    this.shouldReconnect = true  // 认证成功后开启自动重连
    this.reconnectAttempts = 0
    this.startHeartbeat()
  }

  // === 开启自动重连 (不立即连接，等 onclose 触发时重连) ===
  enableReconnect(): void {
    this.shouldReconnect = true
    this.reconnectAttempts = 0
    // 如果当前已断开，立即开始重连
    if (this.connectionState.value === 'disconnected') {
      this.attemptReconnect()
    }
  }

  // === 断开连接 (不自动重连) ===
  disconnect(): void {
    console.log('[WS] Disconnecting (manual)')
    this.shouldReconnect = false
    this.stopHeartbeat()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.connectionState.value = 'disconnected'
    this.authState.value = 'unauthenticated'
    wsRequestManager.clearAll('Disconnected by user')
  }

  // === 发送消息 ===
  send(message: { type: string; seq: number; data?: Record<string, any> }): void {
    if (message.type !== 'ping') {
      console.log('[WS] Send:', message.type, 'seq=', message.seq, message.data || '')
    }
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const msg: WSMessage = {
        type: message.type,
        seq: message.seq,
        data: message.data || {},
        timestamp: Date.now(),
      }
      this.ws.send(JSON.stringify(msg))
    } else {
      console.warn('[WS Client] Cannot send, WebSocket not connected')
    }
  }

  // === 请求-响应 ===
  async request(type: string, data: Record<string, any> = {}, timeout = 10000): Promise<any> {
    if (this.connectionState.value !== 'connected') {
      throw new Error('WebSocket not connected')
    }
    return wsRequestManager.request(
      (msg) => this.send(msg),
      type,
      data,
      timeout,
    )
  }

  // === 处理消息 ===
  private handleMessage(message: WSMessage): void {
    // 调试日志：记录非心跳消息
    if (message.type !== 'pong') {
      console.log('[WS] Recv:', message.type, 'seq=', message.seq, message.data !== undefined ? message.data : '')
    }
    // 1. 尝试匹配请求响应 (seq > 0 且在 pending 中)
    if (message.seq > 0 && wsRequestManager.handleResponse(message.seq, message.data)) {
      return
    }

    // 2. pong 心跳响应 (seq=0)
    if (message.type === WSRespType.PONG) {
      return
    }

    // 3. 错误消息 (可能是请求响应也可能是推送)
    if (message.type === WSRespType.ERROR) {
      messageRouter.route(message.type, message.data)
      return
    }

    // 4. 推送消息 → 路由分发
    messageRouter.route(message.type, message.data)
  }

  // === 心跳 ===
  private startHeartbeat(): void {
    this.stopHeartbeat()
    this.heartbeatInterval = window.setInterval(() => {
      this.send({ type: WSMsgType.PING, seq: 0, data: {} })
    }, this.heartbeatTimeout)
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval)
      this.heartbeatInterval = null
    }
  }

  // === 重连 (仅认证成功后断开才触发) ===
  private attemptReconnect(): void {
    if (!this.shouldReconnect) {
      console.log('[WS] Reconnect skipped: shouldReconnect=false')
      return
    }
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('[WS] Max reconnect attempts reached, giving up')
      this.shouldReconnect = false
      this.authState.value = 'unauthenticated'
      return
    }

    this.reconnectAttempts++
    const delay = this.baseReconnectDelay * Math.pow(2, this.reconnectAttempts - 1)

    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`)

    setTimeout(() => {
      if (this.connectionState.value === 'disconnected') {
        this.createConnection()
        // 重连成功后通过 onopen → connectResolve
        // 调用方需要在 connect 成功后重新认证
      }
    }, delay)
  }

  // === 重连回调 (认证成功后断开重连时使用) ===
  private onReconnectCallback: (() => void) | null = null

  setOnReconnect(callback: () => void): void {
    this.onReconnectCallback = callback
  }

  clearOnReconnect(): void {
    this.onReconnectCallback = null
  }

  // === 状态辅助 ===
  get isConnected(): boolean {
    return this.connectionState.value === 'connected'
  }
}

// 全局单例
export const wsClient = new WSClient()
