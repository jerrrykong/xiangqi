// WS 请求-响应封装 — 将 WS 消息封装为 Promise 风格的请求-响应

import type { WSMessage } from './types'

// 自定义错误
export class WSTimeoutError extends Error {
  type: string
  timeout: number

  constructor(type: string, timeout: number) {
    super(`Request timeout: ${type} (${timeout}ms)`)
    this.name = 'WSTimeoutError'
    this.type = type
    this.timeout = timeout
  }
}

export class WSError extends Error {
  code: number

  constructor(code: number, message: string) {
    super(message)
    this.name = 'WSError'
    this.code = code
  }
}

// 挂起请求结构
interface PendingRequest {
  resolve: (data: any) => void
  reject: (error: Error) => void
  timer: number
}

class WSRequestManager {
  private seqCounter = 0
  private pendingRequests = new Map<number, PendingRequest>()

  // 获取下一个序列号
  nextSeq(): number {
    return ++this.seqCounter
  }

  // 创建一个挂起请求 (由 WSClient 调用 send 后使用)
  createPending(seq: number, timeout = 10000): Promise<any> {
    return new Promise((resolve, reject) => {
      const timer = window.setTimeout(() => {
        this.pendingRequests.delete(seq)
        reject(new WSTimeoutError('', timeout))
      }, timeout)

      this.pendingRequests.set(seq, { resolve, reject, timer })
    })
  }

  // 发送请求并等待响应 (便捷方法，需要外部提供 sendFn)
  async request(
    sendFn: (msg: { type: string; seq: number; data: Record<string, any> }) => void,
    type: string,
    data: Record<string, any> = {},
    timeout = 10000,
  ): Promise<any> {
    const seq = this.nextSeq()
    const promise = this.createPending(seq, timeout)
    sendFn({ type, seq, data })
    return promise
  }

  // 处理响应 (由 WSClient.onmessage 调用)
  handleResponse(seq: number, data: any): boolean {
    const pending = this.pendingRequests.get(seq)
    if (!pending) return false // 不是请求响应

    clearTimeout(pending.timer)
    this.pendingRequests.delete(seq)

    // 检查是否是错误响应
    if (data?.code !== undefined && data?.code !== 0 && data?.message) {
      pending.reject(new WSError(data.code, data.message))
    } else {
      pending.resolve(data)
    }
    return true
  }

  // 清理所有挂起请求 (断线时)
  clearAll(reason: string): void {
    for (const [, pending] of this.pendingRequests) {
      clearTimeout(pending.timer)
      pending.reject(new Error(reason))
    }
    this.pendingRequests.clear()
  }
}

export const wsRequestManager = new WSRequestManager()
