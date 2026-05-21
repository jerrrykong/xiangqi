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
  private maxReconnectAttempts = 10
  private baseReconnectDelay = 1000
  private shouldReconnect = true

  // === 心跳 ===
  private heartbeatInterval: number | null = null
  private heartbeatTimeout = 30000 // 30s

  // === 连接就绪 Promise ===
  private connectResolve: (() => void) | null = null

  // === 连接 ===
  connect(url: string): Promise<void> {
    this.url = url
    this.shouldReconnect = true
    this.reconnectAttempts = 0

    return new Promise((resolve, reject) => {
      this.connectResolve = resolve
      this.createConnection()

      // 连接超时
      const timeout = setTimeout(() => {
        reject(new Error('Connection timeout'))
      }, 10000)

      // 保存 resolve 以便 onopen 中使用
      const originalResolve = this.connectResolve
      this.connectResolve = () => {
        clearTimeout(timeout)
        originalResolve?.()
      }
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
        console.log('[WS Client] Connected')
        this.connectionState.value = 'connected'
        this.reconnectAttempts = 0
        this.startHeartbeat()
        this.connectResolve?.()
        this.connectResolve = null
      }

      this.ws.onmessage = (event) => {
        try {
          const message: WSMessage = JSON.parse(event.data)
          this.handleMessage(message)
        } catch (e) {
          console.error('[WS Client] Failed to parse message:', e)
        }
      }

      this.ws.onerror = (error) => {
        console.error('[WS Client] Error:', error)
      }

      this.ws.onclose = (event) => {
        console.log('[WS Client] Disconnected:', event.code, event.reason)
        this.connectionState.value = 'disconnected'
        this.stopHeartbeat()

        // 清理所有挂起请求
        wsRequestManager.clearAll('WebSocket disconnected')

        // 尝试重连
        this.attemptReconnect()
      }
    } catch (e) {
      console.error('[WS Client] Failed to create connection:', e)
      this.connectionState.value = 'disconnected'
    }
  }

  // === 断开连接 ===
  disconnect(): void {
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
      // 如果 seq > 0 且有 pending，已在步骤1处理
      // 否则作为推送消息路由
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

  // === 重连 ===
  private attemptReconnect(): void {
    if (!this.shouldReconnect) {
      console.log('[WS Client] Reconnect disabled')
      return
    }
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('[WS Client] Max reconnect attempts reached')
      return
    }

    this.reconnectAttempts++
    const delay = this.baseReconnectDelay * Math.pow(2, this.reconnectAttempts - 1)

    console.log(`[WS Client] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)

    setTimeout(() => {
      if (this.connectionState.value === 'disconnected') {
        this.createConnection()
      }
    }, delay)
  }

  // === 状态辅助 ===
  get isConnected(): boolean {
    return this.connectionState.value === 'connected'
  }
}

// 全局单例
export const wsClient = new WSClient()
